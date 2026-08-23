#!/usr/bin/env python3
"""CLI entry point for ForgeCat enrichment pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from forgecat.pipeline import run_pipeline
from forgecat.scorer import score_against_ground_truth


def main() -> None:
    parser = argparse.ArgumentParser(description="ForgeCat Product Enrichment Pipeline")
    parser.add_argument("--input", default=None, help="Path to raw input CSV/XLSX")
    parser.add_argument("--output", default=str(ROOT / "output" / "enriched_delivery_format.csv"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--score", action="store_true")
    args = parser.parse_args()

    print("Importing master data and running pipeline...")
    result = run_pipeline(input_path=args.input, output_path=args.output, limit=args.limit, use_llm=args.llm)
    print(f"Enriched {len(result)} rows -> {args.output}")

    if "_depth_tier" in result.columns:
        print(f"Coverage: A={( result['_depth_tier'] == 'A').sum()}, B={(result['_depth_tier'] == 'B').sum()}, C={(result['_depth_tier'] == 'C').sum()}")

    if args.score:
        metrics = score_against_ground_truth(result)
        metrics_path = ROOT / "output" / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"Ground truth: {metrics['ground_truth_rows']} rows ({metrics['ground_truth_format']})")
        print(f"Field accuracy: {metrics['field_accuracy_pct']}%")
        print(f"LOV compliance: {metrics['lov_compliance_pct']}%")
        print(f"Manufacturer match rate: {metrics['manufacturer_match_rate_pct']}%")
        print(f"Review queue: {metrics['needs_review_count']} rows")
        print(f"Duplicates: {metrics['duplicate_count']} rows")
        print(f"Metrics -> {metrics_path}")


if __name__ == "__main__":
    main()
