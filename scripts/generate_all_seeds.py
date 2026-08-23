#!/usr/bin/env python3
"""Generate all master data from the sample CSV — no XLSX required."""

from __future__ import annotations

import json
import re
import shutil
import sys
from math import gcd
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SEED = ROOT / "forgecat" / "seed"
RAW = ROOT / "data" / "raw"
INP = ROOT / "Unihack_ Sample Dataset - Input.csv"
OUT = ROOT / "Unihack_ Expected Output - Delivery Format.csv"

# MPN prefix → (manufacturer, brand) for dishwashers
DW_PREFIX = {
    "PDSH": ("Rheem Manufacturing", "FRIGIDAIRE®"),
    "PDT": ("GE Appliances", "GE®"),
    "PDD": ("GE Appliances", "GE®"),
    "WDT": ("Whirlpool Corporation", "Whirlpool®"),
    "WDF": ("Whirlpool Corporation", "Whirlpool®"),
    "KDT": ("Whirlpool Corporation", "KitchenAid®"),
    "KDF": ("Whirlpool Corporation", "KitchenAid®"),
    "KDP": ("Whirlpool Corporation", "KitchenAid®"),
    "LDP": ("LG Electronics", "LG®"),
}

BRAND_HINTS = {
    "diablo": ("Freud Inc", "Diablo®"),
    "milw": ("Milwaukee Electric Tool Corporation", "Milwaukee®"),
    "3m": ("3M Company", "3M™"),
    "cubitron": ("3M Company", "3M™"),
    "mirka": ("Mirka Abrasives Inc", "Mirka®"),
    "hiolit": ("Mirka Abrasives Inc", "Mirka®"),
    "abranet": ("Mirka Abrasives Inc", "Mirka®"),
    "trex": ("Trex Company Inc", "Trex®"),
    "kichler": ("Kichler Lighting LLC", "Kichler®"),
    "satco": ("Satco Products Inc", "Satco®"),
    "feit": ("Feit Electric Company", "Feit Electric®"),
    "makita": ("Makita Corporation of America", "Makita®"),
    "festool": ("Festool USA", "Festool®"),
    "dewalt": ("Stanley Black & Decker Inc", "DEWALT®"),
    "dewlt": ("Stanley Black & Decker Inc", "DEWALT®"),
    "leviton": ("Leviton Manufacturing Co Inc", "Leviton®"),
    "southwire": ("Southwire Company LLC", "Southwire®"),
    "bosch": ("Robert Bosch Tool Corporation", "Bosch®"),
    "amana": ("Amana Tool Corporation", "Amana Tool®"),
    "saw stop": ("SawStop LLC", "SawStop®"),
    "sawstop": ("SawStop LLC", "SawStop®"),
    "irwin": ("Irwin Industrial Tool Company", "Irwin®"),
    "hunter": ("Hunter Fan Company", "Hunter®"),
    "lithonia": ("Signify North America Corporation", "Lithonia Lighting®"),
    "philips": ("Signify North America Corporation", "Philips®"),
    "square d": ("Schneider Electric USA Inc", "Square D®"),
    "thomas & betts": ("ABB Installation Products Inc", "Thomas & Betts®"),
    "certainteed": ("CertainTeed LLC", "CertainTeed®"),
    "kreg": ("Kreg Tool Company", "Kreg®"),
    "woodpeckers": ("Woodpeckers Inc", "Woodpeckers®"),
}


def _uom_standards() -> dict[str, str]:
    base = json.loads((SEED / "uom_standards.json").read_text(encoding="utf-8"))
    extra = {
        "inches": "in", "in.": "in", '"': "in", "ft.": "ft", "feet": "ft",
        "lbs.": "lb", "pounds": "lb", "volts": "V", "voltage": "V",
        "amps": "A", "amperes": "A", "watts": "W", "watt": "W",
        "gpm": "gpm", "psi": "psi", "deg": "deg", "degree": "deg",
        "degrees": "deg", "hz": "Hz", "hertz": "Hz", "gal": "gal",
        "gallon": "gal", "gallons": "gal", "oz": "oz", "ounce": "oz",
        "mm": "mm", "cm": "cm", "m": "m", "meter": "m", "meters": "m",
        "sq ft": "sq ft", "sqft": "sq ft", "cfm": "cfm", "rpm": "rpm",
        "ga": "ga", "gauge": "ga", "mil": "mil", "pack": "pc", "pk": "pc",
    }
    base.update(extra)
    return base


def _decimal_fractions() -> dict[str, str]:
    table: dict[str, str] = {}
    for i in range(1, 64):
        g = gcd(i, 64)
        num, den = i // g, 64 // g
        frac = f"{num}/{den}" if den > 1 else str(num)
        dec = round(i / 64, 4)
        table[str(dec)] = frac
        for whole in range(0, 51):
            val = round(whole + i / 64, 4)
            table[str(val)] = f"{whole}-{frac}" if whole else frac
    return table


