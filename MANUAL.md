# Smart Energy Grid Monitoring — Beginner Manual

Purpose: step-by-step guide to set up the local environment and implement the project requirements in the same order as the specification, with the practical workflow kept beginner-friendly. The project spec separates the work into infrastructure, data generation, hypertable conversion/loading, benchmarking, chunk experiments, compression, continuous aggregates, and the dashboard deliverable. This manual is written for beginners and assumes you will run everything from the repository root.

Submission checklist
- [x] Infrastructure running: EMQX, TimescaleDB, Grafana.
- [x] Base table created: `energy_readings`.
- [x] Hypertable created: `energy_readings` with 1-day chunks.
- [ ] Generate the 4-week CSV dataset.
- [ ] Load the CSV into TimescaleDB.
- [ ] Run and record the baseline queries.
- [ ] Run the chunk interval comparison.
- [ ] Record compression metrics.
- [ ] Create continuous aggregates and compare performance.
- [ ] Build the dashboard screenshots for the report.
- [ ] Assemble the final PDF report and repository deliverables.

Contents
- Requirements
- Repository layout
- 0 — Quick test checklist (short test)
- 1 — Start infrastructure (Docker Compose)
- 2 — Create schema (regular table)
- 3 — Run the MQTT subscriber (ingest)
- 4 — Run simulator (short test and full historical generation)
- 5 — Convert to hypertable and bulk load CSV (COPY)
- 6 — Baseline queries and benchmarking
- 7 — Chunk interval experiments
- 8 — Compression
- 9 — Continuous aggregates
- 10 — Analytics and dashboard creation
- 11 — Troubleshooting & tips

---

Requirements
- macOS/Linux/Windows with Docker and Docker Compose installed.
- Python 3.10+ and `pip` to install the small helper scripts. (Docker approach keeps DB inside container.)
- Disk: at least 100 GB free (you indicated 100 GB+; good). For a full 4-week run with 1000 meters expect hundreds of MB–1.5 GB CSV plus DB storage.
- RAM: 16 GB (sufficient for this project; tune TimescaleDB if you have fewer resources).

Repository layout (important files)

- `docker-compose.yml` — EMQX (MQTT), TimescaleDB, Grafana services.
- `sql/schema.sql` — `energy_readings` table DDL and suggested indexes.
- `ingest/subscriber.py` — MQTT subscriber to write JSON messages to Postgres.
- `simulator/generator.py` — Publisher to simulate meters (live or generate modes).
- `scripts/generate_historical_csv.py` — CSV generator for bulk loading.
- `scripts/load_copy.sh` — Copies CSV into TimescaleDB container and runs `COPY`.
- `bench/run_baseline.py` — Runs baseline queries with `EXPLAIN (ANALYZE, BUFFERS)` and collects timings.
- `ROADMAP.md`, `MANUAL.md` — planning and documentation.

Work from repository root. Example: `/.../smart_grid`.

0 — Quick test checklist (short test)

Use the short path to validate the pipeline before heavy operations. Important: create the target table first so the subscriber can insert rows — you can skip converting to a hypertable for this quick test.

