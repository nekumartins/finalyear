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

from sqlalchemy.orm import selectinload

from backend.app.db.models import Session, User
from backend.app.db.session import get_db
from backend.app.services.auth_service import get_current_user

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "debate-coach-backend"}


@router.get("/test-stt")
async def test_stt():
    """Test Deepgram STT with a silent audio clip — verifies API key and connectivity."""
    import io, struct
    from backend.app.config import get_settings
    import httpx

    settings = get_settings()
    key = settings.deepgram_api_key
    if not key:
        return {"error": "No DEEPGRAM_API_KEY configured"}

    # Build a 1-second silent WAV (16kHz, mono, PCM16)
    sample_rate, channels, bits = 16000, 1, 16
    num_samples = sample_rate  # 1 second
    pcm = bytes(num_samples * 2)  # all zeros = silence
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm)

    buf = io.BytesIO()
    buf.write(b"RIFF"); buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE"); buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16)); buf.write(struct.pack("<H", 1))
    buf.write(struct.pack("<H", channels)); buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", byte_rate)); buf.write(struct.pack("<H", block_align))
    buf.write(struct.pack("<H", bits)); buf.write(b"data")
    buf.write(struct.pack("<I", data_size)); buf.write(pcm)
    wav_bytes = buf.getvalue()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params={"model": "nova-3", "language": "en"},
                headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"},
                content=wav_bytes,
            )
        return {
            "status_code": resp.status_code,
            "ok": resp.status_code == 200,
            "transcript": (
                resp.json()
                .get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "(empty — silence expected)")
            ) if resp.status_code == 200 else resp.text[:300],
        }
    except Exception as e:
        return {"error": str(e)}


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
        select(Session)
        .where(Session.id == session_id, Session.user_id == user.id)
        .options(selectinload(Session.transcript_entries))
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
        "transcript": [
            {
                "speaker": t.speaker,
                "text": t.text,
                "startMs": t.start_ms,
                "endMs": t.end_ms,
            }
            for t in session.transcript_entries
        ],
    }