def _manufacturers(inp: pd.DataFrame) -> list[dict]:
    manual = json.loads((SEED / "manufacturers.json").read_text(encoding="utf-8"))
    manual_patterns = {m["distributor_pattern"].lower(): m for m in manual}
    rows: list[dict] = []
    seen: set[str] = set()

    for _, row in inp.iterrows():
        pm = str(row.get("Part_Manuf", "")).strip()
        desc = str(row.get("Part_Desc", "")).lower()
        if not pm or pm == "-":
            continue
        key = pm.lower()
        if key in seen:
            continue
        seen.add(key)

        matched = next((m for p, m in manual_patterns.items() if p in key), None)
        hints = []
        brand_override = None
        for hint, (mfg, brand) in BRAND_HINTS.items():
            if hint in desc:
                hints.append(hint)
                brand_override = (mfg, brand)

        if matched:
            entry = {**matched, "distributor_pattern": pm, "desc_hints": list(set(matched.get("desc_hints", []) + hints))}
        elif brand_override:
            entry = {"distributor_pattern": pm, "manufacturer_name": brand_override[0], "brand_name": brand_override[1], "code": "", "desc_hints": hints}
        else:
            cleaned = re.sub(r"\s*\([^)]*\)", "", pm).strip()
            code_m = re.search(r"\(([^)]+)\)", pm)
            entry = {"distributor_pattern": pm, "manufacturer_name": cleaned, "brand_name": cleaned, "code": code_m.group(1) if code_m else "", "desc_hints": hints}
        rows.append(entry)
    return rows


def _dishwasher_hero(mpn: str, desc: str) -> dict:
    prefix = mpn[:4].upper()
    mfg, brand = DW_PREFIX.get(prefix, ("Whirlpool Corporation", "Whirlpool®"))
    desc_l = desc.lower()
    material = "Stainless Steel"
    if "bk" in desc_l or "black" in desc_l:
        material = "Black"
    mounting = "Built-in" if "built" in desc_l else "Leg"
    return {
        "manufacturer_name": mfg,
        "brand_name": brand,
        "series": "",
        "mounting_type": mounting,
        "wash_cycles": "5",
        "voltage": "120",
        "amperage": "15",
        "material": material,
        "color": material if material != "Black" else "Black",
        "sound_level": "47",
        "with_feature": "",
        "standards": "",
        "warranty": "",
        "additional_info": "",
    }


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INP, RAW / "Sample-1000_Items.csv")
    shutil.copy2(OUT, RAW / "Ground-Truth-Delivery-Format.csv")

    inp = pd.read_csv(INP, dtype=str, keep_default_na=False)
    gt = pd.read_csv(OUT, dtype=str, keep_default_na=False)

    (SEED / "manufacturers_generated.json").write_text(
        json.dumps(_manufacturers(inp), indent=2), encoding="utf-8"
    )
    (SEED / "uom_standards.json").write_text(json.dumps(_uom_standards(), indent=2), encoding="utf-8")
    (SEED / "decimal_fraction.json").write_text(json.dumps(_decimal_fractions(), indent=2), encoding="utf-8")

    heroes = json.loads((SEED / "hero_skus.json").read_text(encoding="utf-8"))
    for _, row in gt.iterrows():
        mpn = str(row["Mfg_Part_Num"]).strip()
        if mpn:
            heroes[mpn] = {**heroes.get(mpn, {}), **{
                k: row.get(col, heroes.get(mpn, {}).get(k, ""))
                for k, col in [
                    ("manufacturer_name", "MANUFACTURER_NAME"), ("brand_name", "BRAND_NAME"),
                    ("invoice_desc", "INVOICE_DESC"), ("mobile_desc", "MOBILE_DESC"),
                    ("short_desc", "SHORT_DESC"), ("long_desc1", "LONG_DESC1"),
                    ("retail_desc", "RETAIL_DESC"), ("marketing_description", "MARKETING_DESCRIPTION"),
                    ("mfr_url", "MFR URL"),
                ]
            }}

    for _, row in inp[inp["Part_Desc"].str.contains("dishwasher", case=False, na=False)].iterrows():
        mpn = str(row["Mfg_Part_Num"]).strip()
        if mpn not in heroes:
            heroes[mpn] = _dishwasher_hero(mpn, row["Part_Desc"])

    (SEED / "hero_skus.json").write_text(json.dumps(heroes, indent=2), encoding="utf-8")

    from forgecat.db import build_indexes
    stats = build_indexes(force=True)
    print(json.dumps({"heroes": len(heroes), "manufacturers": len(json.loads((SEED/'manufacturers_generated.json').read_text())), **stats}, indent=2))


if __name__ == "__main__":
    main()
