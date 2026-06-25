import logging
from pathlib import Path
from typing import Dict, List

from config import settings
from ingestion.docx_parser import parse_docx
from ingestion.pdf_parser import parse_pdf
from ingestion.txt_parser import parse_txt

logger = logging.getLogger(__name__)

SUPPORTED_INGESTION_MAP = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".txt": parse_txt,
}


def list_supported_files(directory: Path) -> List[Path]:
    return [
        p for p in directory.iterdir()
        if p.suffix.lower() in settings.SUPPORTED_FILE_EXTENSIONS
    ]


def is_supported_url(url: str) -> bool:
    return any(token in url for token in settings.SUPPORTED_URL_TYPES)


def save_uploaded_file(uploaded_file, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as file:
        file.write(uploaded_file.getbuffer())
    return destination


def load_content(file_path: Path) -> Dict[str, str]:
    """Load supported document content and return a normalized payload."""
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    if not file_path.exists():
        logger.error("Content file does not exist: %s", file_path)
        raise FileNotFoundError(f"Content file not found: {file_path}")

    extension = file_path.suffix.lower()
    parser = SUPPORTED_INGESTION_MAP.get(extension)

    if parser is None:
        logger.error("Unsupported ingestion file type: %s", extension)
        raise ValueError(f"Unsupported file type: {extension}")

    logger.info("Loading content from %s", file_path)
    return parser(file_path)
