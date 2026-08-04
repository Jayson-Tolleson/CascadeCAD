#!/usr/bin/env bash
set -euo pipefail
export CASCADE_CAD_STORAGE="${CASCADE_CAD_STORAGE:-$PWD/.dev-storage}"
export CASCADE_CAD_HOST="${CASCADE_CAD_HOST:-127.0.0.1}"
export CASCADE_CAD_PORT="${CASCADE_CAD_PORT:-8790}"
export CASCADE_CAD_BASE_PATH="${CASCADE_CAD_BASE_PATH:-/cascade-cad}"
python -m webcad_xbf.worker &
worker=$!
trap 'kill "$worker" 2>/dev/null || true' EXIT
hypercorn --bind "$CASCADE_CAD_HOST:$CASCADE_CAD_PORT" webcad_xbf.app:app
