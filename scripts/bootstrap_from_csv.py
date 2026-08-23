#!/usr/bin/env python3
"""Bootstrap project data from the two provided CSV files."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RAW = ROOT / "data" / "raw"
SEED = ROOT / "forgecat" / "seed"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)

    inp_src = ROOT / "Unihack_ Sample Dataset - Input.csv"
    out_src = ROOT / "Unihack_ Expected Output - Delivery Format.csv"

    shutil.copy2(inp_src, RAW / "Sample-1000_Items.csv")
    shutil.copy2(out_src, RAW / "Ground-Truth-Delivery-Format.csv")
    print(f"Copied input  -> {RAW / 'Sample-1000_Items.csv'}")
    print(f"Copied output -> {RAW / 'Ground-Truth-Delivery-Format.csv'}")

    inp = pd.read_csv(inp_src, dtype=str, keep_default_na=False)
    out = pd.read_csv(out_src, dtype=str, keep_default_na=False)

    manual = json.loads((SEED / "manufacturers.json").read_text(encoding="utf-8"))
    manual_patterns = {m["distributor_pattern"].lower(): m for m in manual}

    generated: list[dict] = []
    seen: set[str] = set()
    for pm in inp["Part_Manuf"].unique():
        pm = str(pm).strip()
        if not pm or pm == "-":
            continue
        if pm.lower() in seen:
            continue
        seen.add(pm.lower())

        matched = next((m for p, m in manual_patterns.items() if p in pm.lower()), None)
        if matched:
            generated.append({**matched, "distributor_pattern": pm})
        else:
            cleaned = re.sub(r"\s*\([^)]*\)", "", pm).strip()
            code_m = re.search(r"\(([^)]+)\)", pm)
            generated.append(
                {
                    "distributor_pattern": pm,
                    "manufacturer_name": cleaned,
                    "brand_name": cleaned,
                    "code": code_m.group(1) if code_m else "",
                    "desc_hints": [],
                }
            )

    (SEED / "manufacturers_generated.json").write_text(
        json.dumps(generated, indent=2), encoding="utf-8"
    )
    print(f"Generated {len(generated)} manufacturer mappings -> forgecat/seed/manufacturers_generated.json")

    heroes = json.loads((SEED / "hero_skus.json").read_text(encoding="utf-8"))
    for _, row in out.iterrows():
        mpn = str(row.get("Mfg_Part_Num", "")).strip()
        if not mpn:
            continue
        existing = heroes.get(mpn, {})
        heroes[mpn] = {
            **existing,
            "manufacturer_name": row.get("MANUFACTURER_NAME", existing.get("manufacturer_name", "")),
            "brand_name": row.get("BRAND_NAME", existing.get("brand_name", "")),
            "invoice_desc": row.get("INVOICE_DESC", existing.get("invoice_desc", "")),
            "mobile_desc": row.get("MOBILE_DESC", existing.get("mobile_desc", "")),
            "short_desc": row.get("SHORT_DESC", existing.get("short_desc", "")),
            "long_desc1": row.get("LONG_DESC1", existing.get("long_desc1", "")),
            "retail_desc": row.get("RETAIL_DESC", existing.get("retail_desc", "")),
            "marketing_description": row.get("MARKETING_DESCRIPTION", existing.get("marketing_description", "")),
            "mfr_url": row.get("MFR URL", existing.get("mfr_url", "")),
            "with_feature": (row.get("With") or existing.get("with_feature", "")).replace("With ", ""),
            "standards": row.get("Standard/Approvals", existing.get("standards", "")),
            "warranty": row.get("Warranty", existing.get("warranty", "")),
        }
    (SEED / "hero_skus.json").write_text(json.dumps(heroes, indent=2), encoding="utf-8")
    print(f"Updated {len(heroes)} hero SKU specs from ground truth")

    from forgecat.db import build_indexes

    stats = build_indexes(force=True)
    print("SQLite indexes rebuilt:", json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
