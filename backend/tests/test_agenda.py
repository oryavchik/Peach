import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from anthropic.types import ToolUseBlock

from app.ai import agenda as parser
from app.ai import agenda_lambda
from app.config import get_settings
from app.schemas.agenda import ParsedAgenda
from tests.tokens import auth, make_token


@pytest.fixture(autouse=True)
def enable_for_unit_tests(monkeypatch):
    monkeypatch.setattr(get_settings(), "parser_enabled", True)


VALID = {
    "title": "Sync",
    "starts_at": None,
    "duration_minutes": None,
    "items": [{"topic": "Pricing", "owner": "Olena", "minutes": 15}],
    "action_items": [],
    "language": "en",
}


def message(data, stop="tool_use"):
    return SimpleNamespace(
        stop_reason=stop,
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        content=[ToolUseBlock(type="tool_use", id="tool-1", name="record_agenda", input=data)],
    )


def fake_client(monkeypatch, responses):
    create = Mock(side_effect=responses)
    monkeypatch.setattr(
        parser, "get_client", lambda: SimpleNamespace(messages=SimpleNamespace(create=create))
    )
    return create


def test_valid_parse_has_no_writes(monkeypatch):
    create = fake_client(monkeypatch, [message(VALID)])
    result, usage = parser.parse_agenda(
        "Sync: Pricing — Olena, 15 min", date(2026, 10, 15), "Europe/Kyiv"
    )
    assert result.items[0].owner == "Olena"
    assert usage == {"input_tokens": 100, "output_tokens": 50}
    request = create.call_args.kwargs
    assert "tool_choice" not in request
    assert "2026-10-15" in request["messages"][0]["content"]
    assert request["tools"][0]["name"] == "record_agenda"


def test_invalid_repair_counts_both_attempts(monkeypatch):
    invalid = {**VALID, "duration_minutes": 999}
    create = fake_client(monkeypatch, [message(invalid), message(VALID)])
    result, usage = parser.parse_agenda("Pricing — Olena", date.today(), "UTC")
    assert result.duration_minutes is None
    assert usage["input_tokens"] == 200
    assert create.call_count == 2
    assert create.call_args.kwargs["messages"][-1]["content"][0]["is_error"] is True


def test_invalid_twice_never_escapes(monkeypatch):
    fake_client(monkeypatch, [message({**VALID, "starts_at": "2026-10-19T10:00:00"})] * 2)
    with pytest.raises(parser.AgendaParseError) as caught:
        parser.parse_agenda("Pricing Olena", date.today(), "UTC")
    assert caught.value.usage["output_tokens"] == 100


@pytest.mark.parametrize("data", [{**VALID, "items": [], "action_items": []}, VALID])
def test_no_agenda_or_refusal(monkeypatch, data):
    fake_client(monkeypatch, [message(data, "end_turn" if data["items"] else "tool_use")])
    with pytest.raises(parser.AgendaParseError):
        parser.parse_agenda("milk, bread", date.today(), "UTC")


def event(body, headers=None):
    return {"body": json.dumps(body), "headers": headers if headers is not None else auth()}


def test_lambda_auth_and_input_limits_do_not_call_model(monkeypatch):
    parse = Mock()
    monkeypatch.setattr(agenda_lambda, "parse_agenda", parse)
    assert agenda_lambda.handler(event({}, {}), None)["statusCode"] == 401
    assert agenda_lambda.handler(event({"text": "x" * 10001}), None)["statusCode"] == 413
    assert (
        agenda_lambda.handler(event({"text": "sync", "today": "2026-10-15", "tz": "wrong"}), None)[
            "statusCode"
        ]
        == 422
    )
    parse.assert_not_called()


def test_lambda_usage_log_without_text(monkeypatch, caplog):
    monkeypatch.setattr(
        agenda_lambda,
        "parse_agenda",
        lambda *args: (
            ParsedAgenda.model_validate(VALID),
            {"input_tokens": 100, "output_tokens": 50},
        ),
    )
    result = agenda_lambda.handler(
        event({"text": "private agenda", "today": "2026-10-15", "tz": "UTC"}), None
    )
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["cost_usd"] > 0
    log = json.loads(caplog.records[-1].message)
    assert log["user"] == "alice-sub" and log["prompt_version"] == "agenda-v1"
    assert "private agenda" not in caplog.text


async def test_save_agenda_and_original_suggestion_are_separate(client):
    created = await client.post(
        "/api/v1/meetings",
        json={
            "title": "Before",
            "starts_at": "2026-10-19T10:00:00Z",
            "duration_minutes": 30,
            "participant_count": 2,
        },
    )
    meeting_id = created.json()["id"]
    final = {**VALID, "title": "Corrected", "duration_minutes": 45}
    result = await client.post(
        f"/api/v1/meetings/{meeting_id}/agenda",
        json={
            "agenda": final,
            "ai_suggestion": {
                "agenda": VALID,
                "model": "test-model",
                "prompt_version": "agenda-v1",
            },
        },
    )
    assert result.status_code == 200
    body = (await client.get(f"/api/v1/meetings/{meeting_id}/agenda")).json()
    assert body["agenda"]["title"] == body["meeting"]["title"] == "Corrected"
    assert body["meeting"]["duration_minutes"] == 45
    assert body["ai_suggestion"]["agenda"]["title"] == "Sync"
    client.headers["Authorization"] = f"Bearer {make_token('bob-sub', 'bob@example.com')}"
    assert (await client.get(f"/api/v1/meetings/{meeting_id}/agenda")).status_code == 404
    assert (
        await client.post(f"/api/v1/meetings/{meeting_id}/agenda", json={"agenda": VALID})
    ).status_code == 404


def test_disabled_parser_never_calls_model(monkeypatch):
    monkeypatch.setattr(get_settings(), "parser_enabled", False)
    create = fake_client(monkeypatch, [])
    with pytest.raises(parser.AgendaParseError, match="disabled"):
        parser.parse_agenda("Pricing sync Olena", date.today(), "UTC")
    assert (
        agenda_lambda.handler(event({"text": "sync", "today": "2026-10-15", "tz": "UTC"}), None)[
            "statusCode"
        ]
        == 503
    )
    create.assert_not_called()
