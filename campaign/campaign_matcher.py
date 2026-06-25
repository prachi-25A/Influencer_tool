import json
import logging
from typing import Any, Dict, List, Optional

try:
    from groq import Groq
except ImportError:  # pragma: no cover
    Groq = None
from pydantic import BaseModel, Field, field_validator

from config import settings

logger = logging.getLogger(__name__)

GROQ_MODEL = settings.GROQ_MODEL
GROQ_TEMPERATURE = 0.0

THEME_WEIGHT = 0.40
MESSAGE_WEIGHT = 0.30
ENTITY_WEIGHT = 0.20
PURPOSE_WEIGHT = 0.10


class CampaignBrief(BaseModel):
    theme: str = Field(..., description="Core campaign theme or topic.")
    message: str = Field(..., description="Key message the campaign aims to convey.")
    required_entities: List[str] = Field(default_factory=list, description="Entities that must be mentioned.")
    purpose: str = Field(..., description="Overall purpose of the campaign.")

    @field_validator("theme", "message", "purpose")
    def fields_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field cannot be empty")
        return value.strip()


class AlignmentResult(BaseModel):
    alignment_score: int = Field(..., description="Overall alignment score (0-100).")
    theme_score: int = Field(..., description="Theme match score (0-100).")
    message_score: int = Field(..., description="Message match score (0-100).")
    entity_score: int = Field(..., description="Required entity match score (0-100).")
    purpose_score: int = Field(..., description="Purpose match score (0-100).")
    strengths: List[str] = Field(default_factory=list, description="Strengths of alignment.")
    gaps: List[str] = Field(default_factory=list, description="Gaps or misalignments.")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations.")

    @field_validator("alignment_score", "theme_score", "message_score", "entity_score", "purpose_score")
    def scores_in_range(cls, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("Score must be between 0 and 100")
        return value


def get_groq_client() -> Groq:
    if Groq is None:
        raise RuntimeError("The groq package is not installed. Install dependencies from requirements.txt.")
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required for campaign matching. Add it to your .env file.")
    return Groq(api_key=settings.GROQ_API_KEY)


def build_comparison_prompt(
    campaign: CampaignBrief,
    narrative: str,
    intent: str,
    entities: List[Dict[str, str]],
    claims: List[str],
) -> str:
    entity_list = ", ".join([f"{e['name']} ({e['type']})" for e in entities]) if entities else "None"
    claims_list = "\n".join([f"- {c}" for c in claims[:10]]) if claims else "None"

    return f"""Analyze the alignment between a campaign brief and influencer content.

CAMPAIGN BRIEF:
Theme: {campaign.theme}
Message: {campaign.message}
Required Entities: {', '.join(campaign.required_entities) if campaign.required_entities else 'None'}
Purpose: {campaign.purpose}

CONTENT ANALYSIS:
Narrative: {narrative}
Intent: {intent}
Entities: {entity_list}
Claims: {claims_list if claims_list != "None" else "None"}

Provide alignment scoring and feedback as ONLY valid JSON:
{{
  "theme_score": <0-100>,
  "message_score": <0-100>,
  "entity_score": <0-100>,
  "purpose_score": <0-100>,
  "strengths": ["<strength1>", "<strength2>", ...],
  "gaps": ["<gap1>", "<gap2>", ...],
  "recommendations": ["<recommendation1>", "<recommendation2>", ...]
}}

SCORING GUIDELINES:
- theme_score: How well does the content's narrative align with the campaign theme? (0=no alignment, 100=perfect)
- message_score: How well does the content convey the campaign's key message? (0=contradicts, 100=reinforces)
- entity_score: What percentage of required entities are mentioned/featured? (0=none, 100=all)
- purpose_score: How well does the content serve the campaign's purpose? (0=counterproductive, 100=perfectly aligned)

INSTRUCTIONS:
- Be precise and specific in feedback.
- Consider partial alignments.
- Return ONLY JSON. No additional text.
"""


def parse_groq_response(response_text: str) -> Dict[str, Any]:
    """Parse and extract JSON from Groq response."""
    try:
        data = json.loads(response_text)
        return data
    except json.JSONDecodeError:
        pass

    try:
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}") + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            data = json.loads(json_str)
            return data
    except json.JSONDecodeError:
        pass

    logger.error("Failed to parse Groq response: %s", response_text[:200])
    raise ValueError("Groq response does not contain valid JSON")


