"""Explicit illustrative core costs, not a provider-calculator export or invoice."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/lab9-evidence'

def calculate(hours,days):
    requests=hours*3600  # 1 request/s during active windows
    cloud_run=max(0,requests-2_000_000)*.40/1_000_000+max(0,requests*.1-180_000)*.000024+max(0,requests*.1*.5-360_000)*.0000025
    daily_reads=2*requests/days if days else 0
    daily_writes=.05*requests/days if days else 0
    firestore=max(0,daily_reads-50_000)*days*.03/100_000+max(0,daily_writes-20_000)*days*.09/100_000
    aws_lambda=max(0,requests-1_000_000)*.20/1_000_000+max(0,requests*.1*.5-400_000)*.0000166667
    aurora=hours*.5*.12+.10
    return {'active_hours':hours,'active_days':days,'requests':int(requests),'AWS_Lambda_USD':round(aws_lambda,4),'AWS_Aurora_USD':round(aurora,4),'AWS_core_lower_bound_USD':round(aws_lambda+aurora,4),'GCP_Cloud_Run_USD':round(cloud_run,4),'GCP_Firestore_USD':round(firestore,4),'GCP_Firestore_core_lower_bound_USD':round(cloud_run+firestore,4),'GCP_Cloud_SQL_always_on_core_USD':round(cloud_run+730*.0105+10*.17,4),'GCP_Cloud_SQL_active_hours_core_USD':round(cloud_run+hours*.0105+10*.17,4)}


def main():
    profiles=[('nobody',0,0),('class demos',20,10),('office hours',176,22),('busy 24h',730,730/24)]
    rows=[{'profile':name,**calculate(hours,days)} for name,hours,days in profiles]
    with (OUT/'cost-profiles.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    assumptions={'status':'illustrative model, not provider calculator execution; not deployed costs','regions':{'AWS':'us-east-1','GCP':'us-central1'},'month_hours':730,'request_rate_during_active_hours':1,'request_cpu_seconds':.1,'request_memory_GiB':.5,'Firestore_reads_per_request':2,'writes_fraction':.05,'database_storage':'Aurora 1 GB; Firestore 0.1 GiB; Cloud SQL 10 GB SSD','Aurora_active_ACU':.5,'free_quotas_assumed':'unused by any other project/account workload','excluded':'network egress, measured Aurora I/O, backups, logging over free tier, cold starts, pause tails, storage growth, paid auth/AI/reporting; this is not a complete bill','price_basis':'Lab9 supplied reference rates, cross-checked with official pricing pages 2026-11-07; verify provider calculators before submitting as final Part3','sources':['https://aws.amazon.com/rds/aurora/pricing/','https://aws.amazon.com/lambda/pricing/','https://cloud.google.com/run/pricing','https://cloud.google.com/firestore/pricing','https://cloud.google.com/sql/pricing']}
    (OUT/'cost-assumptions.json').write_text(json.dumps(assumptions,indent=2)+'\n')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
