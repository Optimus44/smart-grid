#!/usr/bin/env python3
"""Create, load, and benchmark TimescaleDB chunk-interval variants.

This script compares three hypertable configurations:
- `energy_readings` (1 day)
- `energy_readings_3h` (3 hours)
- `energy_readings_week` (1 week)

It recreates the target tables from a source table, copies the same data into
each target, runs the baseline benchmark on each one, and records chunk
metadata.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg2


@dataclass(frozen=True)
class ChunkConfig:
    table: str
    interval: str


CONFIGS = (
    ChunkConfig("energy_readings_3h", "3 hours"),
    ChunkConfig("energy_readings_week", "1 week"),
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-table", default="energy_readings", help="source hypertable to copy from")
    parser.add_argument("--runs", type=int, default=3, help="benchmark runs per table")
    parser.add_argument("--output-dir", default="bench/chunk_experiments", help="directory for benchmark outputs")
    parser.add_argument("--recreate", action="store_true", help="drop and recreate target tables before loading")
    parser.add_argument("--skip-load", action="store_true", help="only create tables and benchmark existing data")
    parser.add_argument("--skip-benchmark", action="store_true", help="only create/load tables, do not benchmark")
    return parser.parse_args()


def get_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "energy"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", "postgres"),
    )


def run_sql(cur, sql_text: str, params=None):
    cur.execute(sql_text, params)


def create_target_table(cur, target_table: str, interval: str, recreate: bool):
    if recreate:
        run_sql(cur, f"DROP TABLE IF EXISTS {target_table} CASCADE;")
    run_sql(cur, f"CREATE TABLE IF NOT EXISTS {target_table} (LIKE energy_readings INCLUDING ALL);")
    run_sql(
        cur,
        f"SELECT create_hypertable('{target_table}', 'timestamp', chunk_time_interval => %s::interval, if_not_exists => TRUE);",
        (interval,),
    )


def copy_data(cur, source_table: str, target_table: str):
    run_sql(cur, f"TRUNCATE {target_table};")
    run_sql(cur, f"INSERT INTO {target_table} SELECT * FROM {source_table};")
    run_sql(cur, f"ANALYZE {target_table};")


def benchmark_table(table: str, runs: int, output_dir: Path):
    results_csv = output_dir / f"{table}.csv"
    explain_dir = output_dir / table / "explain"
    explain_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "bench/run_baseline.py",
        "--table",
        table,
        "--runs",
        str(runs),
        "--out",
        str(results_csv),
        "--explain-dir",
        str(explain_dir),
    ]
    subprocess.run(cmd, check=True)
    return results_csv, explain_dir


def fetch_chunk_metadata(cur, table: str):
    cur.execute(
        """
        SELECT chunk_name, range_start, range_end
        FROM timescaledb_information.chunks
        WHERE hypertable_name = %s
        ORDER BY range_start;
        """,
        (table,),
    )
    return cur.fetchall()


def count_rows(cur, table: str):
    cur.execute(f"SELECT COUNT(*) FROM {table};")
    return cur.fetchone()[0]


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = get_conn()
    cur = conn.cursor()

    summary_rows = []
    timestamp = dt.datetime.now(dt.UTC).isoformat()

    for config in CONFIGS:
        print(f"Preparing {config.table} ({config.interval})...")
        create_target_table(cur, config.table, config.interval, args.recreate)
        conn.commit()

        if not args.skip_load:
            print(f"Loading {config.table} from {args.source_table}...")
            copy_data(cur, args.source_table, config.table)
            conn.commit()

        row_count = count_rows(cur, config.table)
        chunks = fetch_chunk_metadata(cur, config.table)
        conn.commit()

        summary_rows.append(
            {
                "table": config.table,
                "interval": config.interval,
                "rows": row_count,
                "chunks": len(chunks),
                "timestamp": timestamp,
            }
        )

        chunk_path = output_dir / f"{config.table}_chunks.csv"
        with chunk_path.open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["chunk_name", "range_start", "range_end"])
            writer.writerows(chunks)

        if not args.skip_benchmark:
            print(f"Benchmarking {config.table}...")
            benchmark_table(config.table, args.runs, output_dir)

    summary_path = output_dir / "summary.csv"
    with summary_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["table", "interval", "rows", "chunks", "timestamp"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Wrote summary to {summary_path}")


if __name__ == "__main__":
    main()