"""
Service: STT (Speech-to-Text) — Multi-provider

Providers:
  - Deepgram: WebSocket streaming (Nova-3), 1 connection per session
  - Groq: OpenAI-compatible Whisper API (batch), free tier
  - faster-whisper: Local CPU inference, no API needed

Design: All providers share the STTService ABC.
Batch providers (Groq, Local) extend BatchSTTService which handles
buffering, background tasks, sequenced result queuing, and flush.
Deepgram uses a persistent WebSocket — no buffering needed.
"""
import io
import json
import logging
import struct
import asyncio
import time
from abc import ABC, abstractmethod

import httpx

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


# ── Hallucination filter ──────────────────────────────────────
#
# Only block phrases that are known Whisper phantom outputs on silence.
# Real debate words (yes, no, okay, so, right, well) are NOT blocked.

HALLUCINATION_BLOCKLIST = {
    # Whisper-specific phantom phrases (appear on silence)
    # Stored in normalized form (lowercased, no trailing punctuation)
    "my teeth",
    "one, two, three, go",
    "that is my life",
    "it's time to present",
    "what's that",
    "...",
    "…",
    # Pure filler sounds (not words)
    "hmm", "hm", "um", "uh", "ah", "oh", "er",
}


def _filter_hallucination(text: str) -> str | None:
    """Return None if text is a known STT hallucination, else return cleaned text."""
    if not text or len(text.strip()) < 2:
        return None
    cleaned = text.strip()
    normalized = cleaned.lower().strip(" .,!?…")
    # Block if normalized text is empty (pure punctuation like "...")
    if not normalized:
        return None
    if normalized in HALLUCINATION_BLOCKLIST:
        logger.info(f"[STT] Filtered hallucination: '{text}'")
        return None
    return cleaned



# ── WAV conversion helper ─────────────────────────────────────

