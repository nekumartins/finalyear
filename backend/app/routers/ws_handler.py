"""
WebSocket Handler — The central nervous system.

Orchestrates the real-time flow:
  Client audio → Queue → Audio Processor Task → STT + Turn-Taking
                                               → LLM → streamed response
Features:
  - Async audio processing queue (decoupled from WS receive loop)
  - Backpressure: bounded queue drops incoming audio when overloaded
  - Barge-in debounce: requires sustained speech before interruption
  - Latency instrumentation at every pipeline stage

Each connected client gets its own handler instance with isolated state.
"""
import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import delete, select

from backend.app.db.models import (
    Session as DBSessionModel,
    TranscriptEntry as DBTranscriptEntryModel,
)
from backend.app.db.session import async_session_factory
from backend.app.schemas.messages import (
    AiResponseChunkMsg,
    AudioChunkMsg,
    ErrorMsg,
    PongMsg,
    SessionCreatedMsg,
    SessionMetricsMsg,
    SessionMode,
    StartSessionMsg,
    TranscriptEntry,
    TranscriptUpdateMsg,
    TtsAudioChunkMsg,
    TurnSignalMsg,
)
from backend.app.services.latency_tracker import LatencyTracker
from backend.app.services.llm_service import get_llm_service
from backend.app.services.metrics_service import metrics_service
from backend.app.services.coaching_service import coaching_service
from backend.app.services.stt_service import get_stt_service
from backend.app.services.tts_service import get_tts_service, GeminiNativeAudioService
from backend.app.services.turn_taking_service import get_turn_taking_service
from backend.app.services.auth_service import verify_ws_token

logger = logging.getLogger(__name__)

# Queue limits
AUDIO_QUEUE_MAX = 200  # ~20s of 100ms chunks

# Stability (Phase 7)
SESSION_TIMEOUT_S = 60  # End session after 60s of inactivity
BARGE_IN_DEBOUNCE_MS = 500.0


