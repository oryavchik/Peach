import io
import json
from email import policy
from email.parser import BytesParser
from unittest.mock import Mock

import pytest

from app.reports import lambda_handler as builder
from app.reports import mailer
from app.reports.weekly import week_bounds


def test_iso_week_crosses_calendar_year():
    start, end = week_bounds("2026-W01")
    assert start.isoformat() == "2025-12-29T00:00:00+00:00"
    assert (end - start).days == 7


@pytest.mark.parametrize("week", ["2026-W00", "2026-W54", "2026-42", "", "2026-W1"])
def test_invalid_weeks_are_rejected(week):
    with pytest.raises(ValueError):
        week_bounds(week)


@pytest.fixture
def report_clients(monkeypatch):
    s3, ses = Mock(), Mock()
    s3.get_object.return_value = {"Body": io.BytesIO(b"Metric,Value\nTotal meetings,1\n")}
    ses.send_email.return_value = {"MessageId": "ses-test-id"}
    monkeypatch.setattr(mailer.boto3, "client", lambda service: {"s3": s3, "sesv2": ses}[service])
    monkeypatch.setenv("REPORT_SENDER", "reports@example.com")
    monkeypatch.setenv("REPORT_RECIPIENTS", " alice@example.com, bob@example.com ")
    return s3, ses


def s3_event(key="reports/2026-W42.csv"):
    return {"Records": [{"s3": {"bucket": {"name": "test-reports"}, "object": {"key": key}}}]}


def test_mailer_sends_real_csv_attachment_and_logs_ses_id(report_clients, caplog):
    s3, ses = report_clients
    mailer.handler(s3_event("reports%2F2026-W42.csv"), None)
    s3.get_object.assert_called_once_with(Bucket="test-reports", Key="reports/2026-W42.csv")
    sent = ses.send_email.call_args.kwargs
    assert sent["Destination"] == {"ToAddresses": ["alice@example.com", "bob@example.com"]}
    message = BytesParser(policy=policy.default).parsebytes(sent["Content"]["Raw"]["Data"])
    assert message["From"] == "reports@example.com"
    (attachment,) = message.iter_attachments()
    assert attachment.get_filename() == "2026-W42.csv"
    assert attachment.get_payload(decode=True).startswith(b"Metric,Value")
    assert "trigger=s3" in caplog.text
    assert "ses_message_id=ses-test-id" in caplog.text


def test_mailer_does_not_swallow_ses_failure(report_clients):
    _, ses = report_clients
    ses.send_email.side_effect = RuntimeError("SES unavailable")
    with pytest.raises(RuntimeError, match="SES unavailable"):
        mailer.handler(s3_event(), None)


def test_mailer_ignores_other_prefixes(report_clients):
    s3, ses = report_clients
    mailer.handler(s3_event("requests/report.json"), None)
    s3.get_object.assert_not_called()
    ses.send_email.assert_not_called()


def test_mailer_requires_recipient_configuration(report_clients, monkeypatch):
    monkeypatch.setenv("REPORT_RECIPIENTS", " , ")
    with pytest.raises(ValueError, match="must be configured"):
        mailer.handler(s3_event(), None)


def test_duplicate_upload_events_can_send_two_emails(report_clients):
    s3, ses = report_clients
    s3.get_object.side_effect = lambda **_: {"Body": io.BytesIO(b"csv")}
    mailer.handler(s3_event(), None)
    mailer.handler(s3_event(), None)
    assert ses.send_email.call_count == 2


@pytest.mark.parametrize("source,trigger", [("manual", "sqs"), ("schedule", "schedule")])
def test_builder_detects_trigger_and_uses_stable_key(monkeypatch, caplog, source, trigger):
    s3 = Mock()
    monkeypatch.setattr(builder.boto3, "client", lambda _: s3)
    monkeypatch.setattr(builder, "build_weekly_report", lambda week: week.encode())
    monkeypatch.setenv("REPORTS_BUCKET", "test-reports")
    event = {"Records": [{"body": json.dumps({"week": "2026-W42", "source": source})}]}
    for _ in range(2):
        assert builder.handler(event, None)["key"] == "reports/2026-W42.csv"
    assert s3.put_object.call_count == 2
    assert s3.put_object.call_args.kwargs["Key"] == "reports/2026-W42.csv"
    assert f"trigger={trigger} week=2026-W42" in caplog.text


def test_missing_week_is_decided_by_handler(monkeypatch):
    build = Mock(return_value=b"csv")
    monkeypatch.setattr(builder, "previous_week", lambda: "2026-W41")
    monkeypatch.setattr(builder, "build_weekly_report", build)
    monkeypatch.setattr(builder.boto3, "client", lambda _: Mock())
    monkeypatch.setenv("REPORTS_BUCKET", "test-reports")
    builder.handler({"source": "schedule", "week": None}, None)
    build.assert_called_once_with("2026-W41")


def test_controlled_failure_can_be_disabled_for_redrive(monkeypatch):
    build = Mock(return_value=b"csv")
    monkeypatch.setattr(builder, "build_weekly_report", build)
    monkeypatch.setattr(builder.boto3, "client", lambda _: Mock())
    monkeypatch.setenv("REPORTS_BUCKET", "test-reports")
    monkeypatch.setenv("REPORT_FAIL_WEEK", "2026-W42")
    with pytest.raises(RuntimeError, match="Controlled DLQ test failure"):
        builder.handler({"week": "2026-W42"}, None)
    build.assert_not_called()
    monkeypatch.delenv("REPORT_FAIL_WEEK")
    assert builder.handler({"week": "2026-W42"}, None)["key"] == "reports/2026-W42.csv"
