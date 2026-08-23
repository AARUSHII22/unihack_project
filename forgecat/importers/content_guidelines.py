from __future__ import annotations

import json
from pathlib import Path

from forgecat.config import INPUT_CSV, RAW_DATA_DIR, SEED_DIR
from forgecat.importers.xlsx_utils import first_existing, read_sheet


CONTENT_FIELD_RULES = {
    "INVOICE_DESC": {
        "max_length": 40,
        "casing": "UPPER",
        "formula": "Item type + key specs abbreviated, unit immediately after number",
    },
    "MOBILE_DESC": {
        "min_length": 60,
        "max_length": 80,
        "formula": "Manufacturer, Brand, Item Type, Series, MPN",
    },
    "SHORT_DESC": {
        "formula": "Brand + Series + MPN + Item Type + key differentiating attributes",
    },
    "LONG_DESC1": {
        "formula": "Brand + Item Type + attributes in LOV order, comma-separated",
    },
    "RETAIL_DESC": {
        "formula": "Series + Item Type + key attributes, shorter than long desc",
    },
    "MARKETING_DESCRIPTION": {
        "formula": "Manufacturer source copy only; blank if unavailable",
        "source_required": True,
    },
}


def import_content_rules(raw_dir: Path | None = None) -> dict:
    raw_dir = raw_dir or RAW_DATA_DIR
    path = first_existing(raw_dir, "content_field_rules.json")
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    seed_path = SEED_DIR / "content_field_rules.json"
    if seed_path.exists():
        return json.loads(seed_path.read_text(encoding="utf-8"))
    return CONTENT_FIELD_RULES


def import_sample_input(raw_dir: Path | None = None):
    raw_dir = raw_dir or RAW_DATA_DIR
    path = first_existing(raw_dir, "Sample-1000_Items.xlsx", "Sample-1000_Items.xls")
    if path:
        return read_sheet(path, sheet=0)
    import pandas as pd

    return pd.read_csv(INPUT_CSV, dtype=str, keep_default_na=False)
