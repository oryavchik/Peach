import base64
import json
import logging
import time

from anthropic import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from pydantic import ValidationError

from app.ai.agenda import (
    PROMPT_VERSION,
    AgendaParseError,
    AgendaProviderError,
    cost_usd,
    parse_agenda,
)
from app.ai.auth import verify_cognito_token
from app.config import get_settings
from app.schemas.agenda import ParseRequest

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def response(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event, context):
    headers = {key.lower(): value for key, value in (event.get("headers") or {}).items()}
    try:
        user = verify_cognito_token(headers.get("authorization", ""))
    except ValueError as error:
        return response(401, {"error": str(error)})
    method = event.get("requestContext", {}).get("http", {}).get("method", "POST")
    if method != "POST":
        return response(405, {"error": "Use POST"})
    try:
        raw = event.get("body") or ""
        if len(raw) > 100000:
            return response(413, {"error": "Text must be no longer than 10,000 characters."})
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw, validate=True).decode()
        body = json.loads(raw)
        if (
            isinstance(body, dict)
            and isinstance(body.get("text"), str)
            and len(body["text"]) > 10000
        ):
            return response(413, {"error": "Text must be no longer than 10,000 characters."})
        request = ParseRequest.model_validate(body)
    except ValueError, ValidationError, UnicodeError:
        return response(
            422, {"error": "Provide text, today (YYYY-MM-DD), and a valid IANA timezone."}
        )
    if not get_settings().parser_enabled:
        return response(
            503, {"error": "AI parsing is disabled. You can enter and save the agenda by hand."}
        )
    started = time.monotonic()
    settings = get_settings()
    model = (
        settings.openrouter_free_model
        if settings.parser_provider == "openrouter_free"
        else settings.parser_model
    )
    usage = {"input_tokens": 0, "output_tokens": 0}
    status = 200
    try:
        agenda, usage = parse_agenda(request.text, request.today, request.tz)
        model = usage.get("model", model)
        result = {
            "agenda": agenda.model_dump(mode="json"),
            "model": model,
            "prompt_version": PROMPT_VERSION,
        }
    except AgendaParseError as error:
        usage = error.usage
        status, result = 422, {"error": str(error)}
    except AgendaProviderError as error:
        usage = getattr(error, "agenda_usage", usage)
        status, result = error.status, {"error": str(error)}
    except RateLimitError as error:
        usage = getattr(error, "agenda_usage", usage)
        status, result = (
            429,
            {"error": "The service is busy. Wait a moment or enter the agenda by hand."},
        )
    except (APITimeoutError, APIConnectionError) as error:
        usage = getattr(error, "agenda_usage", usage)
        status, result = (
            503,
            {"error": "Could not reach the model. Try again or enter the agenda by hand."},
        )
    except APIStatusError as error:
        usage = getattr(error, "agenda_usage", usage)
        status, result = (
            503,
            {"error": "The model is unavailable. You can still enter and save the agenda by hand."},
        )
    elapsed = int((time.monotonic() - started) * 1000)
    cost = cost_usd(usage)
    log.info(
        json.dumps(
            {
                "event": "agenda_parsed",
                "user": user,
                "model": model,
                "prompt_version": PROMPT_VERSION,
                **usage,
                "latency_ms": elapsed,
                "cost_usd": cost,
                "status": status,
            }
        )
    )
    if status == 200:
        result.update({**usage, "latency_ms": elapsed, "cost_usd": cost})
    return response(status, result)
