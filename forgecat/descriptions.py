from __future__ import annotations

import re
from typing import Any


def _abbrev_word(word: str) -> str:
    skip = {"with", "and", "the", "for", "of", "a", "an", "to", "in", "on", "-", "display", "only"}
    if word.lower() in skip:
        return ""
    mapping = {
        "dishwasher": "DISHWASHER",
        "stainless": "SST",
        "steel": "SST",
        "built-in": "BLTLN",
        "built": "BLTLN",
        "mounting": "MNT",
        "leg": "LEG",
        "professional": "PRO",
        "series": "SER",
        "metal": "MTL",
        "cut": "CUT",
        "off": "OFF",
        "disc": "DISC",
        "grinding": "GRIND",
        "wheel": "WHL",
        "sanding": "SAND",
        "belt": "BELT",
    }
    low = word.lower().strip("-,")
    if low in mapping:
        return mapping[low]
    if len(word) <= 4:
        return word.upper()
    return word[:4].upper()


def build_invoice_desc(
    product_name: str,
    attributes: list[dict[str, str | None]],
    brand_name: str,
) -> str:
    parts = [product_name.upper() if product_name else "ITEM"]

    attr_map = {a["attribute_label"]: a for a in attributes if a.get("attribute_value")}
    for label in ["Mounting Type", "Material", "Number of Wash Cycles", "Type"]:
        attr = attr_map.get(label)
        if attr and attr.get("attribute_value"):
            abbr = _abbrev_word(str(attr["attribute_value"]))
            if abbr:
                parts.append(abbr)

    for label in ["Voltage Rating", "Amperage Rating"]:
        attr = attr_map.get(label)
        if attr and attr.get("attribute_value"):
            uom = attr.get("attribute_uom") or ""
            parts.append(f"{attr['attribute_value']}{uom}")

    sound = attr_map.get("Sound Level")
    if sound and sound.get("attribute_value"):
        parts.append(f"{sound['attribute_value']}DBA")

    depth = attr_map.get("Depth With Door Open")
    if depth and depth.get("attribute_value"):
        val = str(depth["attribute_value"]).replace(" ", "").replace("in", "IN")
        parts.append(val if val.endswith("IN") else f"{val}IN")

    text = " ".join(parts)
    if len(text) > 40:
        text = text[:40].rsplit(" ", 1)[0]
    return text.upper()[:40]


def build_mobile_desc(
    manufacturer_name: str,
    brand_name: str,
    product_name: str,
    mpn: str,
    attributes: list[dict[str, str | None]],
) -> str:
    series = next(
        (a["attribute_value"] for a in attributes if a["attribute_label"] == "Series" and a.get("attribute_value")),
        None,
    )
    mounting = next(
        (
            a["attribute_value"]
            for a in attributes
            if a["attribute_label"] == "Mounting Type" and a.get("attribute_value")
        ),
        None,
    )

    if manufacturer_name and brand_name and manufacturer_name.split()[0].lower() not in brand_name.lower():
        prefix = f"{manufacturer_name.split()[0]} {brand_name.rstrip('®™')}"
    elif brand_name:
        prefix = brand_name.rstrip("®™")
    else:
        prefix = manufacturer_name or ""

    chunks = [c for c in [prefix, product_name, series, mpn] if c]
    if mounting:
        chunks.append(f"{mounting} Mounting")

    text = ", ".join(chunks[:4])
    if len(text) < 60:
        text = ", ".join(chunks)
    if len(text) > 80:
        text = text[:80].rsplit(", ", 1)[0]
    return text


