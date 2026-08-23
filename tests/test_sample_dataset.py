"""Tests run exclusively against the sample CSV dataset — no XLSX required."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "Unihack_ Sample Dataset - Input.csv"
OUT = ROOT / "Unihack_ Expected Output - Delivery Format.csv"


@pytest.fixture(scope="module")
def enriched():
    from forgecat.pipeline import run_pipeline

    return run_pipeline(limit=None)


@pytest.fixture(scope="module")
def metrics(enriched):
    from forgecat.scorer import score_against_ground_truth

    return score_against_ground_truth(enriched)


def test_input_dataset_loaded():
    df = pd.read_csv(INP, dtype=str)
    assert len(df) == 1000
    assert list(df.columns) == [
        "Mfg_Part_Num", "Part_Desc", "E1_Brand", "Unilog_Brand", "DIB_Brand", "Part_Manuf"
    ]


def test_all_rows_enriched(enriched):
    assert len(enriched) == 1000
    assert "MANUFACTURER_NAME" in enriched.columns
    assert "Classpath" in enriched.columns
    assert "INVOICE_DESC" in enriched.columns


def test_no_placeholder_in_output(enriched):
    for col in ["MANUFACTURER_NAME", "BRAND_NAME"]:
        vals = enriched[col].astype(str)
        assert not vals.str.startswith("--").any()


def test_ground_truth_perfect(metrics):
    assert metrics["ground_truth_rows"] == 2
    assert metrics["field_accuracy_pct"] == 100.0
    for row in metrics["per_row"]:
        assert row["accuracy"] == 100.0


def test_tier_coverage(enriched):
    tiers = enriched["_depth_tier"].value_counts()
    assert tiers.get("A", 0) >= 10          # all dishwashers
    assert tiers.get("B", 0) >= 900           # nearly all rows classified
    assert tiers.get("C", 0) == 0             # no unclassified tier


def test_manufacturer_match_rate(metrics):
    assert metrics["manufacturer_match_rate_pct"] >= 85.0


def test_lov_compliance(metrics):
    assert metrics["lov_compliance_pct"] >= 95.0


def test_char_limits(metrics):
    assert metrics["char_limit_compliance"]["INVOICE_DESC"] == 100.0


def test_dishwashers_tier_a(enriched):
    inp = pd.read_csv(INP, dtype=str)
    dw_mpns = inp[inp["Part_Desc"].str.contains("dishwasher", case=False, na=False)]["Mfg_Part_Num"]
    for mpn in dw_mpns:
        row = enriched[enriched["Mfg_Part_Num"] == mpn].iloc[0]
        assert row["_depth_tier"] == "A"
        assert row["MANUFACTURER_NAME"] != ""
        assert row["BRAND_NAME"] != ""


def test_output_schema_matches_delivery_format(enriched):
    expected_cols = pd.read_csv(OUT, nrows=0).columns.tolist()
    output_cols = [c for c in enriched.columns if not c.startswith("_")]
    for col in expected_cols:
        assert col in output_cols
