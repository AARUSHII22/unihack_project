from __future__ import annotations

import json
from pathlib import Path

from forgecat.config import RAW_DATA_DIR, SEED_DIR
from forgecat.importers.xlsx_utils import find_column, first_existing, read_sheet


def import_lov(raw_dir: Path | None = None) -> tuple[list[dict], list[dict]]:
    """Returns (classpath_index_rows, lov_attribute_rows)."""
    raw_dir = raw_dir or RAW_DATA_DIR
    path = first_existing(
        raw_dir,
        "Unicat_Lov_v1_0_Updated_With_Remarks.xlsx",
        "Unicat_Lov_v1_0_Updated_With_Remarks.xls",
    )
    if not path:
        return _from_seed_templates()

    df = read_sheet(path, sheet=0)
    cp_col = find_column(df, "Classpath", "CLASSPATH", "classpath")
    label_col = find_column(df, "Attribute Label", "ATTRIBUTE_LABEL", "attribute_label")
    values_col = find_column(
        df, "Normalized Values", "Attribute Values", "ATTRIBUTE_VALUES", "normalized_values"
    )
    filter_col = find_column(df, "Filtering Y/N", "Filtering", "filtering_yn")
    dept_col = find_column(df, "Dept", "Department")
    class_col = find_column(df, "Class")
    fine_col = find_column(df, "Fine", "Leaf Node")

    classpath_index: dict[str, dict] = {}
    lov_rows: list[dict] = []
    order_counter: dict[str, int] = {}

    for _, r in df.iterrows():
        classpath = str(r.get(cp_col or "", "")).strip()
        label = str(r.get(label_col or "", "")).strip()
        if not classpath or not label:
            continue

        values_raw = str(r.get(values_col or "", "")).strip()
        values = [v.strip() for v in values_raw.split("|") if v.strip()] if values_raw else []

        if classpath not in classpath_index:
            parts = [p.strip() for p in classpath.split(">")]
            classpath_index[classpath] = {
                "classpath": classpath,
                "dept": str(r.get(dept_col or "", parts[0] if parts else "")).strip(),
                "class": str(r.get(class_col or "", parts[1] if len(parts) > 1 else "")).strip(),
                "fine": str(r.get(fine_col or "", parts[-1] if parts else "")).strip(),
                "keywords": _keywords_from_classpath(classpath),
                "product_name": parts[-1] if parts else "Product",
                "depth_tier": "B",
            }

        order_counter[classpath] = order_counter.get(classpath, 0) + 1
        lov_rows.append(
            {
                "classpath": classpath,
                "attribute_label": label,
                "normalized_values": values,
                "uom_allowed": [],
                "filtering_yn": str(r.get(filter_col or "", "N")).strip().upper(),
                "attr_order": order_counter[classpath],
            }
        )

    return list(classpath_index.values()), lov_rows


def _keywords_from_classpath(classpath: str) -> list[str]:
    leaf = classpath.split(">")[-1].lower()
    return [leaf, leaf.replace("-", " "), leaf.replace(" ", "")]


def _from_seed_templates() -> tuple[list[dict], list[dict]]:
    templates = json.loads((SEED_DIR / "lov_templates.json").read_text(encoding="utf-8"))
    classpaths = json.loads((SEED_DIR / "classpaths.json").read_text(encoding="utf-8"))
    classpath_index = [
        {
            "classpath": c["classpath"],
            "dept": c["dept"],
            "class": c["class"],
            "fine": c["fine"],
            "keywords": c["keywords"],
            "product_name": c["product_name"],
            "depth_tier": c["depth_tier"],
        }
        for c in classpaths
        if c.get("keywords") != ["default"]
    ]
    lov_rows: list[dict] = []
    for classpath, spec in templates.items():
        for order, attr in enumerate(spec["attributes"], start=1):
            lov_rows.append(
                {
                    "classpath": classpath,
                    "attribute_label": attr["label"],
                    "normalized_values": attr.get("values", []),
                    "uom_allowed": attr.get("uom", []),
                    "filtering_yn": "Y" if attr.get("values") else "N",
                    "attr_order": order,
                }
            )
    return classpath_index, lov_rows
