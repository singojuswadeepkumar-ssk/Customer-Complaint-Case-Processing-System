"""Reporting module — saves outputs to disk and consolidates a CSV report."""

import json
from pathlib import Path

import pandas as pd

from src.models import ComplaintRecord, ProcessingResult
from src.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Sub-folder names (mirrors the required output/ structure)
# ---------------------------------------------------------------------------
STRUCTURED_DATA_DIR = "structured_data"
CUSTOMER_EMAILS_DIR = "customer_emails"
CASE_SUMMARIES_DIR = "case_summaries"
FINAL_REPORT_NAME = "final_report.csv"


def save_structured_data(complaint: ComplaintRecord, filename_stem: str, output_dir: Path) -> Path:
    """
    Persist the extracted ComplaintRecord as a formatted JSON file.

    Args:
        complaint: Validated structured complaint data.
        filename_stem: Base name (without extension) derived from the source document.
        output_dir: Root output directory.

    Returns:
        Path to the saved JSON file.
    """
    dest = output_dir / STRUCTURED_DATA_DIR
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / f"{filename_stem}_structured.json"
    out_path.write_text(
        json.dumps(complaint.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Structured data saved → %s", out_path)
    return out_path


def save_customer_email(email_text: str, filename_stem: str, output_dir: Path) -> Path:
    """
    Persist the generated customer response email as a plain-text file.

    Args:
        email_text: Email body text.
        filename_stem: Base name (without extension) derived from the source document.
        output_dir: Root output directory.

    Returns:
        Path to the saved file.
    """
    dest = output_dir / CUSTOMER_EMAILS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / f"{filename_stem}_email.txt"
    out_path.write_text(email_text, encoding="utf-8")
    logger.info("Customer email saved → %s", out_path)
    return out_path


def save_case_summary(summary_text: str, filename_stem: str, output_dir: Path) -> Path:
    """
    Persist the internal management case summary as a plain-text file.

    Args:
        summary_text: Summary body text.
        filename_stem: Base name (without extension) derived from the source document.
        output_dir: Root output directory.

    Returns:
        Path to the saved file.
    """
    dest = output_dir / CASE_SUMMARIES_DIR
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / f"{filename_stem}_summary.txt"
    out_path.write_text(summary_text, encoding="utf-8")
    logger.info("Case summary saved → %s", out_path)
    return out_path


def build_csv_row(result: ProcessingResult) -> dict:
    """
    Flatten a ProcessingResult into a single CSV row dictionary.

    Args:
        result: Fully processed complaint result.

    Returns:
        Dictionary representing one CSV row.
    """
    row: dict = {
        "source_file": result.source_file,
        "success": result.success,
        "error": result.error or "",
    }

    if result.complaint:
        c = result.complaint
        row.update({
            "customer_name": c.customer_name,
            "email": c.email or "",
            "phone_number": c.phone_number or "",
            "complaint_category": c.complaint_category,
            "issue_description": c.issue_description,
            "resolution_provided": c.resolution_provided or "",
            "complaint_resolved": c.complaint_resolved,
            "escalation_required": c.escalation_required,
            "supporting_document_available": c.supporting_document_available,
            "overall_case_status": c.overall_case_status,
        })
    else:
        for field in (
            "customer_name", "email", "phone_number", "complaint_category",
            "issue_description", "resolution_provided", "complaint_resolved",
            "escalation_required", "supporting_document_available", "overall_case_status",
        ):
            row[field] = ""

    return row


def save_final_report(results: list[ProcessingResult], output_dir: Path) -> Path:
    """
    Write all processing results to the consolidated final_report.csv.

    Args:
        results: List of ProcessingResult objects (one per document).
        output_dir: Root output directory.

    Returns:
        Path to the saved CSV file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / FINAL_REPORT_NAME

    rows = [build_csv_row(r) for r in results]
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False, encoding="utf-8")

    logger.info("Final report saved → %s  (%d rows)", csv_path, len(df))
    return csv_path


def print_summary_table(results: list[ProcessingResult]) -> None:
    """Print a human-readable summary table to stdout after batch processing."""
    print("\n" + "=" * 80)
    print("  BATCH PROCESSING SUMMARY")
    print("=" * 80)
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    print(f"  Total files processed : {len(results)}")
    print(f"  Successful            : {success_count}")
    print(f"  Failed / Skipped      : {fail_count}")
    print("=" * 80)
    for r in results:
        status = "✓" if r.success else "✗"
        name = r.complaint.customer_name if r.complaint else "—"
        category = r.complaint.complaint_category if r.complaint else "—"
        print(f"  {status}  {r.source_file:<35}  {name:<25}  {category}")
        if not r.success and r.error:
            print(f"       ERROR: {r.error}")
    print("=" * 80 + "\n")
