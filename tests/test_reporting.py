"""Tests for reporting module."""

import json
from pathlib import Path
import pandas as pd
from src.models import ComplaintRecord, ProcessingResult
from src.reporting import (
    build_csv_row,
    save_final_report,
    save_structured_data,
    save_customer_email,
    save_case_summary,
    STRUCTURED_DATA_DIR,
    CUSTOMER_EMAILS_DIR,
    CASE_SUMMARIES_DIR,
    FINAL_REPORT_NAME,
)


COMPLAINT = ComplaintRecord(
    customer_name="Alice Smith",
    email="alice@example.com",
    phone_number="555-0200",
    complaint_category="Technical",
    issue_description="App crashes on login.",
    resolution_provided="Reset account credentials.",
    complaint_resolved="Yes",
    escalation_required="No",
    supporting_document_available="No",
    overall_case_status="Resolved",
)


def _make_result(success: bool = True) -> ProcessingResult:
    r = ProcessingResult(source_file="test_doc.txt", success=success)
    if success:
        r.complaint = COMPLAINT
        r.customer_email = "Dear Alice, ..."
        r.management_summary = "## Case Overview\n..."
    else:
        r.error = "Extraction failed."
    return r


def test_build_csv_row_success():
    row = build_csv_row(_make_result(True))
    assert row["customer_name"] == "Alice Smith"
    assert row["success"] is True
    assert row["error"] == ""


def test_build_csv_row_failure():
    row = build_csv_row(_make_result(False))
    assert row["customer_name"] == ""
    assert row["success"] is False
    assert "Extraction" in row["error"]


def test_save_csv_report(tmp_path: Path):
    results = [_make_result(True), _make_result(False)]
    csv_path = save_final_report(results, tmp_path)
    assert csv_path.name == FINAL_REPORT_NAME
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) == 2
    assert "customer_name" in df.columns


def test_save_structured_data(tmp_path: Path):
    complaint = _make_result(True).complaint
    path = save_structured_data(complaint, "test_doc", tmp_path)
    assert path.exists()
    assert path.parent.name == STRUCTURED_DATA_DIR
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["customer_name"] == "Alice Smith"


def test_save_customer_email(tmp_path: Path):
    path = save_customer_email("Dear Customer …", "test_doc", tmp_path)
    assert path.exists()
    assert path.parent.name == CUSTOMER_EMAILS_DIR
    assert path.read_text(encoding="utf-8") == "Dear Customer …"


def test_save_case_summary(tmp_path: Path):
    path = save_case_summary("## Case Overview\n…", "test_doc", tmp_path)
    assert path.exists()
    assert path.parent.name == CASE_SUMMARIES_DIR
