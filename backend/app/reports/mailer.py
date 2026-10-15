"""React to report uploads without a database or VPC connection."""

import logging
import os
from email.message import EmailMessage
from urllib.parse import unquote_plus

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    sender = os.environ["REPORT_SENDER"]
    recipients = [address.strip() for address in os.environ["REPORT_RECIPIENTS"].split(",")]
    recipients = [address for address in recipients if address]
    if not sender.strip() or not recipients:
        raise ValueError("REPORT_SENDER and REPORT_RECIPIENTS must be configured")

    s3 = boto3.client("s3")
    ses = boto3.client("sesv2")
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        logger.info("trigger=s3 bucket=%s key=%s", bucket, key)
        if not key.startswith("reports/") or not key.endswith(".csv"):
            continue

        obj = s3.get_object(Bucket=bucket, Key=key)
        destination = recipients
        if key.startswith("reports/users/"):
            recipient = obj.get("Metadata", {}).get("recipient")
            if not recipient or "\r" in recipient or "\n" in recipient:
                raise ValueError("Personal report requires recipient metadata")
            destination = [recipient]
        csv_data = obj["Body"].read()
        filename = key.rsplit("/", 1)[-1]
        message = EmailMessage()
        message["Subject"] = f"Peach weekly report: {filename}"
        message["From"] = sender
        message["To"] = ", ".join(destination)
        message.set_content("Your weekly Peach report is attached.")
        message.add_attachment(csv_data, maintype="text", subtype="csv", filename=filename)
        result = ses.send_email(
            FromEmailAddress=sender,
            Destination={"ToAddresses": destination},
            Content={"Raw": {"Data": message.as_bytes()}},
        )
        # SES acceptance is observable; inbox delivery still requires delivery events
        # or confirmation from the recipient. Never log email body or credentials.
        logger.info("email=accepted key=%s ses_message_id=%s", key, result["MessageId"])
    return {"status": "ok"}
