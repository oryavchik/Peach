"""Build reports from direct commands or SQS messages and save them to S3."""

import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import boto3

from app.reports.weekly import build_weekly_report
from app.schemas.report import ReportRequest

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def previous_week() -> str:
    today = datetime.now(ZoneInfo("Europe/Kyiv")).date()
    monday = today - timedelta(days=today.weekday() + 7)
    year, week, _ = monday.isocalendar()
    return f"{year}-W{week:02d}"


def _build(message: dict, trigger: str) -> dict[str, str]:
    week = message.get("week") or previous_week()
    logger.info("trigger=%s week=%s", trigger, week)
    # Disabled by default. Used only for the lab's controlled failure/redrive test.
    if os.environ.get("REPORT_FAIL_WEEK") == week:
        raise RuntimeError(f"Controlled DLQ test failure for {week}")
    metadata = {}
    if "request_id" in message:
        request = ReportRequest.model_validate(message)
        csv_data = build_weekly_report(week, organizer_id=request.organizer_id)
        key = f"reports/users/{request.organizer_id}/{request.request_id}/{week}.csv"
        metadata = {"recipient": request.recipient}
    else:
        csv_data = build_weekly_report(week)
        key = f"reports/{week}.csv"
    bucket = os.environ["REPORTS_BUCKET"]
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=csv_data,
        Metadata=metadata,
        ContentType="text/csv; charset=utf-8",
    )
    logger.info("report_uploaded=%s", key)
    return {"bucket": bucket, "key": key}


def handler(event, context):
    if "Records" in event:
        results = []
        for record in event["Records"]:
            message = json.loads(record["body"])
            trigger = "schedule" if message.get("source") == "schedule" else "sqs"
            results.append(_build(message, trigger))
        return results[0] if len(results) == 1 else {"reports": results}
    return _build(event, event.get("source", "direct"))
