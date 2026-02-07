"""
WebSocket Handler — The central nervous system.

Orchestrates the real-time flow:
  Client audio → STT (buffered) → Transcript update to client
                → Turn-Taking → when user yields → LLM → streamed response

Each connected client gets its own handler instance with isolated state.
"""
import asyncio
import base64
import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

from backend.app.schemas.messages import (
    AiResponseChunkMsg,
    AudioChunkMsg,
    EndSessionMsg,
    ErrorMsg,
    PongMsg,
    SessionCreatedMsg,
    SessionMetricsMsg,
    StartSessionMsg,
    TranscriptEntry,
    TranscriptUpdateMsg,
    TurnSignalMsg,
)
from backend.app.services.llm_service import get_llm_service
from backend.app.services.metrics_service import metrics_service
from backend.app.services.stt_service import get_stt_service
from backend.app.services.turn_taking_service import get_turn_taking_service

logger = logging.getLogger(__name__)


class DebateWebSocketHandler:
    """Handles a single WebSocket connection's lifecycle."""

    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.session_id: str | None = None
        self.mode: str = "cloud"
        self.topic: str = ""
        self.user_position: str = ""
        self.transcript: list[TranscriptEntry] = []
        self.session_start_time: float = 0
        self.current_user_text: str = ""
        self.conversation_history: list[dict] = []
        self._ai_responding: bool = False  # Prevent overlapping AI responses

        # Services (initialized on session start)
        self.stt_service = None
        self.llm_service = None
        self.turn_taking_service = None

    async def handle(self) -> None:
        """Main loop: read messages and dispatch."""
        await self.ws.accept()
        logger.info("WebSocket connected")

        try:
            while True:
                raw = await self.ws.receive_text()
                data = json.loads(raw)
                msg_type = data.get("type")

                match msg_type:
                    case "start_session":
                        await self._handle_start_session(data)
                    case "audio_chunk":
                        await self._handle_audio_chunk(data)
                    case "end_session":
                        await self._handle_end_session(data)
                    case "ping":
                        await self._send(PongMsg())
                    case _:
                        await self._send(ErrorMsg(
                            code="unknown_type",
                            message=f"Unknown message type: {msg_type}"
                        ))

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected (session={self.session_id})")
        except Exception as e:
            logger.exception(f"WebSocket error: {e}")
            try:
                await self._send(ErrorMsg(code="internal_error", message=str(e)))
            except Exception:
                pass

    async def _handle_start_session(self, data: dict) -> None:
        msg = StartSessionMsg(**data)
        self.session_id = f"session-{int(time.time() * 1000)}"
        self.mode = msg.mode.value
        self.topic = msg.topic
        self.user_position = msg.user_position
        self.session_start_time = time.time()
        self.transcript = []
        self.conversation_history = []
        self.current_user_text = ""
        self._ai_responding = False

        # Initialize services for this session's mode
        self.stt_service = get_stt_service(self.mode)
        self.llm_service = get_llm_service(self.mode)
        self.turn_taking_service = get_turn_taking_service()

        await self._send(SessionCreatedMsg(
            session_id=self.session_id,
            topic=self.topic,
            mode=msg.mode,
        ))
        logger.info(f"Session started: {self.session_id} (mode={self.mode})")

    async def _handle_audio_chunk(self, data: dict) -> None:
        if not self.session_id:
            await self._send(ErrorMsg(code="no_session", message="Start a session first"))
            return

        msg = AudioChunkMsg(**data)
        audio_bytes = base64.b64decode(msg.chunk_b64)

        # ── 1. Turn-taking analysis ──
        prediction = await self.turn_taking_service.analyze_chunk(audio_bytes)

        if prediction.should_ai_speak:
            signal = "ai_should_speak"
        elif prediction.is_speech:
            signal = "user_speaking"
        else:
            signal = "user_will_yield"

        await self._send(TurnSignalMsg(
            session_id=self.session_id,
            signal=signal,
            confidence=prediction.eot_probability,
        ))

        # ── 2. Speech-to-Text (buffered) ──
        stt_result = await self.stt_service.transcribe_chunk(audio_bytes)

        if stt_result and stt_result.get("text"):
            text = stt_result["text"]
            self.current_user_text += " " + text

            # Send transcript update to client
            await self._send(TranscriptUpdateMsg(
                session_id=self.session_id,
                text=self.current_user_text.strip(),
                is_final=stt_result.get("is_final", False),
                speaker="user",
            ))

        # ── 3. If turn-taking says user is done → trigger AI response ──
        if prediction.should_ai_speak and self.current_user_text.strip() and not self._ai_responding:
            # Save user turn to transcript
            now_ms = int((time.time() - self.session_start_time) * 1000)
            user_text = self.current_user_text.strip()

            # Flush any remaining audio in STT buffer before AI responds
            flush_result = await self.stt_service.flush()
            if flush_result and flush_result.get("text"):
                user_text += " " + flush_result["text"]
                self.current_user_text = user_text

            self.transcript.append(TranscriptEntry(
                speaker="user",
                text=user_text,
                start_ms=max(0, now_ms - len(user_text) * 30),  # approximate
                end_ms=now_ms,
            ))

            await self._generate_ai_response()

    async def _generate_ai_response(self) -> None:
        """Stream an AI counter-argument back to the client."""
        user_text = self.current_user_text.strip()
        if not user_text:
            return

        self._ai_responding = True

        # Add user turn to conversation history
        self.conversation_history.append({"role": "user", "content": user_text})

        full_response = ""
        ai_start_ms = int((time.time() - self.session_start_time) * 1000)

        try:
            async for token in self.llm_service.generate_response_stream(
                user_text=user_text,
                topic=self.topic,
                user_position=self.user_position,
                conversation_history=self.conversation_history,
            ):
                full_response += token
                await self._send(AiResponseChunkMsg(
                    session_id=self.session_id,
                    text=token,
                    is_final=False,
                ))

            # Send final marker
            await self._send(AiResponseChunkMsg(
                session_id=self.session_id,
                text="",
                is_final=True,
            ))

            # Save AI turn
            ai_end_ms = int((time.time() - self.session_start_time) * 1000)
            if full_response.strip():
                self.conversation_history.append({"role": "assistant", "content": full_response})
                self.transcript.append(TranscriptEntry(
                    speaker="ai",
                    text=full_response.strip(),
                    start_ms=ai_start_ms,
                    end_ms=ai_end_ms,
                ))

        except Exception as e:
            logger.error(f"[LLM] Response generation failed: {e}")
            await self._send(ErrorMsg(code="llm_error", message=str(e)))
        finally:
            # Reset for next user turn
            self.current_user_text = ""
            self._ai_responding = False

    async def _handle_end_session(self, data: dict) -> None:
        if not self.session_id:
            return

        # Flush any remaining STT buffer
        if self.stt_service:
            flush_result = await self.stt_service.flush()
            if flush_result and flush_result.get("text"):
                self.current_user_text += " " + flush_result["text"]

        # Save any unsaved user speech
        if self.current_user_text.strip():
            now_ms = int((time.time() - self.session_start_time) * 1000)
            self.transcript.append(TranscriptEntry(
                speaker="user",
                text=self.current_user_text.strip(),
                start_ms=max(0, now_ms - 1000),
                end_ms=now_ms,
            ))

        duration = time.time() - self.session_start_time

        # Compute metrics
        metrics = metrics_service.compute_metrics(self.transcript, duration)
        metrics["transcript"] = [e.model_dump() for e in self.transcript]

        await self._send(SessionMetricsMsg(
            session_id=self.session_id,
            **metrics,
        ))

        # Reset
        if self.turn_taking_service:
            await self.turn_taking_service.reset()
        logger.info(f"Session ended: {self.session_id} ({duration:.1f}s)")
        self.session_id = None

    async def _send(self, msg) -> None:
        """Send a Pydantic model as JSON over WebSocket."""
        await self.ws.send_text(msg.model_dump_json())
