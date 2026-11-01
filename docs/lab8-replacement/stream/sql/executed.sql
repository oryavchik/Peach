-- ACTUALLY EXECUTED LOCALLY IN DUCKDB. Not Athena.


CREATE VIEW raw AS SELECT invoiceId,amount,ccy,reference,createdDate,merchantId,merchantName,mcc,customerId,paymentMethod,device,status,modifiedDate,finalAmount,receivedAt,failureReason,CAST(dt AS VARCHAR) AS dt FROM read_json('/Users/oryavchik/Desktop/Peach-my/.local/lab8-free/stream/raw/**/events.jsonl*',format='newline_delimited',columns={'invoiceId':'VARCHAR','amount':'BIGINT','ccy':'INTEGER','reference':'VARCHAR','createdDate':'VARCHAR','merchantId':'VARCHAR','merchantName':'VARCHAR','mcc':'INTEGER','customerId':'VARCHAR','paymentMethod':'VARCHAR','device':'VARCHAR','status':'VARCHAR','modifiedDate':'VARCHAR','finalAmount':'BIGINT','receivedAt':'VARCHAR','failureReason':'VARCHAR'},hive_partitioning=true);

CREATE VIEW exact_events AS SELECT DISTINCT * FROM raw;

CREATE VIEW payments_json AS SELECT * EXCLUDE(rn) FROM (
  SELECT *,row_number() OVER(PARTITION BY invoiceId ORDER BY modifiedDate DESC,
    receivedAt DESC,CASE status WHEN 'success' THEN 3 WHEN 'failure' THEN 3
      WHEN 'processing' THEN 2 ELSE 1 END DESC,status DESC,reference DESC) rn
  FROM exact_events) WHERE rn=1;

SELECT (SELECT count(*) FROM raw) raw_rows,
      (SELECT count(*) FROM exact_events) exact_events,
      (SELECT count(*) FROM raw)-(SELECT count(*) FROM exact_events) exact_duplicate_rows,
      (SELECT count(*) FROM payments_json) unique_invoices;

SELECT count(*) total_exact_events,
      count(*) FILTER(WHERE epoch(receivedAt::TIMESTAMPTZ)-epoch(modifiedDate::TIMESTAMPTZ)>60) over_60_seconds,
      count(*) FILTER(WHERE epoch(receivedAt::TIMESTAMPTZ)-epoch(modifiedDate::TIMESTAMPTZ)>3600) over_one_hour,
      100.0*count(*) FILTER(WHERE epoch(receivedAt::TIMESTAMPTZ)-epoch(modifiedDate::TIMESTAMPTZ)>3600)/count(*) percent_over_one_hour,
      count(*) FILTER(WHERE failureReason IS NOT NULL) with_failure_reason,
      count(DISTINCT dt) partitions,min(dt) first_partition,max(dt) last_partition
      FROM exact_events;

COPY (SELECT * FROM payments_json) TO '/Users/oryavchik/Desktop/Peach-my/.local/lab8-free/stream/curated' (FORMAT PARQUET,COMPRESSION SNAPPY,PARTITION_BY(dt));

SELECT merchantId,merchantName,ccy,count(*) successful_payments,
    sum(finalAmount)/100.0 turnover FROM payments_json WHERE status='success'
    GROUP BY merchantId,merchantName,ccy ORDER BY merchantId,ccy;

SELECT merchantId,merchantName,ccy,count(*) successful_payments,
    sum(finalAmount)/100.0 turnover FROM payments_parquet WHERE status='success'
    GROUP BY merchantId,merchantName,ccy ORDER BY merchantId,ccy;

SELECT paymentMethod,device,count(*) payments,
    count(*) FILTER(WHERE status='failure') failures,
    100.0*count(*) FILTER(WHERE status='failure')/
      nullif(count(*) FILTER(WHERE status IN ('success','failure')),0) terminal_failure_percent,
    100.0*count(*) FILTER(WHERE status='failure')/count(*) all_payment_failure_percent
    FROM payments_json GROUP BY paymentMethod,device ORDER BY paymentMethod,device;

SELECT paymentMethod,device,count(*) payments,
    count(*) FILTER(WHERE status='failure') failures,
    100.0*count(*) FILTER(WHERE status='failure')/
      nullif(count(*) FILTER(WHERE status IN ('success','failure')),0) terminal_failure_percent,
    100.0*count(*) FILTER(WHERE status='failure')/count(*) all_payment_failure_percent
    FROM payments_parquet GROUP BY paymentMethod,device ORDER BY paymentMethod,device;

SELECT hour(createdDate::TIMESTAMPTZ) hour_kyiv,count(*) payments
    FROM payments_json GROUP BY 1 ORDER BY 1;

SELECT hour(createdDate::TIMESTAMPTZ) hour_kyiv,count(*) payments
    FROM payments_parquet GROUP BY 1 ORDER BY 1;
