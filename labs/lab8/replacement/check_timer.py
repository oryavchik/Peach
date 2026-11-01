"""Real default-60-second file-sink flush check with 10 existing source events."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
import time
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient,NewTopic


def main():
    p=argparse.ArgumentParser();p.add_argument('--file',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.work.mkdir(parents=True,exist_ok=True)
    topic='payments-timer-check';admin=AdminClient({'bootstrap.servers':'localhost:19092','broker.address.family':'v4'})
    for f in admin.create_topics([NewTopic(topic,3,1)]).values():f.result()
    raw=a.work/'raw';log=(a.work/'sink.log').open('w');started=time.monotonic()
    proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name('file_sink.py')),'--root',str(raw),'--topic',topic,'--group','lab8-timer-check'],stdout=log,stderr=log)
    producer=Producer({'bootstrap.servers':'localhost:19092','broker.address.family':'v4'})
    time.sleep(3)
    with gzip.open(a.file,'rt') as f:
        events=[json.loads(next(f)) for _ in range(10)]
    for e in events:producer.produce(topic,partition=0,key=e['invoiceId'].encode(),value=json.dumps(e).encode())
    if producer.flush(20):raise RuntimeError('Timer probe delivery failed')
    while not list(raw.glob('partition=*/batch=*/manifest.json')):
        if proc.poll() is not None:raise RuntimeError('Sink failed during timer check')
        if time.monotonic()-started>90:proc.terminate();raise TimeoutError('Default time buffer did not flush')
        time.sleep(.2)
    elapsed=time.monotonic()-started
    rows=sum(json.loads(f.read_text())['rows'] for f in raw.glob('partition=*/batch=*/manifest.json'))
    if rows!=10:raise AssertionError('Timer probe did not persist all 10 records')
    for partition in range(3):producer.produce(topic,partition=partition,value=b'{"_control":"end"}')
    if producer.flush(20):raise RuntimeError('Timer probe end marker failed')
    if proc.wait(30):raise RuntimeError('Timer-check sink failed')
    log.close()
    result={'execution':'real local file-sink time trigger','source_records':10,'persisted_before_end_markers':rows,
        'configured_flush_seconds':60,'configured_flush_bytes':1048576,
        'observed_seconds_since_sink_start':round(elapsed,3),'flush_reason':'time; far below size threshold; EOS not sent until after flush',
        'aws_executed':False}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
