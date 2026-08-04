#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${1:-${APP_DIR:-$HOME/broadcast}}"
CFG="$APP_DIR/app/core/config.py"
ENVF="$APP_DIR/.env"
if [[ ! -f "$CFG" ]]; then
  echo "Missing $CFG" >&2
  exit 1
fi
python3 - "$CFG" <<'PYFIX'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
if 'extra="ignore"' not in s:
    s = s.replace('SettingsConfigDict(env_file=".env", env_prefix="LFTR_")', 'SettingsConfigDict(env_file=".env", env_prefix="LFTR_", extra="ignore")')
if 'vertex_model: str' not in s:
    anchor = '    google_maps_api_key: str = ""\n'
    insert = '    google_maps_api_key: str = ""\n\n    # Deployment / Google Cloud / AI placeholders.\n    google_project_id: str = ""\n    google_cloud_project: str = ""\n    google_cloud_region: str = "global"\n    vertex_location: str = "global"\n    vertex_model: str = "gemini-2.5-flash"\n    vertex_enabled: bool = False\n    ai_provider: str = "none"\n    ai_auth_mode: str = "unset"\n    gcp_key: str = ""\n'
    s = s.replace(anchor, insert)
p.write_text(s)
print(f"patched {p}")
PYFIX
if [[ -f "$ENVF" ]]; then
  getv(){ grep -E "^$1=" "$ENVF" | tail -1 | cut -d= -f2- | sed 's/^"//; s/"$//'; }
  gp="$(getv GOOGLE_PROJECT_ID || true)"
  gl="$(getv GOOGLE_CLOUD_REGION || true)"
  vl="$(getv VERTEX_LOCATION || true)"
  vm="$(getv VERTEX_MODEL || true)"
  ap="$(getv AI_PROVIDER || true)"
  gk="$(getv GCP_KEY || true)"
  am="$(getv AI_AUTH_MODE || true)"
  ve="$(getv VERTEX_ENABLED || true)"
  {
    if [[ -n "$gp" ]] && ! grep -q '^LFTR_GOOGLE_PROJECT_ID=' "$ENVF"; then echo "LFTR_GOOGLE_PROJECT_ID=\"$gp\""; fi
    if [[ -n "$gp" ]] && ! grep -q '^LFTR_GOOGLE_CLOUD_PROJECT=' "$ENVF"; then echo "LFTR_GOOGLE_CLOUD_PROJECT=\"$gp\""; fi
    if [[ -n "${gl:-$vl}" ]] && ! grep -q '^LFTR_GOOGLE_CLOUD_REGION=' "$ENVF"; then echo "LFTR_GOOGLE_CLOUD_REGION=\"${gl:-$vl}\""; fi
    if [[ -n "$vl" ]] && ! grep -q '^LFTR_VERTEX_LOCATION=' "$ENVF"; then echo "LFTR_VERTEX_LOCATION=\"$vl\""; fi
    if [[ -n "$vm" ]] && ! grep -q '^LFTR_VERTEX_MODEL=' "$ENVF"; then echo "LFTR_VERTEX_MODEL=\"$vm\""; fi
    if [[ -n "$ap" ]] && ! grep -q '^LFTR_AI_PROVIDER=' "$ENVF"; then echo "LFTR_AI_PROVIDER=\"$ap\""; fi
    if [[ -n "$gk" ]] && ! grep -q '^LFTR_GCP_KEY=' "$ENVF"; then echo "LFTR_GCP_KEY=\"$gk\""; fi
    if [[ -n "$am" ]] && ! grep -q '^LFTR_AI_AUTH_MODE=' "$ENVF"; then echo "LFTR_AI_AUTH_MODE=\"$am\""; fi
    if [[ -n "$ve" ]] && ! grep -q '^LFTR_VERTEX_ENABLED=' "$ENVF"; then echo "LFTR_VERTEX_ENABLED=\"$ve\""; fi
  } >> "$ENVF"
  echo "mirrored LFTR_* runtime env values in $ENVF"
fi
echo "Now run: sudo systemctl restart broadcast && curl -i http://127.0.0.1:8787/health"
