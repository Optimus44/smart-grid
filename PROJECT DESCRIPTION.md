# Smart Energy Grid Monitoring System

## Project Overview:
Design and implement a system to monitor and analyze energy consumption data from
smart meters, demonstrating the advantages of TimescaleDB's time-partitioning features.

## Step 1: Setup Basic Infrastructure
- Install and configure EMQX as your MQTT broker
- Install and configure TimescaleDB
- Create a Python program that:
    - Subscribes to the topic `energy/meters/#`
    - Stores received data in a regular PostgreSQL table called `energy_readings`
    - Include fields: `meter_id`, `timestamp`, `power`, `voltage`, `current`, `frequency`, `energy`

## Step 2: Data Generation Implementation
Create a Python simulation program that generates smart meter data for at least 1000
meters with the following parameters:

- Each meter_id should be a 10-digit number (e.g., 1234567890)
- Each meter reports data every 5 minutes
- Data should follow realistic patterns (higher usage during morning/evening, lower at night)
- Use `paho-mqtt` client to publish messages to topic `energy/meters/{meter_id}`
- Message format must be JSON with the required fields
    - Test your pipeline by generating data for 1 hour and confirming proper storage in PostgreSQL.

## Step 3: Basic Hypertable Creation and Initial Data Loading

1. Convert your PostgreSQL table to a TimescaleDB hypertable with exactly these commands:

```sql
SELECT create_hypertable('energy_readings', 'timestamp', chunk_time_interval => INTERVAL '1 day');
```

2. Generate and load 4 weeks of historical data (approximately 8.4 million rows)

3. Execute and record the execution time of these specific baseline queries:

```sql
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
```

## Step 4: Chunk Interval Experimentation
- Create two additional test tables and hypertables with identical schema:

```sql
CREATE TABLE energy_readings_3h (LIKE energy_readings INCLUDING ALL);
CREATE TABLE energy_readings_week (LIKE energy_readings INCLUDING ALL);
SELECT create_hypertable('energy_readings_3h', 'timestamp', chunk_time_interval => INTERVAL '3 hours');
SELECT create_hypertable('energy_readings_week', 'timestamp', chunk_time_interval => INTERVAL '1 week');
```

- Load identical data into all three hypertable configurations
- Execute the same four queries from Step 3 on each hypertable. Restart PostgreSQL before running queries to ensure cold cache conditions
- Document execution times in a table format showing:

| Query | 3-hour chunks | 1-day chunks | 1-week chunks |
|-------|----------------|---------------|----------------|
| 1     | time           | time          | time           |
| ...   | ...            | ...           | ...            |

- Run this additional query to analyze chunk distribution:

```sql 
SELECT chunk_name, chunk_size, range_start, range_end
FROM chunk_information
WHERE hypertable_name = 'energy_readings';
```

## Step 5: Compression Implementation
1. Before implementing compression:
Record the disk space used by each hypertable with:

```sql 
SELECT hypertable_name, pg_size_pretty(hypertable_size(format('%I',
hypertable_name)::regclass))
FROM timescaledb_information.hypertables;
```
Re-run Query 2 and Query 3 from Step 3 and record execution times. 

2. Apply compression to each hypertable with:
```sql 
-- For the 1-day chunk hypertable
ALTER TABLE energy_readings SET (timescaledb.compress,
timescaledb.compress_orderby = 'timestamp DESC');
SELECT add_compression_policy('energy_readings', INTERVAL '24
hours');

-- Do the same for the other two hypertables
```

3. After compression is applied (you may need to wait or manually compress chunks):
- Measure disk usage again with the same query
- Re-run the same queries and record execution times

4. Calculate and document:
- Compression ratio (uncompressed size / compressed size)
- Query performance difference (% change in execution time)


## Step 6: Continuous Aggregations (Do some reading)
- Create these specific continuous aggregation views:

```sql
-- 15-minute aggregations
CREATE MATERIALIZED VIEW energy_readings_15min
WITH (timescaledb.continuous) AS
SELECT meter_id,
       time_bucket('15 minutes', timestamp) AS bucket,~
       AVG(power) as avg_power,
       MAX(power) as max_power,
       SUM(energy) as total_energy
FROM energy_readings
GROUP BY meter_id, bucket;

-- Create hourly and daily views following the same pattern
```
- Add a refresh policy:

```sql 
SELECT add_continuous_aggregate_policy('energy_readings_15min',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes');
```

- Compare performance by executing these paired queries and recording times:

```sql 
-- Using raw data
SELECT meter_id, time_bucket('15 minutes', timestamp) AS bucket,
AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= NOW() - INTERVAL '1 day'
AND meter_id = '123'
GROUP BY meter_id, bucket
ORDER BY bucket;

-- Using continuous aggregation view
SELECT meter_id, bucket, avg_power
FROM energy_readings_15min
WHERE bucket >= NOW() - INTERVAL '1 day'
AND meter_id = '123'
ORDER BY bucket;
```

## Step 7: Analytics and Dashboard Creation
1. Using your optimized data structure, implement a dashboard with:
    - Real-time meter readings for the last hour
    - Daily consumption patterns (today vs. yesterday)
    - Weekly trends visualization
    - Monthly energy usage by area/region (group meters by first digit of ID) (e.g., '1xxxxxxx' = Region 1)

2. Include a performance metrics panel showing:
    - Query execution time comparison between raw data and aggregated views
    - Storage efficiency gains from compression
    - Side-by-side visualizations using different chunk strategies


## Deliverables:
1. GitHub repository including:
    - All source code (data simulation, database scripts, analysis code)
    - SQL scripts for all table creations, hypertable conversions, and queries

2. Technical report (PDF) containing:
    - Infrastructure overview and implementation details
    - Performance analysis tables with all measurements
    - Charts showing query performance across different configurations
    - Screenshots of database statistics and chunk information
    - Compression analysis with before/after metrics
    - Recommendations for optimal TimescaleDB configuration

3. Dashboard (implemented using Grafana, Dash, or similar) with:
    - Screenshots included in your report
    - Source code in your repository

## Evaluation Criteria
1. Correct implementation of TimescaleDB features (40%)
2. Quality of performance analysis and documentation (30%)
3. Dashboard functionality and insights (15%)
4. Code quality and documentation (15%)