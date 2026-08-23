from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SEED_DIR = Path(__file__).resolve().parent / "seed"
OUTPUT_DIR = ROOT / "output"
DB_PATH = DATA_DIR / "forgecat.db"

INPUT_CSV = RAW_DATA_DIR / "Sample-1000_Items.csv"
if not INPUT_CSV.exists():
    INPUT_CSV = ROOT / "Unihack_ Sample Dataset - Input.csv"

INPUT_XLSX = RAW_DATA_DIR / "Sample-1000_Items.xlsx"
GROUND_TRUTH_CSV = RAW_DATA_DIR / "Ground-Truth-Delivery-Format.csv"
if not GROUND_TRUTH_CSV.exists():
    GROUND_TRUTH_CSV = ROOT / "Unihack_ Expected Output - Delivery Format.csv"
GROUND_TRUTH_XLSX = RAW_DATA_DIR / "Unilog-Sample_200_Items-Input-vs-Output.xlsx"
MASTER_PROMPT_PATH = ROOT / "files" / "MASTER_PROMPT_Enrichment_Agent.md"

PLACEHOLDERS = {
    "-- Unbranded --",
    "-- No Unilog Brand --",
    "-- No DIB Brand --",
    "-",
    "",
}

CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "60"))
FULL_DEPTH_CATEGORIES = os.getenv("FULL_DEPTH_CATEGORIES", "dishwasher,faucet").lower().split(",")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
ENABLE_MANUFACTURER_FETCH = os.getenv("ENABLE_MANUFACTURER_FETCH", "false").lower() == "true"

INVOICE_DESC_MAX = 40
MOBILE_DESC_MIN = 60
MOBILE_DESC_MAX = 80

# Official reference file names (optional XLSX — not required for sample CSV workflow)
REFERENCE_FILES = {
    "sample_1000": "Sample-1000_Items.xlsx",
    "ground_truth_200": "Unilog-Sample_200_Items-Input-vs-Output.xlsx",
    "content_guidelines": "UNILOG_INTERNAL_CONTENT_GUIDELINES.docx",
    "uom": "Unilog_Master_UOM_Standards_Abbreviations_and_Terms.xlsx",
    "decimal_fraction": "Decimal_Fraction.xlsx",
    "unicat_manufacturer": "UniCat_Manufacturer_and_Brand_List.xlsx",
    "unicat_lov": "Unicat_Lov_v1_0_Updated_With_Remarks.xlsx",
    "faucets_lov": "FAUCETS_LOV.xlsx",
    "fittings_lov": "Fittings_LOV.xlsx",
    "reference_index": "Reference_Documents_Summary.xlsx",
}
