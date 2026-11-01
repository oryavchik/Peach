# Short written answers — free local replacement

This report describes actual local Redpanda/DuckDB execution. AWS Athena/Glue/
Firehose/Kinesis were not executed. The instructor must accept this substitution
for the original AWS-specific evidence requirements.

## Architecture questions

A ten-minute delay in the real-time road makes locations, matching, surge and
operational alerts stale. A one-day batch delay postpones reporting and model
training, while the online ride path can continue independently. Recovery can
replay data, but cannot undo a bad live business decision.

GPS can technically go through Lambda, but one HTTP/API/Lambda invocation per
frequent ping adds overhead. Persistent MQTT/IoT ingestion is a better fit for
continuous device traffic. A small startup could defer sophisticated Flink surge
processing, dedicated CDC, ML endpoints and BI dashboards, losing advanced live
pricing/alerts and independently scalable analytics while retaining basic rides.

## Batch findings: the entire real October dataset

- Raw webhook rows: **3,030,197**.
- Exact-deduplicated webhook events: **3,000,000**.
- Exact duplicate rows: **30,197**.
- Unique invoiceId: **1,000,000**.
- Events more than 60 seconds late: **60,231 / 3,000,000**.
- Events more than one hour late: **0 / 3,000,000 = 0%**.
- Observed partitions: **31**, October 1–31, 2026.

Our replacement schema discovery inferred **amount BIGINT, ccy BIGINT,
createdDate/modifiedDate/receivedAt TIMESTAMP, dt DATE**, and nullable
**failureReason VARCHAR**. failureReason was present on **60,180** exact events;
its absence on other rows became NULL. These are actual DuckDB observations,
not a claim about what Glue chose. The explicit schema uses ccy INTEGER and
VARCHAR dates with explicit timezone-aware parsing. Handwritten contracts keep
types stable and reflect domain constraints; automatic discovery is convenient
but does not know those constraints.

DISTINCT removes exact redeliveries before row_number ranks invoice states.
Adding row_number first makes otherwise identical rows differ by rn, so a later
DISTINCT over that output is ineffective. Precisely, rn=1 alone already keeps
one row per invoice, so exact duplicates need not change that particular final
state; they do inflate raw event aggregates and streaming work. Intermediate
created/processing states must not count as separate settled payments.

The latest state uses modifiedDate, receivedAt and deterministic status/reference
tie-breaks. Turnover sums finalAmount/100 for successful latest states, grouped
by merchant AND currency. Failure rate has an explicit terminal denominator.
Peak hour uses creation time in Europe/Kyiv. Lateness is counted on exact events,
not one final state per invoice. All query results are exported as CSV.

Snappy Parquet contains one latest row per invoice and is partitioned by dt.
A bidirectional EXCEPT found zero row differences. Turnover, failure rate and
peak-hour results also matched exactly between JSON and Parquet. Measured local
wall times are in monthly-batch/local-performance.csv and the report HTML.
They are not Athena Data scanned/runtime. The local cost is $0 in new cloud
charges for BOTH formats, so there is no meaningful billed-cost ratio. Physical
file sizes and DuckDB diagnostic I/O counters must not be relabelled as Athena
scan costs. JSON queries also include dedup/ranking work already done for Parquet.

## Streaming findings and substitution

Part 3's five actual experiments remain documented in docs/lab8-evidence/: a
real 60-second stop/restart with all records recovered, a two-consumer group
split of the three partitions, a deterministic roughly 30% failure cohort that
raised more alerts, and zero late allowance that rejected more events.

The new pipeline independently ran **101,084 events** through real Redpanda and
**39 atomic file batches**. Every original record, including exact duplicate
multiplicity, matched the sink. SQL over those actual delivered files found
**33,361 invoices** and matched its Parquet results. The sink does not drop raw
duplicates; dedup is an explicit downstream SQL/alert operation. The configured
buffer limit is 60 seconds OR 1 MiB; finite end markers flush the last records.
This accelerated run exercised size/end flushing, not 60-second residence for
all batches. File-sink checkpoint restoration and corruption/gap failure cases
are verified. A separate Kafka group sees the same full stream for alerts.

The alert consumer uses modifiedDate event-time one-minute windows. Watermark
is the minimum partition maximum event time minus two minutes; closed-window
records are rejected as late. An idle partition conservatively holds progress.
Changing workers/restarts changes cross-partition interleaving, so accepted/late
counts can differ slightly even though no broker records are lost. The invariant
accepted + late + exact duplicates = input is checked. Alert rate is terminal
failures/(success+failure); created/processing do not dilute that rate. The output
also exposes failures/all-events to make the denominator choice explicit.

For this finite run the seen set is unbounded. Production needs TTL-based
Flink/Redis state covering lateness and replay/recovery; early eviction counts
redeliveries again. Local SQLite is single-host state, and a durable outbox is
needed for crash-safe external alerts. Kafka ordering is per partition, not a
global ordering across all events.

## Why keep raw and curated data? When is batch enough?

Raw JSON is the auditable replay source and preserves original duplicates and
schema evolution. Parquet stores compact column-oriented final states for
analytics. Nightly batch is enough for historical reporting/reconciliation;
matching, fraud decisions and operational failure alerts need seconds.

Managed Kinesis/Flink/Glue remove some replication, patching, scaling and
checkpoint operations, but add charges, IAM setup, limits and service-specific
semantics. Our free replacement shifts those operations to local Docker/Python.
It is an executable teaching pipeline, not a managed production deployment.
No AWS screenshot is fabricated; the supplied HTML/CSV evidence is explicitly
local DuckDB. All newly created temporary data, containers and pulled broker
images are cleaned after exporting the evidence.

A separate real timer check verified the 60-second buffer: 10 source records
were persisted after 60.265 seconds since sink startup, with no end marker
until after persistence and well below the size threshold.
