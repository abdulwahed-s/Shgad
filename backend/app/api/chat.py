"""Thin stateless chat route; no ledger mutation or provider credentials in replies."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.llm_client import LLMClient
from app.agents.orchestrator import converse
from app.api.dependencies import AuditTime, Clock, Database, llm_client
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Database,
    clock: Clock,
    now: AuditTime,
    client: Annotated[LLMClient, Depends(llm_client)],
):
    return await converse(
        request, client=client, connection=db, clock=clock, known_at=now
    )