def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Convert raw PCM16 bytes to a WAV file in memory."""
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_bytes)

    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))  # PCM format
    buf.write(struct.pack("<H", channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", byte_rate))
    buf.write(struct.pack("<H", block_align))
    buf.write(struct.pack("<H", bits_per_sample))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm_bytes)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
# Abstract base
# ═══════════════════════════════════════════════════════════════

class STTService(ABC):
    """Abstract STT interface — all implementations must follow this."""

    @abstractmethod
    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        """Feed a single audio chunk. Results come via get_result()."""
        ...

    @abstractmethod
    async def flush(self) -> dict | None:
        """Force-transcribe remaining buffer (e.g. on session end)."""
        ...

    async def get_result(self) -> dict | None:
        """Poll for completed transcription results (non-blocking)."""
        return None

    @abstractmethod
    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        """Transcribe a complete audio buffer. Used for post-session."""
        ...

    @property
    def needs_continuous_audio(self) -> bool:
        """Whether this provider needs a continuous audio stream (including silence).

        Streaming providers (e.g. Deepgram) rely on seeing silence to trigger
        endpointing and emit final transcripts.  Batch providers only need
        speech segments.
        """
        return False

    async def close(self) -> None:
        """Release provider resources and cancel in-flight work."""
        return

    def get_full_transcript(self) -> str:
        """Return the accumulated full transcript."""
        return ""


# ═══════════════════════════════════════════════════════════════
# BatchSTTService — shared logic for buffer-and-send providers
# ═══════════════════════════════════════════════════════════════

class BatchSTTService(STTService):
    """
    Base class for STT providers that buffer audio and send in batches.
    Handles: buffering, background task management, sequenced result
    queuing (prevents out-of-order results), and flush logic.

    Subclasses only need to implement _transcribe_pcm() and transcribe_batch().
    """

    BUFFER_THRESHOLD: int = 32_000  # 1 second of 16kHz PCM16 (default)

    def __init__(self):
        self._buffer = bytearray()
        self._full_transcript = ""
        self._result_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._pending_tasks: list[asyncio.Task] = []
        # Sequencing: ensures results arrive in submission order
        self._next_seq: int = 0
        self._next_emit: int = 0
        self._held: dict[int, dict] = {}  # seq -> result, waiting for ordering

    @abstractmethod
    async def _transcribe_pcm(self, pcm_bytes: bytes) -> str | None:
        """
        Provider-specific: transcribe raw PCM16 bytes and return text.
        Return None if no speech detected or on error.
        """
        ...

    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        """Buffer audio. When threshold is reached, fire a background task."""
        self._buffer.extend(audio_bytes)

        if len(self._buffer) < self.BUFFER_THRESHOLD:
            return None

        pcm_bytes = bytes(self._buffer)
        self._buffer.clear()

        seq = self._next_seq
        self._next_seq += 1

        task = asyncio.create_task(self._transcribe_and_enqueue(pcm_bytes, seq))
        self._pending_tasks.append(task)
        # Clean up finished tasks
        self._pending_tasks = [t for t in self._pending_tasks if not t.done()]
        return None

    async def _transcribe_and_enqueue(self, pcm_bytes: bytes, seq: int) -> None:
        """Transcribe, filter, and enqueue result in sequence order."""
        text = await self._transcribe_pcm(pcm_bytes)
        if text:
            text = _filter_hallucination(text)

        if not text:
            # Even empty results must be "emitted" to unblock sequencing
            self._held[seq] = None
        else:
            self._full_transcript += " " + text
            self._held[seq] = {"text": text, "is_final": True}

        # Flush any results that are now in sequence order
        while self._next_emit in self._held:
            result = self._held.pop(self._next_emit)
            self._next_emit += 1
            if result is not None:
                await self._result_queue.put(result)

    async def get_result(self) -> dict | None:
        try:
            return self._result_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def flush(self) -> dict | None:
        """Force-transcribe any remaining audio in the buffer."""
        # Transcribe remaining buffer (no minimum — don't drop audio)
        if len(self._buffer) > 0:
            pcm_bytes = bytes(self._buffer)
            self._buffer.clear()
            text = await self._transcribe_pcm(pcm_bytes)
            if text:
                text = _filter_hallucination(text)
                if text:
                    self._full_transcript += " " + text
                    await self._result_queue.put({"text": text, "is_final": True})

        # Wait for all in-flight tasks to complete
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()

        # Drain any remaining ordered results
        results = []
        while not self._result_queue.empty():
            try:
                r = self._result_queue.get_nowait()
                results.append(r["text"])
            except asyncio.QueueEmpty:
                break

        if results:
            return {"text": " ".join(results), "is_final": True}
        return None

    def get_full_transcript(self) -> str:
        return self._full_transcript.strip()

    async def close(self) -> None:
        """Cancel pending tasks and clean up."""
        for task in self._pending_tasks:
            if not task.done():
                task.cancel()
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
        self._pending_tasks.clear()
        self._buffer.clear()
        self._held.clear()
        # Drain queue
        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


# ═══════════════════════════════════════════════════════════════
# Deepgram WebSocket Streaming (Nova-3)
# ═══════════════════════════════════════════════════════════════

class DeepgramSTTService(STTService):
    """
    Deepgram Nova-3 via persistent WebSocket streaming.

    Opens a single WebSocket connection to Deepgram on first audio chunk.
    Raw PCM bytes are piped directly — no buffering, no WAV conversion.
    Deepgram streams back final transcripts in order.

    Benefits over the old REST approach:
      - 1 connection per session vs ~240 REST calls per 2-min debate
      - No 500ms buffer delay — audio is sent immediately
      - Results arrive in order (no sequencing needed)
      - ~10x less API credit consumption
    """

    DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

    @property
    def needs_continuous_audio(self) -> bool:
        """Deepgram streaming needs continuous audio (including silence)
        so its internal endpointing (300ms silence) can trigger final results."""
        return True

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.deepgram_api_key
        self._ws = None
        self._listener_task: asyncio.Task | None = None
        self._result_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._full_transcript = ""
        self._connected = False
        self._connecting = False
        self._connect_lock = asyncio.Lock()
        # Fallback REST client for batch transcription
        self._http_client = httpx.AsyncClient(timeout=15.0)
        logger.info(f"[STT/Deepgram] Initialized (api_key={'SET' if self.api_key else 'MISSING'})")

    async def _ensure_connected(self) -> bool:
        """Open WebSocket connection to Deepgram if not already connected."""
        if self._connected and self._ws:
            return True

        async with self._connect_lock:
            # Double-check after acquiring lock
            if self._connected and self._ws:
                return True

            try:
                import websockets

                params = (
                    f"?model=nova-3"
                    f"&language=en"
                    f"&encoding=linear16"
                    f"&sample_rate=16000"
                    f"&channels=1"
                    f"&punctuate=true"
                    f"&smart_format=true"
                    f"&interim_results=true"
                    f"&endpointing=300"
                )
                url = self.DEEPGRAM_WS_URL + params

                self._ws = await websockets.connect(
                    url,
                    additional_headers={"Authorization": f"Token {self.api_key}"},
                    open_timeout=30,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                )
                self._connected = True
                self._listener_task = asyncio.create_task(self._listen_loop())
                logger.info("[STT/Deepgram] WebSocket connected")
                return True

            except Exception as e:
                logger.error(f"[STT/Deepgram] WebSocket connection failed: {e}")
                self._connected = False
                self._ws = None
                return False

    async def _listen_loop(self) -> None:
        """Background task: read Deepgram WebSocket messages and enqueue results."""
        try:
            async for raw_msg in self._ws:
                try:
                    data = json.loads(raw_msg)

                    # Deepgram sends different message types
                    msg_type = data.get("type", "")

                    if msg_type == "Results":
                        channel = data.get("channel", {})
                        alternatives = channel.get("alternatives", [{}])
                        transcript = alternatives[0].get("transcript", "") if alternatives else ""
                        is_final = data.get("is_final", False)

                        if transcript and is_final:
                            text = _filter_hallucination(transcript)
                            if text:
                                self._full_transcript += " " + text
                                await self._result_queue.put({
                                    "text": text,
                                    "is_final": True,
                                })
                                logger.info(f"[STT/Deepgram] Final: '{text}'")

                        elif transcript and not is_final:
                            # Forward interim results for real-time display.
                            # These are progressive refinements of the current
                            # utterance ("hel" → "hello" → "hello world") —
                            # the consumer must replace, not append.
                            await self._result_queue.put({
                                "text": transcript,
                                "is_final": False,
                            })
                            logger.debug(f"[STT/Deepgram] Interim: '{transcript}'")

                    elif msg_type == "Metadata":
                        logger.debug(f"[STT/Deepgram] Metadata: {data.get('request_id', 'unknown')}")

                except json.JSONDecodeError:
                    logger.warning("[STT/Deepgram] Non-JSON message received")

        except asyncio.CancelledError:
            logger.info("[STT/Deepgram] Listener cancelled")
        except Exception as e:
            logger.error(f"[STT/Deepgram] Listener error: {e}")
            self._connected = False

    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        """Send raw PCM bytes directly to Deepgram over WebSocket."""
        if not await self._ensure_connected():
            logger.warning("[STT/Deepgram] Not connected — dropping chunk")
            return None

        try:
            await self._ws.send(audio_bytes)
        except Exception as e:
            logger.error(f"[STT/Deepgram] Send error: {e}")
            self._connected = False

        return None

    async def get_result(self) -> dict | None:
        try:
            return self._result_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def flush(self) -> dict | None:
        """Tell Deepgram to finalize, then collect remaining results."""
        if self._ws and self._connected:
            try:
                # Send Deepgram's close-stream message to flush final results
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                # Give Deepgram a moment to send back final transcripts
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"[STT/Deepgram] Flush send error: {e}")

        # Collect any remaining results
        results = []
        while not self._result_queue.empty():
            try:
                r = self._result_queue.get_nowait()
                results.append(r["text"])
            except asyncio.QueueEmpty:
                break

        if results:
            return {"text": " ".join(results), "is_final": True}
        return None

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        """Batch transcription via REST (used for post-session, not real-time)."""
        wav_bytes = _pcm16_to_wav(audio_bytes)
        try:
            response = await self._http_client.post(
                "https://api.deepgram.com/v1/listen",
                params={"model": "nova-3", "language": "en", "punctuate": "true"},
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "audio/wav",
                },
                content=wav_bytes,
            )
            if response.status_code == 200:
                data = response.json()
                return (
                    data.get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [{}])[0]
                    .get("transcript", "")
                )
            else:
                logger.error(f"[STT/Deepgram] Batch API error {response.status_code}")
        except Exception as e:
            logger.error(f"[STT/Deepgram] Batch error: {e}")
        return ""

    def get_full_transcript(self) -> str:
        return self._full_transcript.strip()

    async def close(self) -> None:
        """Shut down WebSocket and listener."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except (asyncio.CancelledError, Exception):
                pass
            self._listener_task = None

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        self._connected = False

        try:
            await self._http_client.aclose()
        except Exception:
            pass

        # Drain queue
        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


