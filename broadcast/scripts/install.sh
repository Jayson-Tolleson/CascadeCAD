#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# LFTR Broadcast / Marine Intelligence Globe installer
# - whiptail/dialog style prompts when available, text fallback otherwise
# - installs into ~/broadcast by default
# - configures Python venv, frontend build, systemd, nginx, TLS, UFW
# - optionally opens selected ports in Google Cloud and enables Vertex AI APIs

if [[ -t 1 && "${NO_COLOR:-}" == "" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'; C_MAG=$'\033[35m'; C_CYAN=$'\033[36m'
else
  C_RESET=''; C_BOLD=''; C_DIM=''; C_RED=''; C_GREEN=''; C_YELLOW=''; C_BLUE=''; C_MAG=''; C_CYAN=''
fi

say() { printf '%b\n' "$*"; }
ui_line() { say "${C_DIM}────────────────────────────────────────────────────────────${C_RESET}"; }
ui_step() { say "${C_BLUE}${C_BOLD}▶${C_RESET} ${C_BOLD}$*${C_RESET}"; }
ui_ok() { say "${C_GREEN}${C_BOLD}✓${C_RESET} $*"; }
ui_warn() { say "${C_YELLOW}${C_BOLD}!${C_RESET} $*"; }
ui_fail() { say "${C_RED}${C_BOLD}✗${C_RESET} $*" >&2; }
ui_phase() { ui_line; say "${C_MAG}${C_BOLD}PHASE $1${C_RESET} ${C_CYAN}${C_BOLD}— $2${C_RESET}"; ui_line; }

use_tui() {
  [[ -t 0 && -t 1 && "${LFTR_TEXT_INSTALLER:-0}" != "1" ]] && command -v whiptail >/dev/null 2>&1
}

prompt_default() {
  local prompt="$1" default="$2" value=""
  if use_tui; then
    value=$(whiptail --title "LFTR Broadcast Installer" --inputbox "$prompt" 10 78 "$default" 3>&1 1>&2 2>&3) || value="$default"
    printf '%s\n' "${value:-$default}"
  else
    read -r -p "$prompt [$default]: " value || true
    printf '%s\n' "${value:-$default}"
  fi
}

prompt_yes_no() {
  local prompt="$1" default="${2:-yes}" answer=""
  if use_tui; then
    if [[ "$default" == "yes" ]]; then
      whiptail --title "LFTR Broadcast Installer" --yesno "$prompt" 10 78 && return 0 || return 1
    else
      whiptail --title "LFTR Broadcast Installer" --defaultno --yesno "$prompt" 10 78 && return 0 || return 1
    fi
  fi
  read -r -p "$prompt [$default]: " answer || true
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy]([Ee][Ss])?$ ]]
}

pause_msg() {
  local msg="$1"
  if use_tui; then
    whiptail --title "LFTR Broadcast Installer" --msgbox "$msg" 12 78 || true
  else
    ui_ok "$msg"
  fi
}

need_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
  fi
}

shell_escape_sed() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

normalize_ports_csv() {
  local csv="$1"
  csv="${csv// /}"
  csv="${csv//;/,}"
  csv="${csv#,}"; csv="${csv%,}"
  printf '%s' "$csv"
}

port_list_to_gcloud_tcp() {
  local csv="$1" out=""
  IFS=',' read -ra ports <<< "$csv"
  for p in "${ports[@]}"; do
    [[ -n "$p" ]] || continue
    if [[ -z "$out" ]]; then out="tcp:$p"; else out="$out,tcp:$p"; fi
  done
  printf '%s' "$out"
}

install_bootstrap_packages() {
  ui_phase 1 "SYSTEM PACKAGES"
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      curl wget git rsync unzip ca-certificates gnupg lsb-release \
      python3 python3-venv python3-pip build-essential \
      nginx certbot python3-certbot-nginx dnsutils ufw jq \
      python3-netcdf4 python3-h5py gdal-bin \
      postgresql postgresql-contrib postgis \
      whiptail dialog ncurses-bin || true

    # Debian/Ubuntu system-Python fallback for server diagnostics that are run
    # as bare `python3 scripts/check_*.py` before or outside the project venv.
    # The app still installs these into .venv with pip below; this apt layer
    # keeps admin one-liners and smoke tests from failing with import errors.
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3-pydantic python3-pydantic-settings \
      python3-annotated-types python3-pydantic-core >/dev/null 2>&1 \
      || ui_warn "Optional apt pydantic packages not available; .venv pip install will still provide them"

    # Optional build niceties; never fail the installer on these.
    DEBIAN_FRONTEND=noninteractive apt-get install -y figlet toilet lolcat >/dev/null 2>&1 || true
  else
    ui_warn "apt-get not found; skipping OS package install"
  fi
}

