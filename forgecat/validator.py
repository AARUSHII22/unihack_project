from __future__ import annotations

import json
import re
from typing import Any

from forgecat.config import INVOICE_DESC_MAX, MOBILE_DESC_MAX, MOBILE_DESC_MIN
from forgecat.db import get_connection


def _lov_values(classpath: str, label: str) -> list[str]:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT normalized_values FROM lov_attributes
        WHERE classpath = ? AND attribute_label = ?
        """,
        (classpath, label),
    ).fetchone()
    conn.close()
    return json.loads(row["normalized_values"]) if row else []


def _approved_uoms() -> set[str]:
    conn = get_connection()
    rows = conn.execute("SELECT approved_abbrev FROM uom_standards").fetchall()
    conn.close()
    return {r["approved_abbrev"] for r in rows}


def validate_record(record: dict[str, Any], depth_tier: str = "B") -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    classpath = record.get("Classpath", "")

    invoice = record.get("INVOICE_DESC", "")
    if invoice and len(invoice) > INVOICE_DESC_MAX:
        issues.append(
            {
                "field": "INVOICE_DESC",
                "reason": f"exceeds {INVOICE_DESC_MAX} chars ({len(invoice)})",
            }
        )
    if invoice and invoice != invoice.upper():
        issues.append({"field": "INVOICE_DESC", "reason": "must be ALL CAPS"})

    mobile = record.get("MOBILE_DESC", "")
    if depth_tier == "A" and mobile and (len(mobile) < MOBILE_DESC_MIN or len(mobile) > MOBILE_DESC_MAX):
        issues.append(
            {
                "field": "MOBILE_DESC",
                "reason": f"length {len(mobile)} outside {MOBILE_DESC_MIN}-{MOBILE_DESC_MAX}",
            }
        )

    approved_uoms = _approved_uoms()
    for i in range(1, 51):
        label = record.get(f"ATTRIBUTE_LABEL {i}")
        value = record.get(f"ATTRIBUTE_VALUE {i}")
        uom = record.get(f"ATTRIBUTE_UOM {i}")
        if not label and not value:
            continue
        if label and value:
            allowed = _lov_values(classpath, label)
            if allowed and value not in allowed:
                issues.append(
                    {
                        "field": f"ATTRIBUTE_VALUE {i}",
                        "reason": f"'{value}' not in LOV for {label}",
                    }
                )
        if uom and uom not in approved_uoms and uom not in {"dBA", "K"}:
            issues.append(
                {"field": f"ATTRIBUTE_UOM {i}", "reason": f"unapproved UOM '{uom}'"}
            )

    for field in ["MANUFACTURER_NAME", "BRAND_NAME"]:
        val = record.get(field, "")
        if val and val.startswith("--"):
            issues.append({"field": field, "reason": "placeholder value in output"})

    return issues


def merge_needs_review(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, str]] = []
    for group in groups:
        for item in group:
            key = (item.get("field", ""), item.get("reason", ""))
            if key not in seen:
                seen.add(key)
                merged.append(item)
    return merged
