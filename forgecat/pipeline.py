from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from forgecat.attributes import (
    build_decimal_fraction_table,
    build_uom_lookup,
    extract_attributes,
    get_attribute_schema,
)
from forgecat.classification import classify_row
from forgecat.config import GROUND_TRUTH_CSV, OUTPUT_DIR
from forgecat.content_rules import all_field_rules
from forgecat.dedup import annotate_duplicates, duplicate_report
from forgecat.descriptions import build_descriptions
from forgecat.enrichment import fetch_manufacturer_snippets
from forgecat.importers.ground_truth import load_hero_skus
from forgecat.ingest import ingest_file
from forgecat.llm_agent import enrich_with_llm, llm_available
from forgecat.manufacturer import resolve_manufacturer
from forgecat.validator import merge_needs_review, validate_record


def _delivery_columns() -> list[str]:
    df = pd.read_csv(GROUND_TRUTH_CSV, nrows=0)
    return list(df.columns)


def _safe_text(value: Any) -> str:
    """Normalize CSV/XLSX cell values before they reach enrichment stages."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def _brand_slug(brand_name: str) -> str:
    return brand_name.replace("®", "").replace("™", "").replace(" ", "_").upper()


def _populate_attributes(record: dict[str, Any], attributes: list[dict[str, str | None]]) -> None:
    for i in range(1, 51):
        record[f"ATTRIBUTE_LABEL {i}"] = ""
        record[f"ATTRIBUTE_VALUE {i}"] = ""
        record[f"ATTRIBUTE_UOM {i}"] = ""

    for idx, attr in enumerate(attributes[:50], start=1):
        record[f"ATTRIBUTE_LABEL {idx}"] = attr.get("attribute_label") or ""
        record[f"ATTRIBUTE_VALUE {idx}"] = attr.get("attribute_value") or ""
        record[f"ATTRIBUTE_UOM {idx}"] = attr.get("attribute_uom") or ""


def _populate_item_features(record: dict[str, Any], features: list[str]) -> None:
    for i in range(1, 21):
        record[f"ITEM_FEATURES_{i}"] = features[i - 1] if i - 1 < len(features) else ""


def enrich_row(raw_row: dict[str, Any], use_llm: bool = False) -> dict[str, Any]:
    # Uploaded spreadsheets may contain floating-point NaN values.  Ensure all
    # downstream rules receive strings, even if a caller bypasses ingest_file.
    raw_row = {key: _safe_text(value) for key, value in raw_row.items()}
    hero_skus = load_hero_skus()
    mpn = raw_row.get("Mfg_Part_Num", "")
    part_desc = raw_row.get("Part_Desc", "")
    hero = hero_skus.get(mpn)

    manufacturer = resolve_manufacturer(raw_row.get("Part_Manuf"), part_desc)
    classification = classify_row(part_desc)
    classpath = classification.get("classpath_string", "")
    depth_tier = classification.get("depth_tier", "B")

    if hero and ("dishwasher" in part_desc.lower() or "Dishwasher" in classpath):
        depth_tier = "A"
        classification["depth_tier"] = "A"

    attributes, attr_review = extract_attributes(mpn, part_desc, classpath, depth_tier)

    source = fetch_manufacturer_snippets(
        manufacturer.get("manufacturer_name", ""),
        mpn,
        known_url=hero.get("mfr_url") if hero else None,
        enabled=bool(hero or depth_tier == "A"),
    )

    candidate_data = {
        "manufacturer_candidates": manufacturer.get("candidates", []),
        "classpath_candidates": classification.get("candidates", []),
        "attribute_candidates": get_attribute_schema(classpath),
        "uom_lookup": build_uom_lookup(part_desc),
        "decimal_fraction_table": build_decimal_fraction_table(part_desc),
        "manufacturer_source_snippets": source.get("snippets", []),
    }

    descriptions = build_descriptions(raw_row, manufacturer, classification, attributes, hero)

    if use_llm and llm_available():
        llm_result = enrich_with_llm(
            raw_row,
            candidate_data,
            json.dumps(all_field_rules(), indent=2),
        )
        if llm_result:
            for key in ["MOBILE_DESC", "INVOICE_DESC", "SHORT_DESC", "LONG_DESC1", "MARKETING_DESCRIPTION"]:
                if llm_result.get(key):
                    descriptions[key] = llm_result[key]

    columns = _delivery_columns()
    record: dict[str, Any] = {col: "" for col in columns}

    mfr_name = hero.get("manufacturer_name") if hero else manufacturer.get("manufacturer_name", "")
    brand_name = hero.get("brand_name") if hero else manufacturer.get("brand_name", "")

    record.update(
        {
            "Mfg_Part_Num": mpn,
            "Part_Desc": part_desc,
            "E1_Brand": raw_row.get("E1_Brand") or "",
            "Unilog_Brand": raw_row.get("Unilog_Brand") or "",
            "DIB_Brand": raw_row.get("DIB_Brand") or "",
            "Part_Manuf": raw_row.get("Part_Manuf") or "",
            "MANUFACTURER_PART_NUMBER": mpn,
            "MANUFACTURER_NAME": mfr_name,
            "BRAND_NAME": brand_name,
            "Dept": classification.get("dept", ""),
            "Class": classification.get("class", ""),
            "Fine": classification.get("fine", ""),
            "Classpath": classpath,
            "Product Name": classification.get("product_name", ""),
            **descriptions,
        }
    )

    _populate_attributes(record, attributes)

    if hero:
        record["With"] = f"With {hero['with_feature']}" if hero.get("with_feature") else ""
        record["Standard/Approvals"] = hero.get("standards", "")
        record["Warranty"] = hero.get("warranty", "")
        record["MFR URL"] = hero.get("mfr_url", "") or source.get("mfr_url", "")
        for i, url in enumerate((hero.get("ref_urls") or source.get("ref_urls") or [])[:5], start=1):
            record[f"Ref URL {i}"] = url
        _populate_item_features(record, hero.get("item_features", []))
    else:
        record["MFR URL"] = source.get("mfr_url", "")
        _populate_item_features(record, [])

    brand_slug = _brand_slug(record["BRAND_NAME"] or "UNKNOWN")
    record["Product Image"] = f"{brand_slug}_{mpn}.jpg"
    record["Alternate Image 1"] = f"{brand_slug}_{mpn}_1.jpg"
    record["Alternate Image 2"] = f"{brand_slug}_{mpn}_2.jpg"
    record["Specification Sheet"] = f"{brand_slug}_{mpn}_Specification_Sheet.pdf"
    record["Actual Image (Yes/No)"] = "Yes" if hero else ""
    record["image_not_asset_verified"] = "true"

    needs_review = merge_needs_review(
        manufacturer.get("needs_review", []),
        classification.get("needs_review", []),
        attr_review,
        validate_record(record, depth_tier=depth_tier),
    )

    record["_depth_tier"] = depth_tier
    record["_needs_review"] = json.dumps(needs_review)
    record["_manufacturer_score"] = manufacturer.get("score", 0)
    record["_classification_score"] = classification.get("score", 0)
    record["_source_hierarchy"] = source.get("source", "none")
    return record


def run_pipeline(
    input_path: str | None = None,
    output_path: str | None = None,
    limit: int | None = None,
    use_llm: bool = False,
) -> pd.DataFrame:
    from forgecat.db import build_indexes

    stats = build_indexes(force=True)
    Path(OUTPUT_DIR / "import_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    df = ingest_file(input_path)
    if limit:
        df = df.head(limit)

    raw_rows = [row.to_dict() for _, row in df.iterrows()]
    enriched_rows = [enrich_row(row, use_llm=use_llm) for row in raw_rows]
    enriched_rows = annotate_duplicates(enriched_rows)
    result = pd.DataFrame(enriched_rows).fillna("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = output_path or str(OUTPUT_DIR / "enriched_delivery_format.csv")
    review_path = str(OUTPUT_DIR / "review_queue.json")
    dupes_path = str(OUTPUT_DIR / "duplicate_report.json")

    export_cols = [c for c in result.columns if not c.startswith("_")]
    result[export_cols].to_csv(output_path, index=False)

    review_queue = []
    for _, row in result.iterrows():
        flags = json.loads(row.get("_needs_review", "[]"))
        if flags:
            review_queue.append(
                {
                    "Mfg_Part_Num": row.get("Mfg_Part_Num"),
                    "flags": flags,
                    "depth_tier": row.get("_depth_tier"),
                    "manufacturer_score": row.get("_manufacturer_score"),
                    "classification_score": row.get("_classification_score"),
                }
            )

    Path(review_path).write_text(json.dumps(review_queue, indent=2), encoding="utf-8")
    Path(dupes_path).write_text(json.dumps(duplicate_report(raw_rows), indent=2), encoding="utf-8")
    return result
