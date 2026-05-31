# Smart Energy Grid Monitoring — Local Dev

## Group Members 
1. Wayne Rubangisa 
2. Lydia Kigero Mbabazi
3. Jimmy Irakiza
4. Dany Nkurunziza

This repository scaffolds a local environment for the Smart Energy Grid Monitoring System project.

Quick start

1. Start services (EMQX, TimescaleDB, Grafana):

```bash
docker compose up -d
```

2. Connect to TimescaleDB on `localhost:5432` (user: `postgres`, password: `postgres`, db: `energy`).
3. Use `sql/schema.sql` to create the `energy_readings` table and then convert it to a hypertable.
4. Install Python deps for simulator/ingest:

```bash
python -m pip install -r requirements.txt
```

Next steps
- Implement `ingest/subscriber.py` to subscribe to `energy/meters/#` and write to Postgres.
- Implement `simulator/generator.py` to publish simulated meter data to EMQX.
