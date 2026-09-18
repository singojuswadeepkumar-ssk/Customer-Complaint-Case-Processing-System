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

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

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

def _zip_directory(directory: Path) -> bytes:
    """Zip up all files under `directory` (recursively), preserving relative paths."""
    files = [p for p in directory.rglob("*") if p.is_file()]
    if not files:
        return b""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=file_path.relative_to(directory))
    return buffer.getvalue()


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

        # Heavy (langchain/Gemini) imports are deferred until first use so the
        # page shell above renders instantly instead of blocking on module load.
        with st.spinner("Loading AI engine (first run only)…"):
            from src.workflow import run_pipeline

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

        # ---- Download everything at once ----
        zip_bytes = _zip_directory(output_dir)
        if zip_bytes:
            st.download_button(
                "⬇️ Download all outputs (.zip)",
                data=zip_bytes,
                file_name="output.zip",
                mime="application/zip",
                help="Includes structured_data/, customer_emails/, case_summaries/, and final_report.csv",
            )

        # ---- Per-document results ----
        st.subheader("📁 Per-Document Results")
        for result in results:
            with st.expander(f"{'✅' if result.success else '❌'}  {result.source_file}"):
                if not result.success:
                    st.error(result.error or "Unknown error.")
                    continue

                stem = Path(result.source_file).stem
                structured_path = output_dir / "structured_data" / f"{stem}_structured.json"
                email_path = output_dir / "customer_emails" / f"{stem}_email.txt"
                summary_path = output_dir / "case_summaries" / f"{stem}_summary.txt"

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("**Structured Data**")
                    if result.complaint:
                        st.json(result.complaint.model_dump())
                    if structured_path.exists():
                        st.download_button(
                            "⬇️ Download JSON",
                            data=structured_path.read_bytes(),
                            file_name=structured_path.name,
                            mime="application/json",
                            key=f"dl_structured_{result.source_file}",
                        )

                with col2:
                    st.markdown("**Customer Email**")
                    if result.customer_email:
                        st.text_area(
                            "Email", result.customer_email, height=250,
                            key=f"email_{result.source_file}", label_visibility="collapsed",
                        )
                    if email_path.exists():
                        st.download_button(
                            "⬇️ Download Email",
                            data=email_path.read_bytes(),
                            file_name=email_path.name,
                            mime="text/plain",
                            key=f"dl_email_{result.source_file}",
                        )

                with col3:
                    st.markdown("**Management Summary**")
                    if result.management_summary:
                        st.text_area(
                            "Summary", result.management_summary, height=250,
                            key=f"summary_{result.source_file}", label_visibility="collapsed",
                        )
                    if summary_path.exists():
                        st.download_button(
                            "⬇️ Download Summary",
                            data=summary_path.read_bytes(),
                            file_name=summary_path.name,
                            mime="text/plain",
                            key=f"dl_summary_{result.source_file}",
                        )

else:
    st.info("Upload one or more complaint documents above, then click **Process Complaints**.")
