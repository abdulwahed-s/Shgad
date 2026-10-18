"""Optional single development routing probe; maximum four transport attempts."""

import asyncio
import json
import os

import pytest

from app.agents.llm_client import LLMClient
from app.agents.system_instructions import SYSTEM_INSTRUCTIONS
from app.agents.tool_registry import TOOLS, definitions
from app.config import runtime_settings


@pytest.mark.live
def test_opt_in_development_routing(request):
    if (
        os.environ.get("SHGAD_RUN_LIVE") != "1"
        or request.config.option.markexpr != "live"
    ):
        pytest.skip(
            "Requires SHGAD_RUN_LIVE=1 and explicit -m live; deferred by default"
        )

    async def scenario():
        async with LLMClient(runtime_settings()) as client:
            if not client.available:
                pytest.skip("Local model IDs/keys are unconfigured")
            reply = await client.complete(
                [
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "BUSINESS_AS_OF": "2026-09-28",
                                "question": "شكد بعنا كاش هالأسبوع؟",
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                tools=definitions(),
            )
            assert (
                len(reply.tool_calls) == 1 and reply.tool_calls[0].name == "get_sales"
            )
            args = TOOLS["get_sales"][0].model_validate(reply.tool_calls[0].arguments)
            assert args.period == "this_week" and args.kind == "cash"

    asyncio.run(scenario())
