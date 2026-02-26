"""
Service: STT (Speech-to-Text) — Multi-provider

Providers:
  - Deepgram: REST API (Nova-3), low-latency, $200 free credit
  - Groq: OpenAI-compatible Whisper API (batch), free tier
  - faster-whisper: Local CPU inference, no API needed

Design: All providers share the same interface (STTService ABC).
Audio is buffered locally (~2s of 16kHz PCM16) then sent for transcription.
Results are delivered via an async queue (non-blocking).
"""
import io
import logging
import struct
import asyncio
import inspect
import time
from abc import ABC, abstractmethod

import httpx

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

# ── Shared hallucination filter ──
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


def _filter_hallucination(text: str) -> str | None:
    """Return None if text is a known Whisper/STT hallucination, else return cleaned text."""
    if not text or len(text) < 3:
        return None
    text_lower = text.lower().strip(" .,!?")
    if text_lower in HALLUCINATION_BLOCKLIST:
        logger.info(f"[STT] Filtered hallucination: '{text}'")
        return None
    return text.strip()


# ── WAV conversion helper ──

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


async def _cancel_pending_tasks(tasks: list[asyncio.Task], timeout_s: float = 2.0) -> None:
    """Best-effort cancellation for in-flight transcription tasks."""
    if not tasks:
        return

    for task in tasks:
        if not task.done():
            task.cancel()

    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout_s)
    except asyncio.TimeoutError:
        logger.warning(f"[STT] Timed out waiting for {len(tasks)} task(s) to cancel")
    finally:
        tasks.clear()


def _drain_result_queue(result_queue: asyncio.Queue[dict]) -> None:
    while not result_queue.empty():
        try:
            result_queue.get_nowait()
        except asyncio.QueueEmpty:
            break


async def _close_client_if_supported(client: object) -> None:
    close_fn = getattr(client, "close", None)
    if not close_fn:
        return
    maybe_awaitable = close_fn()
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


# ═══════════════════════════════════════════════════════════
# Abstract base
# ═══════════════════════════════════════════════════════════

class STTService(ABC):
    """Abstract STT interface — all implementations must follow this."""

    @abstractmethod
    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        """Feed a single audio chunk. Returns None (results come via get_result)."""
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

    async def close(self) -> None:
        """Release provider resources and cancel in-flight work."""
        return


# ═══════════════════════════════════════════════════════════
# Deepgram REST API (Nova-3)
# ═══════════════════════════════════════════════════════════