# ═══════════════════════════════════════════════════════════════
# Groq Whisper API (fallback)
# ═══════════════════════════════════════════════════════════════

class GroqSTTService(BatchSTTService):
    """
    Groq Whisper API (whisper-large-v3-turbo).
    Free tier but unreliable latency (0.5s to 24s per call).
    Kept as fallback if Deepgram is unavailable.
    """

    BUFFER_THRESHOLD = 32_000  # 1 second (was 2s — too slow)

    def __init__(self):
        super().__init__()
        from openai import AsyncOpenAI
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )

    async def _transcribe_pcm(self, pcm_bytes: bytes) -> str | None:
        """Send WAV to Groq Whisper API."""
        wav_bytes = _pcm16_to_wav(pcm_bytes)
        try:
            audio_file = io.BytesIO(wav_bytes)
            audio_file.name = "audio.wav"

            start_t = time.time()
            logger.info(f"[STT/Groq] Calling API with {len(wav_bytes)} bytes...")

            response = await self._client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                language="en",
                response_format="text",
            )
            dur = time.time() - start_t
            text = response.strip() if isinstance(response, str) else response.text.strip()
            logger.info(f"[STT/Groq] Got '{text}' in {dur:.2f}s")
            return text if text else None

        except Exception as e:
            logger.error(f"[STT/Groq] API error: {e}")
        return None

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        """Batch transcription for post-session."""
        wav_bytes = _pcm16_to_wav(audio_bytes)
        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"
        try:
            response = await self._client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                language="en",
                response_format="text",
            )
            return response.strip() if isinstance(response, str) else response.text.strip()
        except Exception as e:
            logger.error(f"[STT/Groq] Batch error: {e}")
            return ""

    async def close(self) -> None:
        await super().close()
        try:
            await self._client.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# Local faster-whisper (Edge mode — no API needed)
