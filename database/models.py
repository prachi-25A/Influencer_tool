from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Content(Base):
    __tablename__ = "content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=True)
    source_reference = Column(String(1024), nullable=True)
    file_type = Column(String(50), nullable=False)
    raw_text = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    metadata_json = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transcript = relationship("Transcript", back_populates="content", uselist=False)
    analysis = relationship("Analysis", back_populates="content", uselist=False)
    entities = relationship("Entity", back_populates="content", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="content", cascade="all, delete-orphan")
    campaign_score = relationship("CampaignScore", back_populates="content", uselist=False)
    reports = relationship("Report", back_populates="content", cascade="all, delete-orphan")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    transcript_text = Column(Text, nullable=False)
    language = Column(String(50), nullable=True)
    duration = Column(String(50), nullable=True)
    source_file = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content = relationship("Content", back_populates="transcript")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    narrative = Column(String(255), nullable=True)
    intent = Column(String(255), nullable=True)
    entities = Column(JSON, nullable=True)
    claims = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content = relationship("Content", back_populates="analysis")


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)
    stance = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content = relationship("Content", back_populates="entities")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    claim_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content = relationship("Content", back_populates="claims")
    fact_check = relationship("FactCheck", back_populates="claim", uselist=False, cascade="all, delete-orphan")


class FactCheck(Base):
    __tablename__ = "fact_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(Integer, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    verdict = Column(String(50), nullable=False)
    confidence = Column(Integer, nullable=False)
    evidence = Column(Text, nullable=True)
    source = Column(String(1024), nullable=True)
    correction = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    claim = relationship("Claim", back_populates="fact_check")


class CampaignScore(Base):
    __tablename__ = "campaign_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    alignment_score = Column(Integer, nullable=False)
    theme_score = Column(Integer, nullable=False)
    message_score = Column(Integer, nullable=False)
    entity_score = Column(Integer, nullable=False)
    purpose_score = Column(Integer, nullable=False)
    strengths = Column(JSON, nullable=True)
    gaps = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content = relationship("Content", back_populates="campaign_score")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    report_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False, default="ready")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content = relationship("Content", back_populates="reports")
