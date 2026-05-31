# Smart Energy Grid Monitoring — Local Dev

## Group Members
- Wayne Rubangisa
- Lydia Kigero Mbabazi
- Jimmy Irakiza
- Dany Nkurunziza

## Overview
This repository provides a reproducible local environment for the Smart Energy Grid Monitoring project. It includes services (EMQX MQTT broker, TimescaleDB, Grafana), ingestion code, and a simulator for publishing meter data.

## Prerequisites
- Docker & Docker Compose
- Python 3.10+ and `pip`
- (Optional) `psql` for manual DB work

## Quickstart (local)
1. Start the stack (EMQX, TimescaleDB, Grafana):

```bash
docker compose up -d
```

2. Verify services are running (example):

```bash
docker compose ps
```

3. Connect to TimescaleDB:

- Host: `localhost`  Port: `5432`
- User: `postgres`  Password: `postgres`  Database: `energy`

4. Create schema and hypertable (once):

```bash
psql "postgresql://postgres:postgres@localhost:5432/energy" -f sql/schema.sql
```

5. Install Python dependencies for simulator and ingest:

```bash
python -m pip install -r requirements.txt
```

6. (Optional) Run the simulator to publish sample meter data to EMQX:

```bash
python simulator/generator.py
```

7. Start the ingestion subscriber to write MQTT messages into TimescaleDB:

```bash
python ingest/subscriber.py
```

## Project layout
- `sql/` — DB schema, continuous aggregates, and experiment queries
- `simulator/` — MQTT data generator (publishes to `energy/meters/#`)
- `ingest/` — MQTT subscriber that writes readings to Postgres
- `grafana/` — dashboard definitions and provisioning files
- `scripts/` — helper scripts for experiments and CSV generation

## Development notes
- Use the topic prefix `energy/meters/<meter_id>` for simulated messages.
- The ingestion code should parse JSON payloads and insert into `energy_readings`.
- See `sql/continuous_aggregates.sql` for recommended materialized views to support dashboards and experiments.

## Testing & Validation
- After running simulator + subscriber, confirm rows in the DB:

```bash
psql "postgresql://postgres:postgres@localhost:5432/energy" -c "SELECT count(*) FROM energy_readings;"
```

- Load the Grafana dashboard in `grafana/dashboards/smart_grid_dashboard.json` (Grafana is provisioned by the compose stack).

## Troubleshooting
- If Grafana shows no data: check that continuous aggregates are configured and subscriber is writing to `energy_readings`.
- If MQTT messages aren't received: verify EMQX is up and `simulator/generator.py` is publishing to the correct broker/port.

## Next steps (todo)
- Implement `ingest/subscriber.py` to reliably subscribe to `energy/meters/#` and insert readings.
- Implement `simulator/generator.py` to publish realistic meter data (timestamps, kW, voltage, meter_id).
- Add tests and CI to exercise ingestion and DB writes.

## Contact
For questions or contributions, open an issue or contact the project maintainers.
