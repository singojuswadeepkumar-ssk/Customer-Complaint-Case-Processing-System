"""LLM extraction module — uses Gemini via LangChain to parse complaint documents."""

import json
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.models import ComplaintRecord
from src.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Task-based model assignment.
#
# Both models share identical rate limits (15 RPM / 250K TPM / 500 RPD), so
# the choice below is driven by expected output quality per task rather than
# quota — the customer-facing email uses the stronger model, while the
# higher-volume / internal-facing tasks use the lite model.
# ---------------------------------------------------------------------------
EXTRACTION_MODEL = "gemini-3.1-flash-lite"   # Structured JSON — deterministic, normal outcome is sufficient
SUMMARY_MODEL = "gemini-3.1-flash-lite"      # Internal management summary — normal outcome is sufficient
EMAIL_MODEL = "gemini-3.5-flash-lite"        # Customer-facing email — better tone/quality expected


_EXTRACTION_TEMPLATE = """\
You are an expert customer complaint analyst. Carefully read the customer complaint document below and extract structured information in valid JSON.

DOCUMENT:
{document_text}

Extract the following fields and return ONLY a valid JSON object (no markdown, no extra text):

{{
  "customer_name": "<full name of the customer, or 'Unknown' if not found>",
  "email": "<customer email address or null>",
  "phone_number": "<customer phone number or null>",
  "complaint_category": "<one of: Billing, Technical, Delivery, Product Quality, Customer Service, Refund, Account, Other>",
  "issue_description": "<concise but complete description of the issue>",
  "resolution_provided": "<resolution or action taken, or null if none mentioned>",
  "complaint_resolved": "<Yes, No, or Unknown>",
  "escalation_required": "<Yes, No, or Unknown>",
  "supporting_document_available": "<Yes, No, or Unknown>",
  "overall_case_status": "<one of: Open, In Progress, Resolved, Escalated, Closed, Pending>"
}}

Rules:
- Use ONLY information present in the document. Do NOT hallucinate.
- If a field is not mentioned, use null or "Unknown".
- Return ONLY the JSON object, nothing else.
"""


def build_llm(model_name: str, temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """
    Instantiate a single Gemini LLM via LangChain.

    Args:
        model_name: Gemini model identifier.
        temperature: Sampling temperature (low = deterministic).

    Returns:
        Configured ChatGoogleGenerativeAI instance.
    """
    logger.info("Building LLM client | model='%s' | temperature=%s", model_name, temperature)
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
    )
    logger.info("LLM client ready | model='%s'", model_name)
    return llm


def extract_complaint_data(
    document_text: str,
    llm: ChatGoogleGenerativeAI,
) -> Optional[ComplaintRecord]:
    """
    Extract structured complaint data from raw document text using Gemini.

    Args:
        document_text: Plain text content of the complaint document.
        llm: Configured LangChain LLM instance (see EXTRACTION_MODEL).

    Returns:
        Validated ComplaintRecord, or None on failure.
    """
    prompt = PromptTemplate(
        input_variables=["document_text"],
        template=_EXTRACTION_TEMPLATE,
    )
    parser = JsonOutputParser()

    chain = prompt | llm | parser

    model_name = getattr(llm, "model", "unknown")
    try:
        logger.info(
            "Calling LLM [extraction] model='%s' — sending %d chars for structured extraction …",
            model_name, min(len(document_text), 12000),
        )
        raw: dict = chain.invoke({"document_text": document_text[:12000]})  # token guard
        logger.info("LLM [extraction] responded — parsing JSON output …")
        complaint = ComplaintRecord(**raw)
        logger.info(
            "LLM [extraction] produced output OK | customer='%s' | model='%s'",
            complaint.customer_name, model_name,
        )
        return complaint
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM [extraction] FAILED (model: %s): %s", model_name, exc, exc_info=True)
        return None
