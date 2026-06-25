import re
import unicodedata
from typing import Dict


DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
HINGLISH_MARKERS = {
    "hai",
    "hain",
    "nahi",
    "nahin",
    "mein",
    "modi",
    "ji",
    "sarkar",
    "bharat",
    "ka",
    "ki",
    "ke",
}


def detect_language(text: str) -> str:
    lowered = text.lower()
    has_devanagari = bool(DEVANAGARI_RE.search(text))
    has_hinglish = any(marker in lowered.split() for marker in HINGLISH_MARKERS)

    if has_devanagari and has_hinglish:
        return "Hinglish"
    if has_devanagari:
        return "Hindi"
    if has_hinglish:
        return "Hinglish"
    return "English"


def normalize_text(text: str) -> Dict[str, str]:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("\x00", " ")
    normalized = re.sub(r"https?://\S+", " ", normalized)
    normalized = re.sub(r"[@#]\w+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return {
        "text": normalized,
        "lowercase_text": normalized.lower(),
        "language": detect_language(normalized),
    }
