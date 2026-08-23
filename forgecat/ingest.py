from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from forgecat.config import INPUT_CSV, INPUT_XLSX, PLACEHOLDERS, RAW_DATA_DIR
from forgecat.importers.content_guidelines import import_sample_input


def clean_placeholder(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text in PLACEHOLDERS:
        return None
    return text


def ingest_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    rows = df.copy()
    for col in rows.columns:
        # Keep missing source values as empty strings.  This prevents pandas
        # NaN values from reaching string-based enrichment stages.
        rows[col] = rows[col].apply(clean_placeholder).fillna("")
    if "Mfg_Part_Num" in rows.columns:
        rows["Mfg_Part_Num"] = rows["Mfg_Part_Num"].astype(str).str.strip()
    if "Part_Desc" in rows.columns:
        rows["Part_Desc"] = rows["Part_Desc"].astype(str).str.strip()
    return rows


def normalize_mpn(mpn: str) -> str:
    return re.sub(r"[-_\s]+", "", mpn.upper())


def ingest_file(path: str | None = None) -> pd.DataFrame:
    if path:
        p = Path(path)
        if p.suffix.lower() in {".xlsx", ".xls"}:
            df = pd.read_excel(p, dtype=str).fillna("")
        else:
            df = pd.read_csv(p, dtype=str, keep_default_na=False)
        return ingest_dataframe(df)

    if INPUT_XLSX.exists():
        df = pd.read_excel(INPUT_XLSX, dtype=str).fillna("")
        return ingest_dataframe(df)

    sample = import_sample_input(RAW_DATA_DIR)
    if sample is not None and len(sample) > 0:
        return ingest_dataframe(sample)

    return ingest_dataframe(pd.read_csv(INPUT_CSV, dtype=str, keep_default_na=False))


def ingest_csv(path: str) -> pd.DataFrame:
    return ingest_file(path)