collect_config() {
  ui_phase 2 "INSTALL CONFIGURATION"
  local public_ip default_domain default_project default_user
  public_ip="$(curl -4fsS --max-time 5 https://ifconfig.me 2>/dev/null || curl -4fsS --max-time 5 http://ifconfig.me 2>/dev/null || echo 127.0.0.1)"
  default_domain="${LFTR_DOMAIN:-$public_ip}"
  default_project="${GOOGLE_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
  default_project="${default_project//\(unset\)/}"
  default_project="${default_project:-broadcaster-fishmap}"
  default_user="${INSTALL_USER:-${SUDO_USER:-$(logname 2>/dev/null || echo lftr)}}"
  [[ "$default_user" == "root" || -z "$default_user" ]] && default_user="lftr"

  pause_msg "LFTR Broadcast / Marine Intelligence Globe installer. It can configure nginx, TLS, local UFW firewall, Google Cloud firewall rules, and Vertex AI project settings. Defaults target ~/broadcast and backend port 8787."

  INSTALL_USER="$(prompt_default "Linux user that should own/run the app" "$default_user")"
  APP_DIR="$(prompt_default "Install directory" "/home/${INSTALL_USER}/broadcast")"
  SERVICE_NAME="$(prompt_default "systemd service name" "broadcast")"
  DOMAIN="$(prompt_default "Public domain or IP for nginx/TLS" "$default_domain")"
  EMAIL="$(prompt_default "Email for Let's Encrypt" "admin@${DOMAIN}")"
  APP_PORT="$(prompt_default "Backend app port used by Uvicorn" "${LFTR_PORT:-8787}")"
  HTTP_PORT="$(prompt_default "Public HTTP port" "80")"
  HTTPS_PORT="$(prompt_default "Public HTTPS port" "443")"
  FIREWALL_PORTS="$(prompt_default "Local/GCP firewall TCP ports to open" "22,${HTTP_PORT},${HTTPS_PORT}")"
  FIREWALL_PORTS="$(normalize_ports_csv "$FIREWALL_PORTS")"
  if prompt_yes_no "Also expose backend app port ${APP_PORT} publicly? Usually no behind nginx." "no"; then
    FIREWALL_PORTS="$(normalize_ports_csv "${FIREWALL_PORTS},${APP_PORT}")"
  fi

  GOOGLE_PROJECT_ID="$(prompt_default "Google Cloud project ID" "$default_project")"
  GCP_NETWORK="$(prompt_default "GCP VPC network for firewall rule" "default")"
  GCP_FIREWALL_RULE="$(prompt_default "GCP firewall rule name" "lftr-broadcast-web")"
  GCP_TARGET_TAGS="$(prompt_default "Optional GCP target tags, comma-separated blank for all" "")"
  MAPS_API_KEY="$(prompt_default "Google Maps JS API key" "${LFTR_GOOGLE_MAPS_API_KEY:-replace-me}")"
  VERTEX_LOCATION="$(prompt_default "Vertex AI location" "${VERTEX_LOCATION:-global}")"
  VERTEX_MODEL="$(prompt_default "Vertex AI model" "${VERTEX_MODEL:-gemini-2.5-flash}")"
  GCP_KEY="$(prompt_default "Optional GCP service-account JSON key path" "${GCP_KEY:-/etc/broadcast/gcp-key.json}")"

  CONFIGURE_NGINX=0; SETUP_TLS=0; CONFIGURE_UFW=0; CONFIGURE_GCP_FIREWALL=0; ENABLE_VERTEX=0; INSTALL_SERVICE=0; BUILD_FRONTEND=0
  prompt_yes_no "Build Python venv and frontend now?" "yes" && BUILD_FRONTEND=1 || BUILD_FRONTEND=0
  prompt_yes_no "Configure nginx for /, /gfs, /broadcast, /watch, WebSockets, and SSE?" "yes" && CONFIGURE_NGINX=1 || CONFIGURE_NGINX=0
  prompt_yes_no "Request/renew Let's Encrypt TLS certificate?" "yes" && SETUP_TLS=1 || SETUP_TLS=0
  prompt_yes_no "Open selected ports locally with ufw?" "yes" && CONFIGURE_UFW=1 || CONFIGURE_UFW=0
  prompt_yes_no "Open selected ports remotely in Google Cloud firewall with gcloud?" "yes" && CONFIGURE_GCP_FIREWALL=1 || CONFIGURE_GCP_FIREWALL=0
  prompt_yes_no "Configure Google project and enable Vertex AI/Speech/Text-to-Speech APIs?" "yes" && ENABLE_VERTEX=1 || ENABLE_VERTEX=0
  prompt_yes_no "Install/restart systemd service?" "yes" && INSTALL_SERVICE=1 || INSTALL_SERVICE=0

  if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    ui_warn "DOMAIN looks like an IP; TLS will be skipped because public CA certificates need a domain."
    SETUP_TLS=0
  fi

  mkdir -p /etc/broadcast
  cat > /etc/broadcast/install.env <<CFG
DOMAIN=${DOMAIN}
APP_DIR=${APP_DIR}
APP_PORT=${APP_PORT}
HTTP_PORT=${HTTP_PORT}
HTTPS_PORT=${HTTPS_PORT}
FIREWALL_PORTS=${FIREWALL_PORTS}
SERVICE_NAME=${SERVICE_NAME}
GOOGLE_PROJECT_ID=${GOOGLE_PROJECT_ID}
GOOGLE_CLOUD_PROJECT=${GOOGLE_PROJECT_ID}
MAPS_API_KEY=${MAPS_API_KEY}
GOOGLE_MAPS_API_KEY=${MAPS_API_KEY}
LFTR_GOOGLE_MAPS_API_KEY=${MAPS_API_KEY}
LFTR_GOOGLE_PROJECT_ID=${GOOGLE_PROJECT_ID}
LFTR_GOOGLE_CLOUD_PROJECT=${GOOGLE_PROJECT_ID}
LFTR_GOOGLE_CLOUD_REGION=${VERTEX_LOCATION}
GOOGLE_CLOUD_REGION=${VERTEX_LOCATION}
VERTEX_LOCATION=${VERTEX_LOCATION}
LFTR_VERTEX_LOCATION=${VERTEX_LOCATION}
VERTEX_MODEL=${VERTEX_MODEL}
LFTR_VERTEX_MODEL=${VERTEX_MODEL}
AI_PROVIDER=vertex
LFTR_AI_PROVIDER=vertex
GCP_KEY=${GCP_KEY}
LFTR_GCP_KEY=${GCP_KEY}
GCP_NETWORK=${GCP_NETWORK}
GCP_FIREWALL_RULE=${GCP_FIREWALL_RULE}
GCP_TARGET_TAGS=${GCP_TARGET_TAGS}
CERTBOT_EMAIL=${EMAIL}
CFG

  ui_ok "Configuration saved to /etc/broadcast/install.env"
}

sync_app_to_target() {
  ui_phase 3 "APP SYNC + PYTHON/FRONTEND BUILD"
  id -u "$INSTALL_USER" >/dev/null 2>&1 || useradd -m "$INSTALL_USER"
  mkdir -p "$APP_DIR" /etc/broadcast

  local root_real app_real
  root_real="$(realpath "$ROOT_DIR")"
  app_real="$(realpath "$APP_DIR" 2>/dev/null || echo "$APP_DIR")"

  if [[ "$root_real" == "$app_real" ]]; then
    ui_ok "Installer is already running from APP_DIR=$APP_DIR; no package sync needed"
  else
    ui_step "Syncing package from $ROOT_DIR to $APP_DIR"
    rsync -a --delete \
      --exclude '.git/' --exclude '.venv/' --exclude 'venv/' --exclude 'node_modules/' \
      --exclude 'frontend/node_modules/' --exclude '__pycache__/' --exclude '*.pyc' \
      --exclude 'data/cache/' --exclude '.cache/' \
      "$ROOT_DIR/" "$APP_DIR/"
  fi

  chown -R "$INSTALL_USER:$INSTALL_USER" "$APP_DIR"
  mkdir -p "$APP_DIR/data/cache" "$APP_DIR/data/uploads/broadcast" \
    "$APP_DIR/.cache/gfs" "$APP_DIR/.cache/rtofs" "$APP_DIR/.cache/postgis" \
    "$APP_DIR/data/cache/chlorophyll" "$APP_DIR/data/cache/usgs" "$APP_DIR/data/cache/lightning"
  chown -R "$INSTALL_USER:$INSTALL_USER" "$APP_DIR/data" "$APP_DIR/.cache"

  if [[ "$BUILD_FRONTEND" == "1" ]]; then
    ui_step "Creating Python virtualenv and installing package"
    sudo -u "$INSTALL_USER" -H bash -lc "cd '$APP_DIR' && python3 -m venv .venv && . .venv/bin/activate && python -m pip install --upgrade pip setuptools wheel && python -m pip install -r requirements.txt && python -m pip install -e . && python -m pip install 'pydantic>=2.7,<3.0' 'pydantic-settings>=2.3,<3.0' && python scripts/check_python_deps.py"

    if command -v npm >/dev/null 2>&1; then
      ui_step "Installing/building frontend with Maps key"
      ui_ok "Using public npm registry and sanitizing any sandbox/internal package-lock before install"
      cat > "$APP_DIR/frontend/.env.production" <<ENV
VITE_GOOGLE_MAPS_API_KEY=${MAPS_API_KEY}
ENV
      chown "$INSTALL_USER:$INSTALL_USER" "$APP_DIR/frontend/.env.production"
            sudo -u "$INSTALL_USER" -H bash -lc "cd '$APP_DIR/frontend' \
        && cat > .npmrc <<'NPMRC'
registry=https://registry.npmjs.org/
audit=false
fund=false
fetch-retries=2
fetch-retry-factor=2
fetch-retry-mintimeout=10000
fetch-retry-maxtimeout=60000
NPMRC
        if [[ -f package-lock.json ]] && grep -qE 'applied-caas|artifactory|internal\\.api\\.openai' package-lock.json; then
          echo 'Removing sandbox/internal package-lock.json before npm install'
          rm -f package-lock.json
          rm -rf node_modules
        fi
        if [[ -d node_modules && ! -f package-lock.json ]]; then
          echo 'Removing stale node_modules before public-registry npm install'
          rm -rf node_modules
        fi
        npm install --no-audit --no-fund --registry=https://registry.npmjs.org/ \
        && VITE_GOOGLE_MAPS_API_KEY='${MAPS_API_KEY}' npm run build"
    else
      ui_warn "npm not found; skipping frontend build. Install node/npm and rerun if dist is missing."
    fi
  else
    ui_warn "Build skipped by selection."
  fi

  write_app_env

  if [[ -x "$APP_DIR/scripts/check_gfs_renderer_geometry_reality.py" ]]; then
    ui_step "Auditing GFS Google 3D renderer geometry reality"
    sudo -u "$INSTALL_USER" -H bash -lc "cd '$APP_DIR' && .venv/bin/python scripts/check_gfs_renderer_geometry_reality.py" || ui_warn "renderer geometry audit reported an issue"
  fi
  if [[ -x "$APP_DIR/scripts/check_gfs_marine_land_mask.py" ]]; then
    ui_step "Checking marine land mask call gate with harbors/bays included"
    sudo -u "$INSTALL_USER" -H bash -lc "cd '$APP_DIR' && .venv/bin/python scripts/check_gfs_marine_land_mask.py" || ui_warn "marine land mask check reported an issue"
  fi
}


