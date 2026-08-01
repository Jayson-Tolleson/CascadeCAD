#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/repair_frontend.sh" >&2
  exit 1
fi
INSTALL_DIR=/opt/cascade-cad
"$INSTALL_DIR/scripts/vendor_frontend.sh" "$INSTALL_DIR"
chown -R root:root "$INSTALL_DIR/webcad_xbf/static/vendor"
systemctl restart cascade-cad.service
printf '\nFrontend repaired. Force-refresh the browser with Ctrl+Shift+R.\n'