def match_required_entities(required_entities: List[str], extracted_entities: List[Dict[str, str]]) -> int:
    """Calculate entity match score based on required entities."""
    if not required_entities:
        return 100

    extracted_names = {e["name"].lower() for e in extracted_entities}
    required_lower = {e.lower() for e in required_entities}

    matched = len(required_lower & extracted_names)
    score = int((matched / len(required_entities)) * 100)
    return max(0, min(100, score))


def calculate_alignment_score(
    theme_score: int,
    message_score: int,
    entity_score: int,
    purpose_score: int,
) -> int:
    """Calculate weighted overall alignment score."""
    weighted_score = (
        (theme_score * THEME_WEIGHT)
        + (message_score * MESSAGE_WEIGHT)
        + (entity_score * ENTITY_WEIGHT)
        + (purpose_score * PURPOSE_WEIGHT)
    )
    return int(weighted_score)


def match_campaign(
    campaign_brief: Dict[str, Any],
    content_narrative: str,
    content_intent: str,
    content_entities: List[Dict[str, str]],
    content_claims: List[str],
) -> Dict[str, Any]:
    """Match influencer content against a campaign brief."""
    campaign = CampaignBrief(**campaign_brief)

    if not content_narrative or not content_intent:
        logger.error("Content narrative and intent are required")
        raise ValueError("Content narrative and intent cannot be empty")

    client = get_groq_client()
    prompt = build_comparison_prompt(
        campaign=campaign,
        narrative=content_narrative,
        intent=content_intent,
        entities=content_entities,
        claims=content_claims,
    )

    try:
        logger.info("Requesting campaign alignment analysis from Groq")
        message = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=GROQ_TEMPERATURE,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        response_text = message.choices[0].message.content.strip()
        logger.debug("Received Groq response (length=%d)", len(response_text))

        data = parse_groq_response(response_text)

        theme_score = int(data.get("theme_score", 0))
        message_score = int(data.get("message_score", 0))
        entity_score = int(data.get("entity_score", 0))
        purpose_score = int(data.get("purpose_score", 0))

        alignment_score = calculate_alignment_score(
            theme_score=theme_score,
            message_score=message_score,
            entity_score=entity_score,
            purpose_score=purpose_score,
        )

        result = AlignmentResult(
            alignment_score=alignment_score,
            theme_score=theme_score,
            message_score=message_score,
            entity_score=entity_score,
            purpose_score=purpose_score,
            strengths=data.get("strengths", []),
            gaps=data.get("gaps", []),
            recommendations=data.get("recommendations", []),
        )

        logger.info("Campaign alignment calculated: score=%d", alignment_score)
        return result.model_dump()
    except Exception as exc:
        logger.exception("Campaign alignment matching failed")
        raise RuntimeError(f"Campaign matching failed: {exc}") from exc


def batch_match_campaigns(
    campaign_brief: Dict[str, Any],
    content_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Match multiple content items against a campaign."""
    results = []
    for idx, content in enumerate(content_list, start=1):
        try:
            logger.info("Matching content item %d/%d against campaign", idx, len(content_list))
            result = match_campaign(
                campaign_brief=campaign_brief,
                content_narrative=content.get("narrative", ""),
                content_intent=content.get("intent", ""),
                content_entities=content.get("entities", []),
                content_claims=content.get("claims", []),
            )
            results.append(result)
        except Exception as exc:
            logger.error("Failed to match content item %d: %s", idx, exc)
            results.append({
                "error": str(exc),
                "alignment_score": 0,
                "theme_score": 0,
                "message_score": 0,
                "entity_score": 0,
                "purpose_score": 0,
                "strengths": [],
                "gaps": [],
                "recommendations": [],
            })
    return results
