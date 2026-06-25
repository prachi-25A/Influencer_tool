import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import requests
try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
DUCKDUCKGO_SEARCH_URL = "https://html.duckduckgo.com/html/"
TRUSTED_NEWS_DOMAINS = {
    "reuters.com",
    "bbc.com",
    "cnn.com",
    "nytimes.com",
    "theguardian.com",
    "bloomberg.com",
    "ndtv.com",
    "hindustantimes.com",
    "timesofindia.indiatimes.com",
    "indiatoday.in",
}
HEADERS = {
    "User-Agent": "InfluencerContentVerifier/1.0 (+https://example.com)"
}
MAX_SEARCH_RESULTS = 5
MAX_EVIDENCE_CHARS = 1200


class EvidenceResult(BaseModel):
    claim: str = Field(..., description="The original claim to validate.")
    evidence: str = Field(..., description="Retrieved evidence text.")
    source: str = Field(..., description="URL of the evidence source.")
    retrieval_status: str = Field(..., description="Evidence retrieval status.")

    @field_validator("retrieval_status")
    def validate_status(cls, value: str) -> str:
        if value not in {"wikipedia", "trusted_news", "public_web", "not_found", "error"}:
            raise ValueError("Invalid retrieval status")
        return value


def fetch_wikipedia_evidence(claim: str) -> Optional[EvidenceResult]:
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": claim,
        "utf8": 1,
        "srlimit": 3,
    }

    try:
        response = requests.get(WIKIPEDIA_SEARCH_URL, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        search_results = data.get("query", {}).get("search", [])

        if not search_results:
            return None

        page = search_results[0]
        title = page.get("title")
        pageid = page.get("pageid")

        if not title or not pageid:
            return None

        summary_params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "pageids": pageid,
            "utf8": 1,
        }

        summary_response = requests.get(WIKIPEDIA_SEARCH_URL, params=summary_params, headers=HEADERS, timeout=15)
        summary_response.raise_for_status()
        summary_data = summary_response.json()
        page_info = summary_data.get("query", {}).get("pages", {}).get(str(pageid), {})
        extract = page_info.get("extract", "").strip()

        if not extract:
            return None

        evidence_text = summarize_evidence_text(extract)
        source_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        return EvidenceResult(
            claim=claim,
            evidence=evidence_text,
            source=source_url,
            retrieval_status="wikipedia",
        )
    except Exception as exc:
        logger.warning("Wikipedia evidence retrieval failed: %s", exc)
        return None


def search_duckduckgo(claim: str) -> List[Dict[str, str]]:
    if BeautifulSoup is None:
        logger.warning("BeautifulSoup is not installed; skipping public web search.")
        return []

    try:
        data = {"q": claim}
        response = requests.post(DUCKDUCKGO_SEARCH_URL, data=data, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for result in soup.select(".result__body")[:MAX_SEARCH_RESULTS]:
            title_element = result.select_one("a.result__a")
            snippet_element = result.select_one("a.result__snippet") or result.select_one("div.result__snippet")
            if not title_element:
                continue

            href = title_element.get("href") or ""
            snippet = snippet_element.get_text(separator=" ", strip=True) if snippet_element else ""
            results.append({"url": href, "snippet": snippet})

        return results
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)
        return []


def fetch_webpage_text(url: str) -> Optional[str]:
    if BeautifulSoup is None:
        logger.warning("BeautifulSoup is not installed; skipping webpage extraction.")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup(["script", "style", "noscript"]):
            script.extract()

        text = soup.get_text(separator=" ", strip=True)
        clean = re.sub(r"\s+", " ", text).strip()
        return summarize_evidence_text(clean)
    except Exception as exc:
        logger.warning("Failed to fetch webpage text from %s: %s", url, exc)
        return None


def summarize_evidence_text(text: str) -> str:
    if len(text) <= MAX_EVIDENCE_CHARS:
        return text
    return text[:MAX_EVIDENCE_CHARS].rsplit(" ", 1)[0] + "..."


def select_trusted_source(results: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    for item in results:
        url = item.get("url", "")
        domain = extract_domain(url)
        if domain in TRUSTED_NEWS_DOMAINS:
            return item
    return None


def extract_domain(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    if not match:
        return ""
    domain = match.group(1).lower()
    return domain


def retrieve_evidence(claim: str) -> EvidenceResult:
    if not claim or not claim.strip():
        logger.error("Claim cannot be empty for evidence retrieval")
        raise ValueError("Claim cannot be empty")

    logger.info("Retrieving evidence for claim: %s", claim)
    wiki_result = fetch_wikipedia_evidence(claim)
    if wiki_result:
        return wiki_result

    search_results = search_duckduckgo(claim)
    trusted = select_trusted_source(search_results)
    if trusted:
        evidence_text = fetch_webpage_text(trusted["url"]) or trusted.get("snippet", "")
        if evidence_text:
            return EvidenceResult(
                claim=claim,
                evidence=evidence_text,
                source=trusted["url"],
                retrieval_status="trusted_news",
            )

    for item in search_results:
        evidence_text = fetch_webpage_text(item["url"]) or item.get("snippet", "")
        if evidence_text:
            return EvidenceResult(
                claim=claim,
                evidence=evidence_text,
                source=item["url"],
                retrieval_status="public_web",
            )

    logger.warning("No evidence found for claim: %s", claim)
    return EvidenceResult(
        claim=claim,
        evidence="",
        source="",
        retrieval_status="not_found",
    )


def batch_retrieve_evidence(claims: List[str]) -> List[EvidenceResult]:
    results: List[EvidenceResult] = []
    for claim in claims:
        try:
            results.append(retrieve_evidence(claim))
        except Exception as exc:
            logger.error("Evidence retrieval failed for claim '%s': %s", claim, exc)
            results.append(
                EvidenceResult(
                    claim=claim,
                    evidence="",
                    source="",
                    retrieval_status="error",
                )
            )
    return results