class DebateWebSocketHandler:
    """Handles a single WebSocket connection's lifecycle."""

    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.session_id: str | None = None
        self.mode: str = "cloud"
        self.topic: str = ""
        self.user_position: str = ""
        self.coaching_goal: str = "confidence"
        self.transcript: list[TranscriptEntry] = []
        self.session_start_time: float = 0
        self.current_user_text: str = ""
        self._interim_text: str = ""  # Current Deepgram interim (replaced, not appended)
        self.conversation_history: list[dict] = []
        self._ai_responding: bool = False
        self.user_id: str | None = None  # Set by JWT auth

        # Services (initialized on session start)
        self.stt_service = None
        self.llm_service = None
        self.tts_service = None
        self.tts_voice: str = "default"
        self.turn_taking_service = None
        self.latency = LatencyTracker()

        # Async audio processing queue (Phase 3)
        self._audio_queue: asyncio.Queue | None = None
        self._processor_task: asyncio.Task | None = None

        # Barge-in: cancellable AI generation task (Phase 4)
        self._ai_task: asyncio.Task | None = None

        # Placeholder speculative state (feature-gated, currently unused)
        self._speculative_task: asyncio.Task | None = None
        self._speculative_buffer: list[str] = []

        # Barge-in debounce state
        self._barge_in_speech_ms: float = 0.0

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
                    case "resume_session":
                        # Reconnect after a drop — re-announce session_id without
                        # wiping any state.  If no session exists yet, fall through
                        # and start one fresh.
                        self._last_activity = time.monotonic()
                        if self.session_id:
                            logger.info(f"[WS] Resumed existing session {self.session_id}")
                            await self._send(SessionCreatedMsg(
                                session_id=self.session_id,
                                topic=self.topic,
                                mode=SessionMode(self.mode),
                            ))
                        else:
                            # New connection, no session yet — treat as a fresh start.
                            # Override 'type' so StartSessionMsg Pydantic model accepts it.
                            await self._handle_start_session({**data, "type": "start_session"})
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
            await self._shutdown()

    async def _shutdown(self) -> None:
        """Best-effort teardown for disconnects and process reloads."""
        await self._stop_processor()

        # Cancel speculative LLM task (was previously missed)
        if self._speculative_task and not self._speculative_task.done():
            self._speculative_task.cancel()
            try:
                await self._speculative_task
            except (asyncio.CancelledError, Exception):
                pass
        self._speculative_task = None
        self._speculative_buffer.clear()

        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except (asyncio.CancelledError, Exception):
                pass
        self._timeout_task = None

        if self.stt_service:
            try:
                await self.stt_service.close()
            except Exception as e:
                logger.warning(f"[Shutdown] STT close error: {e}")
        self.stt_service = None
        self.llm_service = None
        self.tts_service = None
        self.turn_taking_service = None

    async def _handle_start_session(self, data: dict) -> None:
        # ── Guard: prevent a second start_session from clobbering an active one ──
        if self.session_id:
            logger.warning(
                f"[WS] Ignoring duplicate start_session — session {self.session_id} already active"
            )
            # Re-send session_created so the client knows it's already set up
            await self._send(SessionCreatedMsg(
                session_id=self.session_id,
                topic=self.topic,
                mode=SessionMode(self.mode),
            ))
            return

        msg = StartSessionMsg(**data)
        self.session_id = f"session-{int(time.time() * 1000)}"
        self.mode = msg.mode.value
        self.topic = msg.topic
        self.user_position = msg.user_position
        self.coaching_goal = msg.coaching_goal
        self.session_start_time = time.time()
        self.transcript = []
        self.conversation_history = []
        self.current_user_text = ""
        self._interim_text = ""
        self._ai_responding = False
        self._barge_in_speech_ms = 0.0

        # Initialize services for this session's mode
        self.stt_service = get_stt_service(self.mode)
        self.llm_service = get_llm_service(self.mode)
        self.tts_service = get_tts_service(msg.tts_provider)
        self.tts_voice = msg.tts_voice
        self.turn_taking_service = get_turn_taking_service()
        self.latency.reset()

        # Start async audio processor
        await self._start_processor()

        # Start session timeout watchdog
        self._last_activity = time.monotonic()
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except (asyncio.CancelledError, Exception):
                pass
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
            logger.warning("[Audio] Received chunk but no active session/queue — dropping")
            await self._send(ErrorMsg(code="no_session", message="Start a session first"))
            return

        msg = AudioChunkMsg(**data)
        audio_bytes = base64.b64decode(msg.chunk_b64)
        client_ts = msg.timestamp_ms
        sample_rate = msg.sample_rate if 8000 <= msg.sample_rate <= 48000 else 16000
        logger.info(f"[Audio] Received chunk: {len(audio_bytes)} bytes, queue size: {self._audio_queue.qsize()}")

        # Backpressure: if queue is full, drop incoming chunk (preserve
        # continuity of already buffered audio instead of carving holes).
        if self._audio_queue.full():
            logger.warning("[Backpressure] Audio queue full, dropping incoming audio chunk")
            return

        try:
            self._audio_queue.put_nowait((audio_bytes, client_ts, sample_rate))
        except asyncio.QueueFull:
            logger.warning("[Backpressure] Audio queue race, dropping incoming audio chunk")

    # ── Session Timeout Watchdog (Phase 7) ─────────────────

    async def _session_timeout_watchdog(self) -> None:
        """Background task: ends session if no activity for SESSION_TIMEOUT_S."""
        try:
            while True:
                await asyncio.sleep(10)  # Check every 10s
                if not self.session_id:
                    break
                idle = time.monotonic() - self._last_activity
                if idle >= SESSION_TIMEOUT_S:
                    logger.info(f"[Timeout] Session {self.session_id} idle for {idle:.0f}s — ending")
                    await self._handle_end_session({"type": "end_session", "session_id": self.session_id})
                    # Guard: WS may already be closing — swallow send errors
                    try:
                        await self._send(ErrorMsg(
                            code="session_timeout",
                            message=f"Session timed out after {SESSION_TIMEOUT_S}s of inactivity"
                        ))
                    except Exception:
                        pass
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

        self._barge_in_speech_ms = 0.0
        self._ai_responding = False
        self._audio_queue = None

    async def _audio_processor_loop(self) -> None:
        """Background task: processes queued audio chunks for STT + turn-taking."""
        logger.info(f"[Processor] Audio processor started for session {self.session_id}")
        chunk_count = 0
        try:
            while True:
                audio_bytes, client_ts, sample_rate = await self._audio_queue.get()
                chunk_count += 1
                logger.info(f"[Processor] Chunk #{chunk_count}: {len(audio_bytes)} bytes received")
                await self._process_audio(audio_bytes, client_ts, sample_rate)
        except asyncio.CancelledError:
            logger.info(f"[Processor] Audio processor stopped after {chunk_count} chunks")
        except Exception as e:
            logger.exception(f"[Processor] Error: {e}")

    async def _process_audio(self, audio_bytes: bytes, client_ts: int, sample_rate: int) -> None:
        """Process a single audio chunk: VAD + STT + turn decision."""
        t0 = time.time()
        self.latency.record("audio_received", client_ts_ms=client_ts)
        if sample_rate < 8000 or sample_rate > 48000:
            sample_rate = 16000
        chunk_duration_ms = ((len(audio_bytes) // 2) / sample_rate) * 1000.0

        # ── 1. Turn-taking analysis ──
        prediction = await self.turn_taking_service.analyze_chunk(audio_bytes, sample_rate=sample_rate)
        if prediction.should_ai_speak:
            self.latency.record("turn_detected")
        t1 = time.time()
        if (t1 - t0) > 0.1:
            logger.warning(f"[Perf] TurnJudging took {t1-t0:.3f}s")

        logger.info(
            f"[VAD] is_speech={prediction.is_speech} speech_frames={self.turn_taking_service._speech_frames} "
            f"silence_frames={self.turn_taking_service._silence_frames} eot={prediction.eot_probability:.2f} "
            f"should_ai_speak={prediction.should_ai_speak}"
        )
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

        # ── Barge-in debounce: require sustained speech before cancel ──
        if self._ai_responding:
            if prediction.is_speech:
                self._barge_in_speech_ms += chunk_duration_ms
                if self._barge_in_speech_ms >= BARGE_IN_DEBOUNCE_MS:
                    await self._cancel_ai_response()
            else:
                self._barge_in_speech_ms = 0.0
        else:
            self._barge_in_speech_ms = 0.0

        # ── 2. Speech-to-Text ──
        # Streaming providers (e.g. Deepgram) need continuous audio INCLUDING
        # silence so their internal endpointing can trigger final transcripts.
        # Batch providers (Groq, local whisper) only need speech segments.
        if prediction.is_speech or self.stt_service.needs_continuous_audio:
            await self.stt_service.transcribe_chunk(audio_bytes)

        # Drain ALL available STT results (streaming providers may emit
        # multiple finals while several chunks were in-flight).
        while True:
            stt_result = await self.stt_service.get_result()
            if not stt_result or not stt_result.get("text"):
                break

            text = stt_result["text"]
            is_final = stt_result.get("is_final", False)

            if is_final:
                # Final transcript: accumulate permanently and clear interim
                self.latency.record("stt_result")
                self.current_user_text += " " + text
                self._interim_text = ""

                await self._send(TranscriptUpdateMsg(
                    session_id=self.session_id,
                    text=self.current_user_text.strip(),
                    is_final=True,
                    speaker="user",
                ))
            else:
                # Interim: show accumulated text + current partial as preview.
                # Deepgram interims replace each other ("hel" → "hello"),
                # so we overwrite _interim_text rather than appending.
                self._interim_text = text
                preview = (self.current_user_text + " " + text).strip()

                await self._send(TranscriptUpdateMsg(
                    session_id=self.session_id,
                    text=preview,
                    is_final=False,
                    speaker="user",
                ))

        # ── 3. If turn-taking says user is done → trigger AI response ──
        # Require minimum 2 words to avoid triggering on single-word noise/hallucinations.
        # Include interim text: if the user spoke one continuous utterance, Deepgram
        # may not have emitted a final yet — all the text sits in _interim_text.
        combined_text = (self.current_user_text + " " + self._interim_text).strip()
        user_words = combined_text.split()
        has_meaningful_speech = len(user_words) >= 2
        logger.info(
            f"[Pipeline] should_ai_speak={prediction.should_ai_speak} "
            f"words={len(user_words)} text='{combined_text[:60]}' "
            f"ai_responding={self._ai_responding}"
        )
        if prediction.should_ai_speak and has_meaningful_speech and not self._ai_responding:
            # Save user turn to transcript
            now_ms = int((time.time() - self.session_start_time) * 1000)
            user_text = combined_text

            # Flush any remaining audio in STT buffer before AI responds
            flush_result = await self.stt_service.flush()
            if flush_result and flush_result.get("text"):
                user_text += " " + flush_result["text"]

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
            self._interim_text = ""      # Clear interim preview
            await self.turn_taking_service.reset()  # Reset speech/silence counters

            # Launch AI response as a cancellable task — pass user_text directly
            # because current_user_text has already been cleared above.
            self._ai_task = asyncio.create_task(self._generate_ai_response(user_text))

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
        self._interim_text = ""
        self._barge_in_speech_ms = 0.0

        # Signal client that AI response was interrupted
        await self._send(AiResponseChunkMsg(
            session_id=self.session_id,
            text="",
            is_final=True,
        ))
        # Also send TTS final so client stops waiting for audio
        await self._send(TtsAudioChunkMsg(
            session_id=self.session_id,
            audio_b64="",
            content_type="audio/wav",
            is_final=True,
        ))
        logger.info("[Barge-in] AI response cancelled — user resumed speaking")

    async def _generate_ai_response(self, user_text: str) -> None:
        """Stream an AI counter-argument back to the client."""
        # user_text is passed in directly because current_user_text is reset before
        # this task starts; reading it here would always yield an empty string.
        if not user_text:
            return

        self._ai_responding = True

        full_response = ""
        ai_start_ms = int((time.time() - self.session_start_time) * 1000)
        self.latency.record("llm_start")

        # ── Push user message to history BEFORE the LLM call ──
        # This ensures:
        #   1. The history is correct regardless of success/failure/cancellation
        #   2. No duplicate pushes needed in except blocks
        #   3. No "dangling user message" if the LLM errors out — it's already there
        self.conversation_history.append({"role": "user", "content": user_text})

        try:
            # ── Unified path: Gemini Native Audio (brain + voice in one call) ──
            if isinstance(self.tts_service, GeminiNativeAudioService):
                first_token_logged = False
                self.latency.record("tts_start")

                async for chunk in self.tts_service.generate_debate_response(
                    user_text=user_text,
                    topic=self.topic,
                    user_position=self.user_position,
                    conversation_history=self.conversation_history,
                    voice=self.tts_voice,
                    coaching_goal=self.coaching_goal,
                ):
                    # Transcript text (from output_audio_transcription)
                    if chunk.text:
                        if not first_token_logged:
                            self.latency.record("llm_first_token")
                            first_token_logged = True
                        full_response += chunk.text
                        await self._send(AiResponseChunkMsg(
                            session_id=self.session_id,
                            text=chunk.text,
                            is_final=False,
                        ))

                    # Audio data (streamed in parallel with text)
                    if chunk.audio_b64:
                        await self._send(TtsAudioChunkMsg(
                            session_id=self.session_id,
                            audio_b64=chunk.audio_b64,
                            content_type=chunk.content_type,
                            is_final=False,
                        ))

                    if chunk.is_final:
                        break

                self.latency.record("llm_done")
                self.latency.record("tts_done")

                # Send final markers for both text and audio streams
                await self._send(AiResponseChunkMsg(
                    session_id=self.session_id,
                    text="",
                    is_final=True,
                ))
                await self._send(TtsAudioChunkMsg(
                    session_id=self.session_id,
                    audio_b64="",
                    content_type="audio/wav",
                    is_final=True,
                ))

                # Save AI turn to history and transcript
                ai_end_ms = int((time.time() - self.session_start_time) * 1000)
                if full_response.strip():
                    self.conversation_history.append({"role": "assistant", "content": full_response})
                    self.transcript.append(TranscriptEntry(
                        speaker="ai",
                        text=full_response.strip(),
                        start_ms=ai_start_ms,
                        end_ms=ai_end_ms,
                    ))

            # ── Standard path: LLM stream → TTS synthesis (edge-tts, gTTS, etc.) ──
            else:
                first_token_logged = False

                async for token in self.llm_service.generate_response_stream(
                    user_text=user_text,
                    topic=self.topic,
                    user_position=self.user_position,
                    conversation_history=self.conversation_history,
                    coaching_goal=self.coaching_goal,
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

                # Save AI turn to history and transcript
                ai_end_ms = int((time.time() - self.session_start_time) * 1000)
                if full_response.strip():
                    self.conversation_history.append({"role": "assistant", "content": full_response})
                    self.transcript.append(TranscriptEntry(
                        speaker="ai",
                        text=full_response.strip(),
                        start_ms=ai_start_ms,
                        end_ms=ai_end_ms,
                    ))

                # ── TTS: Synthesize AI response to audio ──
                if full_response.strip() and self.tts_service:
                    try:
                        self.latency.record("tts_start")
                        async for tts_chunk in self.tts_service.synthesize(
                            full_response.strip(), voice=self.tts_voice
                        ):
                            await self._send(TtsAudioChunkMsg(
                                session_id=self.session_id,
                                audio_b64=tts_chunk.audio_b64,
                                content_type=tts_chunk.content_type,
                                is_final=tts_chunk.is_final,
                            ))
                        self.latency.record("tts_done")
                    except Exception as e:
                        logger.error(f"[TTS] Synthesis failed: {e}")
                        # Send final marker so client doesn't hang
                        await self._send(TtsAudioChunkMsg(
                            session_id=self.session_id,
                            audio_b64="",
                            content_type="audio/mpeg",
                            is_final=True,
                        ))

        except asyncio.CancelledError:
            # Barge-in cancellation — save partial response if any
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
            # LLM failed (rate limit exhausted, network error, etc.)
            # Send a proper error message to the client, NOT error text as AI speech
            logger.error(f"[LLM] Response generation failed: {e}")
            await self._send(ErrorMsg(code="llm_error", message="AI couldn't respond right now. Try again."))
            # Send end-of-response marker so the frontend knows the AI turn is over
            await self._send(AiResponseChunkMsg(
                session_id=self.session_id,
                text="",
                is_final=True,
            ))

        finally:
            # current_user_text is intentionally NOT cleared here — any text
            # the user spoke while the AI was responding is preserved so it
            # can be picked up by the next turn-taking cycle.
            self._ai_responding = False
            self._barge_in_speech_ms = 0.0

    async def _handle_end_session(self, data: dict) -> None:
        if not self.session_id:
            return

        # Stop timeout watchdog unless this call is running on that task.
        current_task = asyncio.current_task()
        if self._timeout_task and self._timeout_task is not current_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except (asyncio.CancelledError, Exception):
                pass
            self._timeout_task = None

        # Stop audio processing
        await self._stop_processor()

        # Flush any remaining STT buffer
        if self.stt_service:
            flush_result = await self.stt_service.flush()
            if flush_result and flush_result.get("text"):
                self.current_user_text += " " + flush_result["text"]

        # Include any pending interim text (user clicked End mid-sentence
        # before Deepgram emitted a final for the current utterance).
        if self._interim_text:
            self.current_user_text += " " + self._interim_text
            self._interim_text = ""

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

        # Generate AI coaching report (non-blocking — session still ends if this fails)
        coaching_report = None
        try:
            coaching_report = await coaching_service.generate_report(
                transcript=self.transcript,
                metrics=metrics,
                topic=self.topic,
                user_position=self.user_position,
                coaching_goal=self.coaching_goal,
            )
        except Exception as e:
            logger.warning(f"[Session] Coaching report generation failed: {e}")
        metrics["coaching_report"] = coaching_report

        # Persist authenticated sessions for history view.
        await self._persist_session(metrics, duration)

        await self._send(SessionMetricsMsg(
            session_id=self.session_id,
            **metrics,
        ))

        # Reset
        if self.turn_taking_service:
            await self.turn_taking_service.reset()
        if self.stt_service:
            try:
                await self.stt_service.close()
            except Exception as e:
                logger.warning(f"[Session] STT close error: {e}")
        self.stt_service = None
        self.llm_service = None
        self.tts_service = None
        self.turn_taking_service = None
        if self._timeout_task is current_task:
            self._timeout_task = None
        logger.info(f"Session ended: {self.session_id} ({duration:.1f}s)")
        self.session_id = None

    async def _persist_session(self, metrics: dict, duration: float) -> None:
        """Best-effort persistence of authenticated session history."""
        if not self.user_id or not self.session_id:
            return

        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(DBSessionModel).where(DBSessionModel.id == self.session_id)
                )
                db_session = result.scalar_one_or_none()

                # DB columns are TIMESTAMP WITHOUT TIME ZONE — strip tzinfo
                started_at = datetime.fromtimestamp(self.session_start_time, tz=timezone.utc).replace(tzinfo=None)
                ended_at = datetime.now(timezone.utc).replace(tzinfo=None)

                if db_session is None:
                    db_session = DBSessionModel(
                        id=self.session_id,
                        user_id=self.user_id,
                        mode=self.mode,
                        topic=self.topic,
                        user_position=self.user_position,
                        coaching_goal=self.coaching_goal,
                        started_at=started_at,
                    )
                    db.add(db_session)
                else:
                    db_session.user_id = self.user_id
                    db_session.mode = self.mode
                    db_session.topic = self.topic
                    db_session.user_position = self.user_position
                    db_session.coaching_goal = self.coaching_goal
                    if not db_session.started_at:
                        db_session.started_at = started_at

                db_session.ended_at = ended_at
                db_session.duration_seconds = metrics.get("duration_seconds", duration)
                db_session.user_wpm = metrics.get("user_wpm", 0)
                db_session.ai_wpm = metrics.get("ai_wpm", 0)
                db_session.filler_word_count = metrics.get("filler_word_count", 0)
                db_session.filler_words_json = metrics.get("filler_words", {})
                db_session.avg_pause_duration_ms = metrics.get("avg_pause_duration_ms", 0)
                db_session.turn_count = metrics.get("turn_count", 0)
                db_session.user_talk_ratio = metrics.get("user_talk_ratio", 0)
                db_session.coaching_report = metrics.get("coaching_report")

                # Replace transcript rows on re-end to avoid duplicates.
                await db.execute(
                    delete(DBTranscriptEntryModel).where(
                        DBTranscriptEntryModel.session_id == self.session_id
                    )
                )
                for entry in self.transcript:
                    db.add(DBTranscriptEntryModel(
                        session_id=self.session_id,
                        speaker=entry.speaker,
                        text=entry.text,
                        start_ms=entry.start_ms,
                        end_ms=entry.end_ms,
                    ))

                await db.commit()
        except Exception as e:
            logger.exception(
                f"[Session] Failed to persist session history (session={self.session_id}): {e}"
            )

    async def _send(self, msg) -> None:
        """Send a Pydantic model as JSON over WebSocket."""
        await self.ws.send_text(msg.model_dump_json())
