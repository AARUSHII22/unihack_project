from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from forgecat.config import INVOICE_DESC_MAX, MOBILE_DESC_MAX, MOBILE_DESC_MIN
from forgecat.db import get_connection
from forgecat.importers.ground_truth import import_ground_truth_delivery, load_ground_truth


def _normalize(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return re.sub(r"\s+", " ", text)


def _field_match(expected: str, actual: str) -> bool:
    if not expected and not actual:
        return True
    if expected == actual:
        return True
    exp = _normalize(expected).lower()
    act = _normalize(actual).lower()
    if exp == act:
        return True
    exp_compact = re.sub(r"[^a-z0-9]+", "", exp)
    act_compact = re.sub(r"[^a-z0-9]+", "", act)
    return exp_compact == act_compact


def _lov_compliance(enriched: pd.DataFrame) -> tuple[float, int, int]:
    conn = get_connection()
    lov_cells = 0
    lov_match = 0

    for _, row in enriched.iterrows():
        classpath = row.get("Classpath", "")
        for i in range(1, 51):
            label = _normalize(row.get(f"ATTRIBUTE_LABEL {i}", ""))
            value = _normalize(row.get(f"ATTRIBUTE_VALUE {i}", ""))
            if not value:
                continue
            lov_cells += 1
            allowed_row = conn.execute(
                """
                SELECT normalized_values FROM lov_attributes
                WHERE classpath = ? AND attribute_label = ?
                """,
                (classpath, label),
            ).fetchone()
            if not allowed_row:
                lov_match += 1
                continue
            allowed = json.loads(allowed_row["normalized_values"])
            if not allowed or value in allowed:
                lov_match += 1

    conn.close()
    pct = round((lov_match / lov_cells * 100) if lov_cells else 100, 2)
    return pct, lov_match, lov_cells


def score_against_ground_truth(
    enriched: pd.DataFrame,
    ground_truth_path: str | None = None,
    key_field: str = "Mfg_Part_Num",
) -> dict[str, Any]:
    if ground_truth_path:
        gt = pd.read_csv(ground_truth_path, dtype=str, keep_default_na=False)
    else:
        delivery = import_ground_truth_delivery()
        if delivery is None:
            from forgecat.config import GROUND_TRUTH_CSV

            gt = pd.read_csv(GROUND_TRUTH_CSV, dtype=str, keep_default_na=False)
        else:
            gt = delivery

    gt[key_field] = gt[key_field].astype(str)
    gt_source, gt_fmt = load_ground_truth()

    compare_fields = [
        "MANUFACTURER_NAME", "BRAND_NAME", "Classpath", "MOBILE_DESC", "INVOICE_DESC",
        "SHORT_DESC", "LONG_DESC1", "RETAIL_DESC", "MARKETING_DESCRIPTION", "With",
        "Standard/Approvals", "Warranty", "MFR URL", "Product Name",
    ]
    for i in range(1, 16):
        compare_fields.extend([f"ATTRIBUTE_LABEL {i}", f"ATTRIBUTE_VALUE {i}", f"ATTRIBUTE_UOM {i}"])

    per_row: list[dict[str, Any]] = []
    total_fields = matched_fields = 0
    field_stats: dict[str, dict[str, int]] = {}
    enriched_indexed = enriched.set_index(key_field)

    for _, gt_row in gt.iterrows():
        mpn = gt_row[key_field]
        if mpn not in enriched_indexed.index:
            per_row.append({"Mfg_Part_Num": mpn, "accuracy": 0.0, "missing": True})
            continue

        pred_row = enriched_indexed.loc[mpn]
        row_total = row_match = 0
        diffs: list[dict[str, str]] = []

        for field in compare_fields:
            if field not in gt.columns:
                continue
            expected = _normalize(gt_row.get(field, ""))
            actual = _normalize(pred_row.get(field, ""))
            if not expected:
                continue
            row_total += 1
            total_fields += 1
            field_stats.setdefault(field, {"total": 0, "match": 0})
            field_stats[field]["total"] += 1
            if _field_match(expected, actual):
                row_match += 1
                matched_fields += 1
                field_stats[field]["match"] += 1
            else:
                diffs.append({"field": field, "expected": expected, "actual": actual})

        per_row.append(
            {
                "Mfg_Part_Num": mpn,
                "accuracy": round((row_match / row_total * 100) if row_total else 0, 2),
                "matched": row_match,
                "total": row_total,
                "diffs": diffs,
            }
        )

    lov_pct, lov_match, lov_cells = _lov_compliance(enriched)

    char_checks = {"INVOICE_DESC": 0, "MOBILE_DESC": 0, "SHORT_DESC": 0}
    char_pass = {"INVOICE_DESC": 0, "MOBILE_DESC": 0, "SHORT_DESC": 0}
    for _, row in enriched.iterrows():
        tier = row.get("_depth_tier", "B")
        for field, checker in [
            ("INVOICE_DESC", lambda t: len(t) <= INVOICE_DESC_MAX),
            ("MOBILE_DESC", lambda t: tier != "A" or MOBILE_DESC_MIN <= len(t) <= MOBILE_DESC_MAX),
            ("SHORT_DESC", lambda t: len(t) > 0),
        ]:
            val = _normalize(row.get(field, ""))
            if val:
                char_checks[field] += 1
                if checker(val):
                    char_pass[field] += 1

    review_count = duplicate_count = 0
    if "_needs_review" in enriched.columns:
        for val in enriched["_needs_review"]:
            if json.loads(val) if val else []:
                review_count += 1
    if "_is_duplicate" in enriched.columns:
        duplicate_count = int(enriched["_is_duplicate"].sum())

    mfg_match = 0
    mfg_total = 0
    if "_manufacturer_score" in enriched.columns:
        for score in enriched["_manufacturer_score"]:
            mfg_total += 1
            if int(score or 0) >= 75:
                mfg_match += 1

    return {
        "field_accuracy_pct": round((matched_fields / total_fields * 100) if total_fields else 0, 2),
        "matched_fields": matched_fields,
        "total_scored_fields": total_fields,
        "ground_truth_source": str(gt_source) if gt_source else "csv_fallback",
        "ground_truth_format": gt_fmt or "csv",
        "ground_truth_rows": len(gt),
        "per_row": per_row,
        "field_stats": {k: round(v["match"] / v["total"] * 100, 2) if v["total"] else 0 for k, v in field_stats.items()},
        "lov_compliance_pct": lov_pct,
        "lov_matched_cells": lov_match,
        "lov_total_cells": lov_cells,
        "char_limit_compliance": {
            k: round((char_pass[k] / char_checks[k] * 100) if char_checks[k] else 100, 2) for k in char_checks
        },
        "manufacturer_match_rate_pct": round((mfg_match / mfg_total * 100) if mfg_total else 0, 2),
        "needs_review_count": review_count,
        "duplicate_count": duplicate_count,
        "coverage": {
            "tier_a": int((enriched["_depth_tier"] == "A").sum()) if "_depth_tier" in enriched.columns else 0,
            "tier_b": int((enriched["_depth_tier"] == "B").sum()) if "_depth_tier" in enriched.columns else 0,
            "tier_c": int((enriched["_depth_tier"] == "C").sum()) if "_depth_tier" in enriched.columns else 0,
        },
    }
