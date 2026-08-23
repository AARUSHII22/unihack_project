from __future__ import annotations

import json
from math import gcd
from pathlib import Path

from forgecat.config import RAW_DATA_DIR, SEED_DIR
from forgecat.importers.xlsx_utils import first_existing, read_sheet


def import_uom(raw_dir: Path | None = None) -> dict[str, str]:
    raw_dir = raw_dir or RAW_DATA_DIR
    path = first_existing(
        raw_dir,
        "Unilog_Master_UOM_Standards_Abbreviations_and_Terms.xlsx",
    )
    mapping: dict[str, str] = {}

    if path:
        for sheet in [0, 1]:
            try:
                df = read_sheet(path, sheet=sheet)
            except Exception:
                continue
            for _, row in df.iterrows():
                cells = [str(v).strip() for v in row.values if str(v).strip()]
                if len(cells) >= 2:
                    raw, approved = cells[0].lower(), cells[1]
                    if approved and len(approved) <= 8:
                        mapping[raw] = approved
                    if len(cells) >= 3 and cells[2]:
                        mapping[str(cells[2]).lower()] = approved

    seed = json.loads((SEED_DIR / "uom_standards.json").read_text(encoding="utf-8"))
    mapping.update({k.lower(): v for k, v in seed.items()})
    return mapping


def import_decimal_fraction(raw_dir: Path | None = None) -> dict[str, str]:
    raw_dir = raw_dir or RAW_DATA_DIR
    path = first_existing(raw_dir, "Decimal_Fraction.xlsx")
    table: dict[str, str] = {}

    if path:
        df = read_sheet(path, sheet=0, header_row=None)
        for _, row in df.iterrows():
            cells = [str(v).strip() for v in row.values if str(v).strip()]
            for i in range(0, len(cells) - 1, 2):
                left, right = cells[i], cells[i + 1]
                if "/" in left:
                    try:
                        dec = float(right)
                        table[str(round(dec, 6))] = left
                        table[str(round(dec, 4))] = left
                    except ValueError:
                        pass
                elif "/" in right:
                    try:
                        dec = float(left)
                        table[str(round(dec, 6))] = right
                        table[str(round(dec, 4))] = right
                    except ValueError:
                        pass

    if not table:
        for i in range(1, 64):
            dec = round(i / 64, 6)
            g = gcd(i, 64)
            num, den = i // g, 64 // g
            frac = f"{num}/{den}" if den > 1 else str(num)
            table[str(dec)] = frac
            table[str(round(i / 64, 4))] = frac
            for whole in range(1, 51):
                val = whole + i / 64
                display = f"{whole}-{frac}" if frac != "0" else str(whole)
                table[str(round(val, 4))] = display

    return table
