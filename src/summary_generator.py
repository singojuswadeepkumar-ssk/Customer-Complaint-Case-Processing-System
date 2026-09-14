"""Summary generation module — produces internal management case summaries."""

from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from src.models import ComplaintRecord
from src.llm_utils import extract_text_content
from src.logger import get_logger

logger = get_logger(__name__)


_SUMMARY_TEMPLATE = """\
You are a Senior Case Manager writing an internal management report. Based on the structured complaint data below, produce a concise case summary for management review.

CASE DATA:
- Customer Name              : {customer_name}
- Email                      : {email}
- Phone                      : {phone_number}
- Complaint Category         : {complaint_category}
- Issue Description          : {issue_description}
- Resolution Provided        : {resolution_provided}
- Complaint Resolved         : {complaint_resolved}
- Escalation Required        : {escalation_required}
- Supporting Document        : {supporting_document_available}
- Overall Case Status        : {overall_case_status}

Write a structured management summary with the following sections (use the exact headings):

## Case Overview
(1–2 sentences describing who the customer is and the nature of the complaint)

## Key Issue
(Specific problem raised — factual, no embellishment)

## Action Taken
(What has been done so far to address the complaint)

## Current Status
(Current state of the case)

## Recommended Next Action
(What management should do next to resolve or close this case)

Use ONLY the information provided above. Keep each section to 2–4 sentences.
"""


def generate_management_summary(
    complaint: ComplaintRecord,
    llm: ChatGoogleGenerativeAI,
) -> Optional[str]:
    """
    Generate an internal management case summary for a complaint.

    Args:
        complaint: Structured complaint data.
        llm: Configured LangChain LLM instance.

    Returns:
        Formatted summary string, or None on failure.
    """
    prompt = PromptTemplate(
        input_variables=[
            "customer_name", "email", "phone_number",
            "complaint_category", "issue_description",
            "resolution_provided", "complaint_resolved",
            "escalation_required", "supporting_document_available",
            "overall_case_status",
        ],
        template=_SUMMARY_TEMPLATE,
    )

    chain = prompt | llm

    model_name = getattr(llm, "model", "unknown")
    try:
        logger.info(
            "Calling LLM [summary] model='%s' — generating management summary for '%s' …",
            model_name, complaint.customer_name,
        )
        response = chain.invoke({
            "customer_name": complaint.customer_name,
            "email": complaint.email or "N/A",
            "phone_number": complaint.phone_number or "N/A",
            "complaint_category": complaint.complaint_category,
            "issue_description": complaint.issue_description,
            "resolution_provided": complaint.resolution_provided or "None yet",
            "complaint_resolved": complaint.complaint_resolved,
            "escalation_required": complaint.escalation_required,
            "supporting_document_available": complaint.supporting_document_available,
            "overall_case_status": complaint.overall_case_status,
        })
        logger.info("LLM [summary] responded — extracting text content …")
        summary_text = extract_text_content(response.content) if hasattr(response, "content") else str(response)
        logger.info("LLM [summary] produced output OK | customer='%s' | model='%s'", complaint.customer_name, model_name)
        return summary_text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM [summary] FAILED for '%s' (model: %s): %s", complaint.customer_name, model_name, exc, exc_info=True)
        return None
