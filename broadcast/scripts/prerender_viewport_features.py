#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.prerender.worker import precompute_viewport_render_features
from app.spatial.viewport_query import parse_bbox


def main() -> int:
    parser = argparse.ArgumentParser(description="Precompute LFTR /gfs render features into PostGIS when enabled.")
    parser.add_argument("--bbox", default="-125,32,-117,38", help="west,south,east,north")
    parser.add_argument("--tier", default="regional")
    args = parser.parse_args()
    result = precompute_viewport_render_features(parse_bbox(args.bbox), tier=args.tier)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