configure_local_postgis() {
  ui_phase 4 "POSTGIS LIVE FEATURE STORE"
  local db_name="${LFTR_POSTGIS_DB_NAME:-lftr_next}"
  local db_user="${LFTR_POSTGIS_DB_USER:-${INSTALL_USER}}"
  if ! command -v psql >/dev/null 2>&1; then
    ui_warn "psql not found; PostGIS packages may not be installed. /gfs clouds will still use live GFS extraction, but cache writes will wait for PostGIS."
    return 0
  fi
  if ! id postgres >/dev/null 2>&1; then
    ui_warn "postgres system user not found; skipping local database bootstrap. Set LFTR_POSTGIS_DSN manually if using external PostGIS."
    return 0
  fi
  ui_step "Ensuring local PostGIS database ${db_name} and role ${db_user}"
  sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${db_user}'" | grep -q 1 \
    || sudo -u postgres createuser "${db_user}" || true
  sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${db_name}'" | grep -q 1 \
    || sudo -u postgres createdb -O "${db_user}" "${db_name}" || true
  sudo -u postgres psql -d "${db_name}" -c "CREATE EXTENSION IF NOT EXISTS postgis;" >/dev/null || true
  export LFTR_POSTGIS_DSN="${LFTR_POSTGIS_DSN:-postgresql:///${db_name}}"
  export LFTR_POSTGIS_ENABLED="${LFTR_POSTGIS_ENABLED:-true}"
  export LFTR_SPATIAL_MODE="${LFTR_SPATIAL_MODE:-postgis}"
  export LFTR_RENDER_CACHE_ENABLED="${LFTR_RENDER_CACHE_ENABLED:-true}"
  if [[ -f "$APP_DIR/scripts/migrate_postgis.py" && -x "$APP_DIR/.venv/bin/python" ]]; then
    ui_step "Running PostGIS migrations for /gfs cloud render feature tables"
    sudo -u "$INSTALL_USER" -H bash -lc "cd '$APP_DIR' && export LFTR_POSTGIS_DSN='${LFTR_POSTGIS_DSN}' LFTR_POSTGIS_ENABLED=true LFTR_RENDER_CACHE_ENABLED=true LFTR_SPATIAL_MODE=postgis && .venv/bin/python scripts/migrate_postgis.py" \
      || ui_warn "PostGIS migrations did not complete; /gfs clouds will fall back to live GFS extraction until DB is ready."
  fi
}

