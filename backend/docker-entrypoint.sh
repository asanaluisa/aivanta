#!/bin/sh
# Apply migrations, load the synthetic demo data once, then start the API.
set -e
alembic upgrade head
if [ "${AIVANTA_SEED_DEMO:-true}" = "true" ]; then
  python -m app.seed
fi
exec "$@"
