# Influencer Content Intelligence & Fact-Checking Platform

Production-oriented application built for the Pragyan Impact Solutions assignment. The app converts influencer documents, audio, video, and URL inputs into campaign intelligence, entity stance analysis, claim extraction, evidence-backed fact checks, and exportable stakeholder reports.

## Problem Statement

Organizations review large volumes of influencer content but need decisions in a non-technical format: what the content says, why it was created, who it discusses, whether those entities are supported or criticized, whether the content aligns with a campaign, and whether factual claims are trustworthy.

## Architecture Diagram

```text
Inputs: PDF / DOCX / TXT / MP4 / MOV / AVI / MP3 / WAV / URL
  -> Content Extraction Layer
  -> Local Whisper Speech-to-Text
  -> Text Normalization + Language Detection
  -> Groq Intelligence Layer
  -> Campaign Matching Layer
  -> Evidence Retrieval Layer
  -> Groq Fact Verification
  -> SQLite Persistence
  -> Streamlit Dashboard
  -> CSV / Excel / JSON Exports
```

## Technology Stack

- Python, Streamlit, SQLite, SQLAlchemy
- Groq API only for LLM reasoning
- Model: `llama-3.3-70b-versatile`
- Local Whisper for transcription
- `pypdf`, `python-docx`, MoviePy, Requests, BeautifulSoup
- Pydantic validation for structured outputs

## Features

- Batch upload for documents, audio, and video
- URL input for public webpages and YouTube links with available captions
- Concurrent batch-processing helper with progress callback for queue-ready scaling
- Duplicate content detection through normalized content hashing
- URL staging with extensible loader architecture
- Local Whisper transcription for English, Hindi, and Hinglish workflows
- Text normalization, Unicode cleanup, noise removal, and language detection
- Narrative detection, intent detection, named entities, entity stance, and factual claims
- Evidence retrieval from Wikipedia, trusted news, and public web sources
- Conservative fact-checking that returns `Unverified` when evidence is weak
- Campaign alignment score using required weights: theme 40%, message 30%, entities 20%, purpose 10%
- Human review flags for political content, satire, sarcasm, breaking news, and low-confidence claims
- Dashboard metrics, detailed content view, and export reports
- Claim cache to reduce repeated fact-checking cost
- Configurable LLM input trimming for long documents and webpages

## Assignment Coverage

![Assignment requirements coverage](screenshots/requirements.png)

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Groq Setup

Add your Groq key to `.env`:

```text
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
MAX_ANALYSIS_CHARS=12000
```

The project intentionally does not use OpenAI, Anthropic, or Gemini APIs.

`MAX_ANALYSIS_CHARS` keeps long webpages and documents within model and rate-limit constraints by analyzing a representative shortened version of the extracted text.

## Whisper Setup

Local Whisper is used for speech-to-text. Configure the local model size in `.env`:

```text
WHISPER_MODEL=small
```

For video files, install FFmpeg so MoviePy can extract audio.

## Running The Application

```bash
streamlit run app.py
```

Recommended review flow:

1. Configure a campaign brief.
2. Upload a TXT/PDF/DOCX or media file.
3. Submit staged content.
4. Review dashboard metrics and detailed analysis.
5. Export JSON, CSV, or Excel.

## Demo Flow

Prototype flow:

1. Start the app with `streamlit run app.py`.
2. Open the local Streamlit URL shown in the terminal.
3. Go to `Campaign Configuration` and enter the campaign theme, message, required entities, and purpose.
4. Go to `Batch Upload` and add one or more files or URLs.
5. Click `Stage Content`, confirm the staged rows appear, then click `Submit Staged Content`.
6. Open `Dashboard` to review totals, verdict counts, top narratives, top entities, and latest batch results.
7. Open `Results` to inspect narrative, intent, entity stance, claims, sources, corrections, and campaign score.
8. Open `Export Reports` and download JSON, CSV, or Excel output.

## Testing

```bash
python -m pytest
```

Current test result:

```text
13 passed in 29.49s
```

The tests cover ingestion, media validation, transcription structure, analysis structure, campaign matching, fact-check result shape, duplicate hashing, Hindi/Hinglish detection, and exports. External Groq, Whisper, document, and media integrations are mocked in tests; production runtime uses the real services and local dependencies.

## Testing Strategy

- Unit-test parsers for TXT, PDF, DOCX, URL, audio, and video handling.
- Mock LLM, Whisper, and web evidence calls so tests remain fast and repeatable.
- Validate JSON response parsing and Pydantic schema enforcement.
- Test campaign scoring weights and duplicate content hashing.
- Test export generation for CSV and Excel.
- Run manual end-to-end checks with real sample content, a campaign brief, and exported reports.
- Review failed, duplicate, low-confidence, and `Unverified` cases in the Streamlit UI.

