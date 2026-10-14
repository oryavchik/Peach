"""Generate a weekly report and upload it to S3."""

import json
import logging
import os
from datetime import date, timedelta

import boto3

from app.reports.weekly import build_weekly_report

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def previous_week() -> str:
    monday = date.today() - timedelta(days=date.today().weekday() + 7)
    year, week, _ = monday.isocalendar()
    return f"{year}-W{week:02d}"


def handler(event, context):
    source = event.get("source", "direct")
    week = event.get("week")

    if "Records" in event:
        record = event["Records"][0]
        message = json.loads(record["body"])
        source = message.get("source", "sqs")
        week = message.get("week")

    week = week or previous_week()

    logger.info("trigger=%s week=%s", source, week)

    csv_data = build_weekly_report(week)

    bucket = os.environ["REPORTS_BUCKET"]
    key = f"reports/{week}.csv"

    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=csv_data,
        ContentType="text/csv",
    )

    logger.info("report_uploaded=%s", key)

    return {"bucket": bucket, "key": key}
