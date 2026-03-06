"""
REST API Router — Session history, stats & health endpoints.
The real-time work happens over WebSocket; this is for:
  - Listing past sessions
  - Retrieving session details/metrics
  - Aggregated stats (streak, bests, by-goal)
  - Health check

All session endpoints are protected — users can only see their own sessions.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from backend.app.config import get_settings
from backend.app.db.models import Session, User
from backend.app.db.session import get_db
from backend.app.services.auth_service import get_current_user

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "debate-coach-backend"}


@router.get("/test-stt")
async def test_stt(user: User = Depends(get_current_user)):
    """Debug-only STT connectivity check (authenticated)."""
    import io, struct
    import httpx

    settings = get_settings()
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")

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


@router.get("/tts/providers")
async def list_tts_providers():
    """Return available TTS providers and their voices."""
    from backend.app.services.tts_service import get_available_providers
    return get_available_providers()


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
            "overall_score": (
                s.coaching_report.get("overall_score")
                if isinstance(s.coaching_report, dict)
                else None
            ),
            "coaching_goal": s.coaching_goal,
        }
        for s in sessions
    ]


@router.get("/stats")
async def user_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregated stats for the current user — streak, bests, by-goal breakdown."""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.started_at.desc())
    )
    sessions = result.scalars().all()

    total = len(sessions)
    total_minutes = sum((s.duration_seconds or 0) / 60 for s in sessions)

    # WPM stats
    wpm_vals = [s.user_wpm for s in sessions if s.user_wpm is not None]
    avg_wpm = round(sum(wpm_vals) / len(wpm_vals)) if wpm_vals else 0
    best_wpm = round(max(wpm_vals)) if wpm_vals else 0

    # Score stats
    scored = [
        (s, s.coaching_report.get("overall_score"))
        for s in sessions
        if isinstance(s.coaching_report, dict) and s.coaching_report.get("overall_score") is not None
    ]
    scores = [sc for _, sc in scored]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None
    best_score = max(scores) if scores else None

    # Streak: consecutive calendar days with at least one session (including today)
    day_set = set()
    for s in sessions:
        if s.started_at:
            day_set.add(s.started_at.date())
    streak = 0
    d = datetime.now(timezone.utc).date()
    while d in day_set:
        streak += 1
        from datetime import timedelta
        d -= timedelta(days=1)

    # Last-10 score sparkline
    recent_scores = [sc for _, sc in scored[:10]]

    # By-goal breakdown
    goals: dict[str, dict] = {}
    for s in sessions:
        g = s.coaching_goal or "unknown"
        if g not in goals:
            goals[g] = {"sessions": 0, "scores": []}
        goals[g]["sessions"] += 1
        if isinstance(s.coaching_report, dict):
            sc = s.coaching_report.get("overall_score")
            if sc is not None:
                goals[g]["scores"].append(sc)
    by_goal = {
        g: {
            "sessions": info["sessions"],
            "avg_score": round(sum(info["scores"]) / len(info["scores"]), 1) if info["scores"] else None,
        }
        for g, info in goals.items()
    }

    return {
        "total_sessions": total,
        "total_minutes": round(total_minutes, 1),
        "avg_wpm": avg_wpm,
        "best_wpm": best_wpm,
        "avg_score": avg_score,
        "best_score": best_score,
        "streak": streak,
        "recent_scores": recent_scores,
        "by_goal": by_goal,
    }


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
        "coaching_goal": session.coaching_goal,
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
        "coaching_report": session.coaching_report,
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
