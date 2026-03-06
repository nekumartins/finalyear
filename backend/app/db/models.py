"""
Debate Coach Backend - Database Models (SQLAlchemy 2.0 async)
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Column, DateTime, Enum, Float, Integer, String, Text, JSON, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """A registered user of the debate coach."""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Null for OAuth-only users
    auth_provider = Column(String(20), default="local")   # "local" or "google"
    google_id = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    """A single debate session between user and AI."""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    mode = Column(Enum("cloud", "edge", name="session_mode"), nullable=False)
    topic = Column(Text, nullable=False)
    user_position = Column(String(10), nullable=False)
    coaching_goal = Column(String(20), nullable=True)  # confidence | speed | structure
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    ended_at = Column(DateTime, nullable=True)

    # Post-session metrics (populated when session ends)
    duration_seconds = Column(Float, nullable=True)
    user_wpm = Column(Float, nullable=True)
    ai_wpm = Column(Float, nullable=True)
    filler_word_count = Column(Integer, nullable=True)
    filler_words_json = Column(JSON, nullable=True)
    avg_pause_duration_ms = Column(Float, nullable=True)
    turn_count = Column(Integer, nullable=True)
    user_talk_ratio = Column(Float, nullable=True)

    # AI coaching report (structured JSON generated post-session)
    coaching_report = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")
    transcript_entries = relationship("TranscriptEntry", back_populates="session", cascade="all, delete-orphan")


class TranscriptEntry(Base):
    """A single utterance in the debate transcript."""
    __tablename__ = "transcript_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    speaker = Column(Enum("user", "ai", name="speaker_type"), nullable=False)
    text = Column(Text, nullable=False)
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)

    session = relationship("Session", back_populates="transcript_entries")
