import logging
from pathlib import Path

try:
    from moviepy.editor import VideoFileClip
except ImportError:  # pragma: no cover
    VideoFileClip = None

from config import settings

logger = logging.getLogger(__name__)
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}
SUPPORTED_AUDIO_OUTPUT = ".wav"


def extract_audio(video_path: Path) -> Path:
    """Extract audio from a video file and return the path to a WAV file."""
    if not isinstance(video_path, Path):
        video_path = Path(video_path)

    output_dir = settings.OUTPUT_DIR / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_path.stem}.wav"

    if not video_path.exists():
        logger.error("Video file does not exist: %s", video_path)
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if video_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        logger.error("Unsupported video extension: %s", video_path.suffix)
        raise ValueError(f"Unsupported video type: {video_path.suffix}")

    if VideoFileClip is None:
        raise RuntimeError("MoviePy is not installed. Install dependencies from requirements.txt.")

    try:
        logger.info("Extracting audio from video: %s", video_path)
        with VideoFileClip(str(video_path)) as clip:
            if clip.audio is None:
                logger.error("No audio track found in video: %s", video_path)
                raise RuntimeError(f"Video file contains no audio track: {video_path}")
            clip.audio.write_audiofile(str(output_path), logger=None)

        if not output_path.exists() or output_path.stat().st_size == 0:
            logger.error("Audio extraction produced empty file: %s", output_path)
            raise RuntimeError(f"Audio extraction failed for {video_path}")

        logger.info("Audio extracted to: %s", output_path)
        return output_path
    except Exception as exc:
        if output_path.exists():
            try:
                output_path.unlink()
                logger.debug("Removed partial audio file: %s", output_path)
            except Exception:
                logger.warning("Unable to remove partial audio file: %s", output_path)
        logger.exception("Failed to extract audio from video: %s", video_path)
        raise
