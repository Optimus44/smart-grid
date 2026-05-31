#!/usr/bin/env python3
"""MQTT -> TimescaleDB subscriber

Subscribes to `energy/meters/#` and inserts JSON messages into Postgres table
`energy_readings`.

Environment variables (optional):
- PG_HOST (default: localhost)
- PG_PORT (default: 5432)
- PG_DB (default: energy)
- PG_USER (default: postgres)
- PG_PASSWORD (default: postgres)
- MQTT_HOST (default: localhost)
- MQTT_PORT (default: 1883)

Run:
    python ingest/subscriber.py
"""
import os
import json
import logging
import signal
import sys
from datetime import datetime

import psycopg2
import paho.mqtt.client as mqtt

LOG = logging.getLogger("ingest.subscriber")


def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "energy"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", "postgres"),
    )


INSERT_SQL = (
    "INSERT INTO energy_readings (meter_id, timestamp, power, voltage, current, frequency, energy) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        LOG.info("Connected to MQTT broker, subscribing to energy/meters/#")
        client.subscribe("energy/meters/#")
    else:
        LOG.error("Failed to connect to MQTT broker, rc=%s", rc)


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="ignore")
    try:
        data = json.loads(payload)
    except Exception as e:
        LOG.exception("Invalid JSON payload: %s", payload)
        return

    meter_id = str(data.get("meter_id") or data.get("id") or data.get("meter") or "")
    timestamp = data.get("timestamp") or data.get("time")
    power = data.get("power")
    voltage = data.get("voltage")
    current = data.get("current")
    frequency = data.get("frequency")
    energy = data.get("energy")

    if not meter_id:
        LOG.warning("Payload missing meter_id: %s", payload)
        return

    if timestamp is None:
        # use current UTC time if none provided
        timestamp = datetime.utcnow()

    # Insert into Postgres
    conn = userdata.get("pg_conn")
    try:
        with conn.cursor() as cur:
            cur.execute(INSERT_SQL, (meter_id, timestamp, power, voltage, current, frequency, energy))
        conn.commit()
    except Exception:
        LOG.exception("Failed to insert reading: %s", payload)
        try:
            conn.rollback()
        except Exception:
            pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    mqtt_host = os.getenv("MQTT_HOST", "localhost")
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))

    # prepare Postgres connection and pass it to MQTT userdata
    conn = get_pg_conn()

    client = mqtt.Client()
    client.user_data_set({"pg_conn": conn})
    client.on_connect = on_connect
    client.on_message = on_message

    def _graceful(signum, frame):
        LOG.info("Shutting down (signal=%s)", signum)
        try:
            client.disconnect()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _graceful)
    signal.signal(signal.SIGTERM, _graceful)

    LOG.info("Connecting to MQTT broker %s:%d", mqtt_host, mqtt_port)
    client.connect(mqtt_host, mqtt_port, keepalive=60)

    # Blocking loop
    client.loop_forever()


if __name__ == "__main__":
    main()
