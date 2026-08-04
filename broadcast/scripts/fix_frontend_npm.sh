#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
FRONTEND_DIR="$APP_DIR/frontend"

echo "LFTR frontend npm cleanup"
echo "App dir: $APP_DIR"

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo "Missing frontend directory: $FRONTEND_DIR" >&2
  exit 1
fi

cd "$FRONTEND_DIR"

cat > .npmrc <<'NPMRC'
registry=https://registry.npmjs.org/
audit=false
fund=false
fetch-retries=2
fetch-retry-factor=2
fetch-retry-mintimeout=10000
fetch-retry-maxtimeout=60000
NPMRC

if [[ -f package-lock.json ]] && grep -qE 'applied-caas|artifactory|internal\.api\.openai' package-lock.json; then
  echo "Removing sandbox/internal package-lock.json"
  rm -f package-lock.json
fi

if [[ -d node_modules ]]; then
  echo "Removing partial node_modules"
  rm -rf node_modules
fi

echo "Installing frontend dependencies from public npm registry"
npm install --no-audit --no-fund --registry=https://registry.npmjs.org/

echo "Building frontend"
npm run build

echo "Frontend npm cleanup/build complete"
