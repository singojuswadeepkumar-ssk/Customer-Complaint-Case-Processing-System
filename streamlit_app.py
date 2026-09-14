"""
Streamlit web UI for the AI-Powered Customer Complaint & Case Processing System.

Lets a user upload one or more complaint documents (TXT/PDF/DOCX) through a
browser, runs the existing batch pipeline (src.workflow.run_pipeline) against
them, and displays the structured data, generated customer email, management
summary, and consolidated CSV report — all downloadable.

This module is a thin presentation layer: it does not duplicate any business
logic. All extraction / email / summary generation still goes through the
same modules used by the CLI (main.py), so behaviour is identical either way.
"""

import shutil
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.workflow import run_pipeline
from src.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

st.set_page_config(
    page_title="AI Complaint & Case Processing System",
    page_icon="📋",
    layout="wide",
)

st.title("📋 AI-Powered Customer Complaint & Case Processing System")
st.caption(
    "Upload customer complaint documents (.txt, .pdf, .docx). The system will "
    "extract structured data, draft a customer response email, write an "
    "internal management summary, and build a consolidated CSV report — all "
    "using Gemini via LangChain."
)

uploaded_files = st.file_uploader(
    "Upload complaint documents",
    type=["txt", "pdf", "docx"],
    accept_multiple_files=True,
)

run_clicked = st.button("Process Complaints", type="primary", disabled=not uploaded_files)

if run_clicked and uploaded_files:
    with tempfile.TemporaryDirectory() as tmp_root:
        data_dir = Path(tmp_root) / "data"
        output_dir = Path(tmp_root) / "output"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        for f in uploaded_files:
            dest = data_dir / f.name
            with open(dest, "wb") as out:
                out.write(f.getbuffer())
        logger.info("Saved %d uploaded file(s) to temp data dir for processing.", len(uploaded_files))

        with st.spinner(f"Processing {len(uploaded_files)} document(s) — this can take a minute per file…"):
            results = run_pipeline(data_dir=data_dir, output_dir=output_dir)

        success_count = sum(r.success for r in results)
        st.success(f"Done — {success_count}/{len(results)} document(s) processed successfully.")

        # ---- Consolidated CSV report ----
        csv_path = output_dir / "final_report.csv"
        if csv_path.exists():
            st.subheader("📊 Consolidated Report")
            st.download_button(
                "⬇️ Download final_report.csv",
                data=csv_path.read_bytes(),
                file_name="final_report.csv",
                mime="text/csv",
            )
            import pandas as pd
            st.dataframe(pd.read_csv(csv_path), use_container_width=True)

        # ---- Per-document results ----
        st.subheader("📁 Per-Document Results")
        for result in results:
            with st.expander(f"{'✅' if result.success else '❌'}  {result.source_file}"):
                if not result.success:
                    st.error(result.error or "Unknown error.")
                    continue

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("**Structured Data**")
                    if result.complaint:
                        st.json(result.complaint.model_dump())

                with col2:
                    st.markdown("**Customer Email**")
                    if result.customer_email:
                        st.text_area(
                            "Email", result.customer_email, height=250,
                            key=f"email_{result.source_file}", label_visibility="collapsed",
                        )

                with col3:
                    st.markdown("**Management Summary**")
                    if result.management_summary:
                        st.text_area(
                            "Summary", result.management_summary, height=250,
                            key=f"summary_{result.source_file}", label_visibility="collapsed",
                        )

else:
    st.info("Upload one or more complaint documents above, then click **Process Complaints**.")
