"""Read-only bulk source lookup for Flutter evidence navigation."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import AuditTime, Clock, Database
from app.schemas.source_evidence import SourceEvidencePage
from app.services.source_evidence import source_page

router = APIRouter(tags=["evidence"])


@router.get("/api/evidence/sources", response_model=SourceEvidencePage)
async def sources(
    db: Database,
    clock: Clock,
    now: AuditTime,
    ids: Annotated[str, Query(min_length=1, max_length=64000)],
):
    return source_page(db, ids, clock=clock, known_at=now)
