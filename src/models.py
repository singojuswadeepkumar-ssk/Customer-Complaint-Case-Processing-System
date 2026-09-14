"""Pydantic models for structured complaint data extraction and validation."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class YesNo(str, Enum):
    YES = "Yes"
    NO = "No"
    UNKNOWN = "Unknown"


class ComplaintCategory(str, Enum):
    BILLING = "Billing"
    TECHNICAL = "Technical"
    DELIVERY = "Delivery"
    PRODUCT_QUALITY = "Product Quality"
    CUSTOMER_SERVICE = "Customer Service"
    REFUND = "Refund"
    ACCOUNT = "Account"
    OTHER = "Other"


class CaseStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    ESCALATED = "Escalated"
    CLOSED = "Closed"
    PENDING = "Pending"


class ComplaintRecord(BaseModel):
    """Structured complaint data extracted from a customer document."""

    customer_name: str = Field(
        description="Full name of the customer"
    )
    email: Optional[str] = Field(
        default=None,
        description="Customer email address"
    )
    phone_number: Optional[str] = Field(
        default=None,
        description="Customer phone number"
    )
    complaint_category: ComplaintCategory = Field(
        description="Primary category of the complaint"
    )
    issue_description: str = Field(
        description="Detailed description of the issue raised by the customer"
    )
    resolution_provided: Optional[str] = Field(
        default=None,
        description="Resolution or solution offered to the customer, if any"
    )
    complaint_resolved: YesNo = Field(
        description="Whether the complaint has been resolved (Yes/No)"
    )
    escalation_required: YesNo = Field(
        description="Whether escalation to a higher team is required (Yes/No)"
    )
    supporting_document_available: YesNo = Field(
        description="Whether supporting documents were provided by the customer (Yes/No)"
    )
    overall_case_status: CaseStatus = Field(
        description="Current overall status of the case"
    )

    model_config = ConfigDict(use_enum_values=True)


class ProcessingResult(BaseModel):
    """Full processing result for a single complaint document."""

    source_file: str
    complaint: Optional[ComplaintRecord] = None
    customer_email: Optional[str] = None
    management_summary: Optional[str] = None
    error: Optional[str] = None
    success: bool = False
