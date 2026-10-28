"""OpenRouter free-only adapter. No paid model, fallback, SDK or local weights."""

import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from anthropic.types import TextBlock, ToolUseBlock

from app.ai.agenda import AgendaProviderError
from app.config import get_settings


class FreeClient:
    def __init__(self):
        self.messages = self

    def create(self, *, messages, max_tokens, system="", tools=None, **_):
        self.last_response = None
        key = get_settings().openrouter_api_key.get_secret_value()
        if not key:
            raise AgendaProviderError("Set OPENROUTER_API_KEY on the server to use free AI.")
        converted = [{"role": "system", "content": system}] if system else []
        for message in messages:
            content = message["content"]
            if isinstance(content, str):
                converted.append(message)
            elif message["role"] == "assistant":
                converted.append(
                    {
                        "role": "assistant",
                        "content": "".join(b.get("text", "") for b in content),
                        "tool_calls": [
                            {
                                "id": b["id"],
                                "type": "function",
                                "function": {
                                    "name": b["name"],
                                    "arguments": json.dumps(b["input"]),
                                },
                            }
                            for b in content
                            if b["type"] == "tool_use"
                        ],
                    }
                )
            else:
                converted.extend(
                    {
                        "role": "tool",
                        "tool_call_id": b["tool_use_id"],
                        "content": b["content"],
                    }
                    for b in content
                )
        payload = {
            "model": get_settings().openrouter_free_model,
            "messages": converted,
            "max_tokens": max_tokens,
            "temperature": 0,
            "stream": False,
            "reasoning": {"enabled": False},
            "parallel_tool_calls": False,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
                for tool in tools
            ]
            payload["tool_choice"] = "required"
        req = Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=12) as response:
                result = json.load(response)
                self.last_response = result
        except HTTPError as error:
            if error.code == 429:
                raise AgendaProviderError(
                    "Free AI quota is busy or exhausted. Try later or enter the agenda by hand.",
                    429,
                ) from None
            raise AgendaProviderError(
                "Free AI is unavailable. Check the server API key or enter the agenda by hand."
            ) from None
        except URLError, TimeoutError, ValueError:
            raise AgendaProviderError("Could not reach free AI. Try again later.") from None
        try:
            choice = result["choices"][0]
            message = choice["message"]
            blocks = []
            if message.get("content"):
                blocks.append(TextBlock(type="text", text=message["content"]))
            for call in message.get("tool_calls") or []:
                blocks.append(
                    ToolUseBlock(
                        type="tool_use",
                        id=call["id"],
                        name=call["function"]["name"],
                        input=json.loads(call["function"]["arguments"]),
                    )
                )
            usage = result["usage"]
            return SimpleNamespace(
                content=blocks,
                model=result["model"],
                stop_reason=(
                    "tool_use"
                    if message.get("tool_calls") and choice["finish_reason"] != "length"
                    else "end_turn"
                ),
                usage=SimpleNamespace(
                    input_tokens=usage["prompt_tokens"], output_tokens=usage["completion_tokens"]
                ),
            )
        except KeyError, IndexError, TypeError, ValueError:
            raise AgendaProviderError(
                "Free AI returned an unreadable response. Try again."
            ) from None
