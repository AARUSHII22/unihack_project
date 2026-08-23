from __future__ import annotations

import re

from forgecat.db import get_connection


def normalize_fitting_value(attribute_type: str, raw_value: str) -> str | None:
    if not raw_value:
        return None
    conn = get_connection()
    row = conn.execute(
        """
        SELECT canonical_value FROM fittings_mappings
        WHERE attribute_type = ? AND lower(source_value) = lower(?)
        """,
        (attribute_type, raw_value.strip()),
    ).fetchone()
    if row:
        conn.close()
        return row["canonical_value"]

    row = conn.execute(
        """
        SELECT canonical_value FROM fittings_mappings
        WHERE lower(source_value) = lower(?)
        """,
        (raw_value.strip(),),
    ).fetchone()
    conn.close()
    return row["canonical_value"] if row else None


def extract_fitting_tokens(part_desc: str) -> dict[str, str]:
    desc_upper = part_desc.upper()
    found: dict[str, str] = {}

    conn = get_connection()
    rows = conn.execute("SELECT attribute_type, source_value FROM fittings_mappings").fetchall()
    conn.close()

    for row in rows:
        src = row["source_value"].upper()
        if re.search(rf"\b{re.escape(src)}\b", desc_upper):
            canon = normalize_fitting_value(row["attribute_type"], row["source_value"])
            if canon:
                found[row["attribute_type"]] = canon

    size_match = re.search(r"(\d+(?:/\d+)?)\s*(?:IN|\"|INCH)", part_desc, re.I)
    if size_match:
        found.setdefault("Size", f"{size_match.group(1)} in")

    pressure_match = re.search(r"(\d+)\s*#", part_desc)
    if pressure_match:
        found.setdefault("Pressure Rating", f"{pressure_match.group(1)} psi")

    return found
