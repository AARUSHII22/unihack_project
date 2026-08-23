from __future__ import annotations

import json
from typing import Any

from rapidfuzz import fuzz, process

from forgecat.config import CONFIDENCE_THRESHOLD, FULL_DEPTH_CATEGORIES
from forgecat.db import get_connection


def classify_row(part_desc: str) -> dict[str, Any]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM classpath_index").fetchall()
    conn.close()

    desc = f" {part_desc.lower()} "
    candidates: list[dict[str, Any]] = []

    for row in rows:
        keywords = json.loads(row["keywords"])
        hits = sum(1 for kw in keywords if kw.lower() in desc)
        if hits == 0:
            continue

        score = min(50 + hits * 15, 100)
        depth = row["depth_tier"]
        fine_lower = (row["fine"] or "").lower()
        if any(cat in fine_lower or cat in desc for cat in FULL_DEPTH_CATEGORIES):
            depth = "A"

        candidate = {
            "dept": row["dept"],
            "class": row["class"],
            "fine": row["fine"],
            "classpath_string": row["classpath"],
            "product_name": row["product_name"],
            "depth_tier": depth,
            "score": score,
        }
        candidates.append(candidate)

    # Fuzzy match classpath leaf against description tokens
    if not candidates:
        leaf_names = [(r["fine"], r) for r in rows if r["fine"]]
        match = process.extractOne(part_desc, [n[0] for n in leaf_names], scorer=fuzz.partial_ratio)
        if match and match[1] >= 70:
            for name, row in leaf_names:
                if name == match[0]:
                    candidates.append(
                        {
                            "dept": row["dept"],
                            "class": row["class"],
                            "fine": row["fine"],
                            "classpath_string": row["classpath"],
                            "product_name": row["product_name"],
                            "depth_tier": row["depth_tier"],
                            "score": int(match[1]),
                        }
                    )
                    break

    candidates.sort(key=lambda c: c["score"], reverse=True)
    best = candidates[0] if candidates else None
    needs_review: list[dict[str, str]] = []

    if not best:
        needs_review.append({"field": "Classpath", "reason": "no classpath keyword match"})
        fallback = {
            "dept": "General Merchandise",
            "class": "General",
            "fine": "General Products",
            "classpath_string": "General Merchandise>General>General Products",
            "product_name": "Product",
            "depth_tier": "B",
            "score": 55,
        }
        return {**fallback, "candidates": [fallback], "needs_review": needs_review}

    if best["score"] < CONFIDENCE_THRESHOLD:
        needs_review.append(
            {"field": "Classpath", "reason": f"low classification confidence ({best['score']})"}
        )

    return {**best, "candidates": candidates[:5], "needs_review": needs_review}
