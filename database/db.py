import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm import selectinload

from config import settings
from database.models import Base, CampaignScore, Claim, Content, Entity, FactCheck, Report, Transcript, Analysis

logger = logging.getLogger(__name__)

DATABASE_URL = f"sqlite:///{settings.DATABASE_PATH}"
engine: Engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, expire_on_commit=False)


def init_db() -> None:
    Path(settings.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    logger.info("Initialized database at %s", settings.DATABASE_PATH)


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Database transaction failed, rolling back.")
        raise
    finally:
        session.close()


def create_content(payload: Dict[str, Any]) -> Content:
    with get_session() as session:
        if "metadata" in payload:
            payload = {**payload, "metadata_json": payload.pop("metadata")}
        content = Content(**payload)
        session.add(content)
        session.flush()
        session.refresh(content)
        return content


def get_content(content_id: int) -> Optional[Content]:
    with get_session() as session:
        return (
            session.query(Content)
            .options(
                selectinload(Content.transcript),
                selectinload(Content.analysis),
                selectinload(Content.entities),
                selectinload(Content.claims).selectinload(Claim.fact_check),
                selectinload(Content.campaign_score),
            )
            .filter(Content.id == content_id)
            .one_or_none()
        )


def list_content(limit: int = 100, offset: int = 0) -> List[Content]:
    with get_session() as session:
        return (
            session.query(Content)
            .options(
                selectinload(Content.transcript),
                selectinload(Content.analysis),
                selectinload(Content.entities),
                selectinload(Content.claims).selectinload(Claim.fact_check),
                selectinload(Content.campaign_score),
            )
            .order_by(Content.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )


def update_content(content_id: int, updates: Dict[str, Any]) -> Optional[Content]:
    with get_session() as session:
        content = session.get(Content, content_id)
        if not content:
            return None
        if "metadata" in updates:
            updates = {**updates, "metadata_json": updates.pop("metadata")}
        for key, value in updates.items():
            setattr(content, key, value)
        content.updated_at = datetime.utcnow()
        session.add(content)
        session.flush()
        return content


def create_transcript(content_id: int, payload: Dict[str, Any]) -> Transcript:
    with get_session() as session:
        transcript = Transcript(content_id=content_id, **payload)
        session.add(transcript)
        session.flush()
        session.refresh(transcript)
        return transcript


def create_analysis(content_id: int, payload: Dict[str, Any]) -> Analysis:
    with get_session() as session:
        analysis = Analysis(content_id=content_id, **payload)
        session.add(analysis)
        session.flush()
        session.refresh(analysis)
        return analysis


def create_entities(content_id: int, entities: List[Dict[str, Any]]) -> List[Entity]:
    with get_session() as session:
        created_entities = []
        for record in entities:
            entity = Entity(content_id=content_id, **record)
            session.add(entity)
            created_entities.append(entity)
        session.flush()
        return created_entities


def create_claim(content_id: int, claim_text: str) -> Claim:
    with get_session() as session:
        claim = Claim(content_id=content_id, claim_text=claim_text)
        session.add(claim)
        session.flush()
        session.refresh(claim)
        return claim


def create_fact_check(claim_id: int, payload: Dict[str, Any]) -> FactCheck:
    with get_session() as session:
        fact_check = FactCheck(claim_id=claim_id, **payload)
        session.add(fact_check)
        session.flush()
        session.refresh(fact_check)
        return fact_check


def create_campaign_score(content_id: int, payload: Dict[str, Any]) -> CampaignScore:
    with get_session() as session:
        score = CampaignScore(content_id=content_id, **payload)
        session.add(score)
        session.flush()
        session.refresh(score)
        return score


def create_report(content_id: int, payload: Dict[str, Any]) -> Report:
    with get_session() as session:
        report = Report(content_id=content_id, **payload)
        session.add(report)
        session.flush()
        session.refresh(report)
        return report


def get_claims_for_content(content_id: int) -> List[Claim]:
    with get_session() as session:
        return session.query(Claim).filter_by(content_id=content_id).all()


def get_fact_check_for_claim(claim_id: int) -> Optional[FactCheck]:
    with get_session() as session:
        return session.query(FactCheck).filter_by(claim_id=claim_id).one_or_none()


def get_campaign_score(content_id: int) -> Optional[CampaignScore]:
    with get_session() as session:
        return session.query(CampaignScore).filter_by(content_id=content_id).one_or_none()


def search_content_by_status(status: str, limit: int = 100) -> List[Content]:
    with get_session() as session:
        return session.query(Content).filter_by(status=status).order_by(Content.created_at.desc()).limit(limit).all()


def find_content_by_hash(content_hash: str, exclude_id: Optional[int] = None) -> Optional[Content]:
    with get_session() as session:
        query = session.query(Content).order_by(Content.created_at.desc())
        if exclude_id is not None:
            query = query.filter(Content.id != exclude_id)
        for content in query.limit(1000).all():
            metadata = content.metadata_json or {}
            if metadata.get("content_hash") == content_hash and content.status == "processed":
                return content
    return None
