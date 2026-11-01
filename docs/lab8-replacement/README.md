# Lab 8 — completed free local replacement

All results below were produced by real local executions. This is a replacement for AWS, not a claim of Athena/Glue execution.
Acceptance of a local replacement for an AWS-specific rubric must be agreed with the instructor.

## Replacement mapping

| Requested AWS service | Executed local replacement |
|---|---|
| Kinesis Data Streams | Real Redpanda topic with 3 partitions |
| Firehose | Python file sink: 60 s / 1 MiB buffers, final replay flush |
| S3 | Local Hive-partitioned JSON / Parquet directories |
| Glue Crawler / Catalog | DuckDB full-data schema inference and explicit SQL views |
| Athena | Actual DuckDB SQL; exported CSV and readable HTML |
| Lambda + SNS | Separate Python event-time consumer; real threshold alerts in CSV/console |

## Full-month batch evidence

All 31 provided day files: **3,030,197 raw events**, **3,000,000 exact-deduplicated events**, **1,000,000 invoices**.
Exact duplicate rows: **30,197**. More than 60 seconds late: **60,231** of 3,000,000. More than one hour late: **0 (0%)**.

Actual schema inference selected BIGINT for amount and ccy, TIMESTAMP for ISO date fields, VARCHAR for failureReason, and DATE for the Hive dt partition.
failureReason is nullable and present on 60,180 exact events. Explicit SQL deliberately keeps ccy as INTEGER and dates as VARCHAR, parsing timestamps when needed.

The handwritten schema makes domain types and parsing stable; automatic inference is convenient for discovery. These are observed DuckDB findings, not invented Glue findings.

Latest-state Parquet is partitioned by dt and compressed with Snappy. A bidirectional EXCEPT comparison found zero differing rows. Each of turnover, failure rate and peak hours returned identical results from JSON and Parquet.

| Query | JSON GZIP wall seconds | Parquet wall seconds | Observed local speed-up |
|---|---:|---:|---:|
| turnover | 4.714031 | 0.046170 | 102.10x |
| failure_rate | 4.768898 | 0.019629 | 242.95x |
| peak_hours | 4.743944 | 0.093238 | 50.88x |

One measured run per query, filesystem cache not reset. JSON includes exact deduplication/latest-state ranking while Parquet already stores one final row per invoice. These are local timings, not a controlled hardware benchmark or Athena prices.
Physical files: gzip JSON 126,333,987 bytes; Snappy Parquet 78,964,873 bytes. The size ratio is NOT a billed scan-cost ratio.
DuckDB profiler bytes/rows are retained only as engine diagnostics; caching and operator accounting mean they must not be interpreted as source bytes scanned. Both formats cost $0 in new cloud charges because no AWS execution occurred.

## Actual stream-to-files-to-SQL evidence

Producer -> Redpanda -> file sink delivered **101,084 / 101,084 records** in 39 atomic batches. Full canonical record multisets matched, including duplicate multiplicity. All 3 end markers were excluded from payment files.
File-sink checkpoint recovery read the completed batch manifests/hashes and restored the correct next offsets. Unit tests also simulate unflushed state, partial directories, corrupted files and offset gaps.

The separate alert consumer used another Kafka group, so it received every record independently of the file sink. It used the same modifiedDate event-time windows and two-minute watermark policy as Part 3.
Actual alert output: 908 alerts, 591 late rejects and 1001 exact duplicates. SQL over the sink files found 33,361 invoices and exactly matched the one-day Parquet results.

The main replay was accelerated with original timestamps preserved. It exercised size/end flushing; 60 s is the configured time limit, not a claim every batch waited 60 seconds. The earlier default-rate test and five Part 3 experiments remain in docs/lab8-evidence/.

## What to open or submit

- `monthly-batch/report.html`: actual full-month local SQL results and executed queries.
- `monthly-batch/*.csv`: scale, lateness, turnover, failure rates, peak hours, schemas and performance.
- `stream/sql/report.html`: actual SQL over the records delivered through Redpanda and the file sink.
- `stream/pipeline.json` and `stream/alert-windows.csv`: actual stream checks and alerts.
- `local-pipeline.svg`: the executed replacement architecture.
- `ANSWERS.md`: short English written answers.

For a screenshot of the replacement, open `stream/sql/report.html` in a browser and capture the title and a query result. It explicitly says local DuckDB; it must not be labelled Athena.

## Scope and cleanup

No new AWS resources, paid queries, SNS messages or cloud inference were used. Read-only public dataset downloads do not create resources in this account. This completes the authorized local replacement, not the literal AWS-specific version of the rubric.
Temporary source files, Parquet, broker state, containers and lab-pulled images are removed after evidence export. The remaining evidence is small and contains no raw 1.2 GB dataset.

## Separately verified real timer trigger

A separate real probe sent 10 existing payment events, below the size threshold,
and withheld end markers. The sink persisted all 10 after **60.265 seconds
since startup**, with a 60-second configured interval. Only then were end markers
sent. See `timer-check.json`; this verifies the time trigger independently of
the main size-triggered replay.
