#!/usr/bin/env bash
set -u

echo '=== CascadeCAD health ==='
curl -fsS http://127.0.0.1:8790/cascade-cad/healthz 2>&1 | python3 -m json.tool 2>/dev/null || \
  curl -v --max-time 10 http://127.0.0.1:8790/cascade-cad/healthz 2>&1 || true

echo
echo '=== systemd status ==='
systemctl status cascade-cad cascade-cad-worker --no-pager -l 2>&1 || true

echo
echo '=== recent application logs ==='
journalctl -u cascade-cad -u cascade-cad-worker -b -n 250 --no-pager 2>&1 || true

echo
echo '=== kernel OOM messages ==='
journalctl -k -b --no-pager 2>&1 | grep -Ei 'oom|out of memory|killed process|memory cgroup' | tail -100 || true

echo
echo '=== memory and swap ==='
free -h 2>&1 || true
swapon --show 2>&1 || true

echo
echo '=== filesystems ==='
df -h / /var/lib/cascade-cad 2>&1 || true

echo
echo '=== largest processes ==='
ps -eo pid,user,comm,%cpu,%mem,rss,vsz --sort=-rss | head -25 2>&1 || true

echo
echo '=== CascadeCAD storage dry-run ==='
if command -v cascade-cad-maintenance >/dev/null 2>&1; then
  cascade-cad-maintenance 2>&1 || true
elif [[ -x /opt/cascade-cad/.venv/bin/cascade-cad-maintenance ]]; then
  /opt/cascade-cad/.venv/bin/cascade-cad-maintenance 2>&1 || true
fi

echo
echo '=== effective large-model settings ==='
ENV_FILE=/etc/cascade-cad.env
if [[ -r "$ENV_FILE" ]]; then
  grep -E '^CASCADE_CAD_(PREVIEW_|MAX_|STEP_|FACETED_|WORKER_|JOB_|CHUNK_|STORAGE_RESERVE)' "$ENV_FILE" | sort || true
else
  echo "$ENV_FILE is not readable"
fi

echo
echo '=== service resource limits ==='
systemctl show cascade-cad cascade-cad-worker \
  -p MainPID -p MemoryCurrent -p MemoryPeak -p MemoryHigh -p MemoryMax \
  -p CPUWeight -p TasksCurrent -p TasksMax --no-pager 2>&1 || true
