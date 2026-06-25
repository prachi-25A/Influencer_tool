import json
import logging
from typing import Any, Dict, Optional

try:
    from groq import Groq
except ImportError:  # pragma: no cover
    Groq = None
from pydantic import BaseModel, Field, field_validator

from config import settings
from factcheck.evidence_retriever import EvidenceResult, retrieve_evidence

logger = logging.getLogger(__name__)
GROQ_MODEL = settings.GROQ_MODEL
GROQ_TEMPERATURE = 0.0
ALLOWED_VERDICTS = {
    "True",
    "Mostly True",
    "Partially True",
    "False",
    "Misleading",
    "Unverified",
}
CLAIM_CACHE: Dict[str, Dict[str, Any]] = {}


class FactCheckResult(BaseModel):
    claim: str = Field(..., description="The claim being verified.")
    verdict: str = Field(..., description="Fact-check verdict.")
    confidence: int = Field(..., description="Confidence score between 0 and 100.")
    evidence: str = Field(..., description="Evidence summary used for verdict.")
    source: str = Field(..., description="Evidence source URL.")
    correction: str = Field(..., description="Corrected statement if the claim is false.")
    reasoning: str = Field(..., description="Reasoning behind the verdict.")

    @field_validator("verdict")
    def validate_verdict(cls, value: str) -> str:
        if value not in ALLOWED_VERDICTS:
            raise ValueError(f"Invalid verdict: {value}")
        return value

    @field_validator("confidence")
    def validate_confidence(cls, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("Confidence must be between 0 and 100")
        return value


def get_groq_client() -> Groq:
    if Groq is None:
        raise RuntimeError("The groq package is not installed. Install dependencies from requirements.txt.")
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required for Groq fact verification. Add it to your .env file.")
    return Groq(api_key=settings.GROQ_API_KEY)


def parse_json_response(response_text: str) -> Dict[str, Any]:
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    start_idx = response_text.find("{")
    end_idx = response_text.rfind("}") + 1
    if start_idx >= 0 and end_idx > start_idx:
        try:
            return json.loads(response_text[start_idx:end_idx])
        except json.JSONDecodeError:
            pass

    logger.error("Unable to parse Groq fact-check response: %s", response_text[:200])
    raise ValueError("Invalid JSON response from Groq")


def build_fact_check_prompt(evidence: EvidenceResult) -> str:
    return f"""Verify the following claim using the provided evidence.

CLAIM:
{evidence.claim}

EVIDENCE:
{evidence.evidence}

SOURCE:
{evidence.source or 'No source available'}

Rules:
- Never invent sources.
- Never fabricate evidence.
- If evidence is weak, return Unverified.
- If evidence conflicts, return Partially True.
- If evidence fully supports the claim, return True.
- If evidence mostly supports it, return Mostly True.
- If evidence contradicts the claim, return False.
- If the claim is misleading, return Misleading.
- Provide a confidence score from 0 to 100.
- Provide a correction if the claim is false or misleading.
- Return ONLY valid JSON in the exact schema.

OUTPUT:
{{
  "claim": "<claim>",
  "verdict": "<True|Mostly True|Partially True|False|Misleading|Unverified>",
  "confidence": <0-100>,
  "evidence": "<short evidence summary>",
  "source": "<source URL>",
  "correction": "<corrected claim if false or misleading, else empty>",
  "reasoning": "<concise reasoning for verdict>"
}}
"""


def evaluate_claim_with_groq(evidence: EvidenceResult) -> Dict[str, Any]:
    client = get_groq_client()
    prompt = build_fact_check_prompt(evidence)

    try:
        logger.info("Requesting Groq fact verification for claim")
        message = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=GROQ_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.choices[0].message.content.strip()
        logger.debug("Groq fact-check response: %s", response_text[:300])
        return parse_json_response(response_text)
    except Exception as exc:
        logger.exception("Groq fact verification failed")
        raise RuntimeError(f"Groq verification failed: {exc}") from exc


def build_unverified_result(claim: str, evidence: EvidenceResult, reason: str) -> FactCheckResult:
    return FactCheckResult(
        claim=claim,
        verdict="Unverified",
        confidence=20,
        evidence=evidence.evidence or "No evidence found.",
        source=evidence.source or "",
        correction="",
        reasoning=reason,
    )


def fact_check_claim(claim: str) -> Dict[str, Any]:
    if not claim or not claim.strip():
        logger.error("Claim cannot be empty for fact checking")
        raise ValueError("Claim cannot be empty")

    cache_key = claim.strip().lower()
    if cache_key in CLAIM_CACHE:
        return CLAIM_CACHE[cache_key]

    evidence = retrieve_evidence(claim)

    if evidence.retrieval_status == "not_found" or not evidence.evidence.strip():
        logger.warning("Weak or missing evidence for claim: %s", claim)
        result = build_unverified_result(
            claim,
            evidence,
            "No credible evidence could be retrieved to verify the claim.",
        ).model_dump()
        CLAIM_CACHE[cache_key] = result
        return result

    try:
        raw_result = evaluate_claim_with_groq(evidence)
        raw_result.setdefault("claim", claim)
        raw_result.setdefault("evidence", evidence.evidence)
        raw_result.setdefault("source", evidence.source)
        raw_result.setdefault("correction", "")
        raw_result.setdefault("reasoning", "Evidence-based evaluation.")

        if raw_result.get("verdict") not in ALLOWED_VERDICTS:
            logger.warning("Groq returned invalid verdict '%s' for claim: %s", raw_result.get("verdict"), claim)
            raw_result["verdict"] = "Unverified"
            raw_result["confidence"] = min(100, max(0, int(raw_result.get("confidence", 20))))

        if raw_result.get("verdict") == "Unverified" and raw_result.get("confidence", 0) < 40:
            raw_result["confidence"] = max(raw_result.get("confidence", 0), 20)

        result = FactCheckResult(**raw_result).model_dump()
        CLAIM_CACHE[cache_key] = result
        return result
    except Exception as exc:
        logger.error("Fact-checking pipeline failed for claim '%s': %s", claim, exc)
        result = build_unverified_result(
            claim,
            evidence,
            "Fact verification failed due to an internal error.",
        ).model_dump()
        CLAIM_CACHE[cache_key] = result
        return result


def batch_fact_check(claims: list) -> list:
    results = []
    for claim in claims:
        try:
            results.append(fact_check_claim(claim))
        except Exception as exc:
            logger.error("Fact-checking failed for claim '%s': %s", claim, exc)
            results.append(
                FactCheckResult(
                    claim=claim,
                    verdict="Unverified",
                    confidence=0,
                    evidence="",
                    source="",
                    correction="",
                    reasoning=str(exc),
                ).model_dump()
            )
    return results
