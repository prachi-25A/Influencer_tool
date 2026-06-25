import json
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import desc, func

from batch_processor import process_batch
from config import settings
from database.db import (
    get_content,
    list_content,
    get_session,
    init_db,
)
from database.models import CampaignScore, Claim, Content, Entity, FactCheck, Analysis

APP_TITLE = "Influencer Content Intelligence & Fact-Checking Platform"
ALLOWED_UPLOAD_EXTENSIONS = [".pdf", ".docx", ".txt", ".mp4", ".mov", ".avi", ".wav", ".mp3"]
ALLOWED_MEDIA_EXTENSIONS = {".mp4", ".mov", ".avi", ".mp3", ".wav"}
SENSITIVE_TOPIC_KEYWORDS = {
    "violence",
    "war",
    "terror",
    "religion",
    "caste",
    "communal",
    "hate",
    "self-harm",
    "suicide",
    "abuse",
    "harassment",
}
UPLOAD_DIR = Path(settings.OUTPUT_DIR) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_state() -> None:
    if "campaign_brief" not in st.session_state:
        st.session_state["campaign_brief"] = {
            "theme": "",
            "message": "",
            "required_entities": [],
            "purpose": "",
        }

    if "staged_uploads" not in st.session_state:
        st.session_state["staged_uploads"] = []

    if "selected_content_id" not in st.session_state:
        st.session_state["selected_content_id"] = None

    if "review_queries" not in st.session_state:
        st.session_state["review_queries"] = []

    if "last_batch_results" not in st.session_state:
        st.session_state["last_batch_results"] = []


def configure_page() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")
    init_db()
    init_state()


def get_source_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".pdf", ".docx", ".txt"}:
        return "Document"
    if suffix in {".mp4", ".mov", ".avi"}:
        return "Video"
    if suffix in {".mp3", ".wav"}:
        return "Audio"
    return "URL"


def normalize_required_entities(text: str) -> List[str]:
    return [entity.strip() for entity in text.split(",") if entity.strip()]


def stage_uploads(uploaded_files, urls_text: str) -> None:
    staged = st.session_state["staged_uploads"]
    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
            st.warning(f"Unsupported file type: {filename}")
            continue

        target_path = UPLOAD_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{filename}"
        with open(target_path, "wb") as handle:
            handle.write(uploaded_file.getbuffer())

        staged.append(
            {
                "filename": filename,
                "source_type": get_source_type(filename),
                "file_path": str(target_path),
                "file_type": suffix.replace(".", ""),
                "source_reference": str(target_path),
                "status": "staged",
                "uploaded_at": utc_now_iso(),
            }
        )

    for url in [line.strip() for line in urls_text.splitlines() if line.strip()]:
        staged.append(
            {
                "filename": url,
                "source_type": "URL",
                "file_path": "",
                "file_type": "url",
                "source_reference": url,
                "status": "staged",
                "uploaded_at": utc_now_iso(),
            }
        )

    st.success("Content staged successfully.")


def summarize_review_flags(content: Content, analysis: Optional[Analysis], claim_status: str) -> List[str]:
    flags: List[str] = []
    text = (content.raw_text or "").lower()
    narrative = (analysis.narrative or "").lower() if analysis else ""

    if "politic" in text or narrative == "political awareness":
        flags.append("Political Content")
    if any(keyword in text for keyword in ["satire", "spoof", "parody"]):
        flags.append("Satire")
    if any(keyword in text for keyword in ["sarcasm", "sarcastic", "yeah right"]):
        flags.append("Sarcasm")
    if "breaking" in text or "breaking news" in text:
        flags.append("Breaking News")
    if any(keyword in text for keyword in SENSITIVE_TOPIC_KEYWORDS):
        flags.append("Sensitive Topics")
    if claim_status == "Low Confidence Claims":
        flags.append("Low Confidence Claims")
    if content.status == "duplicate":
        flags.append("Duplicate Content")

    return flags