write_app_env() {
  ui_step "Writing $APP_DIR/.env"
  cat > "$APP_DIR/.env" <<ENV
LFTR_APP_NAME="LFTR Broadcast Marine Intelligence Globe"
LFTR_HOST="0.0.0.0"
LFTR_PORT="${APP_PORT}"
LFTR_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173,https://${DOMAIN},http://${DOMAIN}"
LFTR_GOOGLE_MAPS_API_KEY="${MAPS_API_KEY}"
GOOGLE_MAPS_API_KEY="${MAPS_API_KEY}"
LFTR_GOOGLE_PROJECT_ID="${GOOGLE_PROJECT_ID}"
LFTR_GOOGLE_CLOUD_PROJECT="${GOOGLE_PROJECT_ID}"
LFTR_GOOGLE_CLOUD_REGION="${VERTEX_LOCATION}"
GOOGLE_PROJECT_ID="${GOOGLE_PROJECT_ID}"
GOOGLE_CLOUD_PROJECT="${GOOGLE_PROJECT_ID}"
GOOGLE_CLOUD_REGION="${VERTEX_LOCATION}"
LFTR_VERTEX_LOCATION="${VERTEX_LOCATION}"
VERTEX_LOCATION="${VERTEX_LOCATION}"
LFTR_VERTEX_MODEL="${VERTEX_MODEL}"
VERTEX_MODEL="${VERTEX_MODEL}"
LFTR_AI_PROVIDER="vertex"
AI_PROVIDER="vertex"
LFTR_GCP_KEY="${GCP_KEY}"
GCP_KEY="${GCP_KEY}"
LFTR_POSTGIS_DSN="${LFTR_POSTGIS_DSN:-postgresql:///lftr_next}"
LFTR_POSTGIS_ENABLED="${LFTR_POSTGIS_ENABLED:-true}"
LFTR_SPATIAL_MODE="${LFTR_SPATIAL_MODE:-postgis}"
LFTR_STREAM_TICK_HZ="${LFTR_STREAM_TICK_HZ:-1.0}"
LFTR_TARGET_STREAM_FPS="5-10"
LFTR_CACHE_ROOT="${APP_DIR}"
# Renderer reality: Google 3D map + true polygon/polyline children are active;
# main white-sphere marker fallback paths are disabled.
LFTR_RENDERER_GEOMETRY_MODE="${LFTR_RENDERER_GEOMETRY_MODE:-google3d_extruded_polygon_cylinder_orbs_no_mock_provider_data}"
LFTR_PROVIDER_MODE="${LFTR_PROVIDER_MODE:-live}"
LFTR_RENDER_CACHE_ENABLED="${LFTR_RENDER_CACHE_ENABLED:-true}"
LFTR_RENDER_CACHE_PREFER_POSTGIS="${LFTR_RENDER_CACHE_PREFER_POSTGIS:-true}"
LFTR_RENDER_CACHE_WRITE_THROUGH="${LFTR_RENDER_CACHE_WRITE_THROUGH:-true}"
LFTR_RENDER_CACHE_ALLOW_DEGRADED="${LFTR_RENDER_CACHE_ALLOW_DEGRADED:-false}"
LFTR_STREAM_TICK_HZ="${LFTR_STREAM_TICK_HZ:-1.0}"
LFTR_GFS_ENABLED="${LFTR_GFS_ENABLED:-true}"
LFTR_GFS_NCSS_BASE_URL="${LFTR_GFS_NCSS_BASE_URL:-https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/Best}"
LFTR_GFS_NCSS_FALLBACK_URL="${LFTR_GFS_NCSS_FALLBACK_URL:-https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/TwoD}"
LFTR_GFS_TIMEOUT_SECONDS="${LFTR_GFS_TIMEOUT_SECONDS:-8}"
LFTR_GFS_TTL_SECONDS="${LFTR_GFS_TTL_SECONDS:-900}"
LFTR_GFS_MAX_GRID_POINTS="${LFTR_GFS_MAX_GRID_POINTS:-4096}"
LFTR_GFS_CACHE_DIR="${APP_DIR}/.cache/gfs"
LFTR_RTOFS_ENABLED="${LFTR_RTOFS_ENABLED:-true}"
LFTR_RTOFS_NOMADS_BASE="${LFTR_RTOFS_NOMADS_BASE:-https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod}"
LFTR_RTOFS_TIMEOUT_SECONDS="${LFTR_RTOFS_TIMEOUT_SECONDS:-8}"
LFTR_RTOFS_TTL_SECONDS="${LFTR_RTOFS_TTL_SECONDS:-900}"
LFTR_RTOFS_CACHE_DIR="${APP_DIR}/.cache/rtofs"
LFTR_RTOFS_DEPTH_LEVELS="${LFTR_RTOFS_DEPTH_LEVELS:-surface}"
LFTR_RTOFS_MAX_GRID_POINTS="${LFTR_RTOFS_MAX_GRID_POINTS:-256}"
LFTR_RTOFS_PROVIDER_MODE="${LFTR_RTOFS_PROVIDER_MODE:-live}"
LFTR_MARINE_LAND_MASK_ENABLED="${LFTR_MARINE_LAND_MASK_ENABLED:-true}"
LFTR_MARINE_LAND_MASK_SAMPLE_GRID="${LFTR_MARINE_LAND_MASK_SAMPLE_GRID:-5}"
LFTR_MARINE_LAND_MASK_COAST_BUFFER_DEG="${LFTR_MARINE_LAND_MASK_COAST_BUFFER_DEG:-0.12}"
LFTR_MARINE_LAND_MASK_ALLOW_HARBORS_BAYS="${LFTR_MARINE_LAND_MASK_ALLOW_HARBORS_BAYS:-true}"
LFTR_CHL_ENABLED="${LFTR_CHL_ENABLED:-false}"
LFTR_CHL_PROVIDER="${LFTR_CHL_PROVIDER:-disabled}"
LFTR_CHL_ERDDAP_BASE="${LFTR_CHL_ERDDAP_BASE:-https://coastwatch.pfeg.noaa.gov/erddap}"
LFTR_CHL_DATASET_ID="${LFTR_CHL_DATASET_ID:-}"
LFTR_CHL_TTL_SECONDS="${LFTR_CHL_TTL_SECONDS:-21600}"
LFTR_CHL_CACHE_DIR="${APP_DIR}/data/cache/chlorophyll"
LFTR_USGS_ENABLED="${LFTR_USGS_ENABLED:-false}"
LFTR_USGS_SOURCE_FAMILY="${LFTR_USGS_SOURCE_FAMILY:-mock}"
LFTR_USGS_CACHE_DIR="${APP_DIR}/data/cache/usgs"
LFTR_LIGHTNING_ENABLED="${LFTR_LIGHTNING_ENABLED:-false}"
LFTR_LIGHTNING_PROVIDER="${LFTR_LIGHTNING_PROVIDER:-disabled}"
LFTR_LIGHTNING_TTL_SECONDS="${LFTR_LIGHTNING_TTL_SECONDS:-120}"
LFTR_LIGHTNING_MAX_FLASHES="${LFTR_LIGHTNING_MAX_FLASHES:-50}"
LFTR_LIGHTNING_CACHE_DIR="${APP_DIR}/data/cache/lightning"
LFTR_BROADCAST_DEFAULT_ROOM="${LFTR_BROADCAST_DEFAULT_ROOM:-default}"
LFTR_BROADCAST_MAX_MESSAGE_CHARS="${LFTR_BROADCAST_MAX_MESSAGE_CHARS:-2000}"
LFTR_BROADCAST_UPLOADS_ENABLED="${LFTR_BROADCAST_UPLOADS_ENABLED:-false}"
LFTR_BROADCAST_UPLOAD_DIR="data/uploads/broadcast"
ENV
  chown "$INSTALL_USER:$INSTALL_USER" "$APP_DIR/.env"
  chmod 640 "$APP_DIR/.env" || true
}

