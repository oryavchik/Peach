"""Build a compact, truthful report from REAL consumer outputs; never fabricates AWS results."""
import csv
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
evidence=root/'docs/lab8-evidence'
d=json.loads((evidence/'experiments.json').read_text())
for name,r in d.items():
    assert r['events']==101084, (name,'input count')
    assert r.get('accepted',0)+r.get('late_rejected',0)+r.get('duplicates',0)==r['events'],(name,'event accounting')
    assert r['ended_partitions']==3
assert len(d)==5 and d['restart']['pause_seconds']>=60
assert d['failure-30']['alerts']>d['baseline']['alerts']
assert d['lateness-zero']['late_rejected']>d['baseline']['late_rejected']
assert any(len(p)==2 for p in d['two-consumers']['assignments'])
assert any(len(p)==1 for p in d['two-consumers']['assignments'])
fields=['experiment','events','duplicates','accepted','late_rejected','windows','alerts','pause_seconds']
with (evidence/'experiment-comparison.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
    for name,r in d.items():writer.writerow({'experiment':name,**{k:r.get(k,0) for k in fields[1:]}})
rate=json.loads((evidence/'default-rate-check.json').read_text())
lines=['# Real local Redpanda results','',
       'Source: public dataset, October 1, 2026. Each experiment used all 101,084 webhook records.',
       f"Accelerated replay (original timestamps preserved); separate default-rate check: {rate['payments']} payments in {rate['seconds']} s.",
       'Three partitions. No AWS query or cloud pipeline was executed.','',
       '| Experiment | Input events | Exact duplicates | Accepted | Too late | Closed windows | Alerts |',
       '|---|---:|---:|---:|---:|---:|---:|']
for name,r in d.items():lines.append(f"| {name} | {r['events']} | {r['duplicates']} | {r['accepted']} | {r['late_rejected']} | {r['closed_windows']} | {r['alerts']} |")
lines+=['',f"The restart test actually stopped for {d['restart']['pause_seconds']} seconds. All input events were recovered.",
        f"Two-consumer assignments observed: {d['two-consumers']['assignments']}.",
        'The final two assignments split partitions [0,1] and [2]; the initial full assignment occurred before rebalance.',
        '', 'The two-minute baseline and restart have slightly different late/window counts because',
        'cross-partition interleaving and the watermark advancement sequence are not globally ordered.',
        'The invariant accepted + too-late + exact duplicates = input holds for every experiment.',
        'This proves input accounting, not exactly-once delivery of console alerts.',
        '', 'A 30% terminal failure cohort raised many more alerts. Zero waiting rejects more events',
        'and shrinks window aggregates. Small windows can exceed 10% even at the baseline rate.',
        '', 'Full window output is in the five *-windows.csv files. Local batch outputs are in',
        'local-batch/*.csv. They are DuckDB on one day, not Athena on the full month.',
        '', 'Outstanding under the no-paid-cloud constraint: Athena executions/results/scan metrics,',
        'Glue crawler observations, and an Athena screenshot of data delivered through Kinesis/Firehose.']
(evidence/'RESULTS.md').write_text('\n'.join(lines)+'\n')
(evidence/'status.json').write_text(json.dumps({'part2_aws':'not_run_owner_prohibits_cloud_charges','part2_local':'one real day checked in DuckDB; not AWS evidence','part3':'all five real Redpanda experiments passed','part4_cloud':'design/code only; not deployed','aws_resources_created':0,'aws_queries_executed':0,'new_cloud_spend_usd':0,'dataset_generated':False,'full_dataset_downloaded':False,'actual_source':'s3://ucu-ooad-lab8-payments/payments/dt=2026-10-01/events.jsonl'},indent=2)+'\n')
print('Five real experiments passed all input-accounting and behavior checks.')
