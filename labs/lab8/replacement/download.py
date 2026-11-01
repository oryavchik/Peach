"""Read the existing public dataset; compress each day while downloading.

No generator, account credentials or AWS resource creation. At most one network
chunk per thread is kept in Python memory. Raw 1.2 GB is not stored on disk.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import ssl
from urllib.request import urlopen


def download_day(root, day):
    date=f'2026-10-{day:02d}'
    url=f'https://ucu-ooad-lab8-payments.s3.us-east-1.amazonaws.com/payments/dt={date}/events.jsonl'
    dest=root/f'dt={date}'/'events.jsonl.gz'
    dest.parent.mkdir(parents=True,exist_ok=True)
    partial=dest.with_suffix('.partial')
    digest=hashlib.sha256();size=0
    context=ssl.create_default_context(cafile='/etc/ssl/cert.pem' if Path('/etc/ssl/cert.pem').exists() else None)
    with urlopen(url,context=context,timeout=120) as source,gzip.open(partial,'wb',compresslevel=1) as target:
        etag=source.headers.get('ETag')
        while chunk:=source.read(1024*1024):
            digest.update(chunk);size+=len(chunk);target.write(chunk)
    partial.replace(dest)
    print(json.dumps({'day':date,'source_bytes':size,'compressed_bytes':dest.stat().st_size}),flush=True)
    return {'day':date,'source':url,'source_bytes':size,'gzip_bytes':dest.stat().st_size,
            'sha256_uncompressed':digest.hexdigest(),'etag':etag}


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--days',type=int,default=31);args=p.parse_args()
    if not 1<=args.days<=31:p.error('days must be 1..31')
    args.out.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda day:download_day(args.out,day),range(1,args.days+1)))
    (args.out/'manifest.json').write_text(json.dumps({'source':'existing public October 2026 payments',
        'generated':False,'days':results,'source_bytes':sum(r['source_bytes'] for r in results),
        'gzip_bytes':sum(r['gzip_bytes'] for r in results)},indent=2)+'\n')


if __name__=='__main__':main()