configure_ufw_ports() {
  [[ "$CONFIGURE_UFW" == "1" ]] || { ui_warn "UFW skipped"; return 0; }
  ui_phase 4 "LOCAL FIREWALL"
  command -v ufw >/dev/null 2>&1 || apt-get install -y ufw
  IFS=',' read -ra ports <<< "$FIREWALL_PORTS"
  for p in "${ports[@]}"; do
    [[ -n "$p" ]] || continue
    ui_step "Opening local tcp/${p}"
    ufw allow "${p}/tcp" || true
  done
  ufw --force enable || true
  ui_ok "Local UFW configured for tcp:${FIREWALL_PORTS}"
}

configure_gcp() {
  ui_phase 5 "GOOGLE CLOUD + VERTEX AI"
  local metadata_project="" metadata_sa_email="" gcp_detected="no" auth_mode="disabled"

  if curl -fsS --max-time 2 -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/id >/dev/null 2>&1; then
    gcp_detected="yes"
    metadata_project="$(curl -fsS --max-time 2 -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/project/project-id 2>/dev/null || true)"
    metadata_sa_email="$(curl -fsS --max-time 2 -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email 2>/dev/null || true)"
  fi

  if [[ "$ENABLE_VERTEX" == "1" ]]; then
    if command -v gcloud >/dev/null 2>&1; then
      ui_step "Setting gcloud project to ${GOOGLE_PROJECT_ID}"
      gcloud config set project "$GOOGLE_PROJECT_ID" >/dev/null 2>&1 || ui_warn "gcloud project set failed"
      ui_step "Enabling Vertex AI/Speech/Text-to-Speech APIs"
      gcloud services enable aiplatform.googleapis.com speech.googleapis.com texttospeech.googleapis.com --project "$GOOGLE_PROJECT_ID" >/dev/null 2>&1 || ui_warn "API enable failed; check IAM permissions"
    else
      ui_warn "gcloud not installed; cannot enable Vertex AI APIs automatically"
    fi
  fi

  if [[ -n "$metadata_sa_email" ]]; then
    auth_mode="adc_attached_service_account"
  elif [[ -f "$GCP_KEY" ]]; then
    auth_mode="json_key"
    chmod 600 "$GCP_KEY" || true
  elif command -v gcloud >/dev/null 2>&1 && gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | grep -q .; then
    auth_mode="gcloud_user_adc"
  fi

  if [[ "$CONFIGURE_GCP_FIREWALL" == "1" ]]; then
    gcp_open_firewall_ports
  else
    ui_warn "GCP firewall skipped"
  fi

  cat >> "$APP_DIR/.env" <<ENV
LFTR_AI_AUTH_MODE="${auth_mode}"
AI_AUTH_MODE="${auth_mode}"
LFTR_VERTEX_ENABLED="$([[ "$ENABLE_VERTEX" == "1" ]] && echo true || echo false)"
VERTEX_ENABLED="$([[ "$ENABLE_VERTEX" == "1" ]] && echo true || echo false)"
ENV
  chown "$INSTALL_USER:$INSTALL_USER" "$APP_DIR/.env"

  ui_ok "GCP detected=${gcp_detected} metadata_project=${metadata_project:-none} attached_sa=${metadata_sa_email:-none} auth_mode=${auth_mode}"
}

gcp_open_firewall_ports() {
  if ! command -v gcloud >/dev/null 2>&1; then
    ui_warn "gcloud not found; cannot configure remote GCP firewall"
    return 0
  fi
  if [[ -z "$GOOGLE_PROJECT_ID" ]]; then
    ui_warn "GOOGLE_PROJECT_ID empty; cannot configure remote GCP firewall"
    return 0
  fi
  local allowed target_args=() tcp_ports
  tcp_ports="$(port_list_to_gcloud_tcp "$FIREWALL_PORTS")"
  [[ -n "$tcp_ports" ]] || { ui_warn "No firewall ports selected"; return 0; }
  if [[ -n "$GCP_TARGET_TAGS" ]]; then
    target_args+=(--target-tags "$GCP_TARGET_TAGS")
  fi
  ui_step "Opening GCP firewall rule ${GCP_FIREWALL_RULE}: ${tcp_ports} on network ${GCP_NETWORK}"
  if gcloud compute firewall-rules describe "$GCP_FIREWALL_RULE" --project "$GOOGLE_PROJECT_ID" >/dev/null 2>&1; then
    gcloud compute firewall-rules update "$GCP_FIREWALL_RULE" \
      --project "$GOOGLE_PROJECT_ID" \
      --network "$GCP_NETWORK" \
      --allow "$tcp_ports" \
      --source-ranges "0.0.0.0/0" \
      "${target_args[@]}" >/dev/null 2>&1 || ui_warn "GCP firewall update failed"
  else
    gcloud compute firewall-rules create "$GCP_FIREWALL_RULE" \
      --project "$GOOGLE_PROJECT_ID" \
      --network "$GCP_NETWORK" \
      --direction INGRESS \
      --priority 1000 \
      --action ALLOW \
      --rules "$tcp_ports" \
      --source-ranges "0.0.0.0/0" \
      "${target_args[@]}" >/dev/null 2>&1 || ui_warn "GCP firewall create failed"
  fi
}

