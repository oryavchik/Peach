"""Collect actual free-provider API results; never substitute expected/mock output."""

import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

from app.ai.agenda import (
    PROMPT_VERSION,
    AgendaParseError,
    AgendaProviderError,
    cost_usd,
    get_client,
    parse_agenda,
)
from app.config import get_settings


def main():
    settings = get_settings()
    if (
        settings.parser_provider != "openrouter_free"
        or not settings.parser_enabled
        or not settings.openrouter_api_key.get_secret_value()
    ):
        raise SystemExit("Set the free provider, enabled flag and OPENROUTER_API_KEY first.")
    root = Path(__file__).resolve().parents[3]
    evidence = root / "docs" / "ai-evidence"
    cases = json.loads((evidence / "inputs.json").read_text())
    records = []
    for case in cases:
        started = time.monotonic()
        usage = {"input_tokens": 0, "output_tokens": 0}
        record = {
            "id": case["id"],
            "input": case,
            "source": "real-provider-api-not-deployed-screen",
            "recorded_at": datetime.now(UTC).isoformat(),
            "prompt_version": PROMPT_VERSION,
            "requested_model": settings.openrouter_free_model,
        }
        try:
            agenda, usage = parse_agenda(
                case["text"], date.fromisoformat(case["today"]), case["tz"]
            )
            record.update(status=200, agenda=agenda.model_dump(mode="json"))
        except AgendaParseError as error:
            usage = error.usage
            record.update(status=422, error=str(error))
        except AgendaProviderError as error:
            usage = getattr(error, "agenda_usage", usage)
            record.update(status=error.status, error=str(error))
        record.update(
            **usage,
            latency_ms=int((time.monotonic() - started) * 1000),
            cost_usd=cost_usd(usage),
        )
        raw = getattr(get_client(), "last_response", None)
        if raw:
            record["provider_response"] = raw
        records.append(record)
        # Preserve completed cases if a later request is interrupted.
        (evidence / "free-api-results.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + "\n"
        )
        print(f"Input {case['id']}: status={record['status']}, latency={record['latency_ms']} ms")
        if record["status"] in (429, 503):
            print("Stopped: resolve the free-provider limit/configuration before retrying.")
            break


if __name__ == "__main__":
    main()
