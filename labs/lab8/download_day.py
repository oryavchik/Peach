"""Download one public day; no AWS account credentials or generated dataset."""
import argparse
import datetime
import json
import ssl
from pathlib import Path
from urllib.request import urlopen

p=argparse.ArgumentParser();p.add_argument('--day',default='2026-10-01');p.add_argument('--output',type=Path,required=True);args=p.parse_args()
day=datetime.date.fromisoformat(args.day)
if day.year!=2026 or day.month!=10:p.error('Use an October 2026 dataset day')
url=f'https://ucu-ooad-lab8-payments.s3.us-east-1.amazonaws.com/payments/dt={day}/events.jsonl'
args.output.parent.mkdir(parents=True,exist_ok=True)
cafile = '/etc/ssl/cert.pem' if Path('/etc/ssl/cert.pem').exists() else None
with urlopen(url, context=ssl.create_default_context(cafile=cafile)) as source,args.output.open('wb') as target:
    while chunk:=source.read(1024*1024):target.write(chunk)
print(json.dumps({'source':url,'bytes':args.output.stat().st_size}))
