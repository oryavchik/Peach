"""Prepared AWS Lambda tumbling-window checker. Not deployed.

Kinesis/Lambda windows are shard/arrival-time windows, unlike local GLOBAL
modifiedDate windows. SNS is at-least-once, and email requires confirmation.
"""
import base64
import hashlib
import json
import os


def handler(event,context):
    state=event.get('state') or {'seen':[],'methods':{}}
    seen=set(state['seen']);methods=state['methods']
    for record in event.get('Records',[]):
        raw=base64.b64decode(record['kinesis']['data']);e=json.loads(raw)
        key=hashlib.sha256(json.dumps(e,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if key in seen:continue
        if len(seen)>=5000:raise RuntimeError('Demo window state limit exceeded; use Flink/Redis for production')
        seen.add(key)
        if e['status'] not in ('success','failure'):continue
        m=methods.setdefault(e['paymentMethod'],{'terminal':0,'failure':0})
        m['terminal']+=1;m['failure']+=int(e['status']=='failure')
    if event.get('isFinalInvokeForWindow'):
        import boto3
        sns=boto3.client('sns')
        for method,counts in methods.items():
            rate=counts['failure']/counts['terminal']
            if rate>.1:
                sns.publish(TopicArn=os.environ['ALERT_TOPIC_ARN'],Subject='Payments failure rate >10%',
                    Message=json.dumps({'method':method,'failure_rate':rate,'counts':counts,
                                        'window':event.get('window'),'shard':event.get('shardId'),
                                        'scope':'arrival-time per-shard; not global event-time'}))
    return {'state':{'seen':sorted(seen),'methods':methods}}
