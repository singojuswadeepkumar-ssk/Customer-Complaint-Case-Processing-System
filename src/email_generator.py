"""Email generation module — produces professional customer response emails."""

from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from src.models import ComplaintRecord
from src.llm_utils import extract_text_content
from src.logger import get_logger

logger = get_logger(__name__)


_EMAIL_TEMPLATE = """\
You are a professional Customer Relations Manager. Write a formal, empathetic, and concise response email to a customer based on the complaint case details below.

CASE DETAILS:
- Customer Name      : {customer_name}
- Complaint Category : {complaint_category}
- Issue Description  : {issue_description}
- Resolution Provided: {resolution_provided}
- Complaint Resolved : {complaint_resolved}
- Case Status        : {overall_case_status}

EMAIL REQUIREMENTS:
1. Start with "Subject: Re: Your Complaint – [category]"
2. Use a warm, professional greeting addressing the customer by name.
3. Acknowledge the inconvenience caused.
4. Summarize the issue and the resolution or next steps (use ONLY the information above — do NOT add or invent any details).
5. Provide a clear expected timeline or next action if the issue is not yet resolved.
6. Close with a professional sign-off from "Customer Support Team".
7. Keep the email between 150–250 words.

Write ONLY the email — no explanations, no commentary.
"""


def generate_customer_email(
    complaint: ComplaintRecord,
    llm: ChatGoogleGenerativeAI,
) -> Optional[str]:
    """
    Generate a professional customer response email for a complaint.

    Args:
        complaint: Structured complaint data.
        llm: Configured LangChain LLM instance.

    Returns:
        Email text string, or None on failure.
    """
    prompt = PromptTemplate(
        input_variables=[
            "customer_name",
            "complaint_category",
            "issue_description",
            "resolution_provided",
            "complaint_resolved",
            "overall_case_status",
        ],
        template=_EMAIL_TEMPLATE,
    )

    chain = prompt | llm

    model_name = getattr(llm, "model", "unknown")
    try:
        logger.info(
            "Calling LLM [email] model='%s' — generating customer email for '%s' …",
            model_name, complaint.customer_name,
        )
        response = chain.invoke({
            "customer_name": complaint.customer_name,
            "complaint_category": complaint.complaint_category,
            "issue_description": complaint.issue_description,
            "resolution_provided": complaint.resolution_provided or "Not yet determined",
            "complaint_resolved": complaint.complaint_resolved,
            "overall_case_status": complaint.overall_case_status,
        })
        logger.info("LLM [email] responded — extracting text content …")
        email_text = extract_text_content(response.content) if hasattr(response, "content") else str(response)
        logger.info("LLM [email] produced output OK | customer='%s' | model='%s'", complaint.customer_name, model_name)
        return email_text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM [email] FAILED for '%s' (model: %s): %s", complaint.customer_name, model_name, exc, exc_info=True)
        return None
