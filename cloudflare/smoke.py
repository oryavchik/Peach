"""Exercise the deployed free demo with public/synthetic lab fixtures only."""

import http.cookiejar
import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://peach-agenda-free.peach-free-cloud-demo.workers.dev"
context = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    urllib.request.HTTPSHandler(context=context),
)


def call(path, payload=None):
    req = urllib.request.Request(
        URL + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json", "Origin": URL,
                 "User-Agent": "PeachLabSmoke/1.0"},
    )
    try:
        with opener.open(req, timeout=65) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        content = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(content)
        except ValueError:
            return error.code, {"error": content[:200]}


def main():
    values = {
        line.partition("=")[0]: line.partition("=")[2].strip().strip("\"'")
        for line in (ROOT / ".env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    }
    status, value = call("/api/me")
    assert status == 401, (status, value)
    status, _ = call("/api/login", {"password": values["CLOUDFLARE_DEMO_PASSWORD"]})
    assert status == 200, status
    status, meeting = call("/api/meetings", {"title": "Lab demo — Pricing review"})
    assert status == 201
    cases = json.loads((ROOT / "docs/ai-evidence/inputs.json").read_text())
    results = []
    for case in cases:
        started = time.monotonic()
        status, result = call("/api/parse", {k: case[k] for k in ["text", "today", "tz"]})
        results.append({"id": case["id"], "input": case, "status": status,
                        "response": result, "request_latency_ms": int((time.monotonic()-started)*1000),
                        "source": "deployed-cloudflare-api-not-browser"})
        (ROOT / "docs/ai-evidence/cloudflare-results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n"
        )
        print(f"Case {case['id']}: {status}", flush=True)
        if status in (429, 503):
            break
    successful = next((r for r in results if r["status"] == 200), None)
    assert successful, "No successful parse; see recorded results"
    suggestion = successful["response"]
    final = json.loads(json.dumps(suggestion["agenda"]))
    final["items"][0]["minutes"] = 20 if final["items"][0].get("minutes") != 20 else 25
    status, _ = call(f"/api/meetings/{meeting['id']}/agenda", {
        "agenda": final, "ai_suggestion": suggestion,
    })
    assert status == 200
    status, saved = call(f"/api/meetings/{meeting['id']}/agenda")
    assert status == 200 and saved["agenda"] == final and saved["ai_suggestion"] == suggestion
    evidence = {"url": URL, "meeting_id": meeting["id"], "unsigned_status": 401,
                "login_status": 200, "save_status": 200,
                "correction_persisted": True, "original_suggestion_preserved": True,
                "source": "deployed-api-not-browser", "aws_used": False}
    (ROOT / "docs/ai-evidence/cloudflare-save-check.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    print("Correction persisted; original AI suggestion preserved.", flush=True)


if __name__ == "__main__":
    main()
