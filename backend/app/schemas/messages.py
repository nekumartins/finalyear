"""
Debate Coach Backend - Shared Message Contracts (Pydantic v2)

These schemas define the WebSocket protocol between mobile ↔ backend.
Every message has a "type" discriminator field. Both sides parse using these.
TypeScript mirror types live in: shared/types/messages.ts
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class SessionMode(str, Enum):
    CLOUD = "cloud"
    EDGE = "edge"


class MessageDirection(str, Enum):
    CLIENT_TO_SERVER = "client_to_server"
    SERVER_TO_CLIENT = "server_to_client"


# ──────────────────────────────────────────────
# Client → Server Messages
# ──────────────────────────────────────────────

class StartSessionMsg(BaseModel):
    """Client requests a new debate session."""
    type: Literal["start_session"] = "start_session"
    mode: SessionMode = SessionMode.CLOUD
    topic: str = Field(..., min_length=3, max_length=500)
    user_position: str = Field(..., description="User's stance: 'for' or 'against'")


class AudioChunkMsg(BaseModel):
    """Client streams a chunk of audio (base64-encoded PCM16 mono 16kHz)."""
    type: Literal["audio_chunk"] = "audio_chunk"
    session_id: str
    chunk_b64: str = Field(..., description="Base64-encoded audio bytes")
    timestamp_ms: int = Field(..., description="Client-side timestamp in ms")


class EndSessionMsg(BaseModel):
    """Client ends the debate session."""
    type: Literal["end_session"] = "end_session"
    session_id: str


class PingMsg(BaseModel):
    """Heartbeat from client."""
    type: Literal["ping"] = "ping"


# ──────────────────────────────────────────────
# Server → Client Messages
# ──────────────────────────────────────────────

class SessionCreatedMsg(BaseModel):
    """Server confirms session started."""
    type: Literal["session_created"] = "session_created"
    session_id: str
    topic: str
    mode: SessionMode


class TranscriptUpdateMsg(BaseModel):
    """Incremental STT result (partial or final)."""
    type: Literal["transcript_update"] = "transcript_update"
    session_id: str
    text: str
    is_final: bool = False
    speaker: Literal["user", "ai"] = "user"


class AiResponseChunkMsg(BaseModel):
    """Streamed token(s) from the LLM counter-argument."""
    type: Literal["ai_response_chunk"] = "ai_response_chunk"
    session_id: str
    text: str
    is_final: bool = False


class TurnSignalMsg(BaseModel):
    """
    Predictive turn-taking signal.
    Sent when VAD/EoT predicts the user is about to finish speaking.
    """
    type: Literal["turn_signal"] = "turn_signal"
    session_id: str
    signal: Literal["user_will_yield", "user_speaking", "ai_should_speak"]
    confidence: float = Field(..., ge=0.0, le=1.0)


class SessionMetricsMsg(BaseModel):
    """Post-session analytics delivered when session ends."""
    type: Literal["session_metrics"] = "session_metrics"
    session_id: str
    duration_seconds: float
    user_wpm: float
    ai_wpm: float
    filler_word_count: int
    filler_words: dict[str, int] = Field(default_factory=dict)
    avg_pause_duration_ms: float
    turn_count: int
    user_talk_ratio: float = Field(..., ge=0.0, le=1.0)
    transcript: list[TranscriptEntry] = Field(default_factory=list)


class TranscriptEntry(BaseModel):
    """Single transcript segment for the session history."""
    speaker: Literal["user", "ai"]
    text: str
    start_ms: int
    end_ms: int


class ErrorMsg(BaseModel):
    """Server error message."""
    type: Literal["error"] = "error"
    code: str
    message: str


class PongMsg(BaseModel):
    """Heartbeat response."""
    type: Literal["pong"] = "pong"


# ──────────────────────────────────────────────
# Rebuild forward refs (TranscriptEntry used in SessionMetricsMsg)
# ──────────────────────────────────────────────
SessionMetricsMsg.model_rebuild()
