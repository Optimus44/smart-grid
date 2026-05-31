-- Chunk interval experiment setup

DROP TABLE IF EXISTS energy_readings_3h CASCADE;
DROP TABLE IF EXISTS energy_readings_week CASCADE;

CREATE TABLE energy_readings_3h (LIKE energy_readings INCLUDING ALL);
CREATE TABLE energy_readings_week (LIKE energy_readings INCLUDING ALL);

SELECT create_hypertable('energy_readings_3h', 'timestamp', chunk_time_interval => INTERVAL '3 hours');
SELECT create_hypertable('energy_readings_week', 'timestamp', chunk_time_interval => INTERVAL '1 week');

-- Copy identical data from the baseline hypertable:
-- INSERT INTO energy_readings_3h SELECT * FROM energy_readings;
-- INSERT INTO energy_readings_week SELECT * FROM energy_readings;

-- Helpful checks:
-- SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables ORDER BY hypertable_name;
-- SELECT chunk_name, range_start, range_end FROM timescaledb_information.chunks WHERE hypertable_name = 'energy_readings_3h';