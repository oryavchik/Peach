import argparse
import json
import signal
import time
from pathlib import Path
from confluent_kafka import Consumer, TopicPartition
from window_store import WindowStore


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bootstrap', default='localhost:19092')
    p.add_argument('--topic', default='payments')
    p.add_argument('--group', default='payments-lab8')
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--lateness', type=int, default=120)
    p.add_argument('--idle-timeout', type=int, default=90)
    args = p.parse_args()
    if args.lateness < 0:
        p.error('lateness must be non-negative')
    args.state.parent.mkdir(parents=True, exist_ok=True)
    store = WindowStore(args.state, args.group, args.topic, lateness=args.lateness)
    c = Consumer({'bootstrap.servers': args.bootstrap, 'group.id': args.group,
                  'enable.auto.commit': False, 'broker.address.family': 'v4', 'auto.offset.reset': 'earliest',
                  'partition.assignment.strategy': 'range', 'session.timeout.ms': 10000})
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def assigned(consumer, partitions):
        # Durable state wins over a possibly stale Kafka commit after a crash.
        for part in partitions:
            part.offset = store.offset(part.partition)
        consumer.assign(partitions)
        print(json.dumps({'type': 'assignment', 'group': args.group,
                          'partitions': [part.partition for part in partitions]}), flush=True)
    c.subscribe([args.topic], on_assign=assigned)
    last = time.monotonic()
    try:
        while not stopped:
            if store.db.execute('SELECT SUM(ended) FROM progress').fetchone()[0] == 3:
                break
            msg = c.poll(.5)
            if msg is None:
                if time.monotonic()-last > args.idle_timeout:
                    raise TimeoutError('Replay incomplete; no end markers on all partitions')
                continue
            if msg.error():
                raise RuntimeError(msg.error())
            last = time.monotonic()
            event = json.loads(msg.value())
            for result in store.process(msg.partition(), msg.offset(), event):
                print(json.dumps(result), flush=True)
            # SQLite is the durable checkpoint; Kafka commits are batched.
            if msg.offset() % 1000 == 0 or event.get('_control') == 'end':
                c.commit(offsets=[TopicPartition(args.topic,msg.partition(),msg.offset()+1)], asynchronous=False)
    finally:
        c.close()
        print(json.dumps(store.summary()), flush=True)
        store.close()


if __name__ == '__main__':
    main()
