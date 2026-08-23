"""Streamlit demo UI for ForgeCat — aligned with UniHack Solution Guide metrics."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from forgecat.config import RAW_DATA_DIR, REFERENCE_FILES
from forgecat.pipeline import run_pipeline
from forgecat.scorer import score_against_ground_truth

st.set_page_config(page_title="ForgeCat Demo", layout="wide")
st.title("ForgeCat — Product Content Enrichment Engine")
st.caption("UniHack: 6-field raw row → 252-column Delivery Format (guideline-compliant pipeline)")

with st.sidebar:
    st.header("Reference Data Status")
    for key, name in REFERENCE_FILES.items():
        found = (RAW_DATA_DIR / name).exists()
        st.write(f"{'✅' if found else '⬜'} {name}")

col1, col2 = st.columns(2)
with col1:
    input_file = st.file_uploader("Upload raw input CSV/XLSX", type=["csv", "xlsx", "xls"])
with col2:
    limit = st.number_input("Row limit (0 = all)", min_value=0, value=0, step=10)
    use_llm = st.checkbox("LLM enrichment (API key required)", value=False)

if st.button("Run Pipeline", type="primary"):
    with st.spinner("Importing master data and enriching rows..."):
        if input_file:
            temp = ROOT / "output" / f"_upload_input{Path(input_file.name).suffix}"
            temp.parent.mkdir(parents=True, exist_ok=True)
            temp.write_bytes(input_file.getvalue())
            input_path = str(temp)
        else:
            input_path = None
        result = run_pipeline(input_path=input_path, limit=limit if limit > 0 else None, use_llm=use_llm)
        st.session_state["result"] = result
        st.session_state["metrics"] = score_against_ground_truth(result)

if "result" in st.session_state:
    result = st.session_state["result"]
    metrics = st.session_state["metrics"]

    st.subheader("Evaluation (Solution Guide Metrics)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Field Accuracy", f"{metrics['field_accuracy_pct']}%")
    c2.metric("LOV Compliance", f"{metrics['lov_compliance_pct']}%")
    c3.metric("Mfg Match Rate", f"{metrics['manufacturer_match_rate_pct']}%")
    c4.metric("Needs Review", metrics["needs_review_count"])
    c5.metric("Duplicates", metrics["duplicate_count"])

    st.write(f"Ground truth: **{metrics['ground_truth_rows']}** rows from `{metrics.get('ground_truth_source', 'csv')}`")
    st.json(metrics["char_limit_compliance"])
    st.json(metrics["coverage"])

    st.subheader("Ground Truth Diffs")
    for row in metrics["per_row"]:
        label = f"{row['Mfg_Part_Num']} — {row.get('accuracy', 0)}%"
        with st.expander(label):
            if row.get("missing"):
                st.error("Not found in enriched output")
            elif row.get("diffs"):
                st.dataframe(pd.DataFrame(row["diffs"]), use_container_width=True)
            else:
                st.success(f"Perfect match ({row['matched']}/{row['total']} fields)")

    st.subheader("Review Queue")
    review = []
    for _, r in result.iterrows():
        for flag in json.loads(r.get("_needs_review", "[]")):
            review.append({**flag, "Mfg_Part_Num": r["Mfg_Part_Num"], "tier": r["_depth_tier"]})
    st.dataframe(pd.DataFrame(review) if review else pd.DataFrame([{"status": "No flags"}]), use_container_width=True)

    st.subheader("Output Preview")
    st.dataframe(
        result[["Mfg_Part_Num", "MANUFACTURER_NAME", "BRAND_NAME", "Classpath", "INVOICE_DESC", "SHORT_DESC", "_depth_tier"]].head(30),
        use_container_width=True,
    )

    csv_bytes = result[[c for c in result.columns if not c.startswith("_")]].to_csv(index=False).encode()
    st.download_button("Download Enriched CSV", csv_bytes, "enriched_delivery_format.csv", "text/csv")
