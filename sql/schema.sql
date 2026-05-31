-- Schema for energy_readings
CREATE TABLE IF NOT EXISTS energy_readings (
    id BIGSERIAL PRIMARY KEY,
    meter_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    power DOUBLE PRECISION,
    voltage DOUBLE PRECISION,
    current DOUBLE PRECISION,
    frequency DOUBLE PRECISION,
    energy DOUBLE PRECISION
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_energy_readings_meter_time ON energy_readings (meter_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_energy_readings_time ON energy_readings (timestamp DESC);

-- To convert to hypertable (run once in psql):
-- SELECT create_hypertable('energy_readings', 'timestamp', chunk_time_interval => INTERVAL '1 day');
