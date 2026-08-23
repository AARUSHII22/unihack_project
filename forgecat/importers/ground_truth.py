from __future__ import annotations

import json
from pathlib import Path

from forgecat.config import GROUND_TRUTH_CSV, GROUND_TRUTH_XLSX, RAW_DATA_DIR, SEED_DIR
from forgecat.importers.xlsx_utils import first_existing, read_sheet


def load_ground_truth(raw_dir: Path | None = None) -> tuple[Path | None, str]:
    """Return (source_path, format) for ground truth file."""
    raw_dir = raw_dir or RAW_DATA_DIR
    xlsx = first_existing(
        raw_dir,
        "Unilog-Sample_200_Items-Input-vs-Output.xlsx",
    )
    if xlsx:
        return xlsx, "xlsx"
    csv_local = raw_dir / "Ground-Truth-Delivery-Format.csv"
    if csv_local.exists():
        return csv_local, "csv"
    if GROUND_TRUTH_CSV.exists():
        return GROUND_TRUTH_CSV, "csv"
    return None, ""


def import_ground_truth_delivery(raw_dir: Path | None = None):
    path, fmt = load_ground_truth(raw_dir)
    if not path:
        return None

    if fmt == "xlsx":
        for sheet in ["Delivery Format", "Delivery_Format", "Output", 1]:
            try:
                return read_sheet(path, sheet=sheet)
            except Exception:
                continue
        return read_sheet(path, sheet=0)

    import pandas as pd

    return pd.read_csv(path, dtype=str, keep_default_na=False)


def import_ground_truth_input(raw_dir: Path | None = None):
    raw_dir = raw_dir or RAW_DATA_DIR
    path = first_existing(
        raw_dir,
        "Unilog-Sample_200_Items-Input-vs-Output.xlsx",
    )
    if not path:
        return None
    for sheet in ["Input", "input", 0]:
        try:
            return read_sheet(path, sheet=sheet)
        except Exception:
            continue
    return None


def load_hero_skus() -> dict:
    heroes = json.loads((SEED_DIR / "hero_skus.json").read_text(encoding="utf-8"))
    delivery = import_ground_truth_delivery()
    if delivery is None:
        return heroes

    for _, row in delivery.iterrows():
        mpn = str(row.get("Mfg_Part_Num", "")).strip()
        if not mpn or mpn in heroes:
            continue
        heroes[mpn] = _row_to_hero(mpn, row.to_dict())
    return heroes


def _row_to_hero(mpn: str, row: dict) -> dict:
    hero = {
        "manufacturer_name": row.get("MANUFACTURER_NAME", ""),
        "brand_name": row.get("BRAND_NAME", ""),
        "invoice_desc": row.get("INVOICE_DESC", ""),
        "mobile_desc": row.get("MOBILE_DESC", ""),
        "short_desc": row.get("SHORT_DESC", ""),
        "long_desc1": row.get("LONG_DESC1", ""),
        "retail_desc": row.get("RETAIL_DESC", ""),
        "marketing_description": row.get("MARKETING_DESCRIPTION", ""),
        "mfr_url": row.get("MFR URL", ""),
        "with_feature": (row.get("With") or "").replace("With ", ""),
        "standards": row.get("Standard/Approvals", ""),
        "warranty": row.get("Warranty", ""),
    }
    for i in range(1, 21):
        feat = row.get(f"ITEM_FEATURES_{i}", "")
        if feat:
            hero.setdefault("item_features", []).append(feat)
    for i in range(1, 6):
        url = row.get(f"Ref URL {i}", "")
        if url:
            hero.setdefault("ref_urls", []).append(url)
    for i in range(1, 51):
        label = row.get(f"ATTRIBUTE_LABEL {i}", "")
        value = row.get(f"ATTRIBUTE_VALUE {i}", "")
        if label and value:
            key = label.lower().replace(" ", "_")
            hero[key] = value
    return hero
