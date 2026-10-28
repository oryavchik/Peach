"""Verify the original Peach API against the deployed free Worker/D1 backend."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from smoke import ROOT, URL, call, opener


def main():
    values = {
        line.partition("=")[0]: line.partition("=")[2].strip().strip("\"'")
        for line in (ROOT / ".env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    }
    status, _ = call("/api/login", {"password": values["CLOUDFLARE_DEMO_PASSWORD"]})
    assert status == 200, status
    evidence = {"url": URL, "source": "deployed-original-api-not-browser", "aws_used": False}
    for path in ["/home", "/items", "/meetings", "/meetings/agenda", "/login"]:
        from urllib.request import Request
        with opener.open(Request(URL + path, headers={"User-Agent": "PeachLabSmoke/1.0"}), timeout=30) as response:
            content = response.read()
        local = ROOT / "frontend/out" / (path.strip("/") + ".html")
        assert hashlib.sha256(content).digest() == hashlib.sha256(local.read_bytes()).digest(), path
    evidence["original_export_pages_match"] = True
    status, value = call("/api/v1/items", {"name": "Free host verification", "description": "Synthetic test", "status": "todo"})
    assert status == 201
    item_id = value["id"]
    # urllib Request uses POST for a body unless an explicit method is provided.
    from urllib.request import Request
    req = Request(URL + f"/api/v1/items/{item_id}", data=b'{"status":"done"}', method="PATCH", headers={"Content-Type":"application/json","Origin":URL,"User-Agent":"PeachLabSmoke/1.0"})
    with opener.open(req, timeout=20) as response:
        assert json.load(response)["status"] == "done"
    req = Request(URL + f"/api/v1/items/{item_id}", method="DELETE", headers={"Origin":URL,"User-Agent":"PeachLabSmoke/1.0"})
    with opener.open(req, timeout=20) as response:
        assert response.status == 204
    evidence["board_create_move_delete"] = True
    status, value = call("/api/v1/meetings", {"title":"Original UI compatibility check", "starts_at":datetime.now(UTC).isoformat(), "duration_minutes":45,"participant_count":2})
    assert status == 201
    meeting_id = value["id"]
    cases = json.loads((ROOT / "docs/ai-evidence/inputs.json").read_text())
    case = cases[1]  # Synthetic English email from the lab evaluation fixtures.
    status, suggestion = call("/api/parse", {k:case[k] for k in ["text","today","tz"]})
    evidence["parse_status"] = status
    if status != 200:
        raise AssertionError(f"Free parse returned {status}; no success claimed")
    final = json.loads(json.dumps(suggestion["agenda"]))
    final["items"][0]["minutes"] = 20
    status, saved = call(f"/api/v1/meetings/{meeting_id}/agenda", {"agenda":final,"ai_suggestion":suggestion})
    assert status == 200 and saved["meeting"]["participant_count"] == 2
    status, saved = call(f"/api/v1/meetings/{meeting_id}/agenda")
    assert status == 200 and saved["agenda"] == final and saved["ai_suggestion"] == suggestion
    evidence.update(correction_persisted=True,original_suggestion_preserved=True,
                    model=suggestion["model"],cost_usd=suggestion["cost_usd"],
                    meeting_id=meeting_id)
    status, stats = call("/api/v1/meetings/stats")
    assert status == 200 and "previous_total_hours" in stats
    req = Request(URL + "/api/v1/meetings/report.csv",headers={"User-Agent":"PeachLabSmoke/1.0"})
    with opener.open(req,timeout=20) as response:
        assert "text/csv" in response.headers["content-type"]
        assert "duration_minutes" in response.read().decode("utf-8-sig")
    evidence.update(weekly_stats=True,csv_download=True)
    (ROOT / "docs/ai-evidence/cloudflare-original-ui-check.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print("Original pages match export; board CRUD, meeting/agenda Save, original suggestion, stats and CSV verified.")


if __name__ == "__main__":
    main()
