"""Async mapping proposal only; deterministic service owns preview and confirmation."""

import json

from app.agents.llm_client import LLMUnavailable, strict_json
from app.agents.system_instructions import MAPPING_INSTRUCTIONS
from app.services.errors import FinancialRuleError


class LLMMappingProposer:
    def __init__(self, client):
        self.client = client

    async def propose(self, *, headers, sample_rows):
        messages = [
            {"role": "system", "content": MAPPING_INSTRUCTIONS},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "trust": "untrusted_quoted_data",
                        "headers": list(headers),
                        "sample_rows": list(sample_rows[:3]),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            reply = await self.client.complete(messages, tools=(), json_mode=True)
        except LLMUnavailable:
            raise FinancialRuleError("LLM_UNAVAILABLE") from None
        if reply.tool_calls:
            raise FinancialRuleError("MAPPING_UNRESOLVED")
        try:
            return strict_json(reply.content)
        except (ValueError, TypeError):
            raise FinancialRuleError("MAPPING_UNRESOLVED") from None
