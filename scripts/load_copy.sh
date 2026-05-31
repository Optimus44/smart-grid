#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/load_copy.sh data/energy_readings.csv
CSV_PATH=${1:-data/energy_readings.csv}
CONTAINER=timescaledb
DEST=/tmp/energy_readings.csv

if [ ! -f "$CSV_PATH" ]; then
  echo "CSV not found: $CSV_PATH" >&2
  exit 2
fi

echo "Copying $CSV_PATH -> $CONTAINER:$DEST"
docker cp "$CSV_PATH" "$CONTAINER:$DEST"

echo "Importing CSV into Postgres (this may take a while)"
docker exec -i "$CONTAINER" psql -U postgres -d energy <<SQL
COPY energy_readings (meter_id, timestamp, power, voltage, current, frequency, energy)
FROM '$DEST' CSV HEADER;
SQL

echo "Import complete. Removing $DEST from container."
docker exec -i "$CONTAINER" rm -f "$DEST"

echo "Done."
