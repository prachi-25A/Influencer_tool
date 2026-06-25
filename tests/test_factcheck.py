from unittest.mock import patch

from factcheck.fact_checker import fact_check_claim
from factcheck.evidence_retriever import EvidenceResult


def test_fact_check_claim_structure(monkeypatch):
    monkeypatch.setattr("factcheck.fact_checker.settings.GROQ_API_KEY", "test-key")
    claim = "The Earth orbits the Sun."
    evidence = EvidenceResult(
        claim=claim,
        evidence="Earth revolves around the Sun in an elliptical orbit.",
        source="https://example.com/earth-orbit",
        retrieval_status="public_web",
    )
    groq_result = {
        "claim": claim,
        "verdict": "True",
        "confidence": 95,
        "evidence": evidence.evidence,
        "source": evidence.source,
        "correction": "",
        "reasoning": "The evidence supports the claim.",
    }

    with patch("factcheck.fact_checker.retrieve_evidence", return_value=evidence), patch(
        "factcheck.fact_checker.evaluate_claim_with_groq", return_value=groq_result
    ):
        result = fact_check_claim(claim)

    assert "claim" in result
    assert "verdict" in result
    assert "confidence" in result
    assert "evidence" in result
    assert "reasoning" in result
