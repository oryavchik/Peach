"""Bounded free-tier smoke test using synthetic data and short-lived credentials.

Run from repository root. Never copies production/user data or changes IAM.
"""
import json
import os
import subprocess
from free_api import call, OUT, PROJECT, GCLOUD


def main():
    billing = json.loads(subprocess.check_output(
        [str(GCLOUD), 'billing', 'projects', 'describe', PROJECT, '--format=json'],
        env={**os.environ, 'CLOUDSDK_PYTHON': '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3'}, text=True))
    assert billing.get('billingEnabled') is False, billing
    database = call(f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)')
    assert database.get('freeTier') is True, database
    url = f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/lab9_demo/free-tier-smoke'
    fields = {
        'title': {'stringValue': 'Peach synthetic GCP database check'},
        'synthetic': {'booleanValue': True},
        'duration_minutes': {'integerValue': '30'},
        'contains_personal_data': {'booleanValue': False},
    }
    written = call(url, 'PATCH', {'fields': fields})
    assert not written.get('request_failed'), written
    read = call(url)
    assert read.get('fields') == fields, read
    result = {
        'date': '2026-11-08', 'project': PROJECT, 'billing_enabled': False,
        'database_free_tier': True, 'synthetic_only': True,
        'write_read_equal': True, 'endpoint': url,
        'read_result': read,
        'scope': 'Authenticated Firestore REST write/read; not a deployed Peach FastAPI endpoint',
        'cleanup': 'One synthetic document retained for review; no paid TTL/PITR enabled',
    }
    (OUT / 'firestore-smoke.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'write_read_equal': True, 'database_free_tier': True, 'billing_enabled': False}))


if __name__ == '__main__':
    main()
