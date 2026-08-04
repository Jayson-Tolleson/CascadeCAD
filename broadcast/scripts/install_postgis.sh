#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cat <<'MSG'
PostGIS install notes for Ubuntu/Debian:
  sudo apt-get update
  sudo apt-get install postgresql postgresql-contrib postgis
  createdb lftr_next
  psql -d lftr_next -c 'CREATE EXTENSION IF NOT EXISTS postgis;'

Set LFTR_POSTGIS_DSN before running migrations, for example:
  export LFTR_POSTGIS_DSN='postgresql:///lftr_next'
  export LFTR_POSTGIS_ENABLED=true
  export LFTR_SPATIAL_MODE=postgis
  export LFTR_RENDER_CACHE_ENABLED=true
  export LFTR_RENDER_CACHE_PREFER_POSTGIS=true
  export LFTR_RENDER_CACHE_WRITE_THROUGH=true
MSG
if [[ -n "${LFTR_POSTGIS_DSN:-}" ]]; then
  echo "LFTR_POSTGIS_DSN configured; running idempotent migrations..."
  PYTHONPATH="$ROOT" "$ROOT/scripts/migrate_postgis.py"
else
  echo "LFTR_POSTGIS_DSN not configured; skipping migrations."
fi
