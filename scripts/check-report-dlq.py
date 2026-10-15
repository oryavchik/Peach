#!/usr/bin/env python3
"""Controlled, real AWS DLQ/redrive check; sends one report email after recovery.

Run only with an idle reports queue. During the test, the chosen week fails
before accessing meetings or S3. Queue visibility is temporarily 60 seconds
to observe the retries faster, then restored. SQS polling and propagation
can still make the check take several minutes.
"""

import argparse
import json
import os
import subprocess
import tempfile
import time
from datetime import UTC, datetime

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--week", required=True, help="Report week emailed after redrive")
parser.add_argument("--region", default="us-east-1")
parser.add_argument("--project", default="peach")
args = parser.parse_args()


def aws(*command):
    result = subprocess.run(
        ["aws", *command, "--region", args.region, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def log(message):
    print(datetime.now(UTC).isoformat(), message, flush=True)


account = aws("sts", "get-caller-identity")["Account"]
queue = f"https://sqs.{args.region}.amazonaws.com/{account}/{args.project}-reports-queue"
dlq = f"https://sqs.{args.region}.amazonaws.com/{account}/{args.project}-reports-dlq"
function = f"{args.project}-report-builder"


def attributes(url):
    return aws("sqs", "get-queue-attributes", "--queue-url", url, "--attribute-names", "All")[
        "Attributes"
    ]


def empty(values):
    return all(
        int(values.get(key, 0)) == 0
        for key in (
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
            "ApproximateNumberOfMessagesDelayed",
        )
    )


initial = attributes(queue)
assert empty(initial) and empty(attributes(dlq)), "Stop: both queues must be idle and empty"
original_visibility = initial["VisibilityTimeout"]
original_env = aws("lambda", "get-function-configuration", "--function-name", function)[
    "Environment"
]["Variables"]
assert not original_env.get("REPORT_FAIL_WEEK"), "Stop: another failure test is active"


def configure(env):
    # Database credentials never go into argv, logs, or the repository.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as temp:
        os.chmod(temp.name, 0o600)
        json.dump({"Variables": env}, temp)
        temp.flush()
        aws(
            "lambda",
            "update-function-configuration",
            "--function-name",
            function,
            "--environment",
            f"file://{temp.name}",
        )
    aws("lambda", "wait", "function-updated-v2", "--function-name", function)


try:
    configure({**original_env, "REPORT_FAIL_WEEK": args.week})
    aws("sqs", "set-queue-attributes", "--queue-url", queue, "--attributes", "VisibilityTimeout=60")
    # SQS attribute changes may take up to 60 seconds to propagate.
    time.sleep(60)
    log(f"Controlled failure enabled for {args.week}; temporary visibility=60")
    message = aws(
        "sqs",
        "send-message",
        "--queue-url",
        queue,
        "--message-body",
        json.dumps({"week": args.week, "source": "dlq-test"}),
    )
    log(f"Test command enqueued: {message['MessageId']}")
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        count = int(attributes(dlq)["ApproximateNumberOfMessages"])
        log(f"DLQ visible messages={count}")
        if count:
            break
        time.sleep(15)
    else:
        raise TimeoutError("No DLQ message after 15 minutes; settings will be restored")
    log("PASS: Lambda failures exhausted retries and message reached the real DLQ")
finally:
    # Restore normal settings even if polling or a service call fails.
    try:
        aws(
            "sqs",
            "set-queue-attributes",
            "--queue-url",
            queue,
            "--attributes",
            f"VisibilityTimeout={original_visibility}",
        )
    finally:
        configure(original_env)
    log(f"Restored visibility={original_visibility}; failure injection disabled")

move = aws(
    "sqs",
    "start-message-move-task",
    "--source-arn",
    attributes(dlq)["QueueArn"],
    "--destination-arn",
    initial["QueueArn"],
    "--max-number-of-messages-per-second",
    "1",
)
log("DLQ redrive started")
deadline = time.monotonic() + 180
while time.monotonic() < deadline:
    tasks = aws("sqs", "list-message-move-tasks", "--source-arn", attributes(dlq)["QueueArn"])[
        "Results"
    ]
    # SQS only includes TaskHandle while a move task is RUNNING.
    task = tasks[0] if tasks else None
    if task and task["Status"] == "COMPLETED" and task["ApproximateNumberOfMessagesMoved"] >= 1:
        log(f"PASS: redrive completed; moved={task['ApproximateNumberOfMessagesMoved']}")
        break
    if task and task["Status"] in {"FAILED", "CANCELLED"}:
        raise RuntimeError(f"Redrive did not complete: {task['Status']}")
    time.sleep(5)
else:
    raise TimeoutError("Redrive still running; inspect SQS console")
log("Check builder report_uploaded and mailer ses_message_id for the recovered command")
