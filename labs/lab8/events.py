"""Shared real-dataset parsing. No synthetic dataset generator."""
import hashlib
import json
from datetime import datetime, timezone


def timestamp(value):
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp())


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def fingerprint(event):
    return hashlib.sha256(json.dumps(event, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def load_events(path):
    with open(path) as stream:
        events = [json.loads(line) for line in stream if line.strip()]
    # Stable tie order: do not reorder equal receivedAt timestamps arbitrarily.
    return sorted(events, key=lambda e: timestamp(e['receivedAt']))


def force_failure(event, rate):
    if rate is None or event['status'] not in ('success', 'failure'):
        return event
    result = dict(event)
    fraction = int(hashlib.sha256(event['invoiceId'].encode()).hexdigest()[:16], 16) / 2**64
    result['status'] = 'failure' if fraction < rate else 'success'
    result['finalAmount'] = 0 if result['status'] == 'failure' else result['amount']
    if result['status'] == 'failure':
        result['failureReason'] = 'injected_for_lab_experiment'
    else:
        result.pop('failureReason', None)
    return result
