"""Load the 4 CSVs and print row counts (expect 25 / 5000 / 3534 / 2723); create the SQLite app tables.

The engine reads the CSVs directly (they are small and read-only); SQLite holds app state
(sessions, consents, documents, quotes, orders, audit log).
Usage: python scripts/seed.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import config, db  # noqa: E402
from app.dataio import data_counts  # noqa: E402
from app.utils import gstin  # noqa: E402
from app.dataio import gstin_frame  # noqa: E402

counts = data_counts()
print(" / ".join(str(v) for v in counts.values()), counts)
assert counts == {"catalogue": 25, "leads": 5000, "gstin_registry": 3534, "udyam_registry": 2723}, "unexpected row counts"
ok = sum(gstin.checksum_ok(v) for v in gstin_frame()["gstin"])
print(f"GSTIN checksum passes {ok}/{len(gstin_frame())}")
db.connect()
print(f"SQLite ready at {config.DB_PATH}")