## Reliability Design

- Groq prompts request JSON-only outputs.
- Pydantic validates analysis, campaign matching, and fact-check schemas.
- Temperature is fixed at `0.0`.
- Malformed model responses are parsed defensively and retried.
- Fact checks never fabricate evidence; weak retrieval becomes `Unverified`.
- `GROQ_API_KEY` is required for analysis, campaign matching, and Groq fact verification.
- Local Whisper and FFmpeg are required for real media transcription.
- Long content is shortened before analysis to reduce token-limit failures and cost.
- Latest batch results are surfaced in the dashboard so failed items are visible to reviewers.

## Cost And Scale Decisions

- Local Whisper handles speech-to-text so media transcription does not require paid cloud transcription.
- Duplicate content hashes prevent repeated analysis of the same content.
- Claim caching avoids repeated verification of identical claims in a batch.
- The batch processor uses a bounded thread pool to process multiple items without overwhelming the machine or API limits.
- LLM prompts request compact JSON outputs, use temperature `0.0`, and cap long extracted text with `MAX_ANALYSIS_CHARS`.
- SQLite is used for the prototype; PostgreSQL and queue workers are the intended production path for 500+ item runs.

## Fact-Checking Approach

The prototype extracts checkable factual claims from each content item, retrieves evidence from Wikipedia, trusted news domains, and public web pages, then asks Groq to compare the claim against that evidence. Each claim receives:

- Verdict: `True`, `Mostly True`, `Partially True`, `False`, `Misleading`, or `Unverified`
- Confidence score from 0 to 100
- Evidence summary
- Source URL
- Correction when the claim is false or misleading
- Short reasoning for the verdict

When evidence is missing, weak, blocked, or inconclusive, the system returns `Unverified` rather than guessing.

## Human Review Needed

Human review is still needed for:

- Political, communal, caste, religion, conflict, health, or other sensitive claims
- Breaking news and time-sensitive claims
- Satire, parody, sarcasm, or edited clips where intent may be ambiguous
- Claims with low confidence or `Unverified` verdicts
- Cases where sources conflict or public web retrieval is incomplete
- Final client-facing decisions, legal interpretation, or campaign-risk judgement

## Database

SQLite tables include:

- `content`
- `transcripts`
- `analyses`
- `entities`
- `claims`
- `fact_checks`
- `campaign_scores`
- `reports`

SQLAlchemy keeps the migration path open for PostgreSQL.

## Known Limitations

- URL ingestion supports lightweight article/public web extraction and attempts YouTube transcript extraction when captions are available.
- Evidence retrieval depends on public web availability and may be blocked by network restrictions or publisher anti-scraping controls.
- Prototype source retrieval uses a limited set of public sources and does not yet perform full source credibility scoring.
- Local Whisper can be slow on CPU-only machines.
- Social platform integrations such as Instagram Reels are designed as future extensions.
- Very long content is shortened for analysis, so reviewers should inspect the original source for final decisions.

## Future Improvements

- Add async queue workers for 500+ item processing.
- Add robust social-media adapters for Instagram Reels and platform-specific URLs.
- Add PostgreSQL migrations and deployment scripts.
- Add human review workflow with reviewer decisions.
- Add source credibility scoring and cross-source contradiction detection.
- Add multi-source evidence comparison for every high-impact claim.
- Add reviewer audit logs and user roles for production deployment.

## Screenshots

### Campaign Configuration

![Campaign configuration](screenshots/campaign_conf.png)


### Batch Upload And Processing

![Batch upload and processing](screenshots/batch_upload.png)


### Dashboard Metrics

![Dashboard metrics](screenshots/Dashboard.png)

### Results Detail View

![Results detail view](screenshots/results.png)

### Export Reports

![Export reports](screenshots/Export_report.png)

## Sample Output

The app can export a clean report in JSON, CSV, or Excel. A typical exported report includes content ID, source reference, raw text, transcript, narrative, intent, entities, claims, fact-check verdicts, confidence scores, evidence, sources, corrections, and campaign alignment scores.

## Deployment Notes

- Use Streamlit Community Cloud, an internal VM, or a containerized deployment for the dashboard.
- Keep `GROQ_API_KEY` in environment variables or a secrets manager, never in source control.
- Install FFmpeg on the host for video-to-audio extraction.
- For larger batches, move `batch_processor.py` behind a queue such as Celery/RQ and migrate SQLite to PostgreSQL.
- Persist `outputs/` and the database path on durable storage.
