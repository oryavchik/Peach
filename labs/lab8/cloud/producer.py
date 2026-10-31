"""PREPARED, NOT RUN ON AWS. Uses the same real replay and explicit paid opt-in."""
import argparse
import json
import sys
import time
from pathlib import Path
import boto3
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from events import force_failure, load_events


def main():
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--stream',required=True)
    p.add_argument('--region',default='us-east-1');p.add_argument('--payments-per-second',type=float,default=20)
    p.add_argument('--failure-rate',type=float);p.add_argument('--allow-paid-aws',action='store_true');args=p.parse_args()
    if not args.allow_paid_aws:p.error('AWS execution is disabled: requires explicit cost approval')
    if args.payments_per_second<=0:p.error('Use a positive rate')
    events=load_events(args.file);invoices=len({e['invoiceId'] for e in events});interval=invoices/len(events)/args.payments_per_second
    client=boto3.client('kinesis',region_name=args.region);started=time.monotonic();sent=0
    # put_record + the previous sequence number preserves per-invoice order.
    # Network retries may still duplicate a record; the consumer must dedup.
    sequences={}
    for i,event in enumerate(events):
        record={'StreamName':args.stream,'PartitionKey':event['invoiceId'],
                'Data':(json.dumps(force_failure(event,args.failure_rate),ensure_ascii=False)+'\n').encode()}
        if event['invoiceId'] in sequences:
            record['SequenceNumberForOrdering']=sequences[event['invoiceId']]
        response=client.put_record(**record)
        sequences[event['invoiceId']]=response['SequenceNumber'];sent+=1
        time.sleep(max(0,started+(i+1)*interval-time.monotonic()))
    print(json.dumps({'sent':sent,'source_events':len(events)}))


if __name__=='__main__':main()
