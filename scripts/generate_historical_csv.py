#!/usr/bin/env python3
"""Generate historical CSV of meter readings for bulk loading.

Writes a CSV with columns: meter_id,timestamp,power,voltage,current,frequency,energy

Example:
  python scripts/generate_historical_csv.py --num-meters 1000 --days 28 --interval 300 --out data/energy_readings.csv
"""
import argparse
import os
import csv
import random
import math
from datetime import datetime, timedelta


def make_meter_ids(n, start=1000000000):
    return [str(start + i) for i in range(n)]


def diurnal_scale(dt):
    h = dt.hour + dt.minute / 60.0
    def peak(center, width):
        return math.exp(-0.5 * ((h - center) / width) ** 2)

    scale = 0.6 * peak(8, 2.5) + 0.8 * peak(19, 3.0) + 0.2
    return scale


def generate_reading(meter_id, ts, base_kw, interval_s):
    scale = diurnal_scale(ts)
    power = max(0.0, random.gauss(base_kw * scale, 0.05 * base_kw))
    voltage = random.gauss(230, 2)
    current = (power * 1000.0) / max(1.0, voltage)
    frequency = random.gauss(50.0, 0.02)
    energy = power * (interval_s / 3600.0)
    return [meter_id, ts.isoformat(), f"{power:.4f}", f"{voltage:.2f}", f"{current:.3f}", f"{frequency:.3f}", f"{energy:.6f}"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-meters", type=int, default=1000)
    parser.add_argument("--days", type=int, default=28, help="number of days to generate")
    parser.add_argument("--interval", type=int, default=300, help="seconds between readings (default: 300)")
    parser.add_argument("--out", default="data/energy_readings.csv")
    parser.add_argument("--start-id", type=int, default=1000000000)
    args = parser.parse_args()

    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)

    meter_ids = make_meter_ids(args.num_meters, start=args.start_id)
    base_map = {m: random.uniform(0.2, 2.0) for m in meter_ids}

    start = datetime.utcnow() - timedelta(days=args.days)
    end = datetime.utcnow()
    total_steps = int(((end - start).total_seconds()) // args.interval) + 1
    total_rows = total_steps * args.num_meters

    print(f"Generating {total_rows:,} rows ({args.num_meters} meters x {args.days} days)")

    with open(args.out, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["meter_id", "timestamp", "power", "voltage", "current", "frequency", "energy"])

        step = 0
        ts = start
        while ts <= end:
            for m in meter_ids:
                row = generate_reading(m, ts, base_map[m], args.interval)
                writer.writerow(row)
            step += 1
            if step % 100 == 0:
                print(f"  progress: {step}/{total_steps} steps ({(step/total_steps)*100:.1f}%)")
            ts += timedelta(seconds=args.interval)

    print(f"Wrote CSV to {args.out}")


if __name__ == "__main__":
    main()
