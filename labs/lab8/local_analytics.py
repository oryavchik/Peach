"""Free DuckDB cross-check on ONE real day; not an Athena/Glue result."""
import argparse
import csv
import json
from pathlib import Path
import duckdb


def main():
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    c=duckdb.connect();c.execute("SET TimeZone='Europe/Kyiv'");c.execute("SET memory_limit='512MB'")
    c.execute('CREATE TABLE raw AS SELECT * FROM read_json_auto(?,format=\'newline_delimited\',sample_size=-1)',[str(args.file)])
    c.execute('CREATE VIEW exact_events AS SELECT DISTINCT * FROM raw')
    c.execute('''CREATE TABLE payments AS SELECT * EXCLUDE(rn) FROM (
      SELECT *,row_number() OVER(PARTITION BY invoiceId ORDER BY modifiedDate DESC,receivedAt DESC,
        CASE status WHEN 'success' THEN 3 WHEN 'failure' THEN 3 WHEN 'processing' THEN 2 ELSE 1 END DESC,status DESC,reference DESC) rn
      FROM exact_events) WHERE rn=1''')
    queries={
      'scale':'''SELECT (SELECT count(*) FROM raw) raw_rows,(SELECT count(*) FROM exact_events) exact_events,
        (SELECT count(*) FROM raw)-(SELECT count(*) FROM exact_events) duplicate_rows,(SELECT count(*) FROM payments) unique_invoices''',
      'turnover':'''SELECT merchantId,merchantName,ccy,count(*) successful_payments,sum(finalAmount)/100.0 turnover
        FROM payments WHERE status='success' GROUP BY ALL ORDER BY merchantId,ccy''',
      'failure_rate':'''SELECT paymentMethod,device,count(*) payments,count(*) FILTER(WHERE status='failure') failures,
        100.0*count(*) FILTER(WHERE status='failure')/nullif(count(*) FILTER(WHERE status IN ('success','failure')),0) failure_percent
        FROM payments GROUP BY ALL ORDER BY failure_percent DESC''',
      'peak_hours':'''SELECT hour(createdDate::TIMESTAMPTZ) hour_kyiv,count(*) payments FROM payments GROUP BY 1 ORDER BY 1''',
      'late_events':'''SELECT count(*) total_events,
        count(*) FILTER(WHERE epoch(receivedAt::TIMESTAMPTZ)-epoch(modifiedDate::TIMESTAMPTZ)>60) over_60_seconds,
        count(*) FILTER(WHERE epoch(receivedAt::TIMESTAMPTZ)-epoch(modifiedDate::TIMESTAMPTZ)>3600) over_one_hour FROM exact_events'''
    }
    results={'engine':'DuckDB','scope':'one real day, dt=2026-10-01; not full-month Athena evidence',
             'source':'s3://ucu-ooad-lab8-payments/payments/dt=2026-10-01/events.jsonl','queries':{}}
    for name,sql in queries.items():
        cursor=c.execute(sql);cols=[x[0] for x in cursor.description];rows=cursor.fetchall()
        with (args.out/(name+'.csv')).open('w') as f:
            writer=csv.writer(f);writer.writerow(cols);writer.writerows(rows)
        results['queries'][name]=[dict(zip(cols,row)) for row in rows]
    (args.out/'local-analytics.json').write_text(json.dumps(results,indent=2,ensure_ascii=False,default=str)+'\n')
    print(json.dumps({k:results['queries'][k] for k in ['scale','late_events']}))


if __name__=='__main__':main()
