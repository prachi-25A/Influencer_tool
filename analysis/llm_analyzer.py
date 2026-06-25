import json
import logging
from typing import Any, Dict, List

try:
    from groq import Groq
except ImportError:  # pragma: no cover - exercised when dependencies are not installed
    Groq = None
from pydantic import BaseModel, Field, field_validator

from config import settings

logger = logging.getLogger(__name__)

GROQ_MODEL = settings.GROQ_MODEL
GROQ_TEMPERATURE = 0.0
MAX_RETRIES = 3
TRUNCATION_NOTICE = "[Content shortened to stay within model token limits.]"

NARRATIVE_CATEGORIES = [
    "AI Innovation",
    "Political Awareness",
    "Government Promotion",
    "Public Policy",
    "Brand Promotion",
    "Healthcare",
    "Environmental Advocacy",
    "Social Awareness",
    "Education",
    "None",
]

INTENT_CATEGORIES = [
    "Awareness",
    "Promotion",
    "Advocacy",
    "Education",
    "Persuasion",
    "Criticism",
    "Information",
    "None",
]

ENTITY_TYPES = [
    "Person",
    "Organization",
    "Brand",
    "Political Party",
    "Government Body",
    "Location",
    "Public Figure",
]

STANCE_VALUES = ["Positive", "Negative", "Neutral"]


class Entity(BaseModel):
    name: str = Field(..., description="Name of the entity.")
    type: str = Field(..., description=f"Entity type. One of: {', '.join(ENTITY_TYPES)}")
    stance: str = Field(..., description=f"Stance towards entity. One of: {', '.join(STANCE_VALUES)}")

    @field_validator("type")
    def validate_entity_type(cls, value: str) -> str:
        if value not in ENTITY_TYPES:
            raise ValueError(f"Invalid entity type: {value}. Must be one of: {', '.join(ENTITY_TYPES)}")
        return value

    @field_validator("stance")
    def validate_stance(cls, value: str) -> str:
        if value not in STANCE_VALUES:
            raise ValueError(f"Invalid stance: {value}. Must be one of: {', '.join(STANCE_VALUES)}")
        return value


class ContentAnalysis(BaseModel):
    narrative: str = Field(..., description=f"Core narrative. One of: {', '.join(NARRATIVE_CATEGORIES)}")
    intent: str = Field(..., description=f"Content intent. One of: {', '.join(INTENT_CATEGORIES)}")
    entities: List[Entity] = Field(default_factory=list, description="Named entities extracted from content.")
    claims: List[str] = Field(default_factory=list, description="Factual claims to be fact-checked.")

    @field_validator("narrative")
    def validate_narrative(cls, value: str) -> str:
        if value not in NARRATIVE_CATEGORIES:
            logger.warning("Narrative '%s' is not in predefined categories.", value)
        return value

    @field_validator("intent")
    def validate_intent(cls, value: str) -> str:
        if value not in INTENT_CATEGORIES:
            logger.warning("Intent '%s' is not in predefined categories.", value)
        return value


def get_groq_client() -> Groq:
    if Groq is None:
        raise RuntimeError("The groq package is not installed. Install dependencies from requirements.txt.")
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required for real content analysis. Add it to your .env file.")
    return Groq(api_key=settings.GROQ_API_KEY)


def prepare_text_for_analysis(text: str) -> str:
    max_chars = max(1000, int(settings.MAX_ANALYSIS_CHARS))
    clean_text = text.strip()

    if len(clean_text) <= max_chars:
        return clean_text

    notice_budget = len(TRUNCATION_NOTICE) + 2
    half_budget = max(400, (max_chars - notice_budget) // 2)
    head = clean_text[:half_budget].rsplit(" ", 1)[0].strip()
    tail = clean_text[-half_budget:].split(" ", 1)[-1].strip()
    shortened = f"{head}\n\n{TRUNCATION_NOTICE}\n\n{tail}"
    logger.info(
        "Shortened analysis input from %d to %d characters.",
        len(clean_text),
        len(shortened),
    )
    return shortened


def build_analysis_prompt(text: str) -> str:
    analysis_text = prepare_text_for_analysis(text)
    return f"""Analyze the following influencer content and extract structured intelligence.

Content:
{analysis_text}

Return ONLY valid JSON in this exact format:
{{
  "narrative": "<one of: AI Innovation, Political Awareness, Government Promotion, Public Policy, Brand Promotion, Healthcare, Environmental Advocacy, Social Awareness, Education, None>",
  "intent": "<one of: Awareness, Promotion, Advocacy, Education, Persuasion, Criticism, Information, None>",
  "entities": [
    {{
      "name": "<entity name>",
      "type": "<one of: Person, Organization, Brand, Political Party, Government Body, Location, Public Figure>",
      "stance": "<one of: Positive, Negative, Neutral>"
    }}
  ],
  "claims": ["<claim1>", "<claim2>", ...]
}}

IMPORTANT:
- Extract all named entities mentioned.
- For each entity, determine the stance (Positive/Negative/Neutral) based on how the content treats it.
- Extract ONLY factual claims that can be fact-checked.
- Return ONLY JSON. No additional text.
- If content is in Hindi or Hinglish, analyze it and return results in English.
"""


def parse_json_response(response_text: str) -> Dict[str, Any]:
    """Extract and validate JSON from LLM response."""
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

    logger.error("Failed to parse JSON from response: %s", response_text[:200])
    raise ValueError("LLM response does not contain valid JSON")


def analyze_content(text: str, retry_count: int = 0) -> Dict[str, Any]:
    """Analyze influencer content using Groq API."""
    if not text or not text.strip():
        logger.error("Empty text provided for analysis")
        raise ValueError("Content text cannot be empty")

    client = get_groq_client()
    prompt = build_analysis_prompt(text)

    try:
        logger.info("Sending content analysis request to Groq (attempt %d)", retry_count + 1)
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
        logger.debug("Received response from Groq (length=%d)", len(response_text))

        data = parse_json_response(response_text)

        analysis = ContentAnalysis(**data)
        logger.info("Content analysis completed successfully")
        return analysis.model_dump()
    except json.JSONDecodeError as exc:
        if retry_count < MAX_RETRIES:
            logger.warning("JSON parsing failed, retrying (attempt %d/%d)", retry_count + 1, MAX_RETRIES)
            return analyze_content(text, retry_count=retry_count + 1)
        logger.exception("Failed to parse JSON after %d retries", MAX_RETRIES)
        raise
    except ValueError as exc:
        if retry_count < MAX_RETRIES:
            logger.warning("Validation failed, retrying (attempt %d/%d): %s", retry_count + 1, MAX_RETRIES, exc)
            return analyze_content(text, retry_count=retry_count + 1)
        logger.exception("Content analysis validation failed after %d retries", MAX_RETRIES)
        raise
    except Exception as exc:
        logger.exception("Groq API call failed for content analysis")
        raise RuntimeError(f"Content analysis failed: {exc}") from exc


def batch_analyze_content(text_list: List[str]) -> List[Dict[str, Any]]:
    """Analyze multiple content items."""
    results = []
    for idx, text in enumerate(text_list, start=1):
        try:
            logger.info("Analyzing content item %d/%d", idx, len(text_list))
            result = analyze_content(text)
            results.append(result)
        except Exception as exc:
            logger.error("Failed to analyze content item %d: %s", idx, exc)
            results.append({
                "error": str(exc),
                "narrative": None,
                "intent": None,
                "entities": [],
                "claims": [],
            })
    return results