class DeepgramSTTService(STTService):
    """
    Deepgram Nova-3 via REST API.
    Buffers ~2s of audio, sends as WAV to Deepgram's pre-recorded endpoint.
    Much faster than Groq (typically <1s response time).
    """

    BUFFER_THRESHOLD = 16_000  # ~500ms of 16kHz mono PCM16 (was 64KB/2s — too slow for live feedback)

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.deepgram_api_key
        self.client = httpx.AsyncClient(timeout=10.0)
        self._buffer = bytearray()
        self._full_transcript = ""
        self.result_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._pending_tasks: list[asyncio.Task] = []
        logger.info(f"[STT/Deepgram] Initialized (api_key={'SET' if self.api_key else 'MISSING'})")

    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        """Buffer audio. When full, fire non-blocking API call."""
        self._buffer.extend(audio_bytes)
        logger.debug(f"[STT/Deepgram] Buffer: {len(self._buffer)}/{self.BUFFER_THRESHOLD} bytes")

        if len(self._buffer) < self.BUFFER_THRESHOLD:
            return None

        pcm_bytes = bytes(self._buffer)
        self._buffer.clear()
        logger.info(f"[STT/Deepgram] Buffer full — firing transcription task ({len(pcm_bytes)} bytes)")
        task = asyncio.create_task(self._transcribe_and_enqueue(pcm_bytes))
        self._pending_tasks.append(task)
        self._pending_tasks = [t for t in self._pending_tasks if not t.done()]
        return None

    async def get_result(self) -> dict | None:
        try:
            return self.result_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def _transcribe_and_enqueue(self, pcm_bytes: bytes) -> None:
        result = await self._transcribe_pcm(pcm_bytes)
        if result:
            await self.result_queue.put(result)

    async def _transcribe_pcm(self, pcm_bytes: bytes) -> dict | None:
        """Core: PCM → WAV → Deepgram REST API → filtered text."""
        wav_bytes = _pcm16_to_wav(pcm_bytes)

        try:
            start_t = time.time()
            logger.info(f"[STT/Deepgram] Sending {len(wav_bytes)} bytes...")

            response = await self.client.post(
                "https://api.deepgram.com/v1/listen",
                params={
                    "model": "nova-3",
                    "language": "en",
                    "punctuate": "true",
                    "smart_format": "true",
                },
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "audio/wav",
                },
                content=wav_bytes,
            )
            dur = time.time() - start_t

            if response.status_code != 200:
                logger.error(f"[STT/Deepgram] API error {response.status_code}: {response.text[:200]}")
                return None

            data = response.json()
            text = (
                data.get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "")
            )
            logger.info(f"[STT/Deepgram] Got '{text}' in {dur:.2f}s")

            text = _filter_hallucination(text)
            if text:
                self._full_transcript += " " + text
                return {"text": text, "is_final": True}

        except httpx.TimeoutException:
            logger.warning("[STT/Deepgram] Request timed out (10s)")
        except Exception as e:
            logger.error(f"[STT/Deepgram] Error: {e}")

        return None

    async def flush(self) -> dict | None:
        if len(self._buffer) < 1600:
            if self._pending_tasks:
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            results = []
            while not self.result_queue.empty():
                try:
                    r = self.result_queue.get_nowait()
                    results.append(r["text"])
                except asyncio.QueueEmpty:
                    break
            if results:
                return {"text": " ".join(results), "is_final": True}
            return None

        pcm_bytes = bytes(self._buffer)
        self._buffer.clear()
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()
        result = await self._transcribe_pcm(pcm_bytes)
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
            return {"text": " ".join(all_texts), "is_final": True}
        return result

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        wav_bytes = _pcm16_to_wav(audio_bytes)
        try:
            response = await self.client.post(
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
        except Exception as e:
            logger.error(f"[STT/Deepgram] Batch error: {e}")
        return ""

    def get_full_transcript(self) -> str:
        return self._full_transcript.strip()

    async def close(self) -> None:
        await _cancel_pending_tasks(self._pending_tasks)
        self._buffer.clear()
        _drain_result_queue(self.result_queue)
        try:
            await self.client.aclose()
        except Exception as e:
            logger.warning(f"[STT/Deepgram] Client close error: {e}")


# ═══════════════════════════════════════════════════════════
# Groq Whisper API (kept as fallback)
# ═══════════════════════════════════════════════════════════

class GroqSTTService(STTService):
    """
    Groq Whisper API (whisper-large-v3-turbo).
    Free tier but unreliable latency (0.5s to 24s per call).
    Kept as fallback if Deepgram is unavailable.
    """

    BUFFER_THRESHOLD = 64_000

    def __init__(self):
        from openai import AsyncOpenAI
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )
        self._buffer = bytearray()
        self._full_transcript = ""
        self.result_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._pending_tasks: list[asyncio.Task] = []

    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        self._buffer.extend(audio_bytes)
        if len(self._buffer) < self.BUFFER_THRESHOLD:
            return None

        pcm_bytes = bytes(self._buffer)
        self._buffer.clear()
        task = asyncio.create_task(self._transcribe_and_enqueue(pcm_bytes))
        self._pending_tasks.append(task)
        self._pending_tasks = [t for t in self._pending_tasks if not t.done()]
        return None

    async def get_result(self) -> dict | None:
        try:
            return self.result_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def _transcribe_and_enqueue(self, pcm_bytes: bytes) -> None:
        result = await self._transcribe_pcm(pcm_bytes)
        if result:
            await self.result_queue.put(result)

    async def _transcribe_pcm(self, pcm_bytes: bytes) -> dict | None:
        wav_bytes = _pcm16_to_wav(pcm_bytes)
        try:
            audio_file = io.BytesIO(wav_bytes)
            audio_file.name = "audio.wav"

            start_t = time.time()
            logger.info(f"[STT/Groq] Calling API with {len(wav_bytes)} bytes...")

            response = await self.client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                language="en",
                response_format="text",
            )
            dur = time.time() - start_t
            logger.info(f"[STT/Groq] API returned in {dur:.2f}s")

            text = response.strip() if isinstance(response, str) else response.text.strip()
            text = _filter_hallucination(text)
            if text:
                self._full_transcript += " " + text
                return {"text": text, "is_final": True}

        except Exception as e:
            logger.error(f"[STT/Groq] API error: {e}")
        return None

    async def flush(self) -> dict | None:
        if len(self._buffer) < 1600:
            if self._pending_tasks:
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            results = []
            while not self.result_queue.empty():
                try:
                    r = self.result_queue.get_nowait()
                    results.append(r["text"])
                except asyncio.QueueEmpty:
                    break
            if results:
                return {"text": " ".join(results), "is_final": True}
            return None

        pcm_bytes = bytes(self._buffer)
        self._buffer.clear()
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()
        result = await self._transcribe_pcm(pcm_bytes)
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
            return {"text": " ".join(all_texts), "is_final": True}
        return result

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        from openai import AsyncOpenAI
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
            logger.error(f"[STT/Groq] Batch error: {e}")
            return ""

    def get_full_transcript(self) -> str:
        return self._full_transcript.strip()

    async def close(self) -> None:
        await _cancel_pending_tasks(self._pending_tasks)
        self._buffer.clear()
        _drain_result_queue(self.result_queue)
        try:
            await _close_client_if_supported(self.client)
        except Exception as e:
            logger.warning(f"[STT/Groq] Client close error: {e}")


