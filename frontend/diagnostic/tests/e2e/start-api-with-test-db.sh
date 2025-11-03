#!/bin/bash
# Start API server with test database from global setup

# Read database path from setup file
SETUP_FILE="$(dirname "$0")/.test-setup-info.json"

# Wait for setup file to exist (max 30 seconds)
for i in {1..30}; do
  if [ -f "$SETUP_FILE" ]; then
    break
  fi
  echo "Waiting for test setup file..."
  sleep 1
done

if [ ! -f "$SETUP_FILE" ]; then
  echo "Error: Setup file not found after 30 seconds"
  exit 1
fi

# Extract database path using grep/sed (handle whitespace in JSON)
DB_PATH=$(grep -o '"dbPath"[[:space:]]*:[[:space:]]*"[^"]*"' "$SETUP_FILE" | sed 's/"dbPath"[[:space:]]*:[[:space:]]*"\(.*\)"/\1/')

if [ -z "$DB_PATH" ]; then
  echo "Error: Could not extract database path from setup file"
  exit 1
fi

echo "Starting API server with database: $DB_PATH"

# Start API server with the database path
cd "$(dirname "$0")/../../../../api" || exit 1
export PAYMENT_SIM_DB_PATH="$DB_PATH"
exec uv run uvicorn payment_simulator.api.main:app --host 0.0.0.0 --port 8000
