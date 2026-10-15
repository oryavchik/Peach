import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.reports import weekly
from tests.tokens import make_token


def payload(**changes):
    return {
        "title": "Team sync",
        "starts_at": datetime.now(UTC).isoformat(),
        "duration_minutes": 90,
        "participant_count": 3,
        **changes,
    }


async def test_meeting_roundtrip_and_ownership(client: AsyncClient):
    response = await client.post("/api/v1/meetings", json=payload())
    assert response.status_code == 201
    meeting = response.json()
    listing = (await client.get("/api/v1/meetings")).json()
    assert listing == {"items": [meeting], "total": 1}
    bob = {"Authorization": f"Bearer {make_token('bob-sub', 'bob@example.com')}"}
    assert (await client.get("/api/v1/meetings", headers=bob)).json()["total"] == 0
    assert (await client.get("/api/v1/meetings/stats", headers=bob)).json()["meeting_count"] == 0
    url = f"/api/v1/meetings/{meeting['id']}"
    assert (await client.delete(url, headers=bob)).status_code == 404
    assert (await client.delete(url)).status_code == 204
    assert (await client.delete(url)).status_code == 404
    assert (await client.get("/api/v1/meetings")).json()["total"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "  "},
        {"title": "x" * 201},
        {"duration_minutes": 0},
        {"duration_minutes": 1441},
        {"participant_count": 0},
        {"starts_at": "2026-10-15T12:00:00"},
    ],
)
async def test_validation(client: AsyncClient, changes):
    assert (await client.post("/api/v1/meetings", json=payload(**changes))).status_code == 422


async def test_anonymous_meetings_are_rejected(anon_client: AsyncClient):
    assert (await anon_client.get("/api/v1/meetings")).status_code == 401
    assert (await anon_client.get("/api/v1/meetings/stats")).status_code == 401
    assert (await anon_client.post("/api/v1/meetings", json=payload())).status_code == 401


async def test_week_boundaries_and_report_integration(client, session, monkeypatch):
    now = datetime.now(UTC)
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    for time, minutes in [
        (start, 90),
        (start - timedelta(minutes=1), 60),
        (start + timedelta(days=7), 120),
    ]:
        response = await client.post(
            "/api/v1/meetings",
            json=payload(
                starts_at=time.isoformat(),
                duration_minutes=minutes,
            ),
        )
        assert response.status_code == 201
    stats = (await client.get("/api/v1/meetings/stats")).json()
    assert stats["meeting_count"] == 1
    assert stats["total_hours"] == 1.5
    assert stats["previous_meeting_count"] == 1
    assert stats["previous_total_hours"] == 1

    class ReportSession:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(weekly, "SessionFactory", ReportSession)
    year, week, _ = start.isocalendar()
    content = await weekly._generate_report(f"{year}-W{week:02d}")
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    assert ["Total meetings", "1"] in rows
    assert ["Total hours", "1.5"] in rows
    assert ["Previous week meetings", "1"] in rows
    assert ["Previous week hours", "1.0"] in rows
    assert ["Change in hours", "0.5"] in rows
    organizer_rows = [row for row in rows if len(row) == 8 and row[1] == "alice@example.com"]
    assert len(organizer_rows) == 1
    assert organizer_rows[0][2:] == ["1", "1.5", "1", "1.0", "0", "0.5"]
    assert any(row and row[0] == "Team sync" and row[-1] == "3" for row in rows)


async def test_report_includes_previous_only_organizers_and_top_five(client, session, monkeypatch):
    now = datetime.now(UTC)
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    bob = {"Authorization": f"Bearer {make_token('bob-sub', 'bob@example.com')}"}
    await client.post(
        "/api/v1/meetings",
        headers=bob,
        json=payload(
            starts_at=(start - timedelta(days=1)).isoformat(),
            duration_minutes=120,
        ),
    )
    for minutes in [10, 20, 30, 40, 50, 60]:
        await client.post(
            "/api/v1/meetings",
            json=payload(
                title=f"Meeting {minutes}",
                starts_at=start.isoformat(),
                duration_minutes=minutes,
            ),
        )

    class ReportSession:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(weekly, "SessionFactory", ReportSession)
    year, week, _ = start.isocalendar()
    first = await weekly._generate_report(f"{year}-W{week:02d}")
    assert first == await weekly._generate_report(f"{year}-W{week:02d}")
    rows = list(csv.reader(io.StringIO(first.decode("utf-8-sig"))))
    assert ["Total meetings", "6"] in rows
    assert ["Total hours", "3.5"] in rows
    assert ["Previous week hours", "2.0"] in rows
    (bob_row,) = [row for row in rows if len(row) == 8 and row[1] == "bob@example.com"]
    assert bob_row[2:] == ["0", "0.0", "1", "2.0", "-1", "-2.0"]
    top = rows[rows.index(["Title", "Start", "Duration (minutes)", "Participants"]) + 1 :]
    assert [row[0] for row in top] == [f"Meeting {minutes}" for minutes in [60, 50, 40, 30, 20]]
