"""/api/v1/dashboard routes (read only). Thin: call the service with the caller's workspace."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, SessionDep
from app.dashboard import service
from app.dashboard.schemas import AgeingBucket, Summary, WeekCollected

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def summary(user: CurrentUser, session: SessionDep) -> Summary:
    return service.summary(session, user.workspace_id)


@router.get("/collections")
def collections(
    user: CurrentUser, session: SessionDep, weeks: Annotated[int, Query(ge=1, le=52)] = 8
) -> list[WeekCollected]:
    return service.collections(session, user.workspace_id, weeks)


@router.get("/ageing")
def ageing(user: CurrentUser, session: SessionDep) -> list[AgeingBucket]:
    return service.ageing(session, user.workspace_id)
