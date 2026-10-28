import io
import json
from datetime import date
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest
from pydantic import SecretStr

from app.ai import agenda, agenda_lambda, free_client
from app.config import get_settings
from tests.test_agenda import VALID, event


@pytest.fixture
def free_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "parser_provider", "openrouter_free")
    monkeypatch.setattr(settings, "openrouter_free_model", "openrouter/free")
    monkeypatch.setattr(settings, "parser_enabled", True)
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr("secret-test-key"))
    monkeypatch.setattr(agenda, "get_client", free_client.FreeClient)
    return settings


def completion(data):
    return io.BytesIO(
        json.dumps(
            {
                "model": "test/selected-model:free",
                "usage": {"prompt_tokens": 120, "completion_tokens": 80},
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "function": {
                                        "name": "record_agenda",
                                        "arguments": json.dumps(data),
                                    },
                                }
                            ]
                        },
                    }
                ],
            }
        ).encode()
    )


def test_only_free_router_and_original_tool_contract(free_settings, monkeypatch):
    send = Mock(return_value=completion(VALID))
    monkeypatch.setattr(free_client, "urlopen", send)
    parsed, usage = agenda.parse_agenda("Pricing Olena", date(2026, 10, 15), "Europe/Kyiv")
    assert parsed.items[0].owner == "Olena"
    assert usage["model"] == "test/selected-model:free"
    assert agenda.cost_usd(usage) == 0
    req = send.call_args.args[0]
    payload = json.loads(req.data)
    assert req.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert payload["model"] == "openrouter/free"
    assert payload["parallel_tool_calls"] is False
    assert "models" not in payload and "route" not in payload
    assert payload["tools"][0]["function"]["name"] == "record_agenda"
    assert "2026-10-15" in payload["messages"][1]["content"]
    context = json.loads(payload["messages"][1]["content"])
    assert context["reference_dates"]["end_of_week"] == "2026-10-18"
    assert context["reference_dates"]["Monday / понеділок / Пн"] == "2026-10-19"


def test_repair_counts_both_calls(free_settings, monkeypatch):
    send = Mock(side_effect=[completion({**VALID, "duration_minutes": 999}), completion(VALID)])
    monkeypatch.setattr(free_client, "urlopen", send)
    _, usage = agenda.parse_agenda("Pricing Olena", date(2026, 10, 15), "UTC")
    assert usage["input_tokens"] == 240 and usage["output_tokens"] == 160
    payload = json.loads(send.call_args.args[0].data)
    assert payload["messages"][-1]["role"] == "tool"
    assert payload["messages"][-1]["tool_call_id"] == "call-1"


def test_quota_returns_429_without_secret(free_settings, monkeypatch, caplog):
    send = Mock(side_effect=HTTPError("https://openrouter.ai", 429, "private body", {}, None))
    monkeypatch.setattr(free_client, "urlopen", send)
    result = agenda_lambda.handler(
        event({"text": "Pricing Olena", "today": "2026-10-15", "tz": "UTC"}), None
    )
    assert result["statusCode"] == 429
    assert send.call_count == 1
    assert "secret-test-key" not in result["body"] + caplog.text


def test_missing_key_never_sends(free_settings, monkeypatch):
    monkeypatch.setattr(free_settings, "openrouter_api_key", SecretStr(""))
    send = Mock()
    monkeypatch.setattr(free_client, "urlopen", send)
    with pytest.raises(agenda.AgendaProviderError, match="OPENROUTER_API_KEY"):
        agenda.parse_agenda("Pricing Olena", date(2026, 10, 15), "UTC")
    send.assert_not_called()


def test_actual_selected_model_in_result_and_log(free_settings, monkeypatch, caplog):
    monkeypatch.setattr(free_client, "urlopen", Mock(return_value=completion(VALID)))
    result = agenda_lambda.handler(
        event({"text": "Pricing Olena", "today": "2026-10-15", "tz": "UTC"}), None
    )
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["model"] == "test/selected-model:free"
    log = json.loads(caplog.records[-1].message)
    assert log["cost_usd"] == 0 and log["model"] == "test/selected-model:free"