# ═══════════════════════════════════════════════════════════
# Local faster-whisper (Edge mode - no API needed)
# ═══════════════════════════════════════════════════════════

class LocalSTTService(STTService):
    """
    Local STT using faster-whisper (CTranslate2 backend).
    Runs on CPU with int8 quantization. No API key needed.
    Model downloads automatically on first use (~150MB for 'base').
    """

    BUFFER_THRESHOLD = 64_000

    def __init__(self):
        settings = get_settings()
        model_size = settings.faster_whisper_model
        logger.info(f"[STT/Local] Loading faster-whisper model '{model_size}' (int8, CPU)...")

        from faster_whisper import WhisperModel
        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
        )
        logger.info(f"[STT/Local] Model loaded successfully")

        self._buffer = bytearray()
        self._full_transcript = ""
        self.result_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._pending_tasks: list[asyncio.Task] = []

    async def transcribe_chunk(self, audio_bytes: bytes) -> dict | None:
        self._buffer.extend(audio_bytes)
        if len(self._buffer) < self.BUFFER_THRESHOLD:
            return None

        pcm_bytes = bytes(self._buffer)
        self._buffer.clear()
        task = asyncio.create_task(self._transcribe_and_enqueue(pcm_bytes))
        self._pending_tasks.append(task)
        self._pending_tasks = [t for t in self._pending_tasks if not t.done()]
        return None

    async def get_result(self) -> dict | None:
        try:
            return self.result_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def _transcribe_and_enqueue(self, pcm_bytes: bytes) -> None:
        result = await self._transcribe_pcm(pcm_bytes)
        if result:
            await self.result_queue.put(result)

    async def _transcribe_pcm(self, pcm_bytes: bytes) -> dict | None:
        """Transcribe PCM in a thread pool to avoid blocking the event loop."""
        import numpy as np

        try:
            start_t = time.time()
            # Convert PCM16 bytes to float32 numpy array
            audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # Run in thread pool (faster-whisper is sync/CPU-bound)
            segments, info = await asyncio.to_thread(
                self.model.transcribe,
                audio_array,
                language="en",
                beam_size=1,  # Fastest decoding
                vad_filter=True,  # Built-in VAD
            )

            # Collect all segment texts
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            text = " ".join(text_parts)
            dur = time.time() - start_t
            logger.info(f"[STT/Local] Transcribed in {dur:.2f}s: '{text}'")

            text = _filter_hallucination(text)
            if text:
                self._full_transcript += " " + text
                return {"text": text, "is_final": True}

        except Exception as e:
            logger.error(f"[STT/Local] Error: {e}")
        return None

    async def flush(self) -> dict | None:
        if len(self._buffer) < 1600:
            if self._pending_tasks:
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            results = []
            while not self.result_queue.empty():
                try:
                    r = self.result_queue.get_nowait()
                    results.append(r["text"])
                except asyncio.QueueEmpty:
                    break
            if results:
                return {"text": " ".join(results), "is_final": True}
            return None

        pcm_bytes = bytes(self._buffer)
        self._buffer.clear()
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()
        result = await self._transcribe_pcm(pcm_bytes)
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
            return {"text": " ".join(all_texts), "is_final": True}
        return result

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
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

    def get_full_transcript(self) -> str:
        return self._full_transcript.strip()

    async def close(self) -> None:
        await _cancel_pending_tasks(self._pending_tasks)
        self._buffer.clear()
        _drain_result_queue(self.result_queue)


# ═══════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════

def get_stt_service(mode: str) -> STTService:
    """
    Factory: returns the right STT service based on session mode and config.
    - Cloud mode: uses the configured provider (deepgram, groq)
    - Edge mode: uses faster-whisper locally
    """
    settings = get_settings()

    if mode == "edge":
        logger.info("[STT] Creating LocalSTTService (faster-whisper)")
        return LocalSTTService()

    # Cloud mode — use configured provider
    provider = settings.stt_provider.lower()

    if provider == "deepgram":
        if not settings.deepgram_api_key:
            logger.warning("[STT] No DEEPGRAM_API_KEY set, falling back to Groq")
            return GroqSTTService()
        logger.info("[STT] Creating DeepgramSTTService (Nova-3)")
        return DeepgramSTTService()

    if provider == "faster-whisper":
        logger.info("[STT] Creating LocalSTTService (faster-whisper, cloud-mode override)")
        return LocalSTTService()

    # Default: Groq
    logger.info("[STT] Creating GroqSTTService (Whisper)")
    return GroqSTTService()
