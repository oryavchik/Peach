# Real local Redpanda results

Source: public dataset, October 1, 2026. Each experiment used all 101,084 webhook records.
Accelerated replay (original timestamps preserved); separate default-rate check: 41 payments in 2.054 s.
Three partitions. No AWS query or cloud pipeline was executed.

| Experiment | Input events | Exact duplicates | Accepted | Too late | Closed windows | Alerts |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 101084 | 1001 | 99495 | 588 | 4593 | 905 |
| restart | 101084 | 1001 | 99497 | 586 | 4592 | 906 |
| two-consumers | 101084 | 1001 | 99563 | 520 | 4593 | 904 |
| failure-30 | 101084 | 1001 | 99487 | 596 | 4593 | 3289 |
| lateness-zero | 101084 | 1001 | 99297 | 786 | 4593 | 905 |

The restart test actually stopped for 60.005 seconds. All input events were recovered.
Two-consumer assignments observed: [[0, 1, 2], [0, 1], [2]].
The final two assignments split partitions [0,1] and [2]; the initial full assignment occurred before rebalance.

The two-minute baseline and restart have slightly different late/window counts because
cross-partition interleaving and the watermark advancement sequence are not globally ordered.
The invariant accepted + too-late + exact duplicates = input holds for every experiment.
This proves input accounting, not exactly-once delivery of console alerts.

A 30% terminal failure cohort raised many more alerts. Zero waiting rejects more events
and shrinks window aggregates. Small windows can exceed 10% even at the baseline rate.

Full window output is in the five *-windows.csv files. Local batch outputs are in
local-batch/*.csv. They are DuckDB on one day, not Athena on the full month.

Outstanding under the no-paid-cloud constraint: Athena executions/results/scan metrics,
Glue crawler observations, and an Athena screenshot of data delivered through Kinesis/Firehose.

Baseline versus zero-wait comparison: 635 method/minute window rows differ.
