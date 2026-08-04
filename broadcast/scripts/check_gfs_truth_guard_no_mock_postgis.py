#!/usr/bin/env python3
"""Verify PostGIS only caches live-provider render rows and no truth-guard field is used."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
repo = (ROOT / "app/prerender/postgis_repository.py").read_text()
engine = (ROOT / "app/services/field_truth_engine.py").read_text()
failed = []
if "_lftr_" + "source_filter" in repo + engine:
    failed.append("old source-hiding marker still present")
if "_lftr_source_policy" not in repo:
    failed.append("PostGIS source policy marker missing")
if "source_kind" not in repo + engine:
    failed.append("source_kind live/no-data policy missing")
if 'source_kind != "live_provider"' not in repo:
    failed.append("PostGIS write cache must still require live_provider rows by default")
if ("truth" + "_guard_clear_sky") in engine or ("truth" + "_guard_empty_ocean_features") in engine:
    failed.append("old hidden empty feature patches still present")
if failed:
    raise SystemExit({"ok": False, "check": "gfs_no_mock_postgis_cache", "failed": failed})
print({"ok": True, "check": "gfs_no_mock_postgis_cache"})
