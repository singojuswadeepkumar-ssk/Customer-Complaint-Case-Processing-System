"""
Workflow orchestration module.

Ties together document loading, LLM extraction, email generation,
summary generation, and reporting into a complete processing pipeline.

Processing order per document:
  1. Text extraction  (document_loader)
  2. Structured extraction  (llm_extraction)  — sequential, prerequisite for steps 3–5
  3. Save structured JSON  (reporting)
  4. Customer email generation  (email_generator)  ┐ parallel
  5. Case summary generation  (summary_generator)  ┘ threads
  6. Save email + summary  (reporting)
  7. Append to final_report.csv  (reporting)

Model strategy (task-based, not round-robin):
  Each LLM task uses the model best suited to its output quality needs:
    - Structured extraction → gemini-3.1-flash-lite (normal outcome is sufficient)
    - Management summary    → gemini-3.1-flash-lite (internal, normal outcome is sufficient)
    - Customer email        → gemini-3.5-flash-lite (customer-facing, better outcome expected)
  Both models share identical rate limits (15 RPM / 250K TPM / 500 RPD), so
  this split has no quota downside while giving the customer-facing output
  the stronger model.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from src.document_loader import load_all_documents
from src.llm_extraction import extract_complaint_data, build_llm, EXTRACTION_MODEL, SUMMARY_MODEL, EMAIL_MODEL
from src.email_generator import generate_customer_email
from src.summary_generator import generate_management_summary
from src.reporting import (
    save_structured_data,
    save_customer_email,
    save_case_summary,
    save_final_report,
    print_summary_table,
)
from src.models import ProcessingResult
from src.logger import get_logger

logger = get_logger(__name__)


def _generate_outputs_parallel(
    result: ProcessingResult,
    email_llm: ChatGoogleGenerativeAI,
    summary_llm: ChatGoogleGenerativeAI,
    output_dir: Path,
    filename_stem: str,
) -> ProcessingResult:
    """
    Run customer email and case summary generation concurrently.

    Both tasks are I/O-bound LLM calls that are fully independent once the
    structured extraction is complete, so they are submitted to a thread pool
    and executed in parallel to minimise per-document latency. Each task uses
    its own dedicated model (see module docstring for the rationale).

    Args:
        result: ProcessingResult with a populated complaint field.
        email_llm: LLM instance dedicated to customer email generation.
        summary_llm: LLM instance dedicated to management summary generation.
        output_dir: Root output directory.
        filename_stem: Base filename stem for saved outputs.

    Returns:
        Updated ProcessingResult with customer_email and management_summary set.
    """
    complaint = result.complaint

    def _gen_email() -> Optional[str]:
        logger.info("STEP 4/6 | Parallel task started — customer email generation for '%s'", complaint.customer_name)
        email = generate_customer_email(complaint, email_llm)
        if email:
            save_customer_email(email, filename_stem, output_dir)
            logger.info("STEP 4/6 complete | customer email generated + saved for '%s'", complaint.customer_name)
        else:
            logger.error("STEP 4/6 FAILED | customer email generation failed for '%s'", complaint.customer_name)
        return email

    def _gen_summary() -> Optional[str]:
        logger.info("STEP 5/6 | Parallel task started — management summary generation for '%s'", complaint.customer_name)
        summary = generate_management_summary(complaint, summary_llm)
        if summary:
            save_case_summary(summary, filename_stem, output_dir)
            logger.info("STEP 5/6 complete | management summary generated + saved for '%s'", complaint.customer_name)
        else:
            logger.error("STEP 5/6 FAILED | management summary generation failed for '%s'", complaint.customer_name)
        return summary

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="llm-gen") as executor:
        email_future = executor.submit(_gen_email)
        summary_future = executor.submit(_gen_summary)
        result.customer_email = email_future.result()
        result.management_summary = summary_future.result()

    return result


def process_single_document(
    filename: str,
    text: Optional[str],
    extraction_llm: ChatGoogleGenerativeAI,
    email_llm: ChatGoogleGenerativeAI,
    summary_llm: ChatGoogleGenerativeAI,
    output_dir: Path,
) -> ProcessingResult:
    """
    Full processing pipeline for a single complaint document.

    Steps:
        1. Validate extracted text.
        2. Run structured LLM extraction → ComplaintRecord.
        3. Persist structured JSON to output/structured_data/.
        4. Generate customer email + case summary in parallel.
        5. Persist email to output/customer_emails/.
        6. Persist summary to output/case_summaries/.

    Args:
        filename: Original document filename.
        text: Raw text extracted from the document (None if loading failed).
        extraction_llm: LLM instance dedicated to structured extraction.
        email_llm: LLM instance dedicated to customer email generation.
        summary_llm: LLM instance dedicated to management summary generation.
        output_dir: Root output directory.

    Returns:
        Completed ProcessingResult (success=True on full completion).
    """
    result = ProcessingResult(source_file=filename)
    filename_stem = Path(filename).stem

    if text is None:
        result.error = "Document could not be loaded (unsupported format or read error)."
        logger.warning("Skipping '%s' — no text extracted.", filename)
        return result

    if not text.strip():
        result.error = "Document is empty after text extraction."
        logger.warning("Skipping '%s' — document is blank.", filename)
        return result

    logger.info("-" * 60)
    logger.info("Processing document: '%s'", filename)

    # Step 1: Structured extraction
    logger.info("STEP 2/6 | Calling LLM [extraction] for '%s' …", filename)
    complaint = extract_complaint_data(text, extraction_llm)
    if complaint is None:
        result.error = "Structured LLM extraction failed."
        logger.error("STEP 2/6 FAILED | Extraction failed for '%s'.", filename)
        return result
    logger.info("STEP 2/6 complete | LLM [extraction] produced output for '%s'", filename)

    result.complaint = complaint

    # Step 2: Persist structured data
    logger.info("STEP 3/6 | Saving structured data for '%s' …", filename)
    save_structured_data(complaint, filename_stem, output_dir)
    logger.info("STEP 3/6 complete | structured data saved for '%s'", filename)

    # Step 3: Parallel email + summary generation and persistence
    result = _generate_outputs_parallel(result, email_llm, summary_llm, output_dir, filename_stem)

    result.success = True
    logger.info("STEP 6/6 | '%s' processed successfully — all outputs generated.", filename)
    return result


def run_pipeline(data_dir: Path, output_dir: Path) -> list[ProcessingResult]:
    """
    Main entry-point for the batch complaint processing pipeline.

    Processing flow:
        load_all_documents()
            └── for each document:
                    process_single_document()
                        ├── extract_complaint_data()      [sequential, EXTRACTION_MODEL]
                        ├── save_structured_data()        [sequential]
                        └── _generate_outputs_parallel()  [parallel threads]
                                ├── generate_customer_email()       [EMAIL_MODEL]
                                └── generate_management_summary()   [SUMMARY_MODEL]
        save_final_report()
        print_summary_table()

    Model assignment is task-based (see llm_extraction.py):
        - Structured extraction & management summary → gemini-3.1-flash-lite
        - Customer-facing email                       → gemini-3.5-flash-lite

    Args:
        data_dir: Directory containing complaint documents.
        output_dir: Root directory for all generated outputs.

    Returns:
        List of ProcessingResult for every document attempted.
    """
    logger.info("=" * 60)
    logger.info("Starting AI Complaint Processing Pipeline")
    logger.info("Data Dir   : %s", data_dir)
    logger.info("Output Dir : %s", output_dir)
    logger.info("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)

    documents = load_all_documents(data_dir)
    if not documents:
        logger.error("No documents to process. Exiting pipeline.")
        return []

    logger.info("Building task-based LLM clients …")
    extraction_llm = build_llm(EXTRACTION_MODEL)
    summary_llm = build_llm(SUMMARY_MODEL)
    email_llm = build_llm(EMAIL_MODEL)
    logger.info(
        "Task-based models ready — extraction: %s | summary: %s | email: %s",
        EXTRACTION_MODEL, SUMMARY_MODEL, EMAIL_MODEL,
    )

    results: list[ProcessingResult] = []
    total = len(documents)
    for idx, (filename, text) in enumerate(documents.items(), start=1):
        logger.info("Batch progress: document %d/%d — '%s'", idx, total, filename)
        result = process_single_document(filename, text, extraction_llm, email_llm, summary_llm, output_dir)
        results.append(result)

    logger.info("STEP 6/6 | Updating final CSV report …")
    save_final_report(results, output_dir)
    print_summary_table(results)

    logger.info(
        "Pipeline complete. %d/%d files succeeded.",
        sum(r.success for r in results),
        len(results),
    )
    return results
