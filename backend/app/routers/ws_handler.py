"""
WebSocket Handler — The central nervous system.

Orchestrates the real-time flow:
  Client audio → Queue → Audio Processor Task → STT + Turn-Taking
                                               → LLM → streamed response
Features:
  - Async audio processing queue (decoupled from WS receive loop)
  - Backpressure: drops oldest audio if queue overflows
  - Barge-in: cancels AI response when user starts speaking
  - Latency instrumentation at every pipeline stage

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
from backend.app.services.latency_tracker import LatencyTracker
from backend.app.services.llm_service import get_llm_service
from backend.app.services.metrics_service import metrics_service
from backend.app.services.stt_service import get_stt_service
from backend.app.services.turn_taking_service import get_turn_taking_service
from backend.app.services.auth_service import verify_ws_token

logger = logging.getLogger(__name__)

# Queue limits
AUDIO_QUEUE_MAX = 50  # ~5s of 100ms chunks — drop oldest beyond this

# Stability (Phase 7)
SESSION_TIMEOUT_S = 60  # End session after 60s of inactivity


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
        self._ai_responding: bool = False
        self.user_id: str | None = None  # Set by JWT auth

        # Services (initialized on session start)
        self.stt_service = None
        self.llm_service = None
        self.turn_taking_service = None
        self.latency = LatencyTracker()

        # Async audio processing queue (Phase 3)
        self._audio_queue: asyncio.Queue | None = None
        self._processor_task: asyncio.Task | None = None

        # Barge-in: cancellable AI generation task (Phase 4)
        self._ai_task: asyncio.Task | None = None

        # Speculative LLM execution (Phase 6)
        self._speculative_task: asyncio.Task | None = None
        self._speculative_buffer: list[str] = []
        self._speculative_text: str = ""  # user text that triggered speculation

        # Session timeout (Phase 7)
        self._last_activity: float = time.monotonic()
        self._timeout_task: asyncio.Task | None = None

    async def handle(self) -> None:
        """Main loop: read messages and dispatch."""
        await self.ws.accept()

        # ── Authenticate via query param ──
        token = self.ws.query_params.get("token")
        if token:
            payload = verify_ws_token(token)
            if payload:
                self.user_id = payload.get("sub")
                logger.info(f"WebSocket authenticated (user={self.user_id})")
            else:
                logger.warning("WebSocket auth failed — invalid token")
                await self.ws.close(code=4001, reason="Invalid or expired token")
                return
        else:
            logger.info("WebSocket connected (unauthenticated — guest mode)")

        try:
            while True:
                raw = await self.ws.receive_text()
                data = json.loads(raw)
                msg_type = data.get("type")

                match msg_type:
                    case "start_session":
                        self._last_activity = time.monotonic()
                        await self._handle_start_session(data)
                    case "audio_chunk":
                        self._last_activity = time.monotonic()
                        await self._handle_audio_chunk(data)
                    case "end_session":
                        await self._handle_end_session(data)
                    case "ping":
                        self._last_activity = time.monotonic()
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
        finally:
            # Clean up background tasks
            await self._stop_processor()
            if self._timeout_task and not self._timeout_task.done():
                self._timeout_task.cancel()
                try:
                    await self._timeout_task
                except (asyncio.CancelledError, Exception):
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
        self.latency.reset()

        # Start async audio processor
        await self._start_processor()

        # Start session timeout watchdog
        self._last_activity = time.monotonic()
        self._timeout_task = asyncio.create_task(self._session_timeout_watchdog())

        await self._send(SessionCreatedMsg(
            session_id=self.session_id,
            topic=self.topic,
            mode=msg.mode,
        ))
        logger.info(f"Session started: {self.session_id} (mode={self.mode})")

    async def _handle_audio_chunk(self, data: dict) -> None:
        """Enqueue audio chunk for async processing (non-blocking)."""
        if not self.session_id or not self._audio_queue:
            await self._send(ErrorMsg(code="no_session", message="Start a session first"))
            return

        msg = AudioChunkMsg(**data)
        audio_bytes = base64.b64decode(msg.chunk_b64)
        client_ts = msg.timestamp_ms
        logger.debug(f"[Audio] Received chunk: {len(audio_bytes)} bytes, queue size: {self._audio_queue.qsize()}")

        # Backpressure: if queue is full, drop oldest chunk
        if self._audio_queue.full():
            try:
                self._audio_queue.get_nowait()
                logger.warning("[Backpressure] Dropped oldest audio chunk")
            except asyncio.QueueEmpty:
                pass

        try:
            self._audio_queue.put_nowait((audio_bytes, client_ts))
        except asyncio.QueueFull:
            logger.warning("[Backpressure] Audio queue full, dropping chunk")

    # ── Session Timeout Watchdog (Phase 7) ─────────────────

    async def _session_timeout_watchdog(self) -> None:
        """Background task: ends session if no activity for SESSION_TIMEOUT_S."""
        try:
            while True:
                await asyncio.sleep(10)  # Check every 10s
                idle = time.monotonic() - self._last_activity
                if idle >= SESSION_TIMEOUT_S:
                    logger.info(f"[Timeout] Session {self.session_id} idle for {idle:.0f}s — ending")
                    await self._handle_end_session({"type": "end_session", "session_id": self.session_id})
                    await self._send(ErrorMsg(
                        code="session_timeout",
                        message=f"Session timed out after {SESSION_TIMEOUT_S}s of inactivity"
                    ))
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[Timeout] Watchdog error: {e}")

    # ── Async Audio Processor (Phase 3) ──────────────────

    async def _start_processor(self) -> None:
        """Start the background audio processing task."""
        await self._stop_processor()
        self._audio_queue = asyncio.Queue(maxsize=AUDIO_QUEUE_MAX)
        self._processor_task = asyncio.create_task(self._audio_processor_loop())

    async def _stop_processor(self) -> None:
        """Stop the background audio processing task."""
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()
            try:
                await self._ai_task
            except (asyncio.CancelledError, Exception):
                pass
            self._ai_task = None

        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except (asyncio.CancelledError, Exception):
                pass
            self._processor_task = None

        self._audio_queue = None

    async def _audio_processor_loop(self) -> None:
        """Background task: processes queued audio chunks for STT + turn-taking."""
        logger.info(f"[Processor] Audio processor started for session {self.session_id}")
        try:
            while True:
                audio_bytes, client_ts = await self._audio_queue.get()
                logger.debug(f"[Processor] Processing chunk: {len(audio_bytes)} bytes")
                await self._process_audio(audio_bytes, client_ts)
        except asyncio.CancelledError:
            logger.info("[Processor] Audio processor stopped")
        except Exception as e:
            logger.exception(f"[Processor] Error: {e}")

    async def _process_audio(self, audio_bytes: bytes, client_ts: int) -> None:
        """Process a single audio chunk: VAD + STT + turn decision."""
        
        t0 = time.time()
        # ── Latency: record audio arrival ──
        self.latency.record("audio_received", client_ts_ms=client_ts)

        # ── 1. Turn-taking analysis ──
        prediction = await self.turn_taking_service.analyze_chunk(audio_bytes)
        t1 = time.time()
        if (t1 - t0) > 0.1:
            logger.warning(f"[Perf] TurnJudging took {t1-t0:.3f}s")
        
        if prediction.should_ai_speak:
            signal = "ai_should_speak"
        elif prediction.is_speech:
            signal = "user_speaking"
        elif self.turn_taking_service._speech_frames > 0:
            # User WAS speaking but went silent — they're wrapping up
            signal = "user_will_yield"
        else:
            # No speech detected yet — stay in idle/listening state
            signal = "user_speaking"

        await self._send(TurnSignalMsg(
            session_id=self.session_id,
            signal=signal,
            confidence=prediction.eot_probability,
        ))

        # ── Barge-in: if user speaks during AI response, cancel AI ──
        if prediction.is_speech and self._ai_responding:
            await self._cancel_ai_response()

        # ── Barge-in: also cancel speculative LLM if user resumes ──
        if prediction.is_speech and self._speculative_task and not self._speculative_task.done():
            self._speculative_task.cancel()
            try:
                await self._speculative_task
            except (asyncio.CancelledError, Exception):
                pass
            self._speculative_task = None
            self._speculative_buffer.clear()
            self._speculative_text = ""

        # ── 2. Speech-to-Text (non-blocking, VAD-gated) ──
        # Only feed audio to STT when VAD detects speech.
        # transcribe_chunk fires a background task and returns immediately.
        if prediction.is_speech:
            await self.stt_service.transcribe_chunk(audio_bytes)

        # Poll for any completed STT results (from background tasks)
        stt_result = await self.stt_service.get_result()

        if stt_result and stt_result.get("text"):
            self.latency.record("stt_result")
            text = stt_result["text"]
            self.current_user_text += " " + text

            # Send transcript update to client
            await self._send(TranscriptUpdateMsg(
                session_id=self.session_id,
                text=self.current_user_text.strip(),
                is_final=stt_result.get("is_final", False),
                speaker="user",
            ))

        # ── 3. Speculative LLM: start early when user MIGHT be finishing ──
        if (prediction.eot_probability > 0.5
                and self.current_user_text.strip()
                and not self._ai_responding
                and not self._speculative_task):
            self._start_speculative_llm()

        # ── 4. If turn-taking says user is done → trigger AI response ──
        # Require minimum 4 words to avoid triggering on noise/hallucinations
        user_words = self.current_user_text.strip().split()
        has_meaningful_speech = len(user_words) >= 4
        if prediction.should_ai_speak and has_meaningful_speech and not self._ai_responding:
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

            # ── CRITICAL: Set flag BEFORE create_task to prevent race condition ──
            # Without this, multiple audio chunks can trigger concurrent AI responses
            # between create_task() and the task's first await, causing garbled output.
            self._ai_responding = True
            self.current_user_text = ""  # Reset so next chunks don't re-trigger
            await self.turn_taking_service.reset()  # Reset speech/silence counters

            # Launch AI response as a cancellable task (Phase 4)
            self._ai_task = asyncio.create_task(self._generate_ai_response())

    # ── Barge-in (Phase 4) ───────────────────────────────

    async def _cancel_ai_response(self) -> None:
        """Cancel the current AI response when user starts speaking again."""
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()
            try:
                await self._ai_task
            except (asyncio.CancelledError, Exception):
                pass
            self._ai_task = None

        self._ai_responding = False
        self.current_user_text = ""

        # Signal client that AI response was interrupted
        await self._send(AiResponseChunkMsg(
            session_id=self.session_id,
            text="",
            is_final=True,
        ))
        logger.info("[Barge-in] AI response cancelled — user resumed speaking")

    # ── Speculative LLM Execution (Phase 6) ──────────────

    def _start_speculative_llm(self) -> None:
        """Start generating LLM response speculatively (buffered, not sent)."""
        if self._speculative_task and not self._speculative_task.done():
            return  # Already speculating

        text = self.current_user_text.strip()
        self._speculative_text = text
        self._speculative_buffer.clear()
        self._speculative_task = asyncio.create_task(self._speculative_generate(text))
        logger.info(f"[Speculative] Starting pre-generation for: {text[:50]}...")

    async def _speculative_generate(self, user_text: str) -> None:
        """Silently buffer LLM tokens without sending to client."""
        try:
            async for token in self.llm_service.generate_response_stream(
                user_text=user_text,
                topic=self.topic,
                user_position=self.user_position,
                conversation_history=self.conversation_history,
            ):
                self._speculative_buffer.append(token)
        except asyncio.CancelledError:
            logger.info("[Speculative] Pre-generation cancelled")
        except Exception as e:
            logger.warning(f"[Speculative] Pre-generation error: {e}")

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
        self.latency.record("llm_start")
        first_token_logged = False

        # ── Phase 6: Flush speculative buffer if text matches ──
        if self._speculative_buffer and self._speculative_text == user_text:
            # Speculative generation matched — flush buffered tokens instantly
            for token in self._speculative_buffer:
                if not first_token_logged:
                    self.latency.record("llm_first_token")
                    first_token_logged = True
                full_response += token
                await self._send(AiResponseChunkMsg(
                    session_id=self.session_id,
                    text=token,
                    is_final=False,
                ))
            logger.info(f"[Speculative] Flushed {len(self._speculative_buffer)} pre-generated tokens")

        # Cancel any running speculative task
        if self._speculative_task and not self._speculative_task.done():
            self._speculative_task.cancel()
            try:
                await self._speculative_task
            except (asyncio.CancelledError, Exception):
                pass
        self._speculative_task = None
        self._speculative_buffer.clear()
        self._speculative_text = ""

        try:
            async for token in self.llm_service.generate_response_stream(
                user_text=user_text,
                topic=self.topic,
                user_position=self.user_position,
                conversation_history=self.conversation_history,
            ):
                if not first_token_logged:
                    self.latency.record("llm_first_token")
                    first_token_logged = True
                full_response += token
                await self._send(AiResponseChunkMsg(
                    session_id=self.session_id,
                    text=token,
                    is_final=False,
                ))

            self.latency.record("llm_done")

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

        except asyncio.CancelledError:
            # Barge-in cancellation — save partial response
            logger.info(f"[LLM] Response cancelled after {len(full_response)} chars")
            if full_response.strip():
                ai_end_ms = int((time.time() - self.session_start_time) * 1000)
                self.conversation_history.append({"role": "assistant", "content": full_response + " [interrupted]"})
                self.transcript.append(TranscriptEntry(
                    speaker="ai",
                    text=full_response.strip(),
                    start_ms=ai_start_ms,
                    end_ms=ai_end_ms,
                ))
            raise  # Re-raise so the task is properly cancelled
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

        # Stop audio processing
        await self._stop_processor()

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
        metrics["latency_report"] = self.latency.get_report()

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
