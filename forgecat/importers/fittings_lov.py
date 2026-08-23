from __future__ import annotations

import json
from pathlib import Path

from forgecat.config import RAW_DATA_DIR, SEED_DIR
from forgecat.importers.xlsx_utils import find_column, first_existing, read_sheet


def import_fittings_mappings(raw_dir: Path | None = None) -> list[dict]:
    raw_dir = raw_dir or RAW_DATA_DIR
    path = first_existing(raw_dir, "Fittings_LOV.xlsx")
    if not path:
        return json.loads((SEED_DIR / "fittings_mappings.json").read_text(encoding="utf-8"))

    mappings: list[dict] = []
    xls = Path(path)
    for sheet_name in ["Connection Type", "Material", "Material Construction", "Sheet1", 0, 1, 2]:
        try:
            df = read_sheet(xls, sheet=sheet_name)
        except Exception:
            continue

        src_col = find_column(
            df, "Manufacturer Value", "Source Value", "Variant", "Connection Type Variant"
        )
        canon_col = find_column(
            df, "Canonical Value", "Normalized Value", "Approved Value", "Canonical"
        )
        attr_col = find_column(df, "Attribute", "Attribute Label", "Attribute Type")

        if not src_col or not canon_col:
            continue

        for _, r in df.iterrows():
            src = str(r.get(src_col, "")).strip()
            canon = str(r.get(canon_col, "")).strip()
            if src and canon:
                mappings.append(
                    {
                        "attribute_type": str(r.get(attr_col or "", "Connection Type")).strip(),
                        "source_value": src,
                        "canonical_value": canon,
                    }
                )
    return mappings or json.loads((SEED_DIR / "fittings_mappings.json").read_text(encoding="utf-8"))
