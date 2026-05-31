#!/usr/bin/env python3
"""Run baseline queries with EXPLAIN ANALYZE and record timings.

Generates a CSV summary of execution times and saves EXPLAIN outputs.

Usage:
  python bench/run_baseline.py --runs 3 --out bench/results.csv --explain-dir bench/explain
"""
import os
import csv
import argparse
import datetime
import re
import psycopg2

QUERIES = {
    "Q1": (
        "Average power consumption per hour today",
        "SELECT time_bucket('1 hour', timestamp) AS hour\n"
        ", AVG(power) as avg_power\n"
        "FROM {table}\n"
        "WHERE timestamp >= DATE_TRUNC('day', NOW())\n"
        "GROUP BY hour ORDER BY hour;",
    ),
    "Q2": (
        "Find peak consumption periods in the past week",
        "SELECT time_bucket('15 minutes', timestamp) AS period\n"
        ", AVG(power) as avg_power\n"
        "FROM {table}\n"
        "WHERE timestamp >= NOW() - INTERVAL '7 days'\n"
        "GROUP BY period ORDER BY avg_power DESC LIMIT 10;",
    ),
    "Q3": (
        "Monthly consumption per meter",
        "SELECT meter_id,\n"
        "DATE_TRUNC('month', timestamp) as month,\n"
        "SUM(energy) as total_energy\n"
        "FROM {table}\n"
        "GROUP BY meter_id, month\n"
        "ORDER BY month, total_energy DESC;",
    ),
    "Q4": (
        "Full dataset scan",
        "SELECT COUNT(*), AVG(power), MAX(power), MIN(power)\n"
        "FROM {table};",
    ),
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--table", default="energy_readings", help="table name to benchmark")
    p.add_argument("--runs", type=int, default=3, help="number of runs per query (warm runs)")
    p.add_argument("--out", default="bench/results.csv", help="CSV file to write summary")
    p.add_argument("--explain-dir", default="bench/explain", help="Directory to save EXPLAIN outputs")
    return p.parse_args()


def get_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "energy"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", "postgres"),
    )


def extract_execution_ms(explain_text):
    # Look for line that starts with 'Execution Time:'
    for line in reversed(explain_text.splitlines()):
        line = line.strip()
        if line.startswith("Execution Time:"):
            try:
                parts = line.split()
                # last token is ms
                ms = float(parts[-2]) if parts[-1].lower().startswith("ms") else float(parts[-1])
                return ms
            except Exception:
                continue
    return None


def main():
    args = parse_args()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.table):
        raise SystemExit(f"Invalid table name: {args.table}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs(args.explain_dir, exist_ok=True)

    conn = get_conn()
    cur = conn.cursor()

    summary_rows = []
    run_timestamp = datetime.datetime.now(datetime.UTC).isoformat()

    for run in range(1, args.runs + 1):
        for qid, (desc, q) in QUERIES.items():
            explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, TIMING) {q.format(table=args.table)}"
            print(f"Running {qid} (run {run})...")
            cur.execute(explain_sql)
            rows = cur.fetchall()
            explain_text = "\n".join(r[0] for r in rows)

            exec_ms = extract_execution_ms(explain_text)

            # save explain output
            fname = os.path.join(args.explain_dir, f"{qid}_run{run}.txt")
            with open(fname, "w") as fh:
                fh.write(f"-- {qid}: {desc} (run {run})\n")
                fh.write(explain_text)

            summary_rows.append({
                "query_id": qid,
                "description": desc,
                "run": run,
                "execution_ms": exec_ms,
                "explain_file": fname,
                "timestamp": run_timestamp,
            })

    # write summary CSV
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["query_id", "description", "run", "execution_ms", "explain_file", "timestamp"])
        writer.writeheader()
        for r in summary_rows:
            writer.writerow(r)

    print(f"Wrote summary to {args.out}")


if __name__ == "__main__":
    main()
