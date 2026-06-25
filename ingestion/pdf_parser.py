import logging
from pathlib import Path
from typing import Dict

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

logger = logging.getLogger(__name__)


def parse_pdf(file_path: Path) -> Dict[str, str]:
    """Extract text from a PDF file."""
    if not file_path.exists():
        logger.error("PDF path not found: %s", file_path)
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    if file_path.suffix.lower() != ".pdf":
        logger.error("Unsupported PDF extension: %s", file_path.suffix)
        raise ValueError("File is not a PDF document")

    if PdfReader is None:
        raise RuntimeError("pypdf is not installed. Install dependencies from requirements.txt.")

    try:
        reader = PdfReader(str(file_path))
        text_chunks = []

        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)
            logger.debug("Extracted page %s text length=%s", page_number, len(page_text))

        content = "\n".join(text_chunks).strip()
        return {
            "filename": file_path.name,
            "content": content,
            "type": "pdf",
        }
    except Exception as exc:
        logger.exception("Failed to parse PDF file: %s", file_path)
        raise RuntimeError(f"Unable to parse PDF file {file_path}: {exc}") from exc
