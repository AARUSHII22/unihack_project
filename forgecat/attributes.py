from __future__ import annotations

import json
import re
from typing import Any

from forgecat.config import SEED_DIR
from forgecat.db import get_connection
from forgecat.fittings import extract_fitting_tokens
from forgecat.importers.ground_truth import load_hero_skus


def _load_hero_skus() -> dict[str, Any]:
    return load_hero_skus()


def _load_lov_templates() -> dict[str, Any]:
    return json.loads((SEED_DIR / "lov_templates.json").read_text(encoding="utf-8"))


def _decimal_to_fraction(value: str) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT fraction FROM decimal_fraction WHERE decimal_value = ?",
        (value,),
    ).fetchone()
    conn.close()
    return row["fraction"] if row else value


def _normalize_uom(raw: str) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT approved_abbrev FROM uom_standards WHERE raw_variant = ?",
        (raw.lower(),),
    ).fetchone()
    conn.close()
    return row["approved_abbrev"] if row else raw


def _format_inches(text: str) -> str:
    def repl_decimal(match: re.Match[str]) -> str:
        whole = match.group(1) or ""
        dec = match.group(2)
        key = str(round(float(dec), 4))
        frac = _decimal_to_fraction(key)
        if whole:
            return f"{whole}-{frac} in" if frac else f"{whole} in"
        return f"{frac} in"

    def repl_fraction(match: re.Match[str]) -> str:
        val = match.group(0).replace('"', "").strip()
        return f"{val} in"

    text = re.sub(r"(\d+)-(\d+/\d+)", r"\1-\2 in", text)
    text = re.sub(r"(\d+)/(\d+)\"", r"\1/\2 in", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\"", repl_decimal, text)
    text = re.sub(r"(\d+(?:-\d+/\d+)?)\s*(?:in|inch|inches)\b", repl_fraction, text, flags=re.I)
    return text


