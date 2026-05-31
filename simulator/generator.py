#!/usr/bin/env python3
"""Simulate smart meter data and publish to MQTT (EMQX)

Supports two modes:
- live: publish readings in real-time (sleeps `interval` seconds between publishes)
- generate: publish historical data for a given number of hours as fast as possible

Each message is JSON with fields: meter_id, timestamp, power, voltage, current, frequency, energy
"""
import argparse
import json
import time
import random
from datetime import datetime, timedelta
import math

import paho.mqtt.client as mqtt


def make_meter_ids(n, start=1000000000):
    return [str(start + i) for i in range(n)]


def diurnal_scale(dt):
    # Two-peaked pattern: morning ~8, evening ~19
    h = dt.hour + dt.minute / 60.0
    # Normalize to [0,24)
    # Combine two Gaussians for morning and evening peaks
    def peak(center, width=2.5):
        return math.exp(-0.5 * ((h - center) / width) ** 2)

    scale = 0.6 * peak(8, 2.5) + 0.8 * peak(19, 3.0) + 0.2
    return scale


def generate_reading(meter_id, ts, base_kw):
    scale = diurnal_scale(ts)
    # base_kw is the per-meter nominal power (kW)
    power = max(0.0, random.gauss(base_kw * scale, 0.05 * base_kw))
    voltage = random.gauss(230, 2)
    current = (power * 1000.0) / max(1.0, voltage)
    frequency = random.gauss(50.0, 0.02)
    # energy in kWh for a 5-minute interval (makes sense when interval=300s)
    energy = power * (5.0 / 60.0)

    return {
        "meter_id": meter_id,
        "timestamp": ts.isoformat(),
        "power": round(power, 4),
        "voltage": round(voltage, 2),
        "current": round(current, 3),
        "frequency": round(frequency, 3),
        "energy": round(energy, 6),
    }


def run_live(client, meter_ids, interval, base_map):
    next_ts = datetime.utcnow()
    try:
        while True:
            ts = datetime.utcnow()
            for m in meter_ids:
                r = generate_reading(m, ts, base_map[m])
                topic = f"energy/meters/{m}"
                info = client.publish(topic, json.dumps(r))
                info.wait_for_publish()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopping live simulator")


def run_generate(client, meter_ids, interval, hours, base_map):
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    ts = start
    count = 0
    while ts <= end:
        for m in meter_ids:
            r = generate_reading(m, ts, base_map[m])
            topic = f"energy/meters/{m}"
            info = client.publish(topic, json.dumps(r))
            info.wait_for_publish()
            count += 1
        ts += timedelta(seconds=interval)
    print(f"Published {count} messages for {len(meter_ids)} meters over {hours} hours")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-meters", type=int, default=1000)
    parser.add_argument("--interval", type=int, default=300, help="interval seconds between reports (default 300)")
    parser.add_argument("--mode", choices=["live", "generate"], default="generate")
    parser.add_argument("--hours", type=int, default=1, help="hours history to generate when mode=generate")
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--start-id", type=int, default=1000000000, help="starting 10-digit meter id")
    args = parser.parse_args()

    meter_ids = make_meter_ids(args.num_meters, start=args.start_id)
    # per-meter base kW (variation across meters)
    base_map = {m: random.uniform(0.2, 2.0) for m in meter_ids}

    client = mqtt.Client()
    client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
    client.loop_start()

    try:
        if args.mode == "live":
            print(f"Starting live simulator for {args.num_meters} meters, interval={args.interval}s")
            run_live(client, meter_ids, args.interval, base_map)
        else:
            print(f"Generating {args.hours} hours of historical data for {args.num_meters} meters")
            run_generate(client, meter_ids, args.interval, args.hours, base_map)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