def get_batch_metrics() -> Dict[str, int]:
    with get_session() as session:
        total_content = session.query(func.count(Content.id)).scalar() or 0
        processed_content = (
            session.query(func.count(Content.id))
            .filter(Content.status == "processed")
            .scalar()
            or 0
        )
        error_content = (
            session.query(func.count(Content.id))
            .filter(Content.status == "error")
            .scalar()
            or 0
        )
        duplicate_content = (
            session.query(func.count(Content.id))
            .filter(Content.status == "duplicate")
            .scalar()
            or 0
        )
        average_alignment = session.query(func.avg(CampaignScore.alignment_score)).scalar() or 0
        total_claims = session.query(func.count(Claim.id)).scalar() or 0
        true_claims = (
            session.query(func.count(FactCheck.id))
            .filter(FactCheck.verdict == "True")
            .scalar()
            or 0
        )
        false_claims = (
            session.query(func.count(FactCheck.id))
            .filter(FactCheck.verdict == "False")
            .scalar()
            or 0
        )
        unverified_claims = (
            session.query(func.count(FactCheck.id))
            .filter(FactCheck.verdict == "Unverified")
            .scalar()
            or 0
        )

        top_narratives = [
            row[0]
            for row in session.query(Analysis.narrative, func.count(Analysis.narrative))
            .group_by(Analysis.narrative)
            .order_by(desc(func.count(Analysis.narrative)))
            .limit(5)
            .all()
            if row[0]
        ]

        top_entities = [
            row[0]
            for row in session.query(Entity.name, func.count(Entity.name))
            .group_by(Entity.name)
            .order_by(desc(func.count(Entity.name)))
            .limit(5)
            .all()
            if row[0]
        ]

    return {
        "total_content": total_content,
        "processed_content": processed_content,
        "error_content": error_content,
        "duplicate_content": duplicate_content,
        "average_alignment": int(average_alignment or 0),
        "total_claims": total_claims,
        "true_claims": true_claims,
        "false_claims": false_claims,
        "unverified_claims": unverified_claims,
        "top_narratives": top_narratives,
        "top_entities": top_entities,
    }


def format_content_summary(content: Content) -> Dict[str, Any]:
    analysis = content.analysis
    campaign = content.campaign_score
    claim_list = content.claims or []
    verdicts = [claim.fact_check.verdict for claim in claim_list if claim.fact_check]
    status = "Pending"
    if verdicts:
        if any(v == "False" for v in verdicts):
            status = "False Claims"
        elif any(v == "Unverified" for v in verdicts):
            status = "Unverified Claims"
        elif all(v == "True" for v in verdicts):
            status = "True Claims"
        else:
            status = "Mixed Claims"
    else:
        status = "No Claims"

    return {
        "id": content.id,
        "filename": content.title or Path(content.source_reference).name,
        "source_type": content.file_type.title(),
        "narrative": analysis.narrative if analysis else "Pending",
        "intent": analysis.intent if analysis else "Pending",
        "alignment_score": campaign.alignment_score if campaign else None,
        "claims_count": len(claim_list),
        "fact_check_status": status,
        "review_required": ", ".join(
            summarize_review_flags(content, analysis, status)
        ),
    }


def get_all_content_summary() -> List[Dict[str, Any]]:
    contents = list_content(limit=1000)
    return [format_content_summary(content) for content in contents]


