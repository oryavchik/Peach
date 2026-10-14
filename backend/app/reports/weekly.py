"""Generate weekly meeting reports as CSV."""

import asyncio
import csv
import io
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import SessionFactory
from app.models import Meeting


def week_bounds(week: str) -> tuple[datetime, datetime]:
    """Return UTC boundaries for an ISO week."""
    if not re.fullmatch(r"\d{4}-W\d{2}", week):
        raise ValueError("Week must have format YYYY-Www")

    year = int(week[:4])
    week_number = int(week[6:])

    monday = date.fromisocalendar(year, week_number, 1)

    start = datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=7)

    return start, end


async def _generate_report(week: str) -> bytes:
    start, end = week_bounds(week)
    previous_start = start - timedelta(days=7)

    async with SessionFactory() as session:
        current_count = await session.scalar(
            select(func.count())
            .select_from(Meeting)
            .where(Meeting.starts_at >= start, Meeting.starts_at < end)
        )

        total_minutes = await session.scalar(
            select(func.sum(Meeting.duration_minutes))
            .where(Meeting.starts_at >= start, Meeting.starts_at < end)
        )

        previous_count = await session.scalar(
            select(func.count())
            .select_from(Meeting)
            .where(
                Meeting.starts_at >= previous_start,
                Meeting.starts_at < start,
            )
        )

        result = await session.execute(
            select(Meeting)
            .where(Meeting.starts_at >= start, Meeting.starts_at < end)
            .order_by(Meeting.duration_minutes.desc(), Meeting.id)
            .limit(5)
        )

        longest_meetings = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    writer.writerow(["Weekly Meeting Report", week])
    writer.writerow([])

    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total meetings", current_count or 0])
    writer.writerow(["Total hours", round((total_minutes or 0) / 60, 2)])
    writer.writerow(["Previous week meetings", previous_count or 0])
    writer.writerow([
        "Change in meetings",
        (current_count or 0) - (previous_count or 0),
    ])

    writer.writerow([])
    writer.writerow(["Top 5 longest meetings"])
    writer.writerow([
        "Title",
        "Start",
        "Duration (minutes)",
        "Participants",
    ])

    for meeting in longest_meetings:
        writer.writerow([
            meeting.title,
            meeting.starts_at.isoformat(),
            meeting.duration_minutes,
            meeting.participant_count,
        ])

    return output.getvalue().encode("utf-8-sig")


def build_weekly_report(week: str) -> bytes:
    """Build a CSV report for the requested ISO week."""
    return asyncio.run(_generate_report(week))
