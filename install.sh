#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash install.sh" >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR=/opt/cascade-cad
STORAGE_DIR=/var/lib/cascade-cad
ENV_FILE=/etc/cascade-cad.env
SERVICE_USER=cascadecad
OLD_STORAGE=/var/lib/webcad-xbf

apt-get update
apt-get install -y python3 python3-venv python3-pip curl ca-certificates rsync \
  libgl1 libglu1-mesa libx11-6 libxext6 libxrender1 libsm6 libice6 libgomp1 freecad-python3 ffmpeg

# Stop the v0.1.0 service names if this is an in-place rename/upgrade.
systemctl disable --now webcad-xbf-worker.service webcad-xbf.service 2>/dev/null || true

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home "$STORAGE_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

mkdir -p "$INSTALL_DIR" "$STORAGE_DIR"

# Preserve projects from the earlier XBF WebCAD name when present.
if [[ -d "$OLD_STORAGE" ]] && [[ -z "$(find "$STORAGE_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "Migrating existing project data from $OLD_STORAGE to $STORAGE_DIR"
  rsync -a "$OLD_STORAGE/" "$STORAGE_DIR/"
fi

rsync -a --delete \
  --exclude='.venv' \
  --exclude='webcad_xbf/static/vendor/three/*.js' \
  "$SOURCE_DIR/" "$INSTALL_DIR/"
chown -R root:root "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$STORAGE_DIR"

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
"$INSTALL_DIR/.venv/bin/pip" install --prefer-binary -e "$INSTALL_DIR"
"$INSTALL_DIR/.venv/bin/pip" check
"$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/scripts/check_runtime.py"
if [[ ! -x "$INSTALL_DIR/scripts/freecad_import_fcstd.py" ]]; then
  echo "ERROR: FCStd import helper is missing or not executable" >&2
  exit 1
fi
ln -sfn "$INSTALL_DIR/.venv/bin/cascade-cad-maintenance" /usr/local/sbin/cascade-cad-maintenance
ln -sfn "$INSTALL_DIR/scripts/diagnose_server.sh" /usr/local/sbin/cascade-cad-diagnose
"$INSTALL_DIR/scripts/vendor_frontend.sh" "$INSTALL_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$INSTALL_DIR/env.example" "$ENV_FILE"
  secret=$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)
  sed -i "s#replace-with-a-long-random-value#$secret#" "$ENV_FILE"
fi
# Large-model migration: update only the former stock value. A custom administrator
# value is never overwritten during upgrades.
if grep -q '^CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES=750000$' "$ENV_FILE"; then
  sed -i 's/^CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES=750000$/CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES=5000000/' "$ENV_FILE"
fi
if ! grep -q '^CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES=' "$ENV_FILE"; then
  printf '\n# Maximum mesh triangles for streamed faceted STEP fallback.\nCASCADE_CAD_MAX_FACETED_STEP_TRIANGLES=5000000\n' >> "$ENV_FILE"
fi
if ! grep -q '^CASCADE_CAD_STEP_EXPORT_TIMEOUT_SECONDS=' "$ENV_FILE"; then
  printf 'CASCADE_CAD_STEP_EXPORT_TIMEOUT_SECONDS=3600
' >> "$ENV_FILE"
fi
if ! grep -q '^CASCADE_CAD_FACETED_STEP_CHUNK_TRIANGLES=' "$ENV_FILE"; then
  printf 'CASCADE_CAD_FACETED_STEP_CHUNK_TRIANGLES=1000
' >> "$ENV_FILE"
fi
if ! grep -q '^CASCADE_CAD_MAX_CSG_TRIANGLES=' "$ENV_FILE"; then
  printf 'CASCADE_CAD_MAX_CSG_TRIANGLES=10000000
' >> "$ENV_FILE"
fi
for setting in \
  CASCADE_CAD_FCSTD_IMPORT_TIMEOUT_SECONDS=3600 \
  CASCADE_CAD_FCSTD_RECOMPUTE=1 \
  CASCADE_CAD_FCSTD_INCLUDE_HIDDEN=0 \
  CASCADE_CAD_FACETED_WORKERS=2 \
  CASCADE_CAD_FACETED_QUEUE_DEPTH=60 \
  CASCADE_CAD_FACETED_MEMORY_BUDGET_GB=10 \
  CASCADE_CAD_FACETED_CACHE_ENABLED=1 \
  CASCADE_CAD_FACETED_CACHE_MAX_BYTES=21474836480 \
  CASCADE_CAD_FACETED_DIRECT_OCP=1 \
  CASCADE_CAD_FACETED_FREECAD_FALLBACK=1 \
  CASCADE_CAD_FACETED_UNIFY_SAME_DOMAIN=1; do
  key="${setting%%=*}"
  if ! grep -q "^${key}=" "$ENV_FILE"; then
    printf '%s
' "$setting" >> "$ENV_FILE"
  fi
done
chmod 640 "$ENV_FILE"
chown root:"$SERVICE_USER" "$ENV_FILE"

install -m 0644 "$INSTALL_DIR/deploy/systemd/cascade-cad.service" \
  /etc/systemd/system/cascade-cad.service
install -m 0644 "$INSTALL_DIR/deploy/systemd/cascade-cad-worker.service" \
  /etc/systemd/system/cascade-cad-worker.service
rm -f /etc/systemd/system/webcad-xbf.service /etc/systemd/system/webcad-xbf-worker.service

# Real kernel smoke test: write XBF, reopen it, then write STEP and GLB.
mkdir -p "$STORAGE_DIR/diagnostics" "$STORAGE_DIR/.config"
chown -R "$SERVICE_USER:$SERVICE_USER" "$STORAGE_DIR/diagnostics" "$STORAGE_DIR/.config"
su -s /bin/bash "$SERVICE_USER" -c \
  "cd '$STORAGE_DIR/diagnostics' && HOME='$STORAGE_DIR' XDG_CONFIG_HOME='$STORAGE_DIR/.config' '$INSTALL_DIR/.venv/bin/python' -m webcad_xbf.sample '$STORAGE_DIR/diagnostics'"
su -s /bin/bash "$SERVICE_USER" -c \
  "cd '$STORAGE_DIR/diagnostics' && HOME='$STORAGE_DIR' XDG_CONFIG_HOME='$STORAGE_DIR/.config' '$INSTALL_DIR/.venv/bin/python' '$INSTALL_DIR/scripts/check_combine.py' '$STORAGE_DIR/diagnostics/combine-smoke'"
su -s /bin/bash "$SERVICE_USER" -c \
  "cd '$STORAGE_DIR/diagnostics' && HOME='$STORAGE_DIR' XDG_CONFIG_HOME='$STORAGE_DIR/.config' '$INSTALL_DIR/.venv/bin/python' '$INSTALL_DIR/scripts/check_modeling.py' '$STORAGE_DIR/diagnostics/modeling-smoke'"
HARD_SPEED_STATUS="$STORAGE_DIR/diagnostics/hard-speed-smoke.status"
if su -s /bin/bash "$SERVICE_USER" -c \
  "cd '$STORAGE_DIR/diagnostics' && HOME='$STORAGE_DIR' XDG_CONFIG_HOME='$STORAGE_DIR/.config' '$INSTALL_DIR/.venv/bin/python' '$INSTALL_DIR/scripts/check_hard_speed.py' '$STORAGE_DIR/diagnostics/hard-speed-smoke'"; then
  printf 'ok
' > "$HARD_SPEED_STATUS"
else
  printf 'failed
' > "$HARD_SPEED_STATUS"
  echo "WARNING: direct OCP hard-speed smoke test failed; FreeCAD fallback remains enabled." >&2
fi
chown "$SERVICE_USER:$SERVICE_USER" "$HARD_SPEED_STATUS"
STEP_SMOKE_STATUS="$STORAGE_DIR/diagnostics/step-export-smoke.status"
if su -s /bin/bash "$SERVICE_USER" -c \
  "cd '$STORAGE_DIR/diagnostics' && HOME='$STORAGE_DIR' XDG_CONFIG_HOME='$STORAGE_DIR/.config' '$INSTALL_DIR/.venv/bin/python' '$INSTALL_DIR/scripts/check_step_export.py' '$STORAGE_DIR/diagnostics/step-export-smoke'"; then
  printf 'ok\n' > "$STEP_SMOKE_STATUS"
else
  printf 'failed\n' > "$STEP_SMOKE_STATUS"
  echo >&2
  echo "WARNING: STEP export smoke test failed; CascadeCAD will still be installed." >&2
  echo "The exact error remains visible above and in $STEP_SMOKE_STATUS." >&2
  echo "XBF editing and all non-STEP functions remain available." >&2
fi
chown "$SERVICE_USER:$SERVICE_USER" "$STEP_SMOKE_STATUS"
EXPORT_SMOKE_STATUS="$STORAGE_DIR/diagnostics/export-suite-smoke.status"
if su -s /bin/bash "$SERVICE_USER" -c \
  "cd '$STORAGE_DIR/diagnostics' && HOME='$STORAGE_DIR' XDG_CONFIG_HOME='$STORAGE_DIR/.config' '$INSTALL_DIR/.venv/bin/python' '$INSTALL_DIR/scripts/check_export_suite.py' '$STORAGE_DIR/diagnostics/export-suite-smoke'"; then
  printf 'ok\n' > "$EXPORT_SMOKE_STATUS"
else
  printf 'failed\n' > "$EXPORT_SMOKE_STATUS"
  echo "WARNING: one or more optional XBF/BREP/CSG/FCStd smoke exports failed." >&2
fi
chown "$SERVICE_USER:$SERVICE_USER" "$EXPORT_SMOKE_STATUS"

systemctl daemon-reload
# An in-place upgrade can inherit start-limit-hit from an older worker. Clear
# that state before enabling the new units, and print useful logs if startup
# still fails instead of ending with only systemd's generic message.
systemctl reset-failed cascade-cad.service cascade-cad-worker.service 2>/dev/null || true
systemctl enable cascade-cad.service cascade-cad-worker.service
if ! systemctl restart cascade-cad.service cascade-cad-worker.service; then
  echo >&2
  echo "ERROR: CascadeCAD services did not start. Current diagnostics:" >&2
  systemctl --no-pager --full status cascade-cad.service cascade-cad-worker.service >&2 || true
  journalctl --no-pager -n 120 -u cascade-cad.service -u cascade-cad-worker.service >&2 || true
  exit 1
fi

echo
echo "CascadeCAD installed."
echo "Local test: http://127.0.0.1:8790/cascade-cad/"
echo "HTTPS target: https://lftr.biz/cascade-cad/"
echo "Health check: curl http://127.0.0.1:8790/cascade-cad/healthz"
echo "Sample XBF: $STORAGE_DIR/diagnostics/sample-truck.xbf"
echo "Storage report: sudo cascade-cad-maintenance"
echo
echo "To combine HTTPS with your existing nginx site:"
echo "  sudo cp $INSTALL_DIR/deploy/nginx/cascade-cad-location.conf /etc/nginx/snippets/cascade-cad.conf"
echo "  add: include /etc/nginx/snippets/cascade-cad.conf;"
echo "  inside the existing lftr.biz HTTPS server block, then run:"
echo "  sudo nginx -t && sudo systemctl reload nginx"
