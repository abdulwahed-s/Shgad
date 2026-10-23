"""Explicit synthetic replay and globally bounded real provider transport."""

import asyncio
import json
import time
from collections import Counter

from app.agents.llm_client import LLMClient, LLMUnavailable, parse_reply


class ReplayClient:
    """Fabricated protocol exercise; never described as live model performance."""

    def __init__(self):
        self.messages = []
        self.completions = 0
        self.script = []

    def begin_question(self, case):
        self.script = [{"action": {"intent": case["intent"]}}, *case["turns"]]

    async def complete(self, messages, *, tools=(), json_mode=False):
        self.messages.append(json.loads(json.dumps(messages)))
        self.completions += 1
        if not self.script:
            raise LLMUnavailable("recording_exhausted")
        turn = self.script.pop(0)
        message = {"role": "assistant", "content": None}
        if "calls" in turn:
            message["tool_calls"] = [
                dict(
                    id=f"replay-{i}",
                    type="function",
                    function=dict(
                        name=call["name"],
                        arguments=json.dumps(call["arguments"]),
                    ),
                )
                for i, call in enumerate(turn["calls"])
            ]
        else:
            message["content"] = json.dumps(turn["action"], ensure_ascii=False)
        return parse_reply(
            {"choices": [{"message": message}]},
            provider="synthetic-replay",
            model="synthetic-format-sentinel",
        )

    def receipt(self):
        return dict(provider_requests=0, synthetic_completions=self.completions)


class BudgetedClient(LLMClient):
    """Count actual POST attempts, including retries and fallback, before sending."""

    def __init__(
        self,
        settings,
        *,
        max_requests,
        per_question=6,
        spacing_seconds=10,
        transport=None,
        sleep=asyncio.sleep,
        monotonic=time.monotonic,
    ):
        super().__init__(settings, transport=transport, sleep=sleep)
        self.max_requests = max_requests
        self.per_question = per_question
        self.spacing_seconds = spacing_seconds
        self.monotonic = monotonic
        self.attempts = self.question_attempts = 0
        self.last_request = None
        self.counts = Counter()
        self.statuses = Counter()
        self.limit_hits = 0

    def begin_question(self, _=None):
        self.question_attempts = 0
        self.reset_routing()

    def reset_routing(self):
        # Production creates a new client for each chat request. The separate
        # intent probe must not influence the app conversation's provider order.
        self._preferred = None

    async def _request(self, provider, payload, key):
        if (
            self.attempts >= self.max_requests
            or self.question_attempts >= self.per_question
        ):
            self.limit_hits += 1
            raise LLMUnavailable("evaluation_request_limit")
        if self.last_request is not None:
            await self.sleep(
                max(0, self.spacing_seconds - (self.monotonic() - self.last_request))
            )
        self.last_request = self.monotonic()
        self.attempts += 1
        self.question_attempts += 1
        self.counts[f"{provider}/{payload['model']}"] += 1
        try:
            response = await super()._request(provider, payload, key)
            self.statuses[str(response[0])] += 1
            return response
        except Exception:
            self.statuses["transport_failure"] += 1
            raise

    def receipt(self):
        return dict(
            provider_requests=self.attempts,
            requests_by_provider_model=dict(self.counts),
            http_status_counts=dict(self.statuses),
            request_limit_hits=self.limit_hits,
            max_requests=self.max_requests,
            max_requests_per_question=self.per_question,
            minimum_spacing_seconds=self.spacing_seconds,
        )