# ═══════════════════════════════════════════════════════════════

class LocalSTTService(BatchSTTService):
    """
    Local STT using faster-whisper (CTranslate2 backend).
    Runs on CPU with int8 quantization. No API key needed.
    Model downloads automatically on first use (~150MB for 'base').
    """

    BUFFER_THRESHOLD = 32_000  # 1 second (was 2s)

    def __init__(self):
        super().__init__()
        settings = get_settings()
        model_size = settings.faster_whisper_model
        logger.info(f"[STT/Local] Loading faster-whisper model '{model_size}' (int8, CPU)...")

        from faster_whisper import WhisperModel
        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
        )
        logger.info("[STT/Local] Model loaded successfully")

    async def _transcribe_pcm(self, pcm_bytes: bytes) -> str | None:
        """Transcribe PCM in a thread pool to avoid blocking the event loop."""
        import numpy as np

        try:
            start_t = time.time()
            audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # Run in thread pool (faster-whisper is sync/CPU-bound)
            segments, info = await asyncio.to_thread(
                self.model.transcribe,
                audio_array,
                language="en",
                beam_size=1,
                vad_filter=True,
            )

            text_parts = [segment.text.strip() for segment in segments]
            text = " ".join(text_parts)
            dur = time.time() - start_t
            logger.info(f"[STT/Local] Transcribed in {dur:.2f}s: '{text}'")
            return text if text else None

        except Exception as e:
            logger.error(f"[STT/Local] Error: {e}")
        return None

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        """Batch transcription for post-session."""
        import numpy as np
        try:
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            segments, _ = await asyncio.to_thread(
                self.model.transcribe,
                audio_array,
                language="en",
                beam_size=1,
                vad_filter=True,
            )
            return " ".join(seg.text.strip() for seg in segments)
        except Exception as e:
            logger.error(f"[STT/Local] Batch error: {e}")
            return ""


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════

def _get_cloud_stt_service(settings, *, allow_local_override: bool = True) -> STTService:
    """Return cloud STT provider (optionally allowing local override)."""
    provider = settings.stt_provider.lower()

    if provider == "deepgram":
        if not settings.deepgram_api_key:
            logger.warning("[STT] No DEEPGRAM_API_KEY set, falling back to Groq")
            return GroqSTTService()
        logger.info("[STT] Creating DeepgramSTTService (Nova-3 WebSocket Streaming)")
        return DeepgramSTTService()

    if provider == "faster-whisper" and allow_local_override:
        logger.info("[STT] Creating LocalSTTService (faster-whisper, cloud-mode override)")
        return LocalSTTService()

    # Default: Groq
    logger.info("[STT] Creating GroqSTTService (Whisper)")
    return GroqSTTService()


def get_stt_service(mode: str) -> STTService:
    """
    Factory: returns the right STT service based on session mode and config.
    - Cloud mode: uses configured provider (deepgram/groq)
    - Edge mode: tries local faster-whisper, falls back to cloud if unavailable
    """
    settings = get_settings()

    if mode == "edge":
        try:
            logger.info("[STT] Creating LocalSTTService (faster-whisper)")
            return LocalSTTService()
        except Exception as e:
            logger.warning(
                "[STT] Edge mode unavailable (%s). Falling back to cloud provider '%s'.",
                e,
                settings.stt_provider,
            )
            return _get_cloud_stt_service(settings, allow_local_override=False)

    return _get_cloud_stt_service(settings)
