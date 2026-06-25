import logging
from pathlib import Path

logger = logging.getLogger(__name__)
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3"}


def load_audio(audio_path: Path) -> Path:
    """Validate and return an audio path ready for transcription."""
    if not isinstance(audio_path, Path):
        audio_path = Path(audio_path)

    if not audio_path.exists():
        logger.error("Audio file does not exist: %s", audio_path)
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        logger.error("Unsupported audio extension: %s", audio_path.suffix)
        raise ValueError(f"Unsupported audio type: {audio_path.suffix}")

    if audio_path.stat().st_size == 0:
        logger.error("Audio file is empty: %s", audio_path)
        raise ValueError(f"Audio file is empty: {audio_path}")

    logger.info("Audio file ready for transcription: %s", audio_path)
    return audio_path
