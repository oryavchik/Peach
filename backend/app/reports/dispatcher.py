"""Outside the VPC: turn private S3 request files into SQS commands."""

import logging
import os
from urllib.parse import unquote_plus

import boto3

from app.schemas.report import ReportRequest

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    s3 = boto3.client("s3")
    sqs = boto3.client("sqs")
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        if bucket != os.environ["REPORTS_BUCKET"] or not key.startswith("requests/"):
            continue
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        request = ReportRequest.model_validate_json(body)
        if key != request.key:
            raise ValueError("Report request does not match its object key")
        sqs.send_message(
            QueueUrl=os.environ["REPORT_QUEUE_URL"],
            MessageBody=request.model_dump_json(),
        )
        logger.info("trigger=s3-request request_id=%s week=%s", request.request_id, request.week)
    return {"status": "ok"}
