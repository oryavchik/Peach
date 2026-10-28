"""Run with uv run python -m app.ai.cli hello|parse (TEXT is an environment variable)."""

import json
import os
import sys
from datetime import date

from app.ai.agenda import cost_usd, get_client, parse_agenda
from app.config import get_settings


def main():
    if not get_settings().parser_enabled:
        raise SystemExit(
            "AI parsing is disabled (PARSER_ENABLED=false). No model request was sent."
        )
    if sys.argv[1] == "hello":
        msg = get_client().messages.create(
            model=get_settings().parser_model,
            max_tokens=128,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "In one sentence: what is an ISO week?"}],
        )
        print(
            json.dumps(
                {
                    "model": msg.model,
                    "stop_reason": msg.stop_reason,
                    "content": [block.model_dump() for block in msg.content],
                    "usage": {
                        "input_tokens": msg.usage.input_tokens,
                        "output_tokens": msg.usage.output_tokens,
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        agenda, usage = parse_agenda(
            os.environ["TEXT"],
            date.fromisoformat(os.environ.get("TODAY") or date.today().isoformat()),
            os.environ.get("TZ", "Europe/Kyiv"),
        )
        print(
            json.dumps(
                {"agenda": agenda.model_dump(mode="json"), **usage, "cost_usd": cost_usd(usage)},
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
