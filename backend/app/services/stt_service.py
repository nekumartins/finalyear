"""
Service: STT (Speech-to-Text) — Module 4 (Cloud) / Module 5 (Edge)

This is the INTERFACE. Concrete implementations plug in based on session mode.
Cloud: OpenAI Whisper API (buffered chunked transcription)
Edge:  Vosk on-device (built in Phase 7)

Design decision — why buffered, not streaming:
  OpenAI's Whisper API accepts complete audio files, not streams.
  We accumulate PCM16 audio in a buffer and transcribe every ~2 seconds.
  This gives near-real-time results while keeping API calls manageable.
  For true streaming, Phase 7 (Vosk edge) will handle frame-by-frame.
"""
import io
import logging
import struct
import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from openai import AsyncOpenAI

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class STTService(ABC):
    """Abstract STT interface — all implementations must follow this."""

    @abstractmethod
    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        """
        Feed a single audio chunk. Returns transcription result when ready:
        {"text": "...", "is_final": bool}
        Returns None if still buffering.
        """
        ...

    @abstractmethod
    async def flush(self) -> dict | None:
        """Force-transcribe any remaining buffered audio (e.g. on session end)."""
        ...

    async def get_result(self) -> dict | None:
        """Poll for completed transcription results (non-blocking). Override in async impls."""
        return None

    @abstractmethod
    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        """Transcribe a complete audio buffer. Used for post-session."""
        ...


