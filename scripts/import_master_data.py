#!/usr/bin/env python3
"""Import official UniHack reference XLSX files into SQLite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from forgecat.config import RAW_DATA_DIR, REFERENCE_FILES
from forgecat.db import build_indexes


def main() -> None:
    print(f"Reference data directory: {RAW_DATA_DIR}")
    print("\nExpected files:")
    for key, name in REFERENCE_FILES.items():
        path = RAW_DATA_DIR / name
        status = "FOUND" if path.exists() else "missing"
        print(f"  [{status}] {name}")

    stats = build_indexes(force=True)
    out = ROOT / "output" / "import_stats.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print("\nImport complete:")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
