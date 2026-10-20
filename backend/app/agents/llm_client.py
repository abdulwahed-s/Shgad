"""One compatible HTTP client, fixed provider hosts and bounded failover (§3.2a)."""

import asyncio
import copy
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from app.agents.openai_protocol import REPLAY_ITEMS, normalize_response, request_payload

ENDPOINTS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/responses",
}
RETRIABLE = {408, 429, 500, 502, 503, 504}
MAX_BYTES = 256_000


def retry_delay(header):
    """Respect server backoff; defer this provider if its wait exceeds our bound."""
    header = header.strip()
    if not header:
        return 1
    if re.fullmatch(r"[0-9]+", header):
        if len(header) > 9 or int(header) > 2:
            return None
        return max(1, int(header))
    try:
        # This is an HTTP transport deadline, never a business/calendar date.
        until = parsedate_to_datetime(header)
        if until.tzinfo is None:
            return None
        seconds = (until - datetime.now(UTC)).total_seconds()
        return None if seconds > 2 else max(1, seconds)
    except (ValueError, TypeError, OverflowError):
        return 1


class LLMUnavailable(Exception):
    def __init__(self, reason="busy"):
        self.reason = reason
        super().__init__("LLM_UNAVAILABLE")


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_KEY")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("INVALID_JSON")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def provider_configs(settings):
    result = []
    for provider, model in (
        (settings.llm_provider, settings.llm_model_id),
        (settings.llm_fallback_provider, settings.llm_fallback_model_id),
    ):
        if provider not in ENDPOINTS or not isinstance(model, str):
            continue
        key = getattr(settings, f"{provider}_api_key")
        if (
            key
            and key.get_secret_value().strip()
            and re.fullmatch(r"[A-Za-z0-9/._:-]{1,120}", model)
        ):
            config = (provider, model)
            if not any(
                existing_provider == provider for existing_provider, _ in result
            ):
                result.append(config)
    return tuple(result)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class LLMReply:
    provider: str
    model: str
    content: str | None
    tool_calls: tuple[ToolCall, ...]
    message: dict


def parse_reply(body, *, provider, model):
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("choices"), list)
        or len(body["choices"]) != 1
    ):
        raise ValueError("INVALID_RESPONSE")
    choice = body["choices"][0]
    if not isinstance(choice, dict) or choice.get("finish_reason") not in (
        None,
        "stop",
        "tool_calls",
    ):
        raise ValueError("INCOMPLETE_RESPONSE")
    message = choice["message"]
    if not isinstance(message, dict) or message.get("role", "assistant") != "assistant":
        raise ValueError("INVALID_RESPONSE")
    content = message.get("content")
    if content is not None and (not isinstance(content, str) or len(content) > 12000):
        raise ValueError("INVALID_CONTENT")
    calls = message.get("tool_calls")
    calls = [] if calls is None else calls
    if not isinstance(calls, list) or len(calls) > 4:
        raise ValueError("INVALID_CALLS")
    parsed, kept, ids = [], [], set()
    for call in calls:
        function = call["function"]
        if call["type"] != "function" or not isinstance(function, dict):
            raise ValueError("INVALID_CALL")
        identifier = call["id"]
        name = function["name"]
        if (
            not isinstance(identifier, str)
            or not 1 <= len(identifier) <= 200
            or identifier in ids
            or not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", name)
        ):
            raise ValueError("INVALID_CALL")
        arguments = strict_json(function["arguments"])
        if not isinstance(arguments, dict):
            raise ValueError("INVALID_ARGUMENTS")
        ids.add(identifier)
        parsed.append(ToolCall(identifier, name, arguments))
        item = {
            "id": identifier,
            "type": "function",
            "function": {"name": name, "arguments": function["arguments"]},
        }
        # Gemini's compatible API requires native thought signatures to round trip.
        # They are opaque provider data, never rendered or used as instructions.
        if "extra_content" in call:
            if not isinstance(call["extra_content"], dict):
                raise ValueError("INVALID_SIGNATURE")
            item["extra_content"] = call["extra_content"]
        kept.append(item)
    if not parsed and not content:
        raise ValueError("EMPTY_RESPONSE")
    safe_message = {"role": "assistant", "content": content}
    if kept:
        safe_message["tool_calls"] = kept
    return LLMReply(provider, model, content, tuple(parsed), safe_message)


