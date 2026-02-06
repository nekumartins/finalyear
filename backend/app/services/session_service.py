"""
Service: Session Manager
Handles creating, tracking, and ending debate sessions.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Session
from backend.app.schemas.messages import SessionMode


class SessionService:
    """Manages debate session lifecycle."""

    async def create_session(
        self,
        db: AsyncSession,
        topic: str,
        user_position: str,
        mode: SessionMode,
    ) -> Session:
        session = Session(
            id=str(uuid4()),
            topic=topic,
            user_position=user_position,
            mode=mode.value,
            started_at=datetime.utcnow(),
        )
        db.add(session)
        await db.flush()
        return session

    async def end_session(
        self,
        db: AsyncSession,
        session_id: str,
        metrics: dict,
    ) -> Session:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.ended_at = datetime.utcnow()
        session.duration_seconds = metrics.get("duration_seconds", 0)
        session.user_wpm = metrics.get("user_wpm", 0)
        session.ai_wpm = metrics.get("ai_wpm", 0)
        session.filler_word_count = metrics.get("filler_word_count", 0)
        session.filler_words_json = metrics.get("filler_words", {})
        session.avg_pause_duration_ms = metrics.get("avg_pause_duration_ms", 0)
        session.turn_count = metrics.get("turn_count", 0)
        session.user_talk_ratio = metrics.get("user_talk_ratio", 0)
        await db.flush()
        return session

    async def get_session(self, db: AsyncSession, session_id: str) -> Session | None:
        result = await db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def list_sessions(self, db: AsyncSession, limit: int = 20) -> list[Session]:
        result = await db.execute(
            select(Session).order_by(Session.started_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


session_service = SessionService()
