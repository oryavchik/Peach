import base64
import os
from email.message import EmailMessage

import boto3

s3 = boto3.client("s3")
ses = boto3.client("sesv2")

EMAIL = "0689415525maria@gmail.com"


def handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        if not key.startswith("reports/") or not key.endswith(".csv"):
            continue

        csv_data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()

        message = EmailMessage()
        message["Subject"] = f"Peach weekly report: {key.split('/')[-1]}"
        message["From"] = EMAIL
        message["To"] = EMAIL
        message.set_content("Your weekly Peach report is attached.")
        message.add_attachment(
            csv_data,
            maintype="text",
            subtype="csv",
            filename=key.split("/")[-1],
        )

        ses.send_email(
            FromEmailAddress=EMAIL,
            Destination={"ToAddresses": [EMAIL]},
            Content={
                "Raw": {
                    "Data": message.as_bytes()
                }
            },
        )

        print(f"trigger=s3 bucket={bucket} key={key} email=sent")

    return {"status": "ok"}
