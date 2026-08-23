from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_sheet(path: Path, sheet: str | int = 0, header_row: int | None = None) -> pd.DataFrame:
    """Read an Excel sheet, optionally skipping merged/multi-row headers."""
    if header_row is not None:
        df = pd.read_excel(path, sheet_name=sheet, header=header_row, dtype=str)
    else:
        df = pd.read_excel(path, sheet_name=sheet, dtype=str)
    df = df.dropna(how="all").fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_column(df: pd.DataFrame, *candidates: str) -> str | None:
    lower_map = {str(c).lower().strip(): c for c in df.columns}
    for cand in candidates:
        key = cand.lower()
        if key in lower_map:
            return lower_map[key]
        for col_lower, col_orig in lower_map.items():
            if key in col_lower:
                return col_orig
    return None


def first_existing(path: Path, *names: str) -> Path | None:
    for name in names:
        candidate = path / name
        if candidate.exists():
            return candidate
    return None
