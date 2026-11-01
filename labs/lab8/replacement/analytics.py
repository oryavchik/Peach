"""Actual local JSON/Parquet SQL, schema discovery and exported evidence.

This is DuckDB, not an Athena emulator. All measurements are local execution
measurements; there are no AWS DataScannedInBytes or billed scan figures.
"""
import argparse
import csv
from datetime import date, datetime
from decimal import Decimal
import html
import json
from pathlib import Path
import time
import duckdb

COLUMNS={
    'invoiceId':'VARCHAR','amount':'BIGINT','ccy':'INTEGER','reference':'VARCHAR',
    'createdDate':'VARCHAR','merchantId':'VARCHAR','merchantName':'VARCHAR','mcc':'INTEGER',
    'customerId':'VARCHAR','paymentMethod':'VARCHAR','device':'VARCHAR','status':'VARCHAR',
    'modifiedDate':'VARCHAR','finalAmount':'BIGINT','receivedAt':'VARCHAR','failureReason':'VARCHAR',
}
QUERIES={
 'turnover':"""SELECT merchantId,merchantName,ccy,count(*) successful_payments,
    sum(finalAmount)/100.0 turnover FROM {table} WHERE status='success'
    GROUP BY merchantId,merchantName,ccy ORDER BY merchantId,ccy""",
 'failure_rate':"""SELECT paymentMethod,device,count(*) payments,
    count(*) FILTER(WHERE status='failure') failures,
    100.0*count(*) FILTER(WHERE status='failure')/
      nullif(count(*) FILTER(WHERE status IN ('success','failure')),0) terminal_failure_percent,
    100.0*count(*) FILTER(WHERE status='failure')/count(*) all_payment_failure_percent
    FROM {table} GROUP BY paymentMethod,device ORDER BY paymentMethod,device""",
 'peak_hours':"""SELECT hour(createdDate::TIMESTAMPTZ) hour_kyiv,count(*) payments
    FROM {table} GROUP BY 1 ORDER BY 1""",
}
RANKED="""SELECT * EXCLUDE(rn) FROM (
  SELECT *,row_number() OVER(PARTITION BY invoiceId ORDER BY modifiedDate DESC,
    receivedAt DESC,CASE status WHEN 'success' THEN 3 WHEN 'failure' THEN 3
      WHEN 'processing' THEN 2 ELSE 1 END DESC,status DESC,reference DESC) rn
  FROM exact_events) WHERE rn=1"""


def literal(value):
    return "'"+str(value).replace("'","''")+"'"


def export_csv(path, columns, rows):
    with path.open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(columns);w.writerows(rows)


def json_default(value):
    if isinstance(value,(date,datetime)):return value.isoformat()
    if isinstance(value,Decimal):return str(value)
    raise TypeError(type(value).__name__)


def query_rows(c,sql):
    result=c.execute(sql)
    return [x[0] for x in result.description],result.fetchall()