def build_short_desc(
    brand_name: str,
    mpn: str,
    product_name: str,
    attributes: list[dict[str, str | None]],
    with_feature: str = "",
) -> str:
    series = next(
        (a["attribute_value"] for a in attributes if a["attribute_label"] == "Series" and a.get("attribute_value")),
        None,
    )
    parts = [brand_name, series, mpn, product_name]
    highlights: list[str] = []

    if with_feature:
        highlights.append(f"With {with_feature}")

    for label in ["Mounting Type", "Number of Wash Cycles", "Material", "Color", "Type", "Grit"]:
        attr = next((a for a in attributes if a["attribute_label"] == label and a.get("attribute_value")), None)
        if attr:
            val = str(attr["attribute_value"])
            if label == "Number of Wash Cycles" and val.isdigit():
                highlights.append(f"{val}-Wash Cycle")
            elif label == "Mounting Type":
                highlights.append(f"{val} Mounting")
            else:
                highlights.append(val)

    text = " ".join(p for p in parts if p)
    if highlights:
        text += " " + ", ".join(highlights)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_long_desc1(
    brand_name: str,
    product_name: str,
    attributes: list[dict[str, str | None]],
    with_feature: str = "",
) -> str:
    chunks: list[str] = [f"{brand_name} {product_name}"]
    if with_feature:
        chunks[0] += f" With {with_feature}"

    ordered: list[str] = []
    for attr in attributes:
        label = attr.get("attribute_label") or ""
        value = attr.get("attribute_value")
        uom = attr.get("attribute_uom")
        if not value or label in {"Model", "Series"}:
            continue
        if label == "Additional Information":
            ordered.append(f"Additional Information: {value}")
            continue
        if uom:
            if str(value).endswith("in") or " x " in str(value):
                ordered.append(f"{value}")
            else:
                ordered.append(f"{value} {uom}")
        else:
            ordered.append(str(value))

    if len(chunks[0].split(",")) == 1 and ordered:
        series = next(
            (a["attribute_value"] for a in attributes if a["attribute_label"] == "Series" and a.get("attribute_value")),
            None,
        )
        if series:
            chunks[0] += f", {series}"

    text = chunks[0]
    if ordered:
        text += ", " + ", ".join(ordered)
    return text


def build_tier_b_short_desc(
    brand_name: str,
    mpn: str,
    product_name: str,
    part_desc: str,
    attributes: list[dict[str, str | None]],
) -> str:
    key_attrs = []
    for attr in attributes[:5]:
        if attr.get("attribute_value"):
            uom = f" {attr['attribute_uom']}" if attr.get("attribute_uom") else ""
            key_attrs.append(f"{attr['attribute_value']}{uom}")

    base = f"{brand_name} {mpn} {product_name}".strip()
    if key_attrs:
        return f"{base}, {', '.join(key_attrs)}"
    cleaned = re.sub(r"\b" + re.escape(mpn) + r"\b", "", part_desc, count=1).strip(" -,")
    return f"{base}, {cleaned}" if cleaned else base


def build_descriptions(
    row: dict[str, Any],
    manufacturer: dict[str, Any],
    classification: dict[str, Any],
    attributes: list[dict[str, str | None]],
    hero: dict[str, Any] | None = None,
) -> dict[str, str]:
    brand = manufacturer.get("brand_name", "")
    mpn = row.get("Mfg_Part_Num", "")
    product_name = classification.get("product_name", "Product")
    depth = classification.get("depth_tier", "B")
    with_feature = (hero or {}).get("with_feature", "")

    if depth == "A":
        if hero and hero.get("invoice_desc"):
            return {
                "INVOICE_DESC": hero["invoice_desc"],
                "MOBILE_DESC": hero.get("mobile_desc", ""),
                "SHORT_DESC": hero.get("short_desc", ""),
                "LONG_DESC1": hero.get("long_desc1", ""),
                "RETAIL_DESC": hero.get("retail_desc", ""),
                "MARKETING_DESCRIPTION": hero.get("marketing_description", ""),
            }
        return {
            "INVOICE_DESC": build_invoice_desc(product_name, attributes, brand),
            "MOBILE_DESC": build_mobile_desc(
                manufacturer.get("manufacturer_name", ""),
                brand,
                product_name,
                mpn,
                attributes,
            ),
            "SHORT_DESC": build_short_desc(brand, mpn, product_name, attributes, with_feature),
            "LONG_DESC1": build_long_desc1(brand, product_name, attributes, with_feature),
            "RETAIL_DESC": (hero or {}).get("retail_desc", ""),
            "MARKETING_DESCRIPTION": (hero or {}).get("marketing_description", ""),
        }

    short = build_tier_b_short_desc(
        brand,
        mpn,
        product_name,
        row.get("Part_Desc", ""),
        attributes,
    )
    return {
        "INVOICE_DESC": build_invoice_desc(product_name, attributes, brand),
        "MOBILE_DESC": build_mobile_desc(
            manufacturer.get("manufacturer_name", ""),
            brand,
            product_name,
            mpn,
            attributes,
        )[:80],
        "SHORT_DESC": short,
        "LONG_DESC1": short,
        "RETAIL_DESC": "",
        "MARKETING_DESCRIPTION": "",
    }
