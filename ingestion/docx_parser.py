import logging
from pathlib import Path
from typing import Dict

try:
    from docx import Document
except ImportError:  # pragma: no cover
    Document = None

logger = logging.getLogger(__name__)


def parse_docx(file_path: Path) -> Dict[str, str]:
    """Extract text from a DOCX file."""
    if not file_path.exists():
        logger.error("DOCX path not found: %s", file_path)
        raise FileNotFoundError(f"DOCX file not found: {file_path}")

    if file_path.suffix.lower() != ".docx":
        logger.error("Unsupported DOCX extension: %s", file_path.suffix)
        raise ValueError("File is not a DOCX document")

    if Document is None:
        raise RuntimeError("python-docx is not installed. Install dependencies from requirements.txt.")

    try:
        document = Document(str(file_path))
        paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        content = "\n".join(paragraphs).strip()
        logger.debug("Extracted DOCX paragraphs=%s", len(paragraphs))

        return {
            "filename": file_path.name,
            "content": content,
            "type": "docx",
        }
    except Exception as exc:
        logger.exception("Failed to parse DOCX file: %s", file_path)
        raise RuntimeError(f"Unable to parse DOCX file {file_path}: {exc}") from exc
