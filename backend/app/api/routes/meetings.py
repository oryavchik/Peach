import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select

from app.auth import CurrentUser
from app.db import SessionDep
from app.models import Meeting
from app.schemas.meeting import MeetingCreate, MeetingList, MeetingRead, MeetingStats

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=MeetingList)
async def list_meetings(
    session: SessionDep,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MeetingList:
    owned = Meeting.organizer_id == user.id
    total = await session.scalar(select(func.count()).select_from(Meeting).where(owned))
    result = await session.scalars(
        select(Meeting)
        .where(owned)
        .order_by(Meeting.starts_at.desc(), Meeting.id)
        .limit(limit)
        .offset(offset)
    )
    return MeetingList(items=[MeetingRead.model_validate(m) for m in result], total=total or 0)


@router.get("/stats", response_model=MeetingStats)
async def meeting_stats(session: SessionDep, user: CurrentUser) -> MeetingStats:
    now = datetime.now(UTC)
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)

    async def totals(lower: datetime, upper: datetime) -> tuple[int, float]:
        result = await session.execute(
            select(
                func.count(Meeting.id), func.coalesce(func.sum(Meeting.duration_minutes), 0)
            ).where(
                Meeting.organizer_id == user.id,
                Meeting.starts_at >= lower,
                Meeting.starts_at < upper,
            )
        )
        count, minutes = result.one()
        return count, round(minutes / 60, 2)

    count, hours = await totals(start, end)
    previous_count, previous_hours = await totals(start - timedelta(days=7), start)
    return MeetingStats(
        week_start=start,
        week_end=end,
        meeting_count=count,
        total_hours=hours,
        previous_meeting_count=previous_count,
        previous_total_hours=previous_hours,
    )


@router.post("", response_model=MeetingRead, status_code=201)
async def create_meeting(
    payload: MeetingCreate,
    session: SessionDep,
    user: CurrentUser,
) -> MeetingRead:
    meeting = Meeting(organizer_id=user.id, **payload.model_dump())
    session.add(meeting)
    await session.flush()
    await session.refresh(meeting)
    return MeetingRead.model_validate(meeting)


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    meeting = await session.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.organizer_id == user.id,
        )
    )
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    await session.delete(meeting)
    await session.flush()
    return Response(status_code=204)