class LLMClient:
    def __init__(self, settings, *, transport=None, sleep=asyncio.sleep):
        self.settings = settings
        self.transport = transport
        self.sleep = sleep
        self._client = None
        self._preferred = None

    @property
    def available(self):
        return bool(provider_configs(self.settings))

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.settings.llm_timeout_seconds,
            transport=self.transport,
            trust_env=False,
            follow_redirects=False,
        )
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def _request(self, provider, payload, key):
        # A read timeout alone resets on each byte; enforce a total deadline too.
        async with asyncio.timeout(self.settings.llm_timeout_seconds):
            async with self._client.stream(
                "POST",
                ENDPOINTS[provider],
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
            ) as response:
                status = response.status_code
                retry_after = response.headers.get("retry-after", "")
                if status != 200:
                    return status, retry_after, None
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise ValueError("RESPONSE_TOO_LARGE")
                return status, retry_after, strict_json(bytes(data))

    async def complete(self, messages, *, tools=(), json_mode=False):
        configs = sorted(
            provider_configs(self.settings), key=lambda pair: pair != self._preferred
        )
        if not configs or self._client is None:
            raise LLMUnavailable("not_configured")
        secrets = [
            key.get_secret_value()
            for key in (
                self.settings.gemini_api_key,
                self.settings.groq_api_key,
                self.settings.openai_api_key,
            )
            if key
        ]
        reason = "busy"
        for provider, model in configs:
            key = getattr(self.settings, f"{provider}_api_key").get_secret_value()
            provider_messages = copy.deepcopy(messages)
            for message in provider_messages:
                if provider != "openai":
                    message.pop(REPLAY_ITEMS, None)
            if provider != "gemini":
                for message in provider_messages:
                    for call in message.get("tool_calls", []):
                        call.pop("extra_content", None)
            if provider == "openai":
                payload = request_payload(
                    model,
                    provider_messages,
                    tools=tools,
                    json_mode=json_mode,
                    max_output_tokens=self.settings.llm_max_output_tokens or 8192,
                )
            else:
                payload = {
                    "model": model,
                    "messages": provider_messages,
                    "temperature": 0,
                    "max_tokens": self.settings.llm_max_output_tokens or 2048,
                }
                if tools:
                    payload |= {"tools": list(tools), "tool_choice": "auto"}
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
            if len(json.dumps(payload, ensure_ascii=False).encode()) > 128_000:
                raise LLMUnavailable("context_limit")
            for attempt in range(2):
                delay = min(2, 2**attempt)
                try:
                    status, header, body = await self._request(provider, payload, key)
                    if status != 200:
                        if status not in RETRIABLE or attempt == 1:
                            break
                        delay = retry_delay(header)
                        if delay is None:
                            break
                    else:
                        if any(
                            secret in json.dumps(body, ensure_ascii=False)
                            for secret in secrets
                        ):
                            raise ValueError("SECRET_ECHO")
                        replay = None
                        if provider == "openai":
                            body, replay = normalize_response(body)
                        reply = parse_reply(body, provider=provider, model=model)
                        if replay is not None:
                            reply.message[REPLAY_ITEMS] = replay
                        self._preferred = (provider, model)
                        return reply
                except (TimeoutError, httpx.TimeoutException, httpx.TransportError):
                    reason = "needs_internet"
                    if attempt == 1:
                        break
                except (ValueError, TypeError, KeyError, IndexError):
                    reason = "invalid_response"
                    break
                await self.sleep(delay)
        raise LLMUnavailable(reason)
