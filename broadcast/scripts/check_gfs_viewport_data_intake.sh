#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:-http://127.0.0.1:8787}"
BBOX="${2:--125,32,-117,38}"
TIER="${3:-regional}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1" >&2; exit 1; }; }
need curl
need jq
need python3
urlenc() { python3 - "$1" <<'PY'
import sys, urllib.parse
print(urllib.parse.quote(sys.argv[1]))
PY
}
BBOX_Q="$(urlenc "$BBOX")"

echo "== LFTR /gfs viewport data intake check =="
echo "BASE_URL=$BASE_URL"
echo "BBOX=$BBOX"
echo "TIER=$TIER"
echo

echo "-- health --"
curl -fsS "$BASE_URL/health" | jq -c .
echo

echo "-- site routes --"
for route in / /gfs /broadcast /watch; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL$route")
  echo "$route -> $code"
done
echo

echo "-- providers status --"
curl -fsS "$BASE_URL/gfs/api/providers/status" | jq '{ok, provider_mode, providers: (.providers | keys? // . // [])}'
echo

echo "-- scene frame layer names --"
curl -fsS "$BASE_URL/gfs/api/scene-frame" | jq '{ok, scene_id, layers: [.layers[].label]}'
echo

echo "-- viewport spatial counts --"
curl -fsS "$BASE_URL/gfs/api/viewport-spatial?bbox=$BBOX_Q&tier=$TIER" | jq '{ok, tier, locations: ((.locations // .reports)|length), waterbodies: (.waterbodies|length), lakes: (.lakes|length), harbors: (.harbors|length), source: .diagnostics.source, first_location: ((.locations // .reports)[0] | {id,title,latitude,longitude,source,report_count:(.report_indices|length), field_count:(.csv_fields|keys|length)})}'
echo

echo "-- locations endpoint summary --"
curl -fsS "$BASE_URL/gfs/api/locations?bbox=$BBOX_Q" | jq '{ok, count: ((.locations // .reports)|length), first: ((.locations // .reports)[0] | {id,title,latitude,longitude,source,report_count:(.report_indices|length), field_count:(.csv_fields|keys|length)})}'
echo

echo "-- boats layer summary --"
curl -fsS "$BASE_URL/gfs/api/layers/boats?bbox=$BBOX_Q" | jq '{ok, source, count: (.boats|length), first: (.boats[0] | {id,lat,lon,heading_deg,safety,model})}'
echo

echo "-- waterbodies endpoint summary --"
curl -fsS "$BASE_URL/gfs/api/waterbodies?bbox=$BBOX_Q&tier=$TIER" | jq '{ok, source, count: (.waterbodies|length), first: (.waterbodies[0] | {id,name,kind,source,area_km2,bbox})}'
echo

echo "-- SSE event summary (8 seconds max; no full payload dump) --"
set +e
timeout 8s curl -fsS -N "$BASE_URL/gfs/api/stream?bbox=$BBOX_Q&tier=$TIER" 2>/tmp/lftr_sse_curl.err | python3 -c '
import json, sys
current_event = None
seen = 0
for raw in sys.stdin:
    line = raw.strip()
    if line.startswith("event:"):
        current_event = line.split(":", 1)[1].strip()
    elif line.startswith("data:") and current_event:
        try:
            payload = json.loads(line.split(":", 1)[1].strip())
        except Exception:
            payload = {}
        summary = {"event": current_event}
        if isinstance(payload, dict):
            if "bbox" in payload:
                summary["bbox"] = payload.get("bbox")
            if "tile_id" in payload:
                summary["tile_id"] = payload.get("tile_id")
            if "locations" in payload:
                summary["locations"] = len(payload.get("locations") or [])
            if "reports" in payload and "locations" not in summary:
                summary["locations"] = len(payload.get("reports") or [])
            if "boats" in payload:
                summary["boats"] = len(payload.get("boats") or [])
            if "flashes" in payload:
                summary["flashes"] = len(payload.get("flashes") or [])
            if "channels" in payload:
                summary["channels"] = payload.get("channels")
            grid_shape = None
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None
            if "payload" in payload and isinstance(payload.get("payload"), dict):
                grid_shape = payload["payload"].get("grid_shape")
                if isinstance(payload["payload"].get("metadata"), dict):
                    metadata = payload["payload"].get("metadata")
            if "grid_shape" in payload:
                grid_shape = payload.get("grid_shape")
            if grid_shape:
                summary["grid_shape"] = grid_shape
            if metadata and isinstance(metadata.get("tile_plan"), dict):
                plan = metadata["tile_plan"]
                summary["tile_count"] = plan.get("tile_count")
                summary["tile_deg"] = plan.get("tile_deg")
                summary["parallelism"] = plan.get("parallelism")
            if "feature_count" in payload:
                summary["cloud_features"] = payload.get("feature_count")
                summary["families"] = payload.get("families")
            if "current_vector_count" in payload:
                summary["current_vectors"] = payload.get("current_vector_count")
            if "bait_cluster_count" in payload:
                summary["bait_clusters"] = payload.get("bait_cluster_count")
        print(json.dumps(summary, separators=(",", ":")))
        sys.stdout.flush()
        seen += 1
        current_event = None
        if seen >= 8:
            break
'
rc=$?
set -e
if [ "$rc" -ne 0 ] && [ "$rc" -ne 124 ]; then
  echo "! SSE summary exited with code $rc"
fi
echo

echo "✓ viewport data intake command block completed"