def build_report_payload(selected_items: List[Content]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for content in selected_items:
        payload.append(
            {
                "content_id": content.id,
                "title": content.title,
                "source_reference": content.source_reference,
                "file_type": content.file_type,
                "status": content.status,
                "raw_text": content.raw_text,
                "transcript": content.transcript.transcript_text if content.transcript else "",
                "analysis": {
                    "narrative": content.analysis.narrative if content.analysis else "",
                    "intent": content.analysis.intent if content.analysis else "",
                    "entities": content.analysis.entities if content.analysis else [],
                    "claims": content.analysis.claims if content.analysis else [],
                },
                "campaign_score": {
                    "alignment_score": content.campaign_score.alignment_score if content.campaign_score else None,
                    "theme_score": content.campaign_score.theme_score if content.campaign_score else None,
                    "message_score": content.campaign_score.message_score if content.campaign_score else None,
                    "entity_score": content.campaign_score.entity_score if content.campaign_score else None,
                    "purpose_score": content.campaign_score.purpose_score if content.campaign_score else None,
                },
                "claims": [
                    {
                        "claim_text": claim.claim_text,
                        "fact_check": {
                            "verdict": claim.fact_check.verdict if claim.fact_check else "",
                            "confidence": claim.fact_check.confidence if claim.fact_check else None,
                            "evidence": claim.fact_check.evidence if claim.fact_check else "",
                            "source": claim.fact_check.source if claim.fact_check else "",
                            "correction": claim.fact_check.correction if claim.fact_check else "",
                            "reasoning": claim.fact_check.reasoning if claim.fact_check else "",
                        },
                    }
                    for claim in content.claims
                ],
            }
        )
    return payload


def fetch_selected_content(content_id: Optional[int]) -> Optional[Content]:
    if content_id is None:
        return None
    return get_content(content_id)


def render_dashboard() -> None:
    st.title("Dashboard")
    st.markdown(
        "Use the dashboard to track processed influencer content, campaign alignment, and claim quality in one view."
    )

    metrics = get_batch_metrics()
    cols = st.columns(5)
    cols[0].metric("Total Items", metrics["total_content"])
    cols[1].metric("Average Alignment Score", f"{metrics['average_alignment']}%")
    cols[2].metric("Total Claims", metrics["total_claims"])
    cols[3].metric("True Claims", metrics["true_claims"])
    cols[4].metric("False Claims", metrics["false_claims"])

    status_cols = st.columns(4)
    status_cols[0].metric("Processed", metrics["processed_content"])
    status_cols[1].metric("Errors", metrics["error_content"])
    status_cols[2].metric("Duplicates", metrics["duplicate_content"])
    status_cols[3].metric("Unverified Claims", metrics["unverified_claims"])

    if st.session_state.get("last_batch_results"):
        st.subheader("Latest Batch Results")
        st.dataframe(pd.DataFrame(st.session_state["last_batch_results"]), width="stretch")

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Top Narratives")
        if metrics["top_narratives"]:
            st.write(metrics["top_narratives"])
        else:
            st.info("No narratives have been analyzed yet.")

    with col_right:
        st.subheader("Top Entities")
        if metrics["top_entities"]:
            st.write(metrics["top_entities"])
        else:
            st.info("No entities have been extracted yet.")

    st.divider()
    st.subheader("Review Highlights")
    st.write(
        "Content flagged for human review appears when political content, satire, sarcasm, breaking news, or low-confidence claims are detected."
    )


def render_campaign_configuration() -> None:
    st.title("Campaign Configuration")
    st.markdown(
        "Define the campaign narrative, required entities, and purpose so the platform can match influencer content accurately."
    )

    theme = st.text_input("Campaign Theme", value=st.session_state["campaign_brief"]["theme"])
    message = st.text_area("Campaign Message", value=st.session_state["campaign_brief"]["message"])
    entities_text = st.text_input(
        "Required Entities (comma-separated)", value=", ".join(st.session_state["campaign_brief"]["required_entities"])
    )
    purpose = st.text_input("Campaign Purpose", value=st.session_state["campaign_brief"]["purpose"])

    if st.button("Save Campaign Configuration"):
        st.session_state["campaign_brief"] = {
            "theme": theme,
            "message": message,
            "required_entities": normalize_required_entities(entities_text),
            "purpose": purpose,
        }
        st.success("Campaign configuration saved.")

    if any(st.session_state["campaign_brief"].values()):
        st.subheader("Current Campaign Brief")
        st.json(st.session_state["campaign_brief"])


def render_batch_upload() -> None:
    st.title("Batch Upload")
    st.markdown(
        "Upload influencer documents, audio, and video files. You can also stage URLs for later processing."
    )

    uploaded_files = st.file_uploader(
        "Select files for batch processing",
        type=[suffix.strip(".") for suffix in ALLOWED_UPLOAD_EXTENSIONS],
        accept_multiple_files=True,
    )
    url_text = st.text_area("Enter URLs for batch processing", help="Enter one URL per line.")

    if st.button("Stage Content"):
        stage_uploads(uploaded_files or [], url_text)

    staged = st.session_state["staged_uploads"]
    if staged:
        st.subheader("Staged Content")
        staging_df = pd.DataFrame(staged)
        st.dataframe(staging_df[["filename", "source_type", "file_type", "status", "uploaded_at"]])

        if st.button("Submit Staged Content"):
            process_staged_content()

    else:
        st.info("No content staged yet. Use the uploader or add URLs to begin.")


def process_staged_content() -> None:
    staged = st.session_state["staged_uploads"]
    if not staged:
        st.warning("No staged content to process.")
        return

    errors: List[str] = []
    progress = st.progress(0)
    status_box = st.empty()

    def update_progress(completed: int, total: int, result: Dict[str, Any]) -> None:
        status_box.info(f"Processed {completed}/{total} items. Latest status: {result['status']}")
        progress.progress(completed / total)

    results = process_batch(
        staged,
        campaign_brief=st.session_state.get("campaign_brief"),
        progress_callback=update_progress,
    )
    st.session_state["last_batch_results"] = results
    for result in results:
        if result["status"] == "error":
            errors.append(
                f"Item {result.get('content_id', 'unknown')}: {result.get('error', 'Unknown error')}"
            )

    st.session_state["staged_uploads"] = []
    if errors:
        st.warning("Batch completed with errors. Check Dashboard > Latest Batch Results for details.")
        for error in errors:
            st.error(error)
    else:
        processed = sum(1 for result in results if result["status"] == "processed")
        duplicates = sum(1 for result in results if result["status"] == "duplicate")
        st.success(f"Batch completed. Processed: {processed}. Duplicates: {duplicates}.")


def render_results() -> None:
    st.title("Results")
    st.markdown(
        "Review processed content with narrative, intent, claims, fact-check status, and campaign alignment in one place."
    )

    summary = get_all_content_summary()
    if not summary:
        st.info("No processed content is available yet.")
        return

    df = pd.DataFrame(summary)
    st.dataframe(
        df[[
            "filename",
            "source_type",
            "narrative",
            "intent",
            "alignment_score",
            "claims_count",
            "fact_check_status",
            "review_required",
        ]],
        width="stretch",
    )

    content_ids = [item["id"] for item in summary]
    chosen_id = st.selectbox("Select content to inspect", options=[None] + content_ids)
    if chosen_id:
        selected_item = get_content(chosen_id)
        if selected_item:
            render_content_detail(selected_item)
        else:
            st.error("Selected content could not be found.")


def render_content_detail(content: Content) -> None:
    analysis = content.analysis
    transcript = content.transcript
    campaign = content.campaign_score
    st.subheader(f"Content Detail — {content.title or content.source_reference}")
    st.markdown(f"**Source:** {content.source_reference}")
    st.markdown(f"**File Type:** {content.file_type}")
    st.markdown(f"**Status:** {content.status}")

    review_flags = summarize_review_flags(
        content, analysis, "Low Confidence Claims" if any(
            claim.fact_check and claim.fact_check.confidence and claim.fact_check.confidence < 50
            for claim in content.claims
        ) else ""
    )
    if review_flags:
        st.warning("Human Review Required: " + ", ".join(review_flags))

    with st.expander("Transcript"):
        if transcript:
            st.text_area("Transcript", transcript.transcript_text, height=220)
        else:
            st.info("No transcript is available for this content item.")

    with st.expander("Narrative + Intent"):
        st.write("**Narrative:**", analysis.narrative if analysis else "Pending")
        st.write("**Intent:**", analysis.intent if analysis else "Pending")

    with st.expander("Entities"):
        if analysis and analysis.entities:
            st.json(analysis.entities)
        else:
            st.info("No entities extracted yet.")

    with st.expander("Claims"):
        if content.claims:
            for claim in content.claims:
                st.markdown(f"**Claim:** {claim.claim_text}")
                if claim.fact_check:
                    st.write(
                        {
                            "Verdict": claim.fact_check.verdict,
                            "Confidence": claim.fact_check.confidence,
                            "Source": claim.fact_check.source,
                            "Correction": claim.fact_check.correction,
                            "Reasoning": claim.fact_check.reasoning,
                        }
                    )
                else:
                    st.info("Claim has not been fact-checked yet.")
                st.divider()
        else:
            st.info("No claims extracted for this content item.")

    with st.expander("Campaign Score"):
        if campaign:
            st.write(
                {
                    "alignment_score": campaign.alignment_score,
                    "theme_score": campaign.theme_score,
                    "message_score": campaign.message_score,
                    "entity_score": campaign.entity_score,
                    "purpose_score": campaign.purpose_score,
                    "strengths": campaign.strengths,
                    "gaps": campaign.gaps,
                    "recommendations": campaign.recommendations,
                }
            )
        else:
            st.info("Campaign alignment has not been scored for this content item.")


def render_export_reports() -> None:
    st.title("Export Reports")
    st.markdown(
        "Export content summaries and analysis results for internal review or client reporting."
    )

    contents = list_content(limit=1000)

    if not contents:
        st.info("No content is available to export.")
        return

    content_map = {content.id: content for content in contents}
    selected_ids = st.multiselect(
        "Select items to export",
        options=[content.id for content in contents],
        format_func=lambda value: content_map[value].title or content_map[value].source_reference,
    )

    if not selected_ids:
        selected_items = contents
    else:
        selected_items = [content_map[item_id] for item_id in selected_ids]

    export_type = st.radio("Export format", ["JSON", "CSV", "Excel"])
    payload = build_report_payload(selected_items)

    if export_type == "JSON":
        export_data = json.dumps(payload, indent=2, ensure_ascii=False)
        st.download_button(
            "Download Report JSON",
            export_data,
            file_name="influencer_content_report.json",
            mime="application/json",
        )
    elif export_type == "CSV":
        rows: List[Dict[str, Any]] = []
        for item in payload:
            rows.append(
                {
                    "content_id": item["content_id"],
                    "title": item["title"],
                    "source_reference": item["source_reference"],
                    "file_type": item["file_type"],
                    "status": item["status"],
                    "alignment_score": item["campaign_score"]["alignment_score"],
                    "claims_count": len(item["claims"]),
                }
            )
        df = pd.DataFrame(rows)
        st.download_button(
            "Download Summary CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name="influencer_content_report.csv",
            mime="text/csv",
        )
    else:
        rows = []
        for item in payload:
            claim_rows = item["claims"] or [{"claim_text": "", "fact_check": {}}]
            for claim in claim_rows:
                fact_check = claim.get("fact_check", {})
                rows.append(
                    {
                        "content_id": item["content_id"],
                        "title": item["title"],
                        "source_reference": item["source_reference"],
                        "file_type": item["file_type"],
                        "narrative": item["analysis"]["narrative"],
                        "intent": item["analysis"]["intent"],
                        "entities": json.dumps(item["analysis"]["entities"], ensure_ascii=False),
                        "claim": claim.get("claim_text", ""),
                        "fact_check_verdict": fact_check.get("verdict", ""),
                        "confidence": fact_check.get("confidence", ""),
                        "source": fact_check.get("source", ""),
                        "campaign_score": item["campaign_score"]["alignment_score"],
                    }
                )
        excel_buffer = BytesIO()
        try:
            pd.DataFrame(rows).to_excel(excel_buffer, index=False)
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        except ModuleNotFoundError:
            excel_buffer = BytesIO(pd.DataFrame(rows).to_csv(index=False).encode("utf-8"))
            mime = "text/csv"
        st.download_button(
            "Download Report Excel",
            excel_buffer.getvalue(),
            file_name="influencer_content_report.xlsx",
            mime=mime,
        )


def main() -> None:
    configure_page()
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select a page",
        ["Dashboard", "Campaign Configuration", "Batch Upload", "Results", "Export Reports"],
    )
    st.sidebar.markdown("---")
    st.sidebar.write("Project: Influencer Content Intelligence & Fact-Checking Platform")
    st.sidebar.write(f"Groq configured: {'yes' if settings.GROQ_API_KEY else 'no'}")
    st.sidebar.write(f"Whisper model: {settings.WHISPER_MODEL}")

    if page == "Dashboard":
        render_dashboard()
    elif page == "Campaign Configuration":
        render_campaign_configuration()
    elif page == "Batch Upload":
        render_batch_upload()
    elif page == "Results":
        render_results()
    elif page == "Export Reports":
        render_export_reports()


if __name__ == "__main__":
    main()
