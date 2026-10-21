"""Explicit non-production fictional sample lifecycle."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import Clock, Database
from app.config import Settings, get_settings
from app.schemas.demo import DemoReceipt
from app.services.demo_seed import restore_demo
from app.services.errors import FinancialRuleError

router = APIRouter(tags=["demo"])


@router.post("/api/demo/reset", response_model=DemoReceipt)
async def reset_demo(
    db: Database, clock: Clock, settings: Annotated[Settings, Depends(get_settings)]
):
    if settings.app_env.lower() == "production":
        raise FinancialRuleError("NOT_FOUND")
    restore_demo(db, clock=clock)
    return DemoReceipt()
