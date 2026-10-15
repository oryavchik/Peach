"""Build the same CSV shape for any explicitly selected ISO week."""

import asyncio
import csv
import io
import re
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.db import SessionFactory
from app.models import Meeting, User


def week_bounds(week: str) -> tuple[datetime, datetime]:
    """Return half-open UTC boundaries for an ISO week."""
    if not re.fullmatch(r"\d{4}-W\d{2}", week):
        raise ValueError("Week must have format YYYY-Www")
    monday = date.fromisocalendar(int(week[:4]), int(week[6:]), 1)
    start = datetime.combine(monday, datetime.min.time(), tzinfo=UTC)
    return start, start + timedelta(days=7)


async def _generate_report(week: str, organizer_id: uuid.UUID | None = None) -> bytes:
    start, end = week_bounds(week)
    previous_start = start - timedelta(days=7)

    scope = [] if organizer_id is None else [Meeting.organizer_id == organizer_id]

    async with SessionFactory() as session:
        result = await session.execute(
            select(
                User.id,
                User.name,
                func.count(Meeting.id).filter(Meeting.starts_at >= start),
                func.coalesce(
                    func.sum(Meeting.duration_minutes).filter(Meeting.starts_at >= start), 0
                ),
                func.count(Meeting.id).filter(Meeting.starts_at < start),
                func.coalesce(
                    func.sum(Meeting.duration_minutes).filter(Meeting.starts_at < start), 0
                ),
            )
            .join(Meeting, Meeting.organizer_id == User.id)
            .where(Meeting.starts_at >= previous_start, Meeting.starts_at < end, *scope)
            .group_by(User.id, User.name)
            .order_by(User.name, User.id)
        )
        organizers = result.all()
        result = await session.scalars(
            select(Meeting)
            .where(Meeting.starts_at >= start, Meeting.starts_at < end, *scope)
            .order_by(Meeting.duration_minutes.desc(), Meeting.id)
            .limit(5)
        )
        longest_meetings = result.all()

    current_count = sum(row[2] for row in organizers)
    total_minutes = sum(row[3] for row in organizers)
    previous_count = sum(row[4] for row in organizers)
    previous_minutes = sum(row[5] for row in organizers)

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Weekly Meeting Report", week])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total meetings", current_count])
    writer.writerow(["Total hours", round(total_minutes / 60, 2)])
    writer.writerow(["Previous week meetings", previous_count])
    writer.writerow(["Previous week hours", round(previous_minutes / 60, 2)])
    writer.writerow(["Change in meetings", current_count - previous_count])
    writer.writerow(["Change in hours", round((total_minutes - previous_minutes) / 60, 2)])

    writer.writerow([])
    writer.writerow(["Meetings by organizer"])
    writer.writerow(
        [
            "Organizer ID",
            "Organizer",
            "Meetings",
            "Hours",
            "Previous week meetings",
            "Previous week hours",
            "Change in meetings",
            "Change in hours",
        ]
    )
    for user_id, name, count, minutes, prior_count, prior_minutes in organizers:
        writer.writerow(
            [
                str(user_id),
                name,
                count,
                round(minutes / 60, 2),
                prior_count,
                round(prior_minutes / 60, 2),
                count - prior_count,
                round((minutes - prior_minutes) / 60, 2),
            ]
        )

    writer.writerow([])
    writer.writerow(["Top 5 longest meetings"])
    writer.writerow(["Title", "Start", "Duration (minutes)", "Participants"])
    for meeting in longest_meetings:
        writer.writerow(
            [
                meeting.title,
                meeting.starts_at.isoformat(),
                meeting.duration_minutes,
                meeting.participant_count,
            ]
        )
    return output.getvalue().encode("utf-8-sig")


def build_weekly_report(week: str, organizer_id: uuid.UUID | None = None) -> bytes:
    """Query meetings for the specified week and return a UTF-8 CSV."""
    return asyncio.run(_generate_report(week, organizer_id))
