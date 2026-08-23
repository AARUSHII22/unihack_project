from __future__ import annotations

import json
from typing import Any

from forgecat.db import get_connection
from forgecat.ingest import normalize_mpn


def detect_duplicates(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for row in rows:
        key = normalize_mpn(str(row.get("Mfg_Part_Num", "")))
        if key:
            buckets.setdefault(key, []).append(str(row.get("Mfg_Part_Num", "")))
    return {k: v for k, v in buckets.items() if len(v) > 1}


def annotate_duplicates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dupes = detect_duplicates(records)
    dupe_mpns = {mpn for group in dupes.values() for mpn in group}
    for record in records:
        mpn = str(record.get("Mfg_Part_Num", ""))
        if mpn in dupe_mpns:
            flags = json.loads(record.get("_needs_review", "[]"))
            flags.append({"field": "Mfg_Part_Num", "reason": "probable duplicate MPN"})
            record["_needs_review"] = json.dumps(flags)
            record["_is_duplicate"] = True
        else:
            record["_is_duplicate"] = False
    return records


def duplicate_report(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dupes = detect_duplicates(rows)
    return [{"normalized_key": k, "mpns": v} for k, v in dupes.items()]
