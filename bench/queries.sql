-- Baseline queries for benchmarking

-- Query 1: Average power consumption per hour today
SELECT time_bucket('1 hour', timestamp) AS hour,
AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= DATE_TRUNC('day', NOW())
GROUP BY hour ORDER BY hour;

-- Query 2: Find peak consumption periods in the past week
SELECT time_bucket('15 minutes', timestamp) AS period,
AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY period ORDER BY avg_power DESC LIMIT 10;

-- Query 3: Monthly consumption per meter
SELECT meter_id,
DATE_TRUNC('month', timestamp) as month,
SUM(energy) as total_energy
FROM energy_readings
GROUP BY meter_id, month
ORDER BY month, total_energy DESC;

-- Query 4: Full dataset scan
SELECT COUNT(*), AVG(power), MAX(power), MIN(power)
FROM energy_readings;
