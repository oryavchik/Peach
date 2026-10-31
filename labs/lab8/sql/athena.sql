-- Render ${DATABASE} and ${BUCKET}. PREPARED ONLY; not executed on AWS.
CREATE DATABASE IF NOT EXISTS ${DATABASE};
CREATE EXTERNAL TABLE IF NOT EXISTS ${DATABASE}.payment_events (
  invoiceId string, amount bigint, ccy int, reference string,
  createdDate string, merchantId string, merchantName string, mcc int,
  customerId string, paymentMethod string, device string, status string,
  modifiedDate string, finalAmount bigint, receivedAt string, failureReason string
)
PARTITIONED BY (dt string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES ('case.insensitive'='true')
LOCATION 's3://${BUCKET}/payments/';
MSCK REPAIR TABLE ${DATABASE}.payment_events;

CREATE OR REPLACE VIEW ${DATABASE}.exact_events AS
SELECT DISTINCT * FROM ${DATABASE}.payment_events;
CREATE OR REPLACE VIEW ${DATABASE}.payments AS
SELECT invoiceId, amount, ccy, reference, createdDate, merchantId, merchantName,
       mcc, customerId, paymentMethod, device, status, modifiedDate, finalAmount,
       receivedAt, failureReason, dt
FROM (
  SELECT e.*, row_number() OVER (
    PARTITION BY invoiceId ORDER BY from_iso8601_timestamp(modifiedDate) DESC,
      from_iso8601_timestamp(receivedAt) DESC,
      CASE status WHEN 'success' THEN 3 WHEN 'failure' THEN 3 WHEN 'processing' THEN 2 ELSE 1 END DESC,
      status DESC, reference DESC
  ) AS rn
  FROM ${DATABASE}.exact_events e
) WHERE rn=1;

-- Scale: raw rows, exact duplicate rows, invoices and late events > one hour.
SELECT (SELECT count(*) FROM ${DATABASE}.payment_events) raw_rows,
       (SELECT count(*) FROM ${DATABASE}.exact_events) exact_events,
       (SELECT count(*) FROM ${DATABASE}.payment_events) -
       (SELECT count(*) FROM ${DATABASE}.exact_events) exact_duplicate_rows,
       (SELECT count(*) FROM ${DATABASE}.payments) unique_invoices;
SELECT count(*) total_events,
       count_if(date_diff('second',from_iso8601_timestamp(modifiedDate),from_iso8601_timestamp(receivedAt))>3600) over_one_hour,
       100.0*count_if(date_diff('second',from_iso8601_timestamp(modifiedDate),from_iso8601_timestamp(receivedAt))>3600)/count(*) percent_over_one_hour
FROM ${DATABASE}.exact_events;

-- Query 3: currency stays in the GROUP BY. finalAmount is settled minor units.
SELECT merchantId, merchantName, ccy, count(*) successful_payments,
       sum(finalAmount)/100.0 turnover
FROM ${DATABASE}.payments WHERE status='success'
GROUP BY merchantId,merchantName,ccy ORDER BY merchantId,ccy;
-- Query 4: terminal payment failure rate; also expose the all-payment denominator.
SELECT paymentMethod, device, count(*) payments,
       count_if(status='failure') failures,
       100.0*count_if(status='failure')/nullif(count_if(status IN ('success','failure')),0) terminal_failure_percent,
       100.0*count_if(status='failure')/count(*) all_payment_failure_percent
FROM ${DATABASE}.payments GROUP BY paymentMethod,device ORDER BY terminal_failure_percent DESC;
-- Query 5: one payment counted at its creation hour, explicit Europe/Kyiv timezone.
SELECT hour(from_iso8601_timestamp(createdDate) AT TIME ZONE 'Europe/Kyiv') hour_kyiv,
       count(*) payments FROM ${DATABASE}.payments GROUP BY 1 ORDER BY 1;
-- Query 6 uses exact-deduplicated events (not one row per invoice).
SELECT count(*) total_events,
       count_if(date_diff('second',from_iso8601_timestamp(modifiedDate),from_iso8601_timestamp(receivedAt))>60) late_events,
       100.0*count_if(date_diff('second',from_iso8601_timestamp(modifiedDate),from_iso8601_timestamp(receivedAt))>60)/count(*) late_percent
FROM ${DATABASE}.exact_events;

-- Empty this destination or choose a NEW prefix before retrying CTAS.
CREATE TABLE ${DATABASE}.payments_parquet
WITH (format='PARQUET',write_compression='SNAPPY',partitioned_by=ARRAY['dt'],
      external_location='s3://${BUCKET}/curated/') AS
SELECT invoiceId,amount,ccy,reference,createdDate,merchantId,merchantName,mcc,
       customerId,paymentMethod,device,status,modifiedDate,finalAmount,receivedAt,
       failureReason,dt FROM ${DATABASE}.payments;
-- Re-run queries 3,4,5 with payments_parquet replacing payments.
-- Save QueryExecution.Statistics.DataScannedInBytes and EngineExecutionTimeInMillis
-- for EACH query/source. Do not infer scan costs from local file sizes.
