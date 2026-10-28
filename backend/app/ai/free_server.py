"""Local web adapter for the free cloud parser; no local model or AWS deployment."""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.ai.agenda_lambda import handler
from app.config import get_settings

if get_settings().parser_provider != "openrouter_free":
    raise RuntimeError("Free server requires PARSER_PROVIDER=openrouter_free")

app = FastAPI(docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["POST"],
    allow_headers=["authorization", "content-type"],
)


@app.get("/health")
def health():
    return {"status": "ok", "provider": "openrouter_free", "paid_fallback": False}


@app.post("/")
async def parse(request: Request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 100000:
            return Response(
                '{"error":"Text must be no longer than 10,000 characters."}',
                status_code=413,
                media_type="application/json",
            )
    result = await run_in_threadpool(
        handler,
        {
            "headers": dict(request.headers),
            "body": raw.decode("utf-8", errors="replace"),
            "requestContext": {"http": {"method": "POST"}},
        },
        None,
    )
    return Response(result["body"], status_code=result["statusCode"], headers=result["headers"])