def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Convert raw PCM16 bytes to a WAV file in memory."""
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_bytes)

    buf = io.BytesIO()
    # RIFF header
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    # fmt chunk
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))               # chunk size
    buf.write(struct.pack("<H", 1))                 # PCM format
    buf.write(struct.pack("<H", channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", byte_rate))
    buf.write(struct.pack("<H", block_align))
    buf.write(struct.pack("<H", bits_per_sample))
    # data chunk
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm_bytes)
    return buf.getvalue()


class CloudSTTService(STTService):
    """
    Cloud Path: Groq Whisper API (whisper-large-v3-turbo).

    Buffers PCM16 audio chunks and sends to Whisper every ~2 seconds.
    16kHz mono PCM16 = 32,000 bytes/sec → buffer threshold = 64,000 bytes (~2s).

    Why Groq over OpenAI:
      - Free tier (6K requests/day)
      - Same Whisper model, faster inference (Groq LPU)
      - OpenAI-compatible API — zero code change needed
    """

    BUFFER_THRESHOLD = 64_000  # ~2 seconds of 16kHz mono PCM16

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )
        self._buffer = bytearray()
        self._full_transcript = ""
        # Non-blocking: results arrive here from background tasks
        self.result_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._pending_tasks: list[asyncio.Task] = []

    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        """Buffer audio. When full, fire off API call in background (non-blocking)."""
        self._buffer.extend(audio_bytes)

        if len(self._buffer) < self.BUFFER_THRESHOLD:
            return None  # Still buffering

        # Buffer is full — snapshot it and fire background task
        pcm_bytes = bytes(self._buffer)
        self._buffer.clear()
        task = asyncio.create_task(self._transcribe_and_enqueue(pcm_bytes))
        self._pending_tasks.append(task)
        # Clean up completed tasks
        self._pending_tasks = [t for t in self._pending_tasks if not t.done()]
        return None  # Never blocks — results come via get_result()

    async def get_result(self) -> dict | None:
        """Non-blocking poll for completed transcription results."""
        try:
            return self.result_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def _transcribe_and_enqueue(self, pcm_bytes: bytes) -> None:
        """Background task: transcribe PCM buffer and put result in queue."""
        result = await self._transcribe_pcm(pcm_bytes)
        if result:
            await self.result_queue.put(result)

    async def flush(self) -> dict | None:
        """Transcribe whatever remains in the buffer (blocking — only at session end)."""
        if len(self._buffer) < 1600:  # Less than 0.05s — skip noise
            # But still wait for pending background tasks
            if self._pending_tasks:
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            # Drain any remaining results
            results = []
            while not self.result_queue.empty():
                try:
                    r = self.result_queue.get_nowait()
                    results.append(r["text"])
                except asyncio.QueueEmpty:
                    break
            if results:
                combined = " ".join(results)
                return {"text": combined, "is_final": True}
            return None

        pcm_bytes = bytes(self._buffer)
        self._buffer.clear()
        # Wait for all pending background tasks first
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()
        result = await self._transcribe_pcm(pcm_bytes)
        # Also drain any queued results
        all_texts = []
        while not self.result_queue.empty():
            try:
                r = self.result_queue.get_nowait()
                all_texts.append(r["text"])
            except asyncio.QueueEmpty:
                break
        if result:
            all_texts.append(result["text"])
        if all_texts:
            combined = " ".join(all_texts)
            return {"text": combined, "is_final": True}
        return result

    async def _transcribe_pcm(self, pcm_bytes: bytes) -> dict | None:
        """Core transcription: PCM → WAV → Whisper API → filtered text."""
        wav_bytes = _pcm16_to_wav(pcm_bytes)

        try:
            audio_file = io.BytesIO(wav_bytes)
            audio_file.name = "audio.wav"

            import time
            start_t = time.time()
            logger.info(f"[STT] Calling Groq API with {len(wav_bytes)} bytes...")

            response = await self.client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                language="en",
                response_format="text",
            )
            dur = time.time() - start_t
            logger.info(f"[STT] Groq API returned in {dur:.2f}s")

            text = response.strip() if isinstance(response, str) else response.text.strip()

            # ── Whisper hallucination filter ──
            HALLUCINATION_BLOCKLIST = {
                "you", "yeah", "yes", "yes.", "no", "okay", "ok",
                "thank you", "thank you.", "thanks", "thanks.",
                "bye", "bye.", "goodbye", "goodbye.",
                "hello", "hello.", "hi", "hi.",
                "hmm", "hm", "um", "uh", "ah", "oh",
                "my teeth", "one, two, three, go.",
                "that is my life.", "it's time to present.",
                "what's that?", "...", "…",
                "so", "er", "right", "well",
                "you know", "i mean",
            }
            text_lower = text.lower().strip(" .,!?")
            if not text or len(text) < 3 or text_lower in HALLUCINATION_BLOCKLIST:
                if text:
                    logger.info(f"[STT] Filtered hallucination: '{text}'")
                return None

            if text:
                self._full_transcript += " " + text
                logger.info(f"[STT] Transcribed: {text}")
                return {"text": text, "is_final": True}

        except Exception as e:
            logger.error(f"[STT] Whisper API error: {e}")

        return None

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        wav_bytes = _pcm16_to_wav(audio_bytes)
        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        try:
            response = await self.client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                language="en",
                response_format="text",
            )
            return response.strip() if isinstance(response, str) else response.text.strip()
        except Exception as e:
            logger.error(f"[STT] Batch transcription error: {e}")
            return ""

    def get_full_transcript(self) -> str:
        return self._full_transcript.strip()


class EdgeSTTService(STTService):
    """Edge Path: Vosk (placeholder — implemented in Phase 7)."""

    def __init__(self):
        self._buffer = bytearray()

    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        self._buffer.extend(audio_bytes)
        if len(self._buffer) >= 64_000:
            self._buffer.clear()
            return {"text": "[edge STT — Phase 7]", "is_final": True}
        return None

    async def flush(self) -> dict | None:
        self._buffer.clear()
        return None

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        return "[edge STT batch — Phase 7]"

    async def get_result(self) -> dict | None:
        return None


def get_stt_service(mode: str) -> STTService:
    """Factory: returns the right STT service based on session mode."""
    if mode == "edge":
        return EdgeSTTService()
    return CloudSTTService()
