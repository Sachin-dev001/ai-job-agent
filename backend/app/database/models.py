from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class QAVault(Base):
    """Stores answered screening questions permanently so the agent learns and never asks twice."""
    __tablename__ = "qa_vault"

    id = Column(Integer, primary_key=True, index=True)
    question_pattern = Column(String(500), unique=True, index=True, nullable=False)
    canonical_answer = Column(Text, nullable=False)
    category = Column(String(100), default="general") # e.g., salary, experience, notice_period
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class JobApplicationRecord(Base):
    """Tracks applied, pending, and flagged jobs."""
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    job_title = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False) # linkedin, wellfound, naukri, etc.
    job_url = Column(Text, nullable=False)
    status = Column(String(50), default="found") # found, applied, needs_human, failed
    flag_reason = Column(Text, nullable=True) # e.g. "CAPTCHA encountered", "Custom question unknown"
    match_score = Column(Float, default=0.0)
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
