import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def parse_txt(file_path: Path) -> Dict[str, str]:
    """Extract text from a TXT file."""
    if not file_path.exists():
        logger.error("TXT path not found: %s", file_path)
        raise FileNotFoundError(f"TXT file not found: {file_path}")

    if file_path.suffix.lower() != ".txt":
        logger.error("Unsupported TXT extension: %s", file_path.suffix)
        raise ValueError("File is not a TXT document")

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            content = handle.read().strip()
        return {
            "filename": file_path.name,
            "content": content,
            "type": "txt",
        }
    except UnicodeDecodeError:
        logger.warning("UTF-8 decode failed for TXT file, retrying with latin-1: %s", file_path)
        with open(file_path, "r", encoding="latin-1") as handle:
            content = handle.read().strip()
        return {
            "filename": file_path.name,
            "content": content,
            "type": "txt",
        }
    except Exception as exc:
        logger.exception("Failed to parse TXT file: %s", file_path)
        raise RuntimeError(f"Unable to parse TXT file {file_path}: {exc}") from exc
