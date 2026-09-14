"""Document loader module — reads TXT, PDF, and DOCX files and extracts raw text."""

from pathlib import Path
from typing import Optional

from src.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def load_document(file_path: Path) -> Optional[str]:
    """
    Extract plain text from a supported document file.

    Handles TXT, PDF, and DOCX formats.  Returns None and logs a warning
    for unsupported or unreadable files rather than raising.

    Args:
        file_path: Path to the document file.

    Returns:
        Extracted text string, or None on failure.
    """
    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        logger.warning("Unsupported file type '%s' — skipping %s", suffix, file_path.name)
        return None

    try:
        if suffix == ".txt":
            return _load_txt(file_path)
        if suffix == ".pdf":
            return _load_pdf(file_path)
        if suffix == ".docx":
            return _load_docx(file_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read '%s': %s", file_path.name, exc, exc_info=True)
        return None

    return None  # unreachable, but satisfies type checker


# ---------------------------------------------------------------------------
# Format-specific helpers
# ---------------------------------------------------------------------------

def _load_txt(file_path: Path) -> str:
    """Read a plain-text file with UTF-8 fallback to latin-1."""
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.debug("UTF-8 decode failed for '%s', retrying with latin-1", file_path.name)
        return file_path.read_text(encoding="latin-1")


def _load_pdf(file_path: Path) -> str:
    """Extract text from a PDF using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF  # cspell:ignore fitz
    except ImportError as exc:
        raise ImportError(
            "PyMuPDF is required to read PDF files. Install it with: pip install pymupdf"
        ) from exc

    text_parts: list[str] = []
    with fitz.open(str(file_path)) as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))

    text = "\n".join(text_parts).strip()
    if not text:
        logger.warning("PDF '%s' yielded no extractable text (may be image-only).", file_path.name)
    return text


def _load_docx(file_path: Path) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError(
            "python-docx is required to read DOCX files. Install it with: pip install python-docx"
        ) from exc

    doc = Document(str(file_path))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)


def load_all_documents(data_dir: Path) -> dict[str, Optional[str]]:
    """
    Load every supported document found directly inside *data_dir*.

    Args:
        data_dir: Directory that contains the complaint documents.

    Returns:
        Mapping of filename → extracted text (None if extraction failed).
    """
    if not data_dir.exists():
        logger.error("Data directory does not exist: %s", data_dir)
        return {}

    results: dict[str, Optional[str]] = {}
    files = sorted(
        f for f in data_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        logger.warning("No supported documents found in %s", data_dir)
        return {}

    logger.info("STEP 1/6 | Reading input files from '%s' — %d document(s) found", data_dir, len(files))
    for idx, file_path in enumerate(files, start=1):
        logger.info("Reading file %d/%d: %s", idx, len(files), file_path.name)
        text = load_document(file_path)
        if text:
            logger.info(
                "File read OK: %s (%d characters extracted)", file_path.name, len(text)
            )
        else:
            logger.error("File read FAILED: %s — no text extracted", file_path.name)
        results[file_path.name] = text

    logger.info(
        "STEP 1/6 complete | %d/%d file(s) read successfully",
        sum(1 for v in results.values() if v),
        len(files),
    )
    return results
