#!/usr/bin/env python3
"""Benchmark raw queries versus continuous aggregates.

This script compares raw aggregation queries with their corresponding
continuous aggregate views and writes both EXPLAIN outputs and a CSV summary.

Usage:
  .venv/bin/python bench/run_continuous_aggregates.py \
    --meter-id 1000000000 \
    --runs 3 \
    --out bench/continuous_aggregates/results.csv \
    --explain-dir bench/continuous_aggregates/explain
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
from pathlib import Path

import psycopg2


QUERIES = {
    "RAW_15M": (
        "Raw 15-minute aggregation for a meter over the last day",
        "SELECT meter_id, time_bucket('15 minutes', timestamp) AS bucket, "
        "AVG(power) AS avg_power "
        "FROM energy_readings "
        "WHERE timestamp >= NOW() - INTERVAL '1 day' AND meter_id = %s "
        "GROUP BY meter_id, bucket ORDER BY bucket;",
    ),
    "CAGG_15M": (
        "Continuous aggregate 15-minute view for a meter over the last day",
        "SELECT meter_id, bucket, avg_power "
        "FROM energy_readings_15min "
        "WHERE bucket >= NOW() - INTERVAL '1 day' AND meter_id = %s "
        "ORDER BY bucket;",
    ),
    "RAW_1H": (
        "Raw hourly aggregation for a meter over the last 7 days",
        "SELECT meter_id, time_bucket('1 hour', timestamp) AS bucket, "
        "AVG(power) AS avg_power "
        "FROM energy_readings "
        "WHERE timestamp >= NOW() - INTERVAL '7 days' AND meter_id = %s "
        "GROUP BY meter_id, bucket ORDER BY bucket;",
    ),
    "CAGG_1H": (
        "Continuous aggregate hourly view for a meter over the last 7 days",
        "SELECT meter_id, bucket, avg_power "
        "FROM energy_readings_1h "
        "WHERE bucket >= NOW() - INTERVAL '7 days' AND meter_id = %s "
        "ORDER BY bucket;",
    ),
    "RAW_1D": (
        "Raw daily aggregation for a meter over the last 30 days",
        "SELECT meter_id, time_bucket('1 day', timestamp) AS bucket, "
        "AVG(power) AS avg_power "
        "FROM energy_readings "
        "WHERE timestamp >= NOW() - INTERVAL '30 days' AND meter_id = %s "
        "GROUP BY meter_id, bucket ORDER BY bucket;",
    ),
    "CAGG_1D": (
        "Continuous aggregate daily view for a meter over the last 30 days",
        "SELECT meter_id, bucket, avg_power "
        "FROM energy_readings_1d "
        "WHERE bucket >= NOW() - INTERVAL '30 days' AND meter_id = %s "
        "ORDER BY bucket;",
    ),
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meter-id", default="1000000000", help="meter_id to benchmark")
    parser.add_argument("--runs", type=int, default=3, help="number of runs per query")
    parser.add_argument("--out", default="bench/continuous_aggregates/results.csv", help="CSV file to write summary")
    parser.add_argument("--explain-dir", default="bench/continuous_aggregates/explain", help="directory to save EXPLAIN outputs")
    return parser.parse_args()


def get_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "energy"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", "postgres"),
    )


def extract_execution_ms(explain_text):
    for line in reversed(explain_text.splitlines()):
        line = line.strip()
        if line.startswith("Execution Time:"):
            parts = line.split()
            try:
                return float(parts[-2]) if parts[-1].lower().startswith("ms") else float(parts[-1])
            except Exception:
                return None
    return None


def main():
    args = parse_args()
    if not str(args.meter_id).strip():
        raise SystemExit("meter_id cannot be empty")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs(args.explain_dir, exist_ok=True)

    conn = get_conn()
    cur = conn.cursor()

    summary_rows = []
    run_timestamp = dt.datetime.now(dt.UTC).isoformat()

    for run in range(1, args.runs + 1):
        for qid, (desc, query) in QUERIES.items():
            explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, TIMING) {query}"
            print(f"Running {qid} (run {run})...")
            cur.execute(explain_sql, (args.meter_id,))
            rows = cur.fetchall()
            explain_text = "\n".join(row[0] for row in rows)
            exec_ms = extract_execution_ms(explain_text)

            explain_path = Path(args.explain_dir) / f"{qid}_run{run}.txt"
            with explain_path.open("w") as fh:
                fh.write(f"-- {qid}: {desc} (run {run})\n")
                fh.write(explain_text)

            summary_rows.append(
                {
                    "query_id": qid,
                    "description": desc,
                    "run": run,
                    "execution_ms": exec_ms,
                    "explain_file": str(explain_path),
                    "timestamp": run_timestamp,
                }
            )

    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["query_id", "description", "run", "execution_ms", "explain_file", "timestamp"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Wrote summary to {args.out}")


if __name__ == "__main__":
    main()