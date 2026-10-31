-- Prepared query. Replace the crawler-generated table name AFTER inspecting it.
SELECT paymentMethod, status, count(*) webhook_events
FROM "YOUR_DATABASE"."YOUR_CRAWLER_TABLE"
GROUP BY paymentMethod,status
ORDER BY paymentMethod,status;
-- The screenshot must come from a REAL Athena execution over payments-stream/.
-- A local DuckDB query is not a substitute for this evidence.
