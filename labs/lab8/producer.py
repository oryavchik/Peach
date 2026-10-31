"""Replay one existing day, keyed by invoiceId, ordered by receivedAt."""
import argparse
import json
import time
from confluent_kafka import Producer
from events import force_failure, load_events


def main():
    p = argparse.ArgumentParser()
    p.add_argument('file')
    p.add_argument('--bootstrap', default='localhost:19092')
    p.add_argument('--topic', default='payments')
    p.add_argument('--payments-per-second', type=float, default=20)
    p.add_argument('--failure-rate', type=float)
    args = p.parse_args()
    if args.payments_per_second < 0 or (args.failure_rate is not None and not 0<=args.failure_rate<=1):
        p.error('Invalid rate; use replay rate 0 only for accelerated experiments')
    events = load_events(args.file)
    invoices = len({e['invoiceId'] for e in events})
    # Pace webhook events so the mean rate is ~20 distinct payments per second.
    interval = invoices / len(events) / args.payments_per_second if args.payments_per_second else 0
    producer = Producer({'bootstrap.servers': args.bootstrap, 'enable.idempotence': True, 'acks': 'all', 'broker.address.family': 'v4', 'partitioner': 'murmur2_random'})
    failures = []
    def delivered(error, message):
        if error:
            failures.append(str(error))
    started = time.monotonic()
    for i, event in enumerate(events):
        event = force_failure(event, args.failure_rate)
        data = json.dumps(event, separators=(',', ':'), ensure_ascii=False).encode()
        while True:
            try:
                producer.produce(args.topic, key=event['invoiceId'].encode(), value=data, on_delivery=delivered)
                break
            except BufferError:
                producer.poll(.1)
        producer.poll(0)
        if interval:
            time.sleep(max(0, started+(i+1)*interval-time.monotonic()))
    if producer.flush(60) or failures:
        raise RuntimeError('Delivery failed; end markers were not sent: '+str(failures[:3]))
    # End markers are only for finite replay: drain ALL partitions deterministically.
    for partition in range(3):
        producer.produce(args.topic, partition=partition, value=b'{"_control":"end"}', on_delivery=delivered)
    if producer.flush(30) or failures:
        raise RuntimeError('Failed to deliver end markers')
    print(json.dumps({'events': len(events), 'payments': invoices, 'end_markers': 3,
                      'seconds': round(time.monotonic()-started, 3),
                      'target_payments_per_second': args.payments_per_second, 'injected_failure_rate': args.failure_rate}))


if __name__ == '__main__':
    main()
