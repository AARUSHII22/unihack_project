from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from forgecat.config import RAW_DATA_DIR, SEED_DIR
from forgecat.importers.xlsx_utils import find_column, first_existing, read_sheet


def import_manufacturers(raw_dir: Path | None = None) -> list[dict]:
    raw_dir = raw_dir or RAW_DATA_DIR
    path = first_existing(
        raw_dir,
        "UniCat_Manufacturer_and_Brand_List.xlsx",
        "UniCat_Manufacturer_and_Brand_List.xls",
    )
    if not path:
        generated = SEED_DIR / "manufacturers_generated.json"
        if generated.exists():
            manual = json.loads((SEED_DIR / "manufacturers.json").read_text(encoding="utf-8"))
            auto = json.loads(generated.read_text(encoding="utf-8"))
            return manual + auto
        return json.loads((SEED_DIR / "manufacturers.json").read_text(encoding="utf-8"))

    df = read_sheet(path, sheet=0)
    mfg_col = find_column(df, "MANUFACTURER_NAME", "Manufacturer Name", "manufacturer_name")
    brand_col = find_column(df, "BRAND_NAME", "Brand Name", "brand_name")
    mfg_code = find_column(df, "MANUFACTURER_CODE", "Manufacturer Code")
    brand_code = find_column(df, "BRAND_CODE", "Brand Code")

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for _, r in df.iterrows():
        mfg = str(r.get(mfg_col or "", "")).strip()
        brand = str(r.get(brand_col or "", "")).strip()
        if not mfg:
            continue
        key = (mfg, brand or mfg)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "distributor_pattern": mfg[:40],
                "manufacturer_name": mfg,
                "brand_name": brand or mfg,
                "code": str(r.get(mfg_code or "", "") or r.get(brand_code or "", "")).strip(),
                "desc_hints": [],
            }
        )
    return rows


def augment_from_input_csv(input_csv: Path) -> list[dict]:
    """Build distributor-pattern rows from Part_Manuf values in the sample input."""
    if not input_csv.exists():
        return []

    df = pd.read_csv(input_csv, dtype=str, keep_default_na=False)
    manual = {
        p["distributor_pattern"].lower(): p
        for p in json.loads((SEED_DIR / "manufacturers.json").read_text(encoding="utf-8"))
    }
    rows: list[dict] = []
    seen: set[str] = set()

    for part_manuf in df["Part_Manuf"].dropna().unique():
        part_manuf = str(part_manuf).strip()
        if not part_manuf or part_manuf == "-":
            continue
        key = part_manuf.lower()
        if key in seen:
            continue
        seen.add(key)

        matched = None
        for pattern, entry in manual.items():
            if pattern in key:
                matched = entry
                break

        if matched:
            rows.append(
                {
                    "distributor_pattern": part_manuf,
                    "manufacturer_name": matched["manufacturer_name"],
                    "brand_name": matched["brand_name"],
                    "code": matched.get("code", ""),
                    "desc_hints": matched.get("desc_hints", []),
                }
            )
        else:
            cleaned = re.sub(r"\s*\([^)]*\)", "", part_manuf).strip()
            rows.append(
                {
                    "distributor_pattern": part_manuf,
                    "manufacturer_name": cleaned,
                    "brand_name": cleaned,
                    "code": re.search(r"\(([^)]+)\)", part_manuf).group(1) if "(" in part_manuf else "",
                    "desc_hints": [],
                }
            )
    return rows
