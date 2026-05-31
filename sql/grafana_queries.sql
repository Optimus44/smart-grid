-- Grafana-friendly Postgres queries for dashboard panels
-- 1) Last-hour live meter readings (time series)
-- Replace $meter_id with Grafana template variable or a literal
SELECT
  timestamp AS time,
  power AS value,
  meter_id
FROM energy_readings
WHERE timestamp >= NOW() - INTERVAL '1 hour'
  AND ($meter_id IS NULL OR meter_id = $meter_id)
ORDER BY timestamp;

-- 2) Today vs Yesterday total energy (single stat / time series)
SELECT
  day::date AS time,
  total_energy
FROM (
  SELECT DATE_TRUNC('day', timestamp) AS day, SUM(energy) AS total_energy
  FROM energy_readings
  WHERE timestamp >= NOW() - INTERVAL '2 days'
  GROUP BY day
  ORDER BY day
) t;

-- 3) Weekly trend (time_bucket 1 day for last 28 days)
SELECT
  time_bucket('1 day', timestamp) AS time,
  AVG(power) AS avg_power
FROM energy_readings
WHERE timestamp >= NOW() - INTERVAL '28 days'
GROUP BY time
ORDER BY time;

-- 4) Monthly usage by region (derive region from first digit of meter_id)
SELECT
  region,
  DATE_TRUNC('month', timestamp) AS month,
  SUM(energy) AS total_energy
FROM (
  SELECT SUBSTRING(meter_id FROM 1 FOR 1) AS region, timestamp, energy
  FROM energy_readings
) t
WHERE timestamp >= NOW() - INTERVAL '12 months'
GROUP BY region, month
ORDER BY month, region;

-- 5) Performance panel: raw vs continuous-aggregate timings (use bench outputs CSVs)
-- Example: query bench/continuous_aggregates/results.csv loaded into Grafana as a CSV datasource
-- Alternatively, compute median/avg execution_ms from the CSV via Grafana transform.

-- 6) Storage and chunk stats
SELECT
  h.hypertable_name,
  pg_size_pretty(hypertable_size(format('%I', h.hypertable_name)::regclass)) AS size,
  c.chunk_count
FROM (
  SELECT hypertable_name FROM timescaledb_information.hypertables
) h
LEFT JOIN (
  SELECT hypertable_name, COUNT(*) AS chunk_count
  FROM timescaledb_information.chunks
  GROUP BY hypertable_name
) c USING (hypertable_name);

-- 7) Compression ratio (computed from stored sizes)
SELECT
  hypertable_name,
  (pg_total_relation_size(format('%I', hypertable_name)::regclass)) AS bytes_total,
  (pg_relation_size(format('%I', hypertable_name)::regclass)) AS bytes_table
FROM timescaledb_information.hypertables;
