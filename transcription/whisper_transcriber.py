import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None
try:
    import whisper
except ImportError:  # pragma: no cover
    whisper = None
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)
MODEL_CACHE: Dict[str, Any] = {}
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}
DEFAULT_MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
HINGLISH_MARKERS = {
    "hai", "nahi", "nahin", "ka", "ke", "ki", "mein", "mein", "kya", "ho", "hoon", "hain",
    "acha", "bahut", "chahiye", "kyun", "aap", "tum", "hum",
}


class WhisperTranscript(BaseModel):
    transcript: str = Field(..., description="Clean speech-to-text transcript.")
    language: str = Field(..., description="Detected language label.")
    duration: str = Field(..., description="Duration of the audio in seconds.")
    source_file: str = Field(..., description="Source audio or extracted video audio file path.")

    @field_validator("transcript")
    def transcript_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Transcript cannot be empty")
        return value.strip()

    @field_validator("duration")
    def duration_must_be_valid(cls, value: str) -> str:
        if not value or not value.endswith("s"):
            raise ValueError("Duration must be a string ending with 's'")
        return value

    @field_validator("source_file")
    def source_file_must_be_valid(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Source file must be provided")
        return value.strip()


def get_device() -> str:
    if torch is not None and torch.cuda.is_available():
        logger.info("Using GPU for Whisper transcription.")
        return "cuda"
    logger.info("Using CPU for Whisper transcription.")
    return "cpu"


def load_whisper_model(model_name: Optional[str] = None, device: Optional[str] = None) -> Any:
    if whisper is None:
        raise RuntimeError("The whisper package is not installed. Install dependencies from requirements.txt.")
    model_name = model_name or DEFAULT_MODEL_NAME
    device = device or get_device()
    cache_key = f"{model_name}:{device}"

    if cache_key in MODEL_CACHE:
        logger.debug("Returning cached Whisper model: %s", cache_key)
        return MODEL_CACHE[cache_key]

    try:
        logger.info("Loading Whisper model '%s' on device '%s'", model_name, device)
        model = whisper.load_model(model_name, device=device)
        MODEL_CACHE[cache_key] = model
        return model
    except Exception as exc:
        logger.exception("Failed to load Whisper model %s", model_name)
        raise RuntimeError(f"Unable to load Whisper model '{model_name}': {exc}") from exc


def validate_audio_path(audio_path: Path) -> Path:
    if not isinstance(audio_path, Path):
        audio_path = Path(audio_path)

    if not audio_path.exists():
        logger.error("Audio path does not exist: %s", audio_path)
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        logger.error("Unsupported audio extension: %s", audio_path.suffix)
        raise ValueError(f"Unsupported audio file type: {audio_path.suffix}")

    if audio_path.stat().st_size == 0:
        logger.error("Audio file is empty: %s", audio_path)
        raise ValueError(f"Audio file is empty: {audio_path}")

    return audio_path


def normalize_language(detected_language: str, transcript: str) -> str:
    if not detected_language:
        return "unknown"

    language_code = detected_language.lower()
    normalized = {
        "en": "English",
        "hi": "Hindi",
    }.get(language_code, detected_language)

    if normalized == "Hindi" and is_hinglish(transcript):
        return "Hinglish"

    if normalized == "English" and contains_devanagari(transcript):
        return "Hinglish"

    return normalized


def contains_devanagari(text: str) -> bool:
    return any("\u0900" <= char <= "\u097F" for char in text)


def is_hinglish(text: str) -> bool:
    lower_text = text.lower()
    if contains_devanagari(lower_text):
        return False

    return any(marker in lower_text.split() for marker in HINGLISH_MARKERS)


def format_duration(duration_seconds: float) -> str:
    return f"{duration_seconds:.2f}s"


def transcribe_audio(audio_path: Path, model_name: Optional[str] = None) -> Dict[str, Any]:
    """Transcribe an audio file and return a structured Whisper transcript payload."""
    audio_path = validate_audio_path(audio_path)
    if whisper is None:
        raise RuntimeError("The whisper package is not installed. Install dependencies from requirements.txt.")
    model = load_whisper_model(model_name=model_name)

    try:
        logger.info("Starting transcription for %s", audio_path)
        result = model.transcribe(str(audio_path), temperature=0.0, language=None, verbose=False)

        transcript_text = result.get("text", "").strip()
        detected_language = result.get("language", "unknown")
        audio_duration = float(result.get("audio_duration", 0.0))

        payload = WhisperTranscript(
            transcript=transcript_text,
            language=normalize_language(detected_language, transcript_text),
            duration=format_duration(audio_duration),
            source_file=str(audio_path),
        )

        logger.info("Completed transcription for %s (duration=%s)", audio_path, payload.duration)
        return payload.model_dump()
    except Exception as exc:
        logger.exception("Whisper transcription failed for %s", audio_path)
        raise RuntimeError(f"Transcription failed for {audio_path}: {exc}") from exc
