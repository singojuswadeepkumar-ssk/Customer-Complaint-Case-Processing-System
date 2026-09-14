"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError
from src.models import ComplaintRecord, YesNo, ComplaintCategory, CaseStatus, ProcessingResult


VALID_DATA = {
    "customer_name": "Jane Doe",
    "email": "jane@example.com",
    "phone_number": "+1-555-0100",
    "complaint_category": "Billing",
    "issue_description": "Overcharged on last invoice.",
    "resolution_provided": "Refund initiated.",
    "complaint_resolved": "Yes",
    "escalation_required": "No",
    "supporting_document_available": "Yes",
    "overall_case_status": "Resolved",
}


def test_valid_complaint_record():
    record = ComplaintRecord(**VALID_DATA)
    assert record.customer_name == "Jane Doe"
    assert record.complaint_category == ComplaintCategory.BILLING
    assert record.complaint_resolved == YesNo.YES


def test_optional_fields_none():
    data = VALID_DATA.copy()
    data["email"] = None
    data["phone_number"] = None
    data["resolution_provided"] = None
    record = ComplaintRecord(**data)
    assert record.email is None


def test_invalid_category_raises():
    data = VALID_DATA.copy()
    data["complaint_category"] = "InvalidCategory"
    with pytest.raises(ValidationError):
        ComplaintRecord(**data)


def test_processing_result_default():
    result = ProcessingResult(source_file="test.txt")
    assert result.success is False
    assert result.complaint is None
    assert result.error is None
