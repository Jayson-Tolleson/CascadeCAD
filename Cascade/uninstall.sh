#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo" >&2; exit 1; fi
systemctl disable --now cascade-cad-worker.service cascade-cad.service 2>/dev/null || true
rm -f /etc/systemd/system/cascade-cad.service /etc/systemd/system/cascade-cad-worker.service
systemctl daemon-reload
rm -f /usr/local/sbin/cascade-cad-maintenance /usr/local/sbin/cascade-cad-diagnose
rm -rf /opt/cascade-cad
printf 'CascadeCAD removed. Project data remains in /var/lib/cascade-cad\n'
printf 'Remove the nginx include/location separately if it was installed.\n'
