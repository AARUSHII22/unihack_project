from __future__ import annotations

import json
import re
from typing import Any

from rapidfuzz import fuzz, process

from forgecat.config import CONFIDENCE_THRESHOLD
from forgecat.db import get_connection
from forgecat.ingest import normalize_mpn


def _desc_lower(desc: str) -> str:
    return f" {desc.lower()} "


def resolve_manufacturer(
    part_manuf: str | None,
    part_desc: str,
) -> dict[str, Any]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM manufacturers").fetchall()
    conn.close()

    desc = _desc_lower(part_desc or "")
    distributor = (part_manuf or "").lower()
    candidates: list[dict[str, Any]] = []

    for row in rows:
        hints = json.loads(row["desc_hints"] or "[]")
        hint_match = any(h in desc for h in hints)
        dist_match = (
            row["distributor_pattern"].lower() in distributor
            or distributor in row["distributor_pattern"].lower()
            or row["distributor_pattern"].lower() == distributor
        )
        if not hint_match and not dist_match:
            continue

        score = 0
        if row["distributor_pattern"].lower() == distributor:
            score = 95
        elif dist_match:
            score += 75
        if hint_match:
            score += 25
        score = min(score, 100)

        candidates.append(
            {
                "manufacturer_name": row["manufacturer_name"],
                "brand_name": row["brand_name"],
                "code": row["code"],
                "score": score,
            }
        )

    if not candidates and distributor:
        names = list({r["manufacturer_name"] for r in rows})
        match = process.extractOne(part_manuf or "", names, scorer=fuzz.token_set_ratio)
        if match and match[1] >= 60:
            for row in rows:
                if row["manufacturer_name"] == match[0]:
                    candidates.append(
                        {
                            "manufacturer_name": row["manufacturer_name"],
                            "brand_name": row["brand_name"],
                            "code": row["code"],
                            "score": int(match[1]),
                        }
                    )
                    break

    if not candidates and part_manuf:
        cleaned = re.sub(r"\s*\([^)]*\)", "", part_manuf).strip()
        if cleaned and cleaned != "-":
            candidates.append(
                {
                    "manufacturer_name": cleaned,
                    "brand_name": cleaned,
                    "code": "",
                    "score": 50,
                }
            )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    top = candidates[0] if candidates else None
    needs_review: list[dict[str, str]] = []

    if not top:
        needs_review.append({"field": "MANUFACTURER_NAME", "reason": "no manufacturer candidate matched"})
        return {
            "manufacturer_name": "",
            "brand_name": "",
            "code": "",
            "score": 0,
            "candidates": [],
            "needs_review": needs_review,
        }

    if top["score"] < CONFIDENCE_THRESHOLD:
        needs_review.append(
            {"field": "MANUFACTURER_NAME", "reason": f"low confidence ({top['score']}<{CONFIDENCE_THRESHOLD})"}
        )

    brand = top["brand_name"] or top["manufacturer_name"]
    return {
        "manufacturer_name": top["manufacturer_name"],
        "brand_name": brand,
        "code": top["code"],
        "score": top["score"],
        "candidates": candidates[:5],
        "needs_review": needs_review,
    }


def detect_duplicates(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for row in rows:
        key = normalize_mpn(str(row.get("Mfg_Part_Num", "")))
        buckets.setdefault(key, []).append(str(row.get("Mfg_Part_Num", "")))
    return {k: v for k, v in buckets.items() if len(v) > 1}
