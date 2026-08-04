#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.migrations import run_migrations

if not os.environ.get('LFTR_POSTGIS_DSN'):
    raise SystemExit('LFTR_POSTGIS_DSN is not configured; refusing to run migrations')
print(json.dumps(run_migrations()))