write_acme_nginx() {
  local conf="/etc/nginx/sites-available/${SERVICE_NAME}-acme"
  mkdir -p /var/www/certbot/.well-known/acme-challenge
  cat > "$conf" <<NGINX
server {
    listen ${HTTP_PORT} default_server;
    listen [::]:${HTTP_PORT} default_server;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type "text/plain";
        try_files \$uri =404;
    }

    location / {
        return 200 "LFTR ACME endpoint alive.\n";
        add_header Content-Type text/plain;
    }
}
NGINX
  rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/lftr-next /etc/nginx/sites-enabled/broadcast /etc/nginx/sites-enabled/${SERVICE_NAME}-acme || true
  ln -sf "$conf" "/etc/nginx/sites-enabled/${SERVICE_NAME}-acme"
  nginx -t && systemctl restart nginx
}

setup_tls() {
  [[ "$SETUP_TLS" == "1" ]] || { ui_warn "TLS skipped"; return 0; }
  ui_phase 6 "TLS CERTIFICATE"
  if [[ "$HTTP_PORT" != "80" ]]; then
    ui_warn "Let's Encrypt HTTP-01 expects public port 80. You selected HTTP_PORT=${HTTP_PORT}; skipping certbot."
    return 0
  fi
  mkdir -p /var/www/certbot/.well-known/acme-challenge
  if [[ -s "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" && -s "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" ]]; then
    ui_ok "Existing TLS certificate found for ${DOMAIN}; keeping it"
    return 0
  fi
  write_acme_nginx
  ui_step "Requesting Let's Encrypt certificate for ${DOMAIN}"
  certbot certonly --webroot -w /var/www/certbot \
    --preferred-challenges http --agree-tos --non-interactive \
    --email "$EMAIL" --keep-until-expiring --expand -d "$DOMAIN" || ui_warn "Certbot failed; nginx will remain HTTP-only until a certificate exists"
}

write_nginx_config() {
  [[ "$CONFIGURE_NGINX" == "1" ]] || { ui_warn "nginx skipped"; return 0; }
  ui_phase 7 "NGINX"
  local conf="/etc/nginx/sites-available/${SERVICE_NAME}"
  local has_tls=0
  [[ -s "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" && -s "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" ]] && has_tls=1

  cat > "$conf" <<NGINX
server {
    listen ${HTTP_PORT};
    listen [::]:${HTTP_PORT};
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type "text/plain";
        try_files \$uri =404;
    }

    location / {
        $(if [[ "$has_tls" == "1" ]]; then echo "return 301 https://\$host\$request_uri;"; else echo "try_files \$uri \$uri/ /site.html;"; fi)
    }

    root ${APP_DIR}/frontend/dist;
    index site.html index.html;
}
NGINX

  if [[ "$has_tls" == "1" ]]; then
    cat >> "$conf" <<NGINX

