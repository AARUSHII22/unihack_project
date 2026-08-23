from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from forgecat.config import DB_PATH, INPUT_CSV, RAW_DATA_DIR
from forgecat.importers.content_guidelines import import_content_rules
from forgecat.importers.fittings_lov import import_fittings_mappings
from forgecat.importers.uom import import_decimal_fraction, import_uom
from forgecat.importers.unicat_lov import import_lov
from forgecat.importers.unicat_manufacturer import augment_from_input_csv, import_manufacturers


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _create_schema(cur: sqlite3.Cursor) -> None:
    cur.executescript(
        """
        DROP TABLE IF EXISTS manufacturers;
        DROP TABLE IF EXISTS classpath_index;
        DROP TABLE IF EXISTS lov_attributes;
        DROP TABLE IF EXISTS uom_standards;
        DROP TABLE IF EXISTS decimal_fraction;
        DROP TABLE IF EXISTS fittings_mappings;
        DROP TABLE IF EXISTS content_field_rules;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE manufacturers (
            id INTEGER PRIMARY KEY,
            distributor_pattern TEXT,
            manufacturer_name TEXT NOT NULL,
            brand_name TEXT NOT NULL,
            code TEXT,
            desc_hints TEXT
        );

        CREATE TABLE classpath_index (
            id INTEGER PRIMARY KEY,
            classpath TEXT UNIQUE,
            dept TEXT,
            class TEXT,
            fine TEXT,
            keywords TEXT,
            product_name TEXT,
            depth_tier TEXT
        );

        CREATE TABLE lov_attributes (
            id INTEGER PRIMARY KEY,
            classpath TEXT,
            attribute_label TEXT,
            normalized_values TEXT,
            uom_allowed TEXT,
            filtering_yn TEXT,
            attr_order INTEGER
        );

        CREATE TABLE uom_standards (
            raw_variant TEXT PRIMARY KEY,
            approved_abbrev TEXT
        );

        CREATE TABLE decimal_fraction (
            decimal_value TEXT PRIMARY KEY,
            fraction TEXT
        );

        CREATE TABLE fittings_mappings (
            id INTEGER PRIMARY KEY,
            attribute_type TEXT,
            source_value TEXT,
            canonical_value TEXT
        );

        CREATE TABLE content_field_rules (
            field_name TEXT PRIMARY KEY,
            rules_json TEXT
        );

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE INDEX idx_manufacturers_name ON manufacturers(manufacturer_name);
        CREATE INDEX idx_lov_classpath ON lov_attributes(classpath);
        CREATE INDEX idx_fittings_source ON fittings_mappings(source_value);
        """
    )


def build_indexes(force: bool = False) -> dict[str, int]:
    if DB_PATH.exists() and not force:
        conn = get_connection()
        row = conn.execute("SELECT value FROM meta WHERE key='built'").fetchone()
        conn.close()
        if row:
            return json.loads(row["value"])

    conn = get_connection()
    cur = conn.cursor()
    _create_schema(cur)

    # Manufacturers: official UniCat + distributor patterns from input CSV
    unicat_rows = import_manufacturers(RAW_DATA_DIR)
    input_rows = augment_from_input_csv(INPUT_CSV)
    seen: set[tuple[str, str, str]] = set()
    mfg_count = 0
    for row in unicat_rows + input_rows:
        key = (row["distributor_pattern"], row["manufacturer_name"], row["brand_name"])
        if key in seen:
            continue
        seen.add(key)
        cur.execute(
            """
            INSERT INTO manufacturers
            (distributor_pattern, manufacturer_name, brand_name, code, desc_hints)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row["distributor_pattern"],
                row["manufacturer_name"],
                row["brand_name"],
                row.get("code", ""),
                json.dumps(row.get("desc_hints", [])),
            ),
        )
        mfg_count += 1

    # LOV + classpath index
    classpath_rows, lov_rows = import_lov(RAW_DATA_DIR)
    cp_count = 0
    for row in classpath_rows:
        cur.execute(
            """
            INSERT OR REPLACE INTO classpath_index
            (classpath, dept, class, fine, keywords, product_name, depth_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["classpath"],
                row["dept"],
                row["class"],
                row["fine"],
                json.dumps(row.get("keywords", [])),
                row.get("product_name", ""),
                row.get("depth_tier", "B"),
            ),
        )
        cp_count += 1

    lov_count = 0
    for row in lov_rows:
        cur.execute(
            """
            INSERT INTO lov_attributes
            (classpath, attribute_label, normalized_values, uom_allowed, filtering_yn, attr_order)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["classpath"],
                row["attribute_label"],
                json.dumps(row.get("normalized_values", [])),
                json.dumps(row.get("uom_allowed", [])),
                row.get("filtering_yn", "N"),
                row["attr_order"],
            ),
        )
        lov_count += 1

    # UOM + decimal fraction
    uom_map = import_uom(RAW_DATA_DIR)
    for raw, approved in uom_map.items():
        cur.execute(
            "INSERT OR REPLACE INTO uom_standards (raw_variant, approved_abbrev) VALUES (?, ?)",
            (raw.lower(), approved),
        )

    frac_map = import_decimal_fraction(RAW_DATA_DIR)
    for dec, frac in frac_map.items():
        cur.execute(
            "INSERT OR REPLACE INTO decimal_fraction (decimal_value, fraction) VALUES (?, ?)",
            (dec, frac),
        )

    # Fittings many-to-one
    fit_count = 0
    for row in import_fittings_mappings(RAW_DATA_DIR):
        cur.execute(
            """
            INSERT INTO fittings_mappings (attribute_type, source_value, canonical_value)
            VALUES (?, ?, ?)
            """,
            (row["attribute_type"], row["source_value"], row["canonical_value"]),
        )
        fit_count += 1

    # Content field rules
    rules = import_content_rules(RAW_DATA_DIR)
    for field, rule in rules.items():
        cur.execute(
            "INSERT OR REPLACE INTO content_field_rules (field_name, rules_json) VALUES (?, ?)",
            (field, json.dumps(rule)),
        )

    stats = {
        "manufacturers": mfg_count,
        "classpaths": cp_count,
        "lov_attributes": lov_count,
        "uom_variants": len(uom_map),
        "decimal_fractions": len(frac_map),
        "fittings_mappings": fit_count,
        "content_rules": len(rules),
    }
    cur.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('built', ?)",
        (json.dumps(stats),),
    )
    conn.commit()
    conn.close()
    return stats
