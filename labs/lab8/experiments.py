"""Real Redpanda experiments. Replays are accelerated; default producer rate is 20 payments/s."""
import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from confluent_kafka.admin import AdminClient, NewTopic

ROOT=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    args.work.mkdir(parents=True,exist_ok=True);args.out.mkdir(parents=True,exist_ok=True)
    admin=AdminClient({'bootstrap.servers':'localhost:19092','broker.address.family':'v4'})
    results={}
    for name,lateness,workers,rate,restart in [
        ('baseline',120,1,None,False),('restart',120,1,None,True),
        ('two-consumers',120,2,None,False),('failure-30',120,1,.3,False),
        ('lateness-zero',0,1,None,False)]:
        topic='payments' if name=='baseline' else 'payments-'+name
        for future in admin.create_topics([NewTopic(topic,num_partitions=3,replication_factor=1)]).values():future.result()
        group='lab8-'+name;state=args.work/(name+'.db');logs=[];processes=[];opened=[]
        def start_worker(index,suffix=''):
            log=args.work/(name+f'-consumer-{index}'+suffix+'.jsonl');f=log.open('w');opened.append(f);logs.append(log)
            proc=subprocess.Popen([sys.executable,str(ROOT/'consumer.py'),'--topic',topic,'--group',group,'--state',str(state),'--lateness',str(lateness),'--idle-timeout','180'],stdout=f,stderr=f)
            processes.append(proc);return proc
        first=start_worker(0)
        if workers==2:start_worker(1)
        time.sleep(4)
        command=[sys.executable,str(ROOT/'producer.py'),str(args.file),'--topic',topic,'--payments-per-second','0']
        if rate is not None:command+=['--failure-rate',str(rate)]
        producer_log=(args.work/(name+'-producer.json')).open('w');opened.append(producer_log)
        producer=subprocess.Popen(command,stdout=producer_log,stderr=producer_log)
        paused=0
        if restart:
            import sqlite3
            for _ in range(300):
                try:
                    with sqlite3.connect(state) as db:
                        count=db.execute("SELECT count FROM counters WHERE name='events'").fetchone()
                    if count and count[0]>=1000:break
                except sqlite3.Error:pass
                if first.poll() is not None:raise RuntimeError('Consumer exited before restart test')
                time.sleep(.1)
            first.terminate();first.wait(30)
            stopped=time.monotonic();time.sleep(60);paused=round(time.monotonic()-stopped,3)
            start_worker(0,'-resumed')
        if producer.wait(240)!=0:raise RuntimeError('Producer failed: '+name)
        for proc in processes:
            if proc.wait(300)!=0:raise RuntimeError('Consumer failed; inspect log: '+name)
        for f in opened:f.close()
        windows=[];assignments=[];summaries=[]
        for log in logs:
            for line in log.read_text().splitlines():
                try:r=json.loads(line)
                except ValueError:continue
                if r.get('type')=='window':windows.append(r)
                if r.get('type')=='assignment':assignments.append(r['partitions'])
                if r.get('type')=='summary':summaries.append(r)
        if not summaries:raise RuntimeError('No consumer summary')
        summary=summaries[-1]
        # Both workers see the final durable shared counters, so do not add them.
        summary.update({'assignments':assignments,'pause_seconds':paused,'broker':'real Redpanda v26.2.6',
                        'replay_payments_per_second':0,'replay_mode':'accelerated; event and received timestamps preserved'})
        results[name]=summary
        if windows:
            with (args.out/(name+'-windows.csv')).open('w') as f:
                writer=csv.DictWriter(f,fieldnames=windows[0].keys());writer.writeheader();writer.writerows(windows)
        (args.out/'experiments.json').write_text(json.dumps(results,indent=2)+'\n')
        print(name+': '+json.dumps(summary),flush=True)
    baseline=results['baseline']
    if results['restart']['events']!=baseline['events']:raise RuntimeError('Restart lost broker records')
    if results['two-consumers']['events']!=baseline['events']:raise RuntimeError('Group workers lost records')
    if results['lateness-zero'].get('late_rejected',0)<baseline.get('late_rejected',0):raise RuntimeError('Zero-lateness check failed')


if __name__=='__main__':main()
