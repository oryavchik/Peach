"""Local Firehose replacement: Kafka -> bounded buffers -> atomic JSONL batches.

Offsets are committed only after an fsynced batch directory has been renamed
into place. Restart seeks to the last complete directory, never to temp files.
"""
import argparse
import fcntl
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid
from confluent_kafka import Consumer, TopicPartition


class FileSink:
    def __init__(self,root,topic,partitions=3):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        config=self.root/'sink-config.json';expected={'topic':topic,'partitions':partitions}
        if config.exists() and json.loads(config.read_text())!=expected:raise ValueError('Lake belongs to another topic')
        if not config.exists():config.write_text(json.dumps(expected))
        self.buffers=defaultdict(list);self.bytes=defaultdict(int);self.starts={}
        self.ended=set();self.offsets={}
        for p in range(partitions):
            folder=self.root/f'partition={p}';folder.mkdir(exist_ok=True)
            for tmp in folder.glob('.partial-*'):shutil.rmtree(tmp)
            batches=sorted(folder.glob('batch=*'))
            offset=0
            for b in batches:
                m=json.loads((b/'manifest.json').read_text())
                if m['start_offset']!=offset:raise ValueError('Lake checkpoint gap')
                for f in m['files']:
                    if hashlib.sha256((b/f['path']).read_bytes()).hexdigest()!=f['sha256']:raise ValueError('Corrupt sink batch')
                offset=m['next_offset']
            self.offsets[p]=offset
            if (folder/'end.json').exists():
                end=json.loads((folder/'end.json').read_text())
                if end['offset']!=offset:raise ValueError('Invalid end-marker offset')
                self.offsets[p]=offset+1;self.ended.add(p)

    def next_offset(self,p):
        return self.starts.get(p,self.offsets[p])+len(self.buffers[p])

    def add(self,p,offset,event):
        if offset<self.offsets[p]:return
        if offset!=self.next_offset(p):raise ValueError('Sink record offset gap')
        if p in self.ended:raise ValueError('Record after finite replay end')
        if event.get('_control')=='end':
            self.flush(p)
            path=self.root/f'partition={p}'/'end.json'
            temp=path.with_suffix('.partial')
            with temp.open('w') as f:json.dump({'offset':offset},f);f.flush();os.fsync(f.fileno())
            temp.replace(path)
            descriptor=os.open(path.parent,os.O_RDONLY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
            self.offsets[p]=offset+1;self.ended.add(p)
            return
        self.starts.setdefault(p,offset)
        data=json.dumps(event,ensure_ascii=False,separators=(',',':'))+'\n'
        self.buffers[p].append((event['modifiedDate'][:10],data))
        self.bytes[p]+=len(data.encode())

    def flush(self,p):
        records=self.buffers[p]
        if not records:return
        start=self.starts[p];end=start+len(records)
        parent=self.root/f'partition={p}';temp=parent/('.partial-'+uuid.uuid4().hex)
        temp.mkdir();files=[]
        by_day=defaultdict(list)
        for day,data in records:
            # ISO date validation prevents paths escaping the lake.
            from datetime import date
            date.fromisoformat(day);by_day[day].append(data)
        for day,lines in by_day.items():
            folder=temp/f'dt={day}';folder.mkdir();path=folder/'events.jsonl'
            data=''.join(lines).encode()
            with path.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            descriptor=os.open(folder,os.O_RDONLY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
            files.append({'path':str(path.relative_to(temp)),'rows':len(lines),'sha256':hashlib.sha256(data).hexdigest()})
        manifest={'partition':p,'start_offset':start,'next_offset':end,'rows':len(records),'files':files}
        with (temp/'manifest.json').open('w') as f:json.dump(manifest,f);f.flush();os.fsync(f.fileno())
        descriptor=os.open(temp,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        dest=parent/f'batch={start:012d}-{end:012d}'
        temp.rename(dest)
        # Flush the parent directory entry before acknowledging the offset.
        descriptor=os.open(parent,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        self.offsets[p]=end;self.buffers[p]=[];self.bytes[p]=0;self.starts.pop(p,None)

    def rows(self):
        return sum(json.loads(p.read_text())['rows'] for p in self.root.glob('partition=*/batch=*/manifest.json'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--topic',default='payments-replacement');parser.add_argument('--group',default='lab8-file-sink')
    parser.add_argument('--flush-seconds',type=float,default=60);parser.add_argument('--flush-bytes',type=int,default=1048576)
    args=parser.parse_args()
    if args.flush_seconds<=0 or args.flush_bytes<=0:parser.error('Positive buffer limits required')
    args.root.mkdir(parents=True,exist_ok=True)
    lock=(args.root/'.writer.lock').open('w')
    # One writer per lake. Alert consumers use a DIFFERENT Kafka group.
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sink=FileSink(args.root,args.topic)
    c=Consumer({'bootstrap.servers':'localhost:19092','broker.address.family':'v4','group.id':args.group,
                'enable.auto.commit':False,'auto.offset.reset':'earliest'})
    def assign(consumer,partitions):
        for p in partitions:p.offset=sink.offsets[p.partition]
        consumer.assign(partitions)
    c.subscribe([args.topic],on_assign=assign);last_flush=time.monotonic();last_record=time.monotonic()
    try:
        while len(sink.ended)<3:
            msg=c.poll(.2)
            if msg is not None:
                if msg.error():raise RuntimeError(msg.error())
                last_record=time.monotonic();p=msg.partition();event=json.loads(msg.value())
                sink.add(p,msg.offset(),event)
                if sink.bytes[p]>=args.flush_bytes or event.get('_control')=='end':
                    sink.flush(p);c.commit(offsets=[TopicPartition(args.topic,p,sink.offsets[p])],asynchronous=False)
            if time.monotonic()-last_flush>=args.flush_seconds:
                for p in range(3):
                    sink.flush(p)
                    c.commit(offsets=[TopicPartition(args.topic,p,sink.offsets[p])],asynchronous=False)
                last_flush=time.monotonic()
            if time.monotonic()-last_record>180:raise TimeoutError('Incomplete finite replay')
    finally:
        c.close()
        lock.close()
    print(json.dumps({'type':'file_sink_result','topic':args.topic,'rows':sink.rows(),
        'ended_partitions':len(sink.ended),'batches':len(list(args.root.glob('partition=*/batch=*'))),
        'buffer_seconds':args.flush_seconds,'buffer_bytes':args.flush_bytes,'aws_executed':False}),flush=True)


if __name__=='__main__':main()