server {
    listen ${HTTPS_PORT} ssl http2;
    listen [::]:${HTTPS_PORT} ssl http2;
    server_name ${DOMAIN};

    root ${APP_DIR}/frontend/dist;
    index site.html index.html;

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    location = / { try_files /site.html @lftr_backend; }
    location = /gfs { try_files /index.html @lftr_backend; }
    location = /broadcast { try_files /broadcast.html @lftr_backend; }
    location = /watch { try_files /watch.html @lftr_backend; }
    location / { try_files \$uri \$uri/ /site.html; }

    location /gfs/api/stream {
        proxy_pass http://127.0.0.1:${APP_PORT}/gfs/api/stream;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 1h;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /gfs/api/ {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /health { proxy_pass http://127.0.0.1:${APP_PORT}/health; }

    location /api/broadcast/status {
        proxy_pass http://127.0.0.1:${APP_PORT}/api/broadcast/status;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /ws/gfs { proxy_pass http://127.0.0.1:${APP_PORT}/ws/gfs; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host \$host; }
    location /ws/broadcast { proxy_pass http://127.0.0.1:${APP_PORT}/ws/broadcast; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host \$host; }
    location /ws/watch { proxy_pass http://127.0.0.1:${APP_PORT}/ws/watch; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host \$host; }
    location /ws/chat { proxy_pass http://127.0.0.1:${APP_PORT}/ws/chat; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host \$host; }

    location @lftr_backend {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
NGINX
  else
    cat >> "$conf" <<NGINX

# HTTP-only runtime block because no TLS certificate is installed yet.
server {
    listen ${HTTP_PORT};
    listen [::]:${HTTP_PORT};
    server_name ${DOMAIN};

    root ${APP_DIR}/frontend/dist;
    index site.html index.html;

    location = / { try_files /site.html @lftr_backend; }
    location = /gfs { try_files /index.html @lftr_backend; }
    location = /broadcast { try_files /broadcast.html @lftr_backend; }
    location = /watch { try_files /watch.html @lftr_backend; }
    location / { try_files \$uri \$uri/ /site.html; }

    location /gfs/api/stream { proxy_pass http://127.0.0.1:${APP_PORT}/gfs/api/stream; proxy_http_version 1.1; proxy_buffering off; proxy_cache off; proxy_read_timeout 1h; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; }
    location /gfs/api/ { proxy_pass http://127.0.0.1:${APP_PORT}; proxy_http_version 1.1; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; }
    location /health { proxy_pass http://127.0.0.1:${APP_PORT}/health; }
    location /api/broadcast/status { proxy_pass http://127.0.0.1:${APP_PORT}/api/broadcast/status; proxy_http_version 1.1; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; }
    location /ws/gfs { proxy_pass http://127.0.0.1:${APP_PORT}/ws/gfs; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host \$host; }
    location /ws/broadcast { proxy_pass http://127.0.0.1:${APP_PORT}/ws/broadcast; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host \$host; }
    location /ws/watch { proxy_pass http://127.0.0.1:${APP_PORT}/ws/watch; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host \$host; }
    location /ws/chat { proxy_pass http://127.0.0.1:${APP_PORT}/ws/chat; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host \$host; }

    location @lftr_backend { proxy_pass http://127.0.0.1:${APP_PORT}; proxy_http_version 1.1; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; }
}
NGINX
  fi

  # The first HTTP server block only redirects when TLS exists. Avoid duplicate listeners if HTTP-only.
  if [[ "$has_tls" != "1" ]]; then
    # remove the preliminary server block and keep only the HTTP runtime block
    awk 'BEGIN{block=0; seen=0} /^# HTTP-only runtime block/{seen=1} seen{print}' "$conf" > "${conf}.tmp" && mv "${conf}.tmp" "$conf"
  fi

  rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/lftr-next /etc/nginx/sites-enabled/broadcast /etc/nginx/sites-enabled/${SERVICE_NAME}-acme || true
  ln -sf "$conf" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
  nginx -t
  systemctl restart nginx
  systemctl enable nginx
  ui_ok "nginx configured for ${DOMAIN} → app port ${APP_PORT}"
}

install_systemd_service() {
  [[ "$INSTALL_SERVICE" == "1" ]] || { ui_warn "systemd skipped"; return 0; }
  ui_phase 8 "SYSTEMD SERVICE"
  local service="/etc/systemd/system/${SERVICE_NAME}.service"
  cat > "$service" <<SERVICE
[Unit]
Description=LFTR Broadcast Marine Intelligence Globe
After=network.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=-${APP_DIR}/.env
EnvironmentFile=-/etc/broadcast/install.env
ExecStartPre=/usr/bin/mkdir -p ${APP_DIR}/.cache/gfs ${APP_DIR}/.cache/rtofs ${APP_DIR}/.cache/postgis
ExecStart=${APP_DIR}/.venv/bin/python -m app.main
Restart=always
RestartSec=5
TimeoutStopSec=12
KillMode=control-group
User=${INSTALL_USER}
Group=${INSTALL_USER}

[Install]
WantedBy=multi-user.target
SERVICE
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
  ui_ok "systemd service ${SERVICE_NAME}.service installed and restarted"
}

health_checks() {
  ui_phase 9 "HEALTH CHECKS"
  local tries=45 code=""
  for ((i=1; i<=tries; i++)); do
    code="$(curl --noproxy '*' -sS -m 2 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${APP_PORT}/health" 2>/dev/null || true)"
    if [[ "$code" =~ ^(2|3) ]]; then
      ui_ok "Backend health ready on port ${APP_PORT} (${code})"
      break
    fi
    if (( i % 10 == 0 )); then ui_warn "Waiting for backend health attempt ${i}/${tries} code=${code:-connect}"; fi
    sleep 1
  done
  if [[ ! "$code" =~ ^(2|3) ]]; then
    ui_warn "Backend health did not answer yet. Check: journalctl -u ${SERVICE_NAME} -n 100 --no-pager"
  fi

  if [[ -x "$APP_DIR/scripts/check_site_routes.py" ]]; then
    sudo -u "$INSTALL_USER" -H bash -lc "cd '$APP_DIR' && . .venv/bin/activate && python scripts/check_site_routes.py" || ui_warn "site route check reported an issue"
  fi
  if [[ -x "$APP_DIR/scripts/check_broadcast_runtime.py" ]]; then
    sudo -u "$INSTALL_USER" -H bash -lc "cd '$APP_DIR' && . .venv/bin/activate && python scripts/check_broadcast_runtime.py" || ui_warn "broadcast runtime check reported an issue"
  fi
  if [[ -x "$APP_DIR/scripts/check_gfs_renderer_geometry_reality.py" ]]; then
    sudo -u "$INSTALL_USER" -H bash -lc "cd '$APP_DIR' && .venv/bin/python scripts/check_gfs_renderer_geometry_reality.py" || ui_warn "renderer geometry audit reported an issue"
  fi

  ui_ok "Install completed."
  ui_line
  say "${C_CYAN}App dir:${C_RESET} ${APP_DIR}"
  say "${C_CYAN}Service:${C_RESET} ${SERVICE_NAME}.service"
  say "${C_CYAN}Backend:${C_RESET} http://127.0.0.1:${APP_PORT}"
  say "${C_CYAN}Public:${C_RESET} http://${DOMAIN}${HTTPS_PORT:+ / https://${DOMAIN}}"
  say "${C_CYAN}Routes:${C_RESET} /  /gfs  /broadcast  /watch"
  say "${C_CYAN}Renderer:${C_RESET} Google 3D polygon/polyline visuals; marker fallback disabled for main white-sphere layers; see docs/gfs_renderer_geometry_reality.md"
  say "${C_CYAN}No-mock data:${C_RESET} /gfs/api/stream emits live/last-good provider data or honest no_data patches"
  say "${C_CYAN}PostGIS-first clouds:${C_RESET} cloud feature recipes write-through/read-through lftr.cloud_render_features when LFTR_POSTGIS_DSN is reachable"
}

main() {
  need_root "$@"
  install_bootstrap_packages
  collect_config
  sync_app_to_target
  configure_local_postgis
  configure_ufw_ports
  configure_gcp
  setup_tls
  write_nginx_config
  install_systemd_service
  health_checks
}

main "$@"
