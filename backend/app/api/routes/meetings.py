import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app.auth import CurrentUser, _decode_token, bearer
from app.config import get_settings
from app.db import SessionDep
from app.models import Meeting
from app.schemas.agenda import AgendaSave
from app.schemas.meeting import MeetingCreate, MeetingList, MeetingRead, MeetingStats
from app.schemas.report import ReportRequest

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


@router.post("/report", status_code=202)
async def request_weekly_report(
    session: SessionDep,
    user: CurrentUser,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict[str, str]:
    bucket = get_settings().reports_bucket
    if not bucket:
        raise HTTPException(status_code=503, detail="Report requests are not configured")
    if (
        credentials is None
        or _decode_token(credentials.credentials).get("email_verified") is not True
    ):
        raise HTTPException(status_code=403, detail="Verify your email before requesting a report")
    allowed = {
        email.strip().lower()
        for email in get_settings().report_request_recipients.split(",")
        if email.strip()
    }
    if allowed and user.email.lower() not in allowed:
        raise HTTPException(
            status_code=403, detail="Email reports are not enabled for your address"
        )
    year, week, _ = datetime.now(UTC).isocalendar()
    request = ReportRequest(
        request_id=uuid.uuid4(),
        organizer_id=user.id,
        recipient=user.email,
        week=f"{year}-W{week:02d}",
    )
    # Persist a first-login user before the asynchronous builder queries its meetings.
    await session.commit()
    try:
        await run_in_threadpool(
            lambda: boto3.client("s3").put_object(
                Bucket=bucket,
                Key=request.key,
                Body=request.model_dump_json().encode(),
                ContentType="application/json",
            )
        )
    except (BotoCoreError, ClientError) as error:
        raise HTTPException(
            status_code=503, detail="Could not queue report; please try again"
        ) from error
    return {"request_id": str(request.request_id), "week": request.week, "status": "queued"}


@router.get("/{meeting_id}/agenda")
async def get_agenda(meeting_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    meeting = await session.scalar(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.organizer_id == user.id)
    )
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {
        "meeting": MeetingRead.model_validate(meeting),
        "agenda": meeting.agenda,
        "ai_suggestion": meeting.ai_suggestion,
    }


@router.post("/{meeting_id}/agenda")
async def save_agenda(
    meeting_id: uuid.UUID, payload: AgendaSave, session: SessionDep, user: CurrentUser
):
    meeting = await session.scalar(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.organizer_id == user.id)
    )
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting.agenda = payload.agenda.model_dump(mode="json")
    meeting.ai_suggestion = (
        payload.ai_suggestion.model_dump(mode="json") if payload.ai_suggestion else None
    )
    # Only the user's checked values change meeting metadata and report statistics.
    for field in ("title", "starts_at", "duration_minutes"):
        value = getattr(payload.agenda, field)
        if value is not None:
            setattr(meeting, field, value)
    await session.flush()
    return {
        "meeting": MeetingRead.model_validate(meeting),
        "agenda": meeting.agenda,
        "ai_suggestion": meeting.ai_suggestion,
    }
