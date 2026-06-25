import logging
import re
from typing import Any, Dict, Iterable, List

import requests
try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:  # pragma: no cover
    YouTubeTranscriptApi = None

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "InfluencerContentIntelligence/1.0"}


def clean_url(url: str) -> str:
    return (url or "").strip().rstrip(",").strip()


def is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def extract_youtube_video_id(url: str) -> str:
    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{6,})",
        r"[?&]v=([A-Za-z0-9_-]{6,})",
        r"/shorts/([A-Za-z0-9_-]{6,})",
        r"/embed/([A-Za-z0-9_-]{6,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


def extract_transcript_text(transcript: Any) -> str:
    if hasattr(transcript, "to_raw_data"):
        transcript = transcript.to_raw_data()
    elif hasattr(transcript, "snippets"):
        transcript = transcript.snippets

    segments: Iterable[Any]
    if isinstance(transcript, list):
        segments = transcript
    else:
        try:
            segments = list(transcript)
        except TypeError:
            segments = []

    parts: List[str] = []
    for segment in segments:
        if isinstance(segment, dict):
            text = segment.get("text", "")
        else:
            text = getattr(segment, "text", "")
        if text:
            parts.append(str(text).replace("\n", " ").strip())

    return " ".join(part for part in parts if part).strip()


def fetch_youtube_transcript(video_id: str) -> Any:
    languages = ["en", "hi", "en-US", "hi-IN"]

    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        try:
            return YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        except Exception:
            if hasattr(YouTubeTranscriptApi, "list_transcripts"):
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                for transcript in transcript_list:
                    return transcript.fetch()
            raise

    api = YouTubeTranscriptApi()
    if hasattr(api, "fetch"):
        try:
            return api.fetch(video_id, languages=languages)
        except Exception:
            if hasattr(api, "list"):
                transcript_list = api.list(video_id)
                for transcript in transcript_list:
                    if hasattr(transcript, "fetch"):
                        return transcript.fetch()
            raise

    raise RuntimeError("Unsupported youtube-transcript-api version.")


def parse_youtube_url(url: str) -> Dict[str, str]:
    url = clean_url(url)
    video_id = extract_youtube_video_id(url)
    if not video_id or YouTubeTranscriptApi is None:
        raise RuntimeError("youtube-transcript-api is required for YouTube transcript extraction.")

    try:
        transcript = fetch_youtube_transcript(video_id)
        text = extract_transcript_text(transcript)
        return {
            "filename": url,
            "content": text or "YouTube transcript was empty.",
            "type": "url",
        }
    except Exception as exc:
        logger.warning("YouTube transcript extraction failed for %s: %s", url, exc)
        return {
            "filename": url,
            "content": (
                "YouTube video transcript is unavailable for this link. "
                "Captions may be disabled, blocked, or unavailable in supported languages. "
                f"Source URL: {url}"
            ),
            "type": "url",
        }


def parse_url(url: str) -> Dict[str, str]:
    url = clean_url(url)
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    if is_youtube_url(url):
        return parse_youtube_url(url)

    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 is required for URL extraction.")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            element.extract()
        text = soup.get_text(separator=" ", strip=True)
        clean_text = re.sub(r"\s+", " ", text).strip()
        return {
            "filename": url,
            "content": clean_text,
            "type": "url",
        }
    except Exception as exc:
        logger.warning("URL extraction failed for %s: %s", url, exc)
        raise RuntimeError(f"URL extraction failed for {url}") from exc
