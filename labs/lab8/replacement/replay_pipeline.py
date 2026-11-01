"""Run the real local replacement pipeline and verify file-sink completeness."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from confluent_kafka.admin import AdminClient,NewTopic
from events import fingerprint,load_events
from replacement.file_sink import FileSink


def main():
    p=argparse.ArgumentParser();p.add_argument('--file',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.work.mkdir(parents=True,exist_ok=True);a.out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1];topic='payments-replacement'
    admin=AdminClient({'bootstrap.servers':'localhost:19092','broker.address.family':'v4'})
    for f in admin.create_topics([NewTopic(topic,3,1)]).values():f.result()
    raw=a.work/'raw';logs=[];processes=[]
    commands={
        'sink':[sys.executable,str(root/'replacement/file_sink.py'),'--root',str(raw),'--topic',topic],
        'alerts':[sys.executable,str(root/'consumer.py'),'--topic',topic,'--group','lab8-replacement-alerts',
                  '--state',str(a.work/'alerts.db')],
    }
    for name,command in commands.items():
        f=(a.work/(name+'.jsonl')).open('w');logs.append(f)
        processes.append(subprocess.Popen(command,stdout=f,stderr=f))
    time.sleep(4)
    with (a.out/'producer.json').open('w') as log:
        subprocess.run([sys.executable,str(root/'producer.py'),str(a.file),'--topic',topic,
                        '--payments-per-second','0'],stdout=log,check=True)
    for proc in processes:
        if proc.wait(300)!=0:raise RuntimeError('Pipeline consumer failed; inspect private process logs')
    for log in logs:log.close()
    original=Counter(fingerprint(e) for e in load_events(a.file))
    delivered=Counter()
    for path in raw.glob('partition=*/batch=*/dt=*/events.jsonl'):
        with path.open() as f:
            for line in f:delivered[fingerprint(json.loads(line))]+=1
    if original!=delivered:raise AssertionError('Source and sink record multisets differ')
    # Simulate restart after file persistence; reads existing files, changes nothing.
    restored=FileSink(raw,topic)
    if restored.rows()!=sum(original.values()) or len(restored.ended)!=3:raise AssertionError('Sink restart verification failed')
    sink_results=[];window_rows=[];alert_summary=None
    for line in (a.work/'sink.jsonl').read_text().splitlines():
        try:r=json.loads(line)
        except ValueError:continue
        if r.get('type')=='file_sink_result':sink_results.append(r)
    for line in (a.work/'alerts.jsonl').read_text().splitlines():
        try:r=json.loads(line)
        except ValueError:continue
        if r.get('type')=='window':window_rows.append(r)
        if r.get('type')=='summary':alert_summary=r
    import csv
    with (a.out/'alert-windows.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=window_rows[0],lineterminator='\n');w.writeheader();w.writerows(window_rows)
    report={'execution':'real local Redpanda -> buffered JSONL file sink; separate event-time alert consumer',
      'aws_executed':False,'topic':topic,'source_rows':sum(original.values()),'sink_rows':sum(delivered.values()),
      'unique_exact_records':len(original),'source_sink_multiset_equal':True,'sink_checkpoint_restart_verified':True,
      'sink':sink_results[-1],'alert_summary':alert_summary,'replay':'accelerated, original timestamps preserved'}
    (a.out/'pipeline.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    subprocess.run([sys.executable,str(root/'replacement/analytics.py'),'--raw',str(raw),
      '--curated',str(a.work/'curated'),'--out',str(a.out/'sql'),
      '--scope','October 1 data actually delivered through Redpanda and the buffered file sink; local replacement for cloud pipeline'],check=True)


if __name__=='__main__':main()
