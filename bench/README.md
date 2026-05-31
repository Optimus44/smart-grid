# Baseline Benchmarking

Run the baseline queries and capture execution times and EXPLAIN outputs.

Usage:

```bash
# ensure env vars or defaults: PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
python bench/run_baseline.py --runs 3 --out bench/results.csv --explain-dir bench/explain
```

For chunk interval experiments, run the same benchmark against a specific table:

```bash
python bench/run_baseline.py --table energy_readings_3h --runs 3 --out bench/chunk_experiments/energy_readings_3h.csv --explain-dir bench/chunk_experiments/energy_readings_3h/explain
```

The orchestration script in `scripts/run_chunk_experiments.py` can create the 3-hour and 1-week tables, copy the source data into them, and generate the benchmark outputs.

Notes:
- For a proper cold-run measurement, restart the TimescaleDB container before running the first run:

```bash
docker restart timescaledb
```

- The script saves EXPLAIN outputs to `bench/explain/` and a CSV summary to `bench/results.csv`.
