# Lab 8 — written answers and evidence scope

## Execution scope

The owner explicitly prohibited cloud execution and any possible AWS charges.
Only Part 3 was executed on real local Redpanda. Local batch cross-checks use
DuckDB on **one real day (October 1)**, not the entire month. There is no fake
Athena screenshot, fabricated crawler schema, AWS timing, scan-cost ratio or
claim that the undeployed cloud pipeline ran. Part 2 AWS evidence and Part 4
AWS execution/screenshot remain outstanding under that constraint.

## Part 1 — the two roads

**If real time is ten minutes late:** driver locations are stale, matching and
surge decisions use old supply/demand, ETA and operational alerts lose value.
A backlogged stream can replay later, but cannot undo a bad live match.
**If batch is a day late:** business reports, historical metrics and model
training are delayed. The ride path can continue if online systems remain
healthy; the decision latency requirement differs.

**Why GPS does not go through Lambda:** Lambda can process GPS, but a Lambda
invocation and HTTP/API request per ping are unnecessary for a sustained,
high-frequency connection. MQTT/IoT Core maintains device connections and
feeds a buffered stream. Lambda is better suited here to bounded file checks
or event-triggered tasks. This is an architectural trade-off, not a claim
that Lambda technically cannot handle GPS.

**What a small startup could drop first:** postpone Flink/Redis/DynamoDB surge
processing, dedicated CDC, Quick dashboards and SageMaker; begin with an app,
Postgres, basic cached locations, object storage and scheduled SQL/reports.
It loses sophisticated real-time pricing/alerts, independent analytics
scalability, low-latency location lookup and trained ETA/demand predictions.
Keep components that the product's latency and reliability actually require.

## Part 2 — SQL and batch

The handwritten Athena schema uses BIGINT for amount/finalAmount, INT for ccy
and mcc, STRING for IDs, status, optional failureReason and ISO-8601 dates;
dt is an explicit STRING partition. Parse timestamps inside queries. The
actual Glue crawler types and handling of sparse failureReason are **not
observed**, because no crawler was run. A JSON sample or local inference cannot
be submitted as a Glue result. A crawler might merge sparse fields or choose
unexpected types; inspect its output before asserting what happened.

Handwritten schemas are useful for stable contracts, correct currency/decimal
semantics, predictable timestamp parsing and reproducible partition naming.
Crawlers reduce discovery effort but do not replace domain knowledge.

**Why DISTINCT precedes row_number():** remove exact webhook redeliveries before
ranking states. Adding row_number first makes otherwise duplicate rows differ
by rn, so a later DISTINCT over that result cannot remove them. Keep exactly
one latest state per invoice using modifiedDate, receivedAt and a documented
status tie-break. Strictly, rn=1 already collapses duplicates per invoice, so
exact duplicates need not change that particular final-state result; they do
inflate event counts/rates and streaming work when not removed. Raw statuses
also must not be counted as separate payments for turnover and peak hours.

Turnover includes successful latest states only and uses finalAmount/100.
Never sum different currencies into a single unlabelled amount. Failure-rate
queries expose the terminal denominator explicitly. Peak hour is based on
createdDate in Europe/Kyiv, not the hour a final webhook arrived. Event lateness
is receivedAt minus modifiedDate; count it on exact-deduplicated events, not on
one final row per invoice.

Real one-day results are in local-batch/*.csv. Full-month unique invoices,
late-over-one-hour share and duplicate counts must not be extrapolated from one
day. JSON/Parquet Athena Data scanned and runtime are not measured. For each
query record DataScannedInBytes and EngineExecutionTimeInMillis separately.
Cost reduction factor is JSON bytes scanned / Parquet bytes scanned for the
same query, using actual Athena executions, not file size or local CPU timing.

## Part 3 — interpretation

See experiments.json and the five *-windows.csv files for actual consumer
outputs. The runner performs a real 60-second stop and restart; SQLite
checkpoints/window state persist and Kafka retains unconsumed records.
Two workers in one group split the three partitions; their shared SQLite
transactional state prevents summing partial-partition rates as global alerts.
A deterministic per-invoice hash selects roughly 30% of terminal outcomes to
be failures; exact observed proportions depend on the finite input cohort.
This mutation is the requested failure experiment, not a generated dataset.

With a zero waiting allowance, the watermark closes more windows before their
late events arrive; late_rejected increases and accepted totals shrink. A
one-minute end boundary can still admit an out-of-order event in an open
minute: zero allowance does not mean every out-of-order record is rejected.

Kafka preserves order within a partition, not across partitions. Different
worker/restart scheduling can advance the minimum-partition watermark in a
different sequence and slightly change accepted/late/alert counts. Equal total
input counts and accepted+late+duplicates=input prove no broker records were
lost; equal window counts alone would not prove that. Consumer terminal rate
per minute differs from batch latest-payment rate, and low-volume windows can
exceed 10% from a single failed payment.

No TTL is used for the finite replay's seen set. Production needs bounded state
and eviction after the lateness/recovery horizon; too-short TTL causes duplicate
recounting. A local SQLite file is not a multi-host production state backend.
Delivery and external alerts still need idempotency/outbox handling.

## Part 4 — design comparison and cost

cloud-pipeline.svg and labs/lab8/cloud/ show the prepared pipeline using the same
payments source. Kinesis is the durable stream; Firehose batches newline JSON
into S3; Glue discovers schema; Athena queries stored objects. Lambda aggregates
terminal failures in **per-shard arrival-time** windows and SNS sends email to
a confirmed subscriber. This differs from the global modifiedDate event-time
windows in the local implementation; cross-shard event-time semantics require
Flink or a shared durable window store. Replay duplicates crossing cloud window
boundaries require more dedup state than the example's bounded window state.

Managed services remove broker patching, replication, capacity operations and
some checkpoint coordination, but introduce AWS charges, IAM/network setup,
service limits and service-specific semantics. Kafka/Redpanda itself is a log,
not a complete event-time processor. The supplied Python code supplies the
window/state logic; Flink would provide a managed framework for that logic.

Actual new AWS spend for this lab is $0 because no cloud resources or queries
were executed. This is not a price estimate or a claim the services are free.
No screenshot of streamed data in Athena exists. Before any future approved
run, review pricing, run briefly, export evidence and remove Kinesis/Firehose
(and other temporary lab resources) promptly; do not rely on a budget alert
as a hard spending cap.

## Final discussion

Event time describes when the business event happened; processing time describes
when a worker handled it. Watermarks trade completeness for alert latency.
Keep raw JSON as an auditable replayable source and Parquet for compressed,
column-pruned analytics with fewer scanned bytes. Nightly batch is enough for
historical reconciliation and reports; fraud/driver matching/operational failure
alerts need seconds. Managed infrastructure reduces operational work, while
charging for capacity, compute, ingestion, storage and scanning.
