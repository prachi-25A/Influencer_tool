import logging
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from analysis.llm_analyzer import analyze_content
from analysis.text_normalization import normalize_text
from campaign.campaign_matcher import match_campaign
from database.db import (
    create_analysis,
    create_campaign_score,
    create_claim,
    create_content,
    create_entities,
    create_fact_check,
    create_transcript,
    find_content_by_hash,
    update_content,
)
from factcheck.fact_checker import fact_check_claim
from ingestion.loader import load_content
from ingestion.url_parser import parse_url
from transcription.audio_processor import load_audio
from transcription.video_processor import extract_audio
from transcription.whisper_transcriber import transcribe_audio

logger = logging.getLogger(__name__)

DOCUMENT_TYPES = {"pdf", "docx", "txt"}
AUDIO_TYPES = {"mp3", "wav"}
VIDEO_TYPES = {"mp4", "mov", "avi"}


def compute_content_hash(text: str) -> str:
    compact = " ".join((text or "").lower().split())
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()


def extract_unified_text(item: Dict[str, Any]) -> Dict[str, Any]:
    file_type = item["file_type"].lower()
    file_path = Path(item["file_path"]) if item.get("file_path") else None

    if file_type in DOCUMENT_TYPES and file_path:
        parsed = load_content(file_path)
        return {"raw_text": parsed.get("content", ""), "transcript": None}

    if file_type in AUDIO_TYPES and file_path:
        audio_path = load_audio(file_path)
        transcript = transcribe_audio(audio_path)
        return {"raw_text": transcript["transcript"], "transcript": transcript}

    if file_type in VIDEO_TYPES and file_path:
        audio_path = extract_audio(file_path)
        transcript = transcribe_audio(audio_path)
        return {"raw_text": transcript["transcript"], "transcript": transcript}

    if file_type == "url":
        parsed = parse_url(item.get("source_reference", ""))
        return {"raw_text": parsed.get("content", ""), "transcript": None}

    raise ValueError(f"Unsupported content type: {file_type}")


def campaign_is_configured(campaign_brief: Optional[Dict[str, Any]]) -> bool:
    if not campaign_brief:
        return False
    return bool(campaign_brief.get("theme") and campaign_brief.get("message") and campaign_brief.get("purpose"))


def process_content_item(item: Dict[str, Any], campaign_brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    content = create_content(
        {
            "title": item["filename"],
            "source_reference": item.get("source_reference") or item.get("file_path"),
            "file_type": item["file_type"],
            "raw_text": "",
            "status": "processing",
            "metadata": {
                "source_type": item.get("source_type"),
                "uploaded_at": item.get("uploaded_at"),
            },
        }
    )

    try:
        extracted = extract_unified_text(item)
        normalized = normalize_text(extracted["raw_text"])
        content_hash = compute_content_hash(normalized["text"])
        duplicate = find_content_by_hash(content_hash, exclude_id=content.id)
        update_content(
            content.id,
            {
                "raw_text": normalized["text"],
                "metadata": {
                    **(content.metadata_json or {}),
                    "language": normalized["language"],
                    "content_hash": content_hash,
                    "duplicate_of": duplicate.id if duplicate else None,
                },
            },
        )

        if duplicate:
            update_content(content.id, {"status": "duplicate"})
            return {
                "content_id": content.id,
                "status": "duplicate",
                "duplicate_of": duplicate.id,
                "facts": [],
            }

        if extracted.get("transcript"):
            transcript = extracted["transcript"]
            create_transcript(
                content.id,
                {
                    "transcript_text": transcript["transcript"],
                    "language": transcript["language"],
                    "duration": transcript["duration"],
                    "source_file": transcript["source_file"],
                },
            )

        analysis = analyze_content(normalized["text"])
        create_analysis(
            content.id,
            {
                "narrative": analysis.get("narrative"),
                "intent": analysis.get("intent"),
                "entities": analysis.get("entities", []),
                "claims": analysis.get("claims", []),
            },
        )
        create_entities(content.id, analysis.get("entities", []))

        fact_results: List[Dict[str, Any]] = []
        for claim_text in analysis.get("claims", []):
            claim = create_claim(content.id, claim_text)
            fact_result = fact_check_claim(claim_text)
            fact_results.append(fact_result)
            create_fact_check(
                claim.id,
                {
                    "verdict": fact_result["verdict"],
                    "confidence": int(fact_result["confidence"]),
                    "evidence": fact_result.get("evidence", ""),
                    "source": fact_result.get("source", ""),
                    "correction": fact_result.get("correction", ""),
                    "reasoning": fact_result.get("reasoning", ""),
                },
            )

        if campaign_is_configured(campaign_brief):
            score = match_campaign(
                campaign_brief=campaign_brief or {},
                content_narrative=analysis.get("narrative", ""),
                content_intent=analysis.get("intent", ""),
                content_entities=analysis.get("entities", []),
                content_claims=analysis.get("claims", []),
            )
            create_campaign_score(content.id, score)

        update_content(content.id, {"status": "processed"})
        return {"content_id": content.id, "status": "processed", "facts": fact_results}
    except Exception as exc:
        logger.exception("Pipeline failed for content_id=%s", content.id)
        update_content(content.id, {"status": "error"})
        return {"content_id": content.id, "status": "error", "error": str(exc)}