Detailed explanations for each short-test command live in [docs/short-test-guide.md](docs/short-test-guide.md). That guide is meant to grow as we work through Step 0 together.
If the simulator prints `Published ...` but the row count does not increase, see the detailed diagnosis in [docs/short-test-guide.md#detailed-diagnosis](docs/short-test-guide.md#detailed-diagnosis).

1. Start containers (in repo root):

```bash
docker compose up -d
```

2. Install Python deps (in repo root):

```bash
python -m pip install -r requirements.txt
```

3. Create the `energy_readings` table so the subscriber can write rows (you may skip hypertable conversion for this quick test):

```bash
docker exec -i timescaledb psql -U postgres -d energy < sql/schema.sql
# Optional (not required for the short test):
docker exec -it timescaledb psql -U postgres -d energy -c "SELECT create_hypertable('energy_readings','timestamp', chunk_time_interval => INTERVAL '1 day');"
```

If you are not in the repository root, use the full path to the file or `cd` into the repo first. The `< sql/schema.sql` part is important because it sends the file contents from your Mac into `psql`; `-f sql/schema.sql` would make `psql` look for the file inside the container instead.

4. In one terminal, run subscriber (writes to Postgres):

```bash
python ingest/subscriber.py
```

5. In another terminal, publish a small set of messages (10 meters × 1 hour fast generate):

```bash
python simulator/generator.py --mode generate --hours 1 --num-meters 10 --start-id 1000000000
```

6. Verify rows inserted (run inside timescaledb container or via psql client):

```bash
docker exec -it timescaledb psql -U postgres -d energy -c "SELECT COUNT(*) FROM energy_readings;"
```

If this works, the pipeline is validated and you can proceed to larger data loads.

1 — Start infrastructure (Docker Compose)

What this does
- Starts EMQX (MQTT broker) bound on port 1883, TimescaleDB on 5432, Grafana on 3000.

Commands (repo root):

```bash
docker compose up -d
docker ps  # confirm containers are running
```

Access:
- EMQX dashboard: http://localhost:8081 (if image exposes dashboard)
- Grafana: http://localhost:3000 (default admin: admin/admin — change on first login)

Notes
- If ports are occupied, stop conflicting services or edit `docker-compose.yml`.

2 — Create schema (regular table)

The repository includes `sql/schema.sql`. Create the regular PostgreSQL table first so the subscriber can write rows during the short test.

Run in the TimescaleDB container (from repo root):

```bash
docker exec -i timescaledb psql -U postgres -d energy -f sql/schema.sql
```

Verify table:

```bash
docker exec -it timescaledb psql -U postgres -d energy -c "\dt energy_readings"
```

What’s happening
- This creates the base table required by the Step 1 subscriber in the project description.
- The hypertable conversion comes later, when we begin the Step 3 loading and benchmarking work.

3 — Run the MQTT subscriber (ingest)

Purpose
- `ingest/subscriber.py` subscribes to `energy/meters/#` and inserts incoming JSON readings into `energy_readings`.

Run (repo root):

```bash
python ingest/subscriber.py
```

Environment variables (optional):
- `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`, `MQTT_HOST`, `MQTT_PORT`.

How it works (short explanation)
- The script connects to MQTT, subscribes to `energy/meters/#`, decodes JSON, and executes a SQL `INSERT` into the table using `psycopg2`.

4 — Run simulator (short test and full historical generation)

Short-test first (recommended)

```bash
# 10 meters for 1 hour (fast generation)
python simulator/generator.py --mode generate --hours 1 --num-meters 10
```

Live mode (publish every 5 minutes for testing live ingestion):

```bash
python simulator/generator.py --mode live --interval 300 --num-meters 10
```

Full historical CSV generation (4 weeks, 1000 meters) — heavy

```bash
python scripts/generate_historical_csv.py --num-meters 1000 --days 28 --interval 300 --out data/energy_readings.csv
```

Notes on heavy ops
- This will create ~8 million rows. On a 16 GB RAM machine with SSD, it may take 10–60+ minutes to generate, and copying/loading may take additional time. Ensure >50 GB free for comfortable operation.

5 — Convert to hypertable and bulk load CSV into TimescaleDB (COPY)

The project description says to convert `energy_readings` to a hypertable before the larger historical load. For the full workload, do that first, then use `COPY` from inside the Postgres container.

Steps

1. Convert the table to a hypertable with the required 1-day chunk interval:

```bash
docker exec -it timescaledb psql -U postgres -d energy -c "ALTER TABLE energy_readings DROP CONSTRAINT IF EXISTS energy_readings_pkey;"
docker exec -it timescaledb psql -U postgres -d energy -c "ALTER TABLE energy_readings ADD CONSTRAINT energy_readings_meter_time_key UNIQUE (meter_id, timestamp);"
docker exec -it timescaledb psql -U postgres -d energy -c "SELECT create_hypertable('energy_readings','timestamp', chunk_time_interval => INTERVAL '1 day');"
```

2. Generate CSV (see step 4) or split it into smaller CSVs if parallel load is desired.
3. Copy CSV into container and `COPY`:

```bash
chmod +x scripts/load_copy.sh
./scripts/load_copy.sh data/energy_readings.csv
```

The script copies the CSV to `/tmp/energy_readings.csv` inside the `timescaledb` container and runs:

```sql
COPY energy_readings (meter_id, timestamp, power, voltage, current, frequency, energy) FROM '/tmp/energy_readings.csv' CSV HEADER;
```

Verify row counts:

```bash
docker exec -it timescaledb psql -U postgres -d energy -c "SELECT COUNT(*) FROM energy_readings;"
```

If you already loaded short-test rows into the regular table, the hypertable conversion step above preserves the data path for the larger workload. For a clean benchmark run, it is usually better to convert before the large CSV load.

6 — Baseline queries and benchmarking

The repository contains `bench/run_baseline.py` and `bench/queries.sql`. These implement the four baseline queries and capture `EXPLAIN (ANALYZE, BUFFERS)` outputs.

Before running benchmark for cold-cache measurement, restart the DB container:

```bash
docker restart timescaledb
```

Run the benchmark (example, 3 runs):

```bash
python bench/run_baseline.py --runs 3 --out bench/results.csv --explain-dir bench/explain
```

Outputs
- `bench/results.csv` — summary of execution times (execution_ms per run per query)
- `bench/explain/` — EXPLAIN outputs for each run

Interpreting results
- Use the first run after a restart as the cold-run. Average subsequent runs as warm-run.
- `EXPLAIN (ANALYZE, BUFFERS)` shows buffer I/O usage which helps to understand disk vs memory-bound queries.

7 — Chunk interval experiments

Goal
- Compare performance between hypertables with different `chunk_time_interval` settings (3 hours, 1 day, 1 week). You will create separate tables with the same schema, load identical data into all three, and convert them to hypertables with different chunk intervals.
- Use `scripts/run_chunk_experiments.py` to automate table creation, data copy, benchmark runs, and chunk metadata export.

Commands (in psql / via docker exec):

```sql
CREATE TABLE energy_readings_3h (LIKE energy_readings INCLUDING ALL);
CREATE TABLE energy_readings_week (LIKE energy_readings INCLUDING ALL);
SELECT create_hypertable('energy_readings_3h', 'timestamp', chunk_time_interval => INTERVAL '3 hours');
SELECT create_hypertable('energy_readings_week', 'timestamp', chunk_time_interval => INTERVAL '1 week');
```

Load identical data into each hypertable. For large datasets, generate separate CSVs or `COPY` selectively. The helper script can also copy from the baseline hypertable directly.
The point is to keep the dataset the same across all three configurations so the query timings are comparable.

For cold cache measurements: restart DB before each hypertable's benchmark run.

Collect chunk metadata:

```sql
SELECT chunk_name, chunk_size, range_start, range_end
FROM timescaledb_information.chunks
WHERE hypertable_name = 'energy_readings';
```

8 — Compression

Purpose
- TimescaleDB compression reduces disk usage and can change query performance for historical data.

Enable compression and add a compression policy for each hypertable (example shown for the 1-day hypertable):

```sql
ALTER TABLE energy_readings SET (timescaledb.compress, timescaledb.compress_orderby = 'timestamp DESC');
SELECT add_compression_policy('energy_readings', INTERVAL '24 hours');

ALTER TABLE energy_readings_3h SET (timescaledb.compress, timescaledb.compress_orderby = 'timestamp DESC');
SELECT add_compression_policy('energy_readings_3h', INTERVAL '24 hours');

ALTER TABLE energy_readings_week SET (timescaledb.compress, timescaledb.compress_orderby = 'timestamp DESC');
SELECT add_compression_policy('energy_readings_week', INTERVAL '24 hours');
```

Alternatively, manually compress chunks using `SELECT compress_chunk(chunk)` if you want immediate compression.

Measure disk usage before/after:

```sql
SELECT hypertable_name, pg_size_pretty(hypertable_size(format('%I', hypertable_name)::regclass))
FROM timescaledb_information.hypertables;
```

Re-run benchmark queries (Q2, Q3) and record execution times; compute compression ratio as `uncompressed_size / compressed_size`.

Compression results from the current experiment

The table below is suitable for the final report. It compares storage size and benchmark timing before and after compression across the three hypertable layouts.

| Hypertable | Pre-compression size | Post-compression size | Compression ratio | Q2 pre (avg ms) | Q2 post (avg ms) | Q2 change | Q3 pre (avg ms) | Q3 post (avg ms) | Q3 change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| energy_readings | 1727 MB | 381 MB | 4.53x | 191.75 | 149.57 | -22.00% | 11589.58 | 680.95 | -94.12% |
| energy_readings_3h | 1775 MB | 555 MB | 3.20x | 773.34 | 306.07 | -60.42% | 14138.59 | 1076.39 | -92.39% |
| energy_readings_week | 1909 MB | 321 MB | 5.95x | 238.36 | 165.70 | -30.48% | 10915.81 | 671.64 | -93.85% |

Key findings
- Storage dropped by roughly 3.2x to 6.0x depending on the chunk layout.
- Q2 improved for all three hypertables after compression.
- Q3 saw the largest gain, with execution time falling by more than 92% in every case.

9 — Continuous aggregates (Step 6)

Use these repository files for Step 6:
- `sql/continuous_aggregates.sql` — creates the 15-minute, hourly, and daily continuous aggregates and refreshes them immediately.
- `bench/run_continuous_aggregates.py` — benchmarks raw queries versus the aggregate views.

Step 6 report summary

The repository now includes:
- `sql/continuous_aggregates.sql` — creates the 15-minute, hourly, and daily continuous aggregates, refreshes them, and adds refresh policies.
- `bench/run_continuous_aggregates.py` — benchmarks raw aggregation queries against the continuous aggregate views.

Run it with:

```bash
.venv/bin/python bench/run_continuous_aggregates.py --meter-id 1000000000 --runs 3 --out bench/continuous_aggregates/results.csv --explain-dir bench/continuous_aggregates/explain
```

Benchmark results from the current run:

| Query pair | Raw avg ms | Continuous aggregate avg ms | Change |
| --- | ---: | ---: | ---: |
| 15-minute aggregation | 0.40 | 0.08 | -81.28% |
| Hourly aggregation | 1.67 | 0.13 | -92.38% |
| Daily aggregation | 5.64 | 0.11 | -98.09% |

Key findings
- Continuous aggregates were faster in all three cases.
- The daily rollup showed the biggest improvement because the raw query had to scan and aggregate the widest time range.
- This step is now ready for the dashboard and final report write-up.

10 — Analytics and dashboard creation

The project description also requires a dashboard. Keep this section tied to the deliverable and avoid adding extra features that do not help the report.

Required panels:
- Real-time meter readings for the last hour.
- Daily consumption patterns comparing today vs. yesterday.
- Weekly trends visualization.
- Monthly energy usage by area or region, where the region is derived from the first digit of the meter ID.

Performance panel:
- Query execution time comparison between raw data and aggregated views.
- Storage efficiency gains from compression.
- Side-by-side visualizations showing the impact of chunk strategy.

Implementation note:
- Grafana is already included in the stack, so it is the most direct path for the dashboard deliverable.
- Keep the dashboard simple enough to screenshot for the report.

11 — Troubleshooting & tips

- If `docker compose up` fails, run `docker compose pull` then try again. Check `docker logs <container>`.
- If Python scripts fail with `psycopg2` import error, re-run `pip install -r requirements.txt`. On macOS you may need `brew install postgresql` or proper wheel support.
- If `COPY` reports permission issues, ensure the file exists inside the container and that the Postgres user can access it (the loader script handles copying and cleanup).
- If performance is poor: check `pg_stat_activity`, `pg_stat_database`, increase `shared_buffers` in Postgres config, or add indexes where necessary.
- For safe runs, always test with the short-test configuration before generating full datasets.

Appendix A — Useful commands summary

```bash
# Start services
docker compose up -d

# Install Python deps
python -m pip install -r requirements.txt

# Run subscriber
python ingest/subscriber.py

# Generate small test data
python simulator/generator.py --mode generate --hours 1 --num-meters 10

# Generate full CSV (heavy)
python scripts/generate_historical_csv.py --num-meters 1000 --days 28 --interval 300 --out data/energy_readings.csv

# Copy & load CSV into container
./scripts/load_copy.sh data/energy_readings.csv

# Convert to hypertable (if not done)
docker exec -it timescaledb psql -U postgres -d energy -c "SELECT create_hypertable('energy_readings','timestamp', chunk_time_interval => INTERVAL '1 day');"

# Run baseline benchmark
python bench/run_baseline.py --runs 3 --out bench/results.csv --explain-dir bench/explain

# Create 15min continuous aggregate
docker exec -it timescaledb psql -U postgres -d energy -c "<the CREATE MATERIALIZED VIEW SQL from above>"
```

Appendix B — Where to run commands
- Host terminal (repo root): Docker Compose, Python scripts, helper shell scripts.
- Inside container: use `docker exec -it timescaledb psql -U postgres -d energy` for SQL commands that directly reference container files.

Appendix C — Next steps after Step 6
- Chunk interval experiments, compression policy tuning, continuous aggregate policy tuning, Grafana dashboard creation, and writing the technical report.

---

If you want, I can now:
- generate a small test CSV and run the short end-to-end test locally (prepare commands), or
- produce a PDF from this Markdown (requires `pandoc`/LaTeX on your machine), or
- start the full 4-week CSV generation (this will take time and disk). Which do you want next?
