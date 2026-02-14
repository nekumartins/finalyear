"""
REST API Router — Session history & health endpoints.
The real-time work happens over WebSocket; this is for:
  - Listing past sessions
  - Retrieving session details/metrics
  - Health check

All session endpoints are protected — users can only see their own sessions.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Session, User
from backend.app.db.session import get_db
from backend.app.services.auth_service import get_current_user

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "debate-coach-backend"}


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the current user's debate sessions."""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.started_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "topic": s.topic,
            "mode": s.mode,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "duration_seconds": s.duration_seconds,
            "user_wpm": s.user_wpm,
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get details of a specific session (must belong to current user)."""
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": session.id,
        "topic": session.topic,
        "mode": session.mode,
        "user_position": session.user_position,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "duration_seconds": session.duration_seconds,
        "user_wpm": session.user_wpm,
        "ai_wpm": session.ai_wpm,
        "filler_word_count": session.filler_word_count,
        "filler_words": session.filler_words_json,
        "avg_pause_duration_ms": session.avg_pause_duration_ms,
        "turn_count": session.turn_count,
        "user_talk_ratio": session.user_talk_ratio,
    }