def get_attribute_schema(classpath: str) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT attribute_label, normalized_values, uom_allowed, attr_order
        FROM lov_attributes WHERE classpath = ?
        ORDER BY attr_order
        """,
        (classpath,),
    ).fetchall()
    conn.close()
    return [
        {
            "attribute_label": r["attribute_label"],
            "normalized_values": json.loads(r["normalized_values"]),
            "uom_allowed": json.loads(r["uom_allowed"]),
            "attr_order": r["attr_order"],
        }
        for r in rows
    ]


def _match_lov_value(label: str, raw: str, allowed: list[str]) -> str | None:
    if not raw:
        return None
    raw_clean = raw.strip()
    for val in allowed:
        if val.lower() == raw_clean.lower():
            return val
    for val in allowed:
        if val.lower() in raw_clean.lower() or raw_clean.lower() in val.lower():
            return val
    return None


def extract_dishwasher_attributes(
    mpn: str,
    part_desc: str,
    classpath: str,
) -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    hero = _load_hero_skus().get(mpn)
    schema = get_attribute_schema(classpath)
    attrs: list[dict[str, str | None]] = []
    needs_review: list[dict[str, str]] = []
    desc_lower = part_desc.lower()

    if hero:
        mapping = [
            ("Series", hero.get("series", ""), ""),
            ("Model", mpn, ""),
            ("Number of Wash Cycles", hero.get("wash_cycles", ""), ""),
            ("Voltage Rating", hero.get("voltage", ""), "V"),
            ("Amperage Rating", hero.get("amperage", ""), "A"),
            ("Mounting Type", hero.get("mounting_type", ""), ""),
            ("Plug Type", "", ""),
            ("Size", hero.get("size", ""), ""),
            ("Depth With Door Open", hero.get("depth_door_open", ""), "in"),
            ("Minimum Height", hero.get("min_height", ""), "in" if hero.get("min_height") and "in" not in hero.get("min_height", "") else ""),
            ("Maximum Height", hero.get("max_height", ""), "in" if hero.get("max_height") and "in" not in hero.get("max_height", "") else ""),
            ("Sound Level", hero.get("sound_level", ""), "dBA"),
            ("Material", hero.get("material", ""), ""),
            ("Color", hero.get("color", ""), ""),
            ("Additional Information", hero.get("additional_info", ""), ""),
        ]
        for label, value, uom in mapping:
            attrs.append(
                {"attribute_label": label, "attribute_value": value or None, "attribute_uom": uom or None}
            )
        return attrs, needs_review

    templates = _load_lov_templates().get(classpath, {})
    material_map = templates.get("material_map", {})
    mounting_map = templates.get("mounting_map", {})

    material = None
    for token, mat in material_map.items():
        if token in desc_lower:
            material = mat
            break

    mounting = None
    for token, mount in mounting_map.items():
        if token in desc_lower:
            mounting = mount
            break

    brand_hint = ""
    for hint in ["kitchen aid", " ge ", " lg ", "whirlpool", "frigidaire"]:
        if hint.strip() in desc_lower:
            brand_hint = hint.strip()
            break

    defaults = {
        "Series": "",
        "Model": mpn,
        "Number of Wash Cycles": "",
        "Voltage Rating": "120",
        "Amperage Rating": "",
        "Mounting Type": mounting or "",
        "Plug Type": "",
        "Size": "",
        "Depth With Door Open": "",
        "Minimum Height": "",
        "Maximum Height": "",
        "Sound Level": "",
        "Material": material or "Stainless Steel" if "ss" in desc_lower or "stainless" in desc_lower else "",
        "Color": material or "",
        "Additional Information": f"Brand hint: {brand_hint}" if brand_hint else "",
    }

    for spec in schema:
        label = spec["attribute_label"]
        value = defaults.get(label, "")
        allowed = spec["normalized_values"]
        uom = spec["uom_allowed"][0] if spec["uom_allowed"] else None

        if value and allowed:
            matched = _match_lov_value(label, value, allowed)
            if not matched:
                needs_review.append(
                    {"field": label, "reason": f"value '{value}' not in LOV"}
                )
                value = ""
            else:
                value = matched

        attrs.append(
            {
                "attribute_label": label,
                "attribute_value": value or None,
                "attribute_uom": uom if value else None,
            }
        )

    return attrs, needs_review


def extract_abrasive_attributes(part_desc: str, classpath: str) -> list[dict[str, str | None]]:
    templates = _load_lov_templates().get(classpath, {})
    type_map = templates.get("type_map", {})
    desc_lower = part_desc.lower()

    product_type = ""
    for token, ptype in type_map.items():
        if token in desc_lower:
            product_type = ptype
            break

    grit_match = re.search(r"\bP(\d{2,3})\b", part_desc, re.I)
    grit = f"P{grit_match.group(1)}" if grit_match else None

    allowed_types = ["Sanding Belt", "Cut-Off Disc", "Grinding Wheel", "Sanding Disc", "Flap Disc"]
    if product_type and product_type not in allowed_types:
        product_type = None

    dims = re.findall(r'(\d+(?:-\d+/\d+)?(?:\.\d+)?)\s*"', part_desc)
    diameter = f"{dims[0]} in" if dims else None
    width = f"{dims[1]} in" if len(dims) > 1 else None

    pack_match = re.search(r"(\d+)\s*(?:pc|pack|disc)", part_desc, re.I)
    pack_qty = pack_match.group(1) if pack_match else None

    return [
        {"attribute_label": "Type", "attribute_value": product_type or None, "attribute_uom": None},
        {"attribute_label": "Diameter", "attribute_value": diameter, "attribute_uom": "in" if diameter else None},
        {"attribute_label": "Width", "attribute_value": width, "attribute_uom": "in" if width else None},
        {"attribute_label": "Arbor Size", "attribute_value": None, "attribute_uom": None},
        {"attribute_label": "Grit", "attribute_value": grit, "attribute_uom": None},
        {"attribute_label": "Material", "attribute_value": None, "attribute_uom": None},
        {
            "attribute_label": "Pack Quantity",
            "attribute_value": pack_qty,
            "attribute_uom": "pc" if pack_qty else None,
        },
    ]


def extract_lighting_attributes(part_desc: str, classpath: str) -> list[dict[str, str | None]]:
    templates = _load_lov_templates().get(classpath, {})
    shape_map = templates.get("shape_map", {})
    desc_lower = part_desc.lower()

    shape = next((v for k, v in shape_map.items() if k in desc_lower), None)
    watt_match = re.search(r"(\d+)\s*w", part_desc, re.I)
    lumens_match = re.search(r"(\d+)\s*lm", part_desc, re.I)
    temp_match = re.search(r"(\d{4})\s*k", part_desc, re.I)

    return [
        {"attribute_label": "Type", "attribute_value": "LED Bulb", "attribute_uom": None},
        {
            "attribute_label": "Wattage",
            "attribute_value": watt_match.group(1) if watt_match else None,
            "attribute_uom": "W" if watt_match else None,
        },
        {
            "attribute_label": "Color Temperature",
            "attribute_value": f"{temp_match.group(1)} K" if temp_match else None,
            "attribute_uom": None,
        },
        {"attribute_label": "Base Type", "attribute_value": "Medium" if "med" in desc_lower else None, "attribute_uom": None},
        {"attribute_label": "Shape", "attribute_value": shape, "attribute_uom": None},
        {
            "attribute_label": "Lumens",
            "attribute_value": lumens_match.group(1) if lumens_match else None,
            "attribute_uom": "lm" if lumens_match else None,
        },
    ]


def extract_decking_attributes(part_desc: str, classpath: str) -> list[dict[str, str | None]]:
    templates = _load_lov_templates().get(classpath, {})
    type_map = templates.get("type_map", {})
    desc_lower = part_desc.lower()

    product_type = next((v for k, v in type_map.items() if k in desc_lower), "Deck Board")
    length_match = re.search(r"(\d+)\s*'", part_desc)
    width_match = re.search(r"(\d+)x(\d+)", part_desc)

    return [
        {"attribute_label": "Type", "attribute_value": product_type, "attribute_uom": None},
        {
            "attribute_label": "Length",
            "attribute_value": length_match.group(1) if length_match else None,
            "attribute_uom": "ft" if length_match else None,
        },
        {
            "attribute_label": "Width",
            "attribute_value": width_match.group(0).replace("x", " x ") if width_match else None,
            "attribute_uom": "in" if width_match else None,
        },
        {"attribute_label": "Material", "attribute_value": "Composite", "attribute_uom": None},
        {"attribute_label": "Color", "attribute_value": None, "attribute_uom": None},
    ]


def extract_fittings_attributes(part_desc: str, classpath: str) -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    schema = get_attribute_schema(classpath)
    tokens = extract_fitting_tokens(part_desc)
    needs_review: list[dict[str, str]] = []
    attrs: list[dict[str, str | None]] = []

    for spec in schema:
        label = spec["attribute_label"]
        value = tokens.get(label)
        allowed = spec["normalized_values"]
        uom = spec["uom_allowed"][0] if spec.get("uom_allowed") else None

        if value and allowed:
            matched = _match_lov_value(label, value, allowed)
            if not matched:
                needs_review.append({"field": label, "reason": f"value '{value}' not in LOV"})
                value = None
            else:
                value = matched

        attrs.append(
            {
                "attribute_label": label,
                "attribute_value": value,
                "attribute_uom": uom if value else None,
            }
        )
    return attrs, needs_review


def extract_faucet_attributes(part_desc: str, classpath: str) -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    schema = get_attribute_schema(classpath)
    desc_lower = part_desc.lower()
    attrs: list[dict[str, str | None]] = []

    finish = next((f for f in ["chrome", "nickel", "matte black", "bronze"] if f in desc_lower), None)
    handles = re.search(r"(\d+)\s*handle", part_desc, re.I)

    defaults = {
        "Series": "",
        "Mounting Type": "Deck Mount" if "deck" in desc_lower else "",
        "Number of Handles": handles.group(1) if handles else "",
        "Spout Reach": "",
        "Spout Height": "",
        "Flow Rate": "",
        "Material": "Brass",
        "Finish": finish.title() if finish else "",
        "Additional Information": "",
    }

    for spec in schema:
        label = spec["attribute_label"]
        value = defaults.get(label, "")
        allowed = spec["normalized_values"]
        uom = spec["uom_allowed"][0] if spec.get("uom_allowed") else None
        if value and allowed:
            value = _match_lov_value(label, value, allowed) or ""
        attrs.append(
            {
                "attribute_label": label,
                "attribute_value": value or None,
                "attribute_uom": uom if value else None,
            }
        )
    return attrs, []


def extract_attributes(
    mpn: str,
    part_desc: str,
    classpath: str,
    depth_tier: str,
) -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    if "Dishwasher" in classpath or "dishwasher" in part_desc.lower():
        return extract_dishwasher_attributes(mpn, part_desc, classpath)
    if "Pipe Fitting" in classpath or "Fittings" in classpath:
        return extract_fittings_attributes(part_desc, classpath)
    if "Faucet" in classpath or "faucet" in part_desc.lower():
        return extract_faucet_attributes(part_desc, classpath)

    if depth_tier == "A":
        return [], [{"field": "attributes", "reason": "no attribute template for classpath"}]

    if "Abrasive" in classpath or "abrasive" in classpath.lower():
        return extract_abrasive_attributes(part_desc, classpath), []
    if "Lighting" in classpath or "Lamps" in classpath:
        return extract_lighting_attributes(part_desc, classpath), []
    if "Decking" in classpath:
        return extract_decking_attributes(part_desc, classpath), []
    return [], []


def build_uom_lookup(part_desc: str) -> dict[str, str]:
    conn = get_connection()
    rows = conn.execute("SELECT raw_variant, approved_abbrev FROM uom_standards").fetchall()
    conn.close()
    lookup: dict[str, str] = {}
    desc_lower = part_desc.lower()
    for row in rows:
        if row["raw_variant"] in desc_lower:
            lookup[row["raw_variant"]] = row["approved_abbrev"]
    return lookup


def build_decimal_fraction_table(part_desc: str) -> dict[str, str]:
    decimals = re.findall(r"\d+\.\d+", part_desc)
    table: dict[str, str] = {}
    for dec in decimals:
        key = str(round(float(dec), 4))
        frac = _decimal_to_fraction(key)
        if frac != key:
            table[dec] = frac
    return table