def run(raw,curated,out,scope):
    if curated.exists() and any(curated.iterdir()):
        raise ValueError('Choose an empty curated directory; refusing to mix old Parquet data')
    curated.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    c=duckdb.connect();c.execute("SET TimeZone='Europe/Kyiv'")
    c.execute("SET memory_limit='512MB'");c.execute('SET threads=2')
    temp=curated.parent/'duckdb-temp';temp.mkdir(exist_ok=True)
    c.execute('SET temp_directory='+literal(temp))
    pattern=str(raw.resolve()/'**'/'events.jsonl*')
    paths=sorted(raw.glob('**/events.jsonl*'))
    if not paths:raise ValueError('No real input JSON files')
    # Scan all records for discovery, including sparse failureReason.
    inferred=query_rows(c,f"DESCRIBE SELECT * FROM read_json_auto({literal(pattern)},format='newline_delimited',sample_size=-1,union_by_name=true,hive_partitioning=true)")[1]
    expected=set(COLUMNS)|{'dt','partition','batch'}
    unexpected={r[0] for r in inferred}-expected
    if unexpected:raise ValueError('Unmapped source fields: '+str(unexpected))
    projection=','.join(COLUMNS)+',CAST(dt AS VARCHAR) AS dt'
    definition='{'+','.join(literal(k)+':'+literal(v) for k,v in COLUMNS.items())+'}'
    c.execute(f"CREATE VIEW raw AS SELECT {projection} FROM read_json({literal(pattern)},format='newline_delimited',columns={definition},hive_partitioning=true)")
    c.execute('CREATE VIEW exact_events AS SELECT DISTINCT * FROM raw')
    c.execute('CREATE VIEW payments_json AS '+RANKED)
    all_sql=['-- ACTUALLY EXECUTED LOCALLY IN DUCKDB. Not Athena.\n',
             f'CREATE VIEW raw AS SELECT {projection} FROM read_json({literal(pattern)},format=\'newline_delimited\',columns={definition},hive_partitioning=true);',
             'CREATE VIEW exact_events AS SELECT DISTINCT * FROM raw;',
             'CREATE VIEW payments_json AS '+RANKED+';']
    schema={r[0]:{'type':r[1],'nullable':r[2]} for r in inferred}
    export_csv(out/'schema-inferred.csv',['column','type','nullable'],[(k,v['type'],v['nullable']) for k,v in schema.items()])
    export_csv(out/'schema-handwritten.csv',['column','type'],list(COLUMNS.items())+[('dt','VARCHAR (Hive partition)')])
    stats_sql="""SELECT (SELECT count(*) FROM raw) raw_rows,
      (SELECT count(*) FROM exact_events) exact_events,
      (SELECT count(*) FROM raw)-(SELECT count(*) FROM exact_events) exact_duplicate_rows,
      (SELECT count(*) FROM payments_json) unique_invoices"""
    cols,rows=query_rows(c,stats_sql);stats=dict(zip(cols,rows[0]));export_csv(out/'scale.csv',cols,rows);all_sql.append(stats_sql+';')
    late_sql="""SELECT count(*) total_exact_events,
      count(*) FILTER(WHERE epoch(receivedAt::TIMESTAMPTZ)-epoch(modifiedDate::TIMESTAMPTZ)>60) over_60_seconds,
      count(*) FILTER(WHERE epoch(receivedAt::TIMESTAMPTZ)-epoch(modifiedDate::TIMESTAMPTZ)>3600) over_one_hour,
      100.0*count(*) FILTER(WHERE epoch(receivedAt::TIMESTAMPTZ)-epoch(modifiedDate::TIMESTAMPTZ)>3600)/count(*) percent_over_one_hour,
      count(*) FILTER(WHERE failureReason IS NOT NULL) with_failure_reason,
      count(DISTINCT dt) partitions,min(dt) first_partition,max(dt) last_partition
      FROM exact_events"""
    cols,rows=query_rows(c,late_sql);lateness=dict(zip(cols,rows[0]));export_csv(out/'late-events.csv',cols,rows);all_sql.append(late_sql+';')
    # The row-number filter chooses one logical final state BEFORE CTAS.
    ctas=f"COPY (SELECT * FROM payments_json) TO {literal(curated.resolve())} (FORMAT PARQUET,COMPRESSION SNAPPY,PARTITION_BY(dt))"
    start=time.perf_counter();c.execute(ctas);ctas_seconds=time.perf_counter()-start;all_sql.append(ctas+';')
    c.execute(f"CREATE VIEW payments_parquet AS SELECT * FROM read_parquet({literal(str(curated.resolve()/'**'/'*.parquet'))},hive_partitioning=true)")
    parity=query_rows(c,'SELECT count(*) FROM ((SELECT * FROM payments_json EXCEPT SELECT * FROM payments_parquet) UNION ALL (SELECT * FROM payments_parquet EXCEPT SELECT * FROM payments_json))')[1][0][0]
    if parity:raise AssertionError('JSON and Parquet final states differ')
    json_storage = 'JSON_GZIP' if all(p.suffix == '.gz' for p in paths) else 'JSON_LINES' if all(p.suffix != '.gz' for p in paths) else 'JSON_MIXED'
    metrics=[];results={}
    for name,template in QUERIES.items():
        reference=None
        for storage,table in [(json_storage,'payments_json'),('PARQUET_SNAPPY','payments_parquet')]:
            sql=template.format(table=table);profile=out/(name+'-'+storage.lower()+'-profile.json')
            c.execute("SET profiling_output="+literal(profile.resolve()))
            c.execute("PRAGMA enable_profiling='json'")
            start=time.perf_counter();cols,rows=query_rows(c,sql);seconds=time.perf_counter()-start
            c.execute('PRAGMA disable_profiling')
            if reference is None:reference=rows
            elif rows!=reference:raise AssertionError(name+': query results differ')
            export_csv(out/(name+'-'+storage.lower()+'.csv'),cols,rows)
            results[name]=[dict(zip(cols,row)) for row in rows]
            measured=json.loads(profile.read_text())
            # Profiles contain only paths, operator metrics and these public-data SQL queries.
            metrics.append({'query':name,'storage':storage,'wall_seconds':round(seconds,6),
                'duckdb_total_bytes_read':measured.get('total_bytes_read'),
                'duckdb_cumulative_rows_scanned':measured.get('cumulative_rows_scanned'),
                'result_rows':len(rows),'matches_other_format':True})
            all_sql.append(sql+';')
    physical_json=sum(p.stat().st_size for p in paths)
    physical_parquet=sum(p.stat().st_size for p in curated.rglob('*.parquet'))
    export_csv(out/'local-performance.csv',list(metrics[0]),[list(r.values()) for r in metrics])
    manifest={'engine':'DuckDB '+duckdb.__version__,'scope':scope,'aws_executed':False,
      'scale':stats,'lateness':lateness,'inferred_schema':schema,'metrics':metrics,
      'ctas_seconds':round(ctas_seconds,6),'parquet_value_parity':parity==0,
      'json_storage':json_storage,'json_file_bytes':physical_json,'parquet_snappy_file_bytes':physical_parquet,
      'notes':['Local wall times and DuckDB profiler reads; not Athena timings or billing.',
               'One measured run per query; filesystem cache is not reset.',
               'Physical file-size ratio is not a cloud scan-cost ratio.',
               'JSON queries include exact deduplication and latest-state ranking; Parquet already contains final states.'],
      'results':results}
    (out/'analytics.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False,default=json_default)+'\n')
    (out/'executed.sql').write_text('\n\n'.join(all_sql)+'\n')
    table=lambda rows:'<table><thead><tr>'+''.join('<th>'+html.escape(str(k))+'</th>' for k in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row.values())+'</tr>' for row in rows)+'</tbody></table>'
    body=f'<h1>Real local DuckDB results</h1><p>{html.escape(scope)}</p><p>AWS replacement — no Athena or Glue execution.</p>'
    body+='<h2>Scale</h2>'+table([stats])+'<h2>Lateness</h2>'+table([lateness])+'<h2>Local JSON / Parquet measurements</h2>'+table(metrics)
    for name,data in results.items():body+='<h2>'+html.escape(name)+'</h2>'+table(data)
    body+='<h2>Executed local SQL</h2><pre>'+html.escape('\n\n'.join(all_sql))+'</pre>'
    page='<!doctype html><html lang="en"><meta charset="utf-8"><title>Local payments SQL evidence</title><style>body{font:15px system-ui;margin:32px;color:#203047}table{border-collapse:collapse;margin:20px 0}th,td{border:1px solid #bbb;padding:7px;text-align:left}th{background:#eef2f8}pre{white-space:pre-wrap;background:#f4f5f7;padding:20px}h2{margin-top:36px}</style>'+body+'</html>'
    (out/'report.html').write_text(page)
    c.close()
    print(json.dumps({'scope':scope,'scale':stats,'lateness':lateness,'parquet_parity':parity==0},default=json_default),flush=True)
    return manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True)
    p.add_argument('--curated',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--scope',required=True);a=p.parse_args();run(a.raw,a.curated,a.out,a.scope)


if __name__=='__main__':main()
