import io
import json
import uuid
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from app.api.routes import meetings
from app.config import get_settings
from app.reports import dispatcher, lambda_handler, mailer
from app.schemas.report import ReportRequest


def request_payload():
    return ReportRequest(
        request_id=uuid.uuid4(),
        organizer_id=uuid.uuid4(),
        recipient="alice@example.com",
        week="2026-W42",
    )


async def test_button_queues_only_authenticated_user_report(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "reports_bucket", "test-reports")
    s3 = Mock()
    monkeypatch.setattr(meetings.boto3, "client", lambda _: s3)
    response = await client.post(
        "/api/v1/meetings/report", json={"recipient": "attacker@example.com"}
    )
    assert response.status_code == 202
    kwargs = s3.put_object.call_args.kwargs
    body = json.loads(kwargs["Body"])
    assert body["recipient"] == "alice@example.com"
    assert body["request_id"] == response.json()["request_id"]
    assert kwargs["Key"] == f"requests/{body['organizer_id']}/{body['request_id']}.json"


async def test_report_rejects_unverified_email(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "reports_bucket", "test-reports")
    monkeypatch.setattr(meetings, "_decode_token", lambda _: {"email_verified": False})
    assert (await client.post("/api/v1/meetings/report")).status_code == 403


async def test_report_rejects_address_not_enabled_in_sandbox(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "reports_bucket", "test-reports")
    monkeypatch.setattr(get_settings(), "report_request_recipients", "someone@example.com")
    assert (await client.post("/api/v1/meetings/report")).status_code == 403


async def test_report_does_not_claim_queued_if_s3_fails(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "reports_bucket", "test-reports")
    s3 = Mock()
    s3.put_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
    monkeypatch.setattr(meetings.boto3, "client", lambda _: s3)
    assert (await client.post("/api/v1/meetings/report")).status_code == 503


async def test_report_requires_authentication(anon_client):
    assert (await anon_client.post("/api/v1/meetings/report")).status_code == 401


def test_dispatcher_validates_request_and_sends_sqs(monkeypatch):
    payload = request_payload()
    s3, sqs = Mock(), Mock()
    s3.get_object.return_value = {"Body": io.BytesIO(payload.model_dump_json().encode())}
    monkeypatch.setattr(dispatcher.boto3, "client", lambda service: {"s3": s3, "sqs": sqs}[service])
    monkeypatch.setenv("REPORTS_BUCKET", "test-reports")
    monkeypatch.setenv("REPORT_QUEUE_URL", "test-queue")
    event = {
        "Records": [{"s3": {"bucket": {"name": "test-reports"}, "object": {"key": payload.key}}}]
    }
    dispatcher.handler(event, None)
    assert json.loads(sqs.send_message.call_args.kwargs["MessageBody"])["organizer_id"] == str(
        payload.organizer_id
    )
    assert sqs.send_message.call_args.kwargs["QueueUrl"] == "test-queue"


def test_personal_builder_scopes_query_and_sets_recipient(monkeypatch):
    payload = request_payload()
    build, s3 = Mock(return_value=b"private csv"), Mock()
    monkeypatch.setattr(lambda_handler, "build_weekly_report", build)
    monkeypatch.setattr(lambda_handler.boto3, "client", lambda _: s3)
    monkeypatch.setenv("REPORTS_BUCKET", "test-reports")
    result = lambda_handler.handler(payload.model_dump(mode="json"), None)
    build.assert_called_once_with(payload.week, organizer_id=payload.organizer_id)
    assert (
        result["key"]
        == f"reports/users/{payload.organizer_id}/{payload.request_id}/{payload.week}.csv"
    )
    assert s3.put_object.call_args.kwargs["Metadata"] == {"recipient": payload.recipient}


def test_personal_mailer_uses_owner_instead_of_global_list(monkeypatch):
    s3, ses = Mock(), Mock()
    s3.get_object.return_value = {
        "Body": io.BytesIO(b"private csv"),
        "Metadata": {"recipient": "alice@example.com"},
    }
    ses.send_email.return_value = {"MessageId": "test"}
    monkeypatch.setattr(mailer.boto3, "client", lambda service: {"s3": s3, "sesv2": ses}[service])
    monkeypatch.setenv("REPORT_SENDER", "reports@example.com")
    monkeypatch.setenv("REPORT_RECIPIENTS", "admin@example.com")
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "test-reports"},
                    "object": {"key": "reports/users/owner/id/2026-W42.csv"},
                }
            }
        ]
    }
    mailer.handler(event, None)
    assert ses.send_email.call_args.kwargs["Destination"] == {"ToAddresses": ["alice@example.com"]}
    s3.get_object.return_value = {"Body": io.BytesIO(b"private csv")}
    with pytest.raises(ValueError, match="recipient metadata"):
        mailer.handler(event, None)
