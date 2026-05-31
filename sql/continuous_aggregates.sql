-- Continuous aggregates for Step 6
-- Run this after `energy_readings` has been loaded as a hypertable.

DROP MATERIALIZED VIEW IF EXISTS energy_readings_15min CASCADE;
DROP MATERIALIZED VIEW IF EXISTS energy_readings_1h CASCADE;
DROP MATERIALIZED VIEW IF EXISTS energy_readings_1d CASCADE;

CREATE MATERIALIZED VIEW energy_readings_15min
WITH (timescaledb.continuous) AS
SELECT meter_id,
       time_bucket('15 minutes', timestamp) AS bucket,
       AVG(power) AS avg_power,
       MAX(power) AS max_power,
       SUM(energy) AS total_energy
FROM energy_readings
GROUP BY meter_id, bucket;

CREATE MATERIALIZED VIEW energy_readings_1h
WITH (timescaledb.continuous) AS
SELECT meter_id,
       time_bucket('1 hour', timestamp) AS bucket,
       AVG(power) AS avg_power,
       MAX(power) AS max_power,
       SUM(energy) AS total_energy
FROM energy_readings
GROUP BY meter_id, bucket;

CREATE MATERIALIZED VIEW energy_readings_1d
WITH (timescaledb.continuous) AS
SELECT meter_id,
       time_bucket('1 day', timestamp) AS bucket,
       AVG(power) AS avg_power,
       MAX(power) AS max_power,
       SUM(energy) AS total_energy
FROM energy_readings
GROUP BY meter_id, bucket;

CALL refresh_continuous_aggregate('energy_readings_15min', NULL, NULL);
CALL refresh_continuous_aggregate('energy_readings_1h', NULL, NULL);
CALL refresh_continuous_aggregate('energy_readings_1d', NULL, NULL);

SELECT add_continuous_aggregate_policy('energy_readings_15min',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes');

SELECT add_continuous_aggregate_policy('energy_readings_1h',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

SELECT add_continuous_aggregate_policy('energy_readings_1d',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');
