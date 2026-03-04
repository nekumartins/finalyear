"""
Service: Text-to-Speech — Multiple provider support.

Providers:
  1. edge-tts   (Microsoft Edge TTS — FREE, 400+ voices, streaming, high quality)
  2. gTTS       (Google Translate TTS — FREE, simpler, fewer voices, no streaming)
  3. gemini     (Gemini 2.5 Flash Native Audio — Live API, streaming, 30 voices)
  4. placeholder (silence — for dev/testing)

The ws_handler calls `synthesize(text, voice)` after the LLM finishes
and streams base64-encoded audio chunks back to the client.
"""
import asyncio
import base64
import io
import logging
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

logger = logging.getLogger(__name__)


# ── Data types ──────────────────────────────────────────

@dataclass
class TTSChunk:
    """A chunk of synthesized audio ready for streaming."""
    audio_b64: str              # Base64-encoded audio (mp3 or pcm)
    content_type: str           # "audio/mpeg" or "audio/pcm"
    sample_rate: int = 24000    # Hz
    is_final: bool = False      # True for the last chunk


# ── Abstract interface ──────────────────────────────────

class TTSService(ABC):
    """Abstract text-to-speech interface."""

    @abstractmethod
    async def synthesize(self, text: str, voice: str = "default") -> AsyncIterator[TTSChunk]:
        """
        Synthesize text to audio, yielding chunks as they're ready.
        Final chunk has is_final=True.
        """
        ...

    @abstractmethod
    def list_voices(self) -> list[dict]:
        """Return available voices: [{id, name, gender, locale}]"""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...


# ── 1. Edge TTS (Microsoft — free, streaming, high quality) ─────

class EdgeTTSService(TTSService):
    """
    Microsoft Edge TTS via the `edge-tts` library.
    - 400+ voices, many languages
    - Streaming MP3 output
    - No API key required
    """

    # Popular voices for debate coaching
    VOICES = [
        {"id": "en-US-GuyNeural", "name": "Guy (US)", "gender": "Male", "locale": "en-US"},
        {"id": "en-US-JennyNeural", "name": "Jenny (US)", "gender": "Female", "locale": "en-US"},
        {"id": "en-US-AriaNeural", "name": "Aria (US)", "gender": "Female", "locale": "en-US"},
        {"id": "en-US-DavisNeural", "name": "Davis (US)", "gender": "Male", "locale": "en-US"},
        {"id": "en-US-JasonNeural", "name": "Jason (US)", "gender": "Male", "locale": "en-US"},
        {"id": "en-US-SaraNeural", "name": "Sara (US)", "gender": "Female", "locale": "en-US"},
        {"id": "en-US-TonyNeural", "name": "Tony (US)", "gender": "Male", "locale": "en-US"},
        {"id": "en-US-NancyNeural", "name": "Nancy (US)", "gender": "Female", "locale": "en-US"},
        {"id": "en-GB-RyanNeural", "name": "Ryan (UK)", "gender": "Male", "locale": "en-GB"},
        {"id": "en-GB-SoniaNeural", "name": "Sonia (UK)", "gender": "Female", "locale": "en-GB"},
        {"id": "en-GB-ThomasNeural", "name": "Thomas (UK)", "gender": "Male", "locale": "en-GB"},
        {"id": "en-AU-WilliamNeural", "name": "William (AU)", "gender": "Male", "locale": "en-AU"},
        {"id": "en-AU-NatashaNeural", "name": "Natasha (AU)", "gender": "Female", "locale": "en-AU"},
        {"id": "en-ZA-LeahNeural", "name": "Leah (ZA)", "gender": "Female", "locale": "en-ZA"},
        {"id": "en-ZA-LukeNeural", "name": "Luke (ZA)", "gender": "Male", "locale": "en-ZA"},
    ]

    DEFAULT_VOICE = "en-US-GuyNeural"

    async def synthesize(self, text: str, voice: str = "default") -> AsyncIterator[TTSChunk]:
        import edge_tts

        voice_id = voice if voice != "default" else self.DEFAULT_VOICE

        # Validate voice ID — fall back to default if invalid
        valid_ids = {v["id"] for v in self.VOICES}
        if voice_id not in valid_ids:
            logger.warning(f"[TTS] Unknown Edge voice '{voice_id}', using default")
            voice_id = self.DEFAULT_VOICE

        communicate = edge_tts.Communicate(text, voice_id)

        chunk_count = 0
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data = chunk["data"]
                    if audio_data:
                        chunk_count += 1
                        yield TTSChunk(
                            audio_b64=base64.b64encode(audio_data).decode("ascii"),
                            content_type="audio/mpeg",
                            sample_rate=24000,
                            is_final=False,
                        )

            # Final marker
            yield TTSChunk(
                audio_b64="",
                content_type="audio/mpeg",
                sample_rate=24000,
                is_final=True,
            )
            logger.info(f"[TTS:Edge] Synthesized {chunk_count} chunks for {len(text)} chars")

        except Exception as e:
            logger.error(f"[TTS:Edge] Synthesis failed: {e}")
            # Yield final marker so client knows stream ended
            yield TTSChunk(audio_b64="", content_type="audio/mpeg", sample_rate=24000, is_final=True)

    def list_voices(self) -> list[dict]:
        return self.VOICES

    @property
    def provider_name(self) -> str:
        return "edge-tts"


# ── 2. gTTS (Google Translate TTS — simple fallback) ────

class GoogleTTSService(TTSService):
    """
    Google Translate TTS via the `gtts` library.
    - Limited voices (language-only, no named voices)
    - Non-streaming (generates full MP3, then yields in chunks)
    - No API key required
    """

    VOICES = [
        {"id": "en-us", "name": "English (US)", "gender": "Neutral", "locale": "en-US"},
        {"id": "en-gb", "name": "English (UK)", "gender": "Neutral", "locale": "en-GB"},
        {"id": "en-au", "name": "English (AU)", "gender": "Neutral", "locale": "en-AU"},
        {"id": "en-za", "name": "English (ZA)", "gender": "Neutral", "locale": "en-ZA"},
        {"id": "en-in", "name": "English (IN)", "gender": "Neutral", "locale": "en-IN"},
    ]

    DEFAULT_VOICE = "en-us"

    async def synthesize(self, text: str, voice: str = "default") -> AsyncIterator[TTSChunk]:
        from gtts import gTTS

        tld_map = {
            "en-us": ("en", "com"),
            "en-gb": ("en", "co.uk"),
            "en-au": ("en", "com.au"),
            "en-za": ("en", "co.za"),
            "en-in": ("en", "co.in"),
        }

        voice_id = voice if voice != "default" else self.DEFAULT_VOICE
        lang, tld = tld_map.get(voice_id, ("en", "com"))

        try:
            # gTTS is synchronous — run in executor
            loop = asyncio.get_event_loop()
            mp3_buffer = io.BytesIO()
            tts = gTTS(text=text, lang=lang, tld=tld)
            await loop.run_in_executor(None, tts.write_to_fp, mp3_buffer)
            mp3_buffer.seek(0)
            full_mp3 = mp3_buffer.read()

            # Yield in ~32KB chunks for smooth streaming
            CHUNK_SIZE = 32 * 1024
            for i in range(0, len(full_mp3), CHUNK_SIZE):
                chunk_data = full_mp3[i:i + CHUNK_SIZE]
                yield TTSChunk(
                    audio_b64=base64.b64encode(chunk_data).decode("ascii"),
                    content_type="audio/mpeg",
                    sample_rate=24000,
                    is_final=False,
                )

            yield TTSChunk(
                audio_b64="",
                content_type="audio/mpeg",
                sample_rate=24000,
                is_final=True,
            )
            logger.info(f"[TTS:gTTS] Synthesized {len(full_mp3)} bytes for {len(text)} chars")

        except Exception as e:
            logger.error(f"[TTS:gTTS] Synthesis failed: {e}")
            yield TTSChunk(audio_b64="", content_type="audio/mpeg", sample_rate=24000, is_final=True)

    def list_voices(self) -> list[dict]:
        return self.VOICES

    @property
    def provider_name(self) -> str:
        return "gtts"


# ── 3. Gemini Native Audio Dialog (Live API, streaming) ──

class GeminiTTSService(TTSService):
    """
    Gemini 2.5 Flash Native Audio via the Live API.
    - Uses `client.aio.live.connect()` for real-time streaming audio
    - 30 named voices with distinct personality traits
    - Native audio reasoning — natural intonation, emotion, pacing
    - Streaming PCM output at 24 kHz, wrapped in WAV for browser playback
    - Requires GEMINI_API_KEY
    """

    MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

    VOICES = [
        {"id": "Zephyr", "name": "Zephyr (Bright)", "gender": "Neutral", "locale": "en"},
        {"id": "Puck", "name": "Puck (Upbeat)", "gender": "Neutral", "locale": "en"},
        {"id": "Charon", "name": "Charon (Informative)", "gender": "Neutral", "locale": "en"},
        {"id": "Kore", "name": "Kore (Firm)", "gender": "Neutral", "locale": "en"},
        {"id": "Fenrir", "name": "Fenrir (Excitable)", "gender": "Neutral", "locale": "en"},
        {"id": "Leda", "name": "Leda (Youthful)", "gender": "Neutral", "locale": "en"},
        {"id": "Orus", "name": "Orus (Firm)", "gender": "Neutral", "locale": "en"},
        {"id": "Aoede", "name": "Aoede (Breezy)", "gender": "Neutral", "locale": "en"},
        {"id": "Callirrhoe", "name": "Callirrhoe (Easy-going)", "gender": "Neutral", "locale": "en"},
        {"id": "Autonoe", "name": "Autonoe (Bright)", "gender": "Neutral", "locale": "en"},
        {"id": "Enceladus", "name": "Enceladus (Breathy)", "gender": "Neutral", "locale": "en"},
        {"id": "Iapetus", "name": "Iapetus (Clear)", "gender": "Neutral", "locale": "en"},
        {"id": "Umbriel", "name": "Umbriel (Easy-going)", "gender": "Neutral", "locale": "en"},
        {"id": "Algieba", "name": "Algieba (Smooth)", "gender": "Neutral", "locale": "en"},
        {"id": "Despina", "name": "Despina (Smooth)", "gender": "Neutral", "locale": "en"},
        {"id": "Erinome", "name": "Erinome (Clear)", "gender": "Neutral", "locale": "en"},
        {"id": "Algenib", "name": "Algenib (Gravelly)", "gender": "Neutral", "locale": "en"},
        {"id": "Rasalgethi", "name": "Rasalgethi (Informative)", "gender": "Neutral", "locale": "en"},
        {"id": "Laomedeia", "name": "Laomedeia (Upbeat)", "gender": "Neutral", "locale": "en"},
        {"id": "Achernar", "name": "Achernar (Soft)", "gender": "Neutral", "locale": "en"},
        {"id": "Alnilam", "name": "Alnilam (Firm)", "gender": "Neutral", "locale": "en"},
        {"id": "Schedar", "name": "Schedar (Even)", "gender": "Neutral", "locale": "en"},
        {"id": "Gacrux", "name": "Gacrux (Mature)", "gender": "Neutral", "locale": "en"},
        {"id": "Pulcherrima", "name": "Pulcherrima (Forward)", "gender": "Neutral", "locale": "en"},
        {"id": "Achird", "name": "Achird (Friendly)", "gender": "Neutral", "locale": "en"},
        {"id": "Zubenelgenubi", "name": "Zubenelgenubi (Casual)", "gender": "Neutral", "locale": "en"},
        {"id": "Vindemiatrix", "name": "Vindemiatrix (Gentle)", "gender": "Neutral", "locale": "en"},
        {"id": "Sadachbia", "name": "Sadachbia (Lively)", "gender": "Neutral", "locale": "en"},
        {"id": "Sadaltager", "name": "Sadaltager (Knowledgeable)", "gender": "Neutral", "locale": "en"},
        {"id": "Sulafat", "name": "Sulafat (Warm)", "gender": "Neutral", "locale": "en"},
    ]

    DEFAULT_VOICE = "Kore"

    # Minimum PCM bytes to accumulate before yielding a WAV chunk.
    # 24000 Hz × 2 bytes × 0.5 s = 24000 bytes (~0.5 s of audio)
    MIN_PCM_CHUNK = 24_000

    async def synthesize(self, text: str, voice: str = "default") -> AsyncIterator[TTSChunk]:
        from google import genai
        from google.genai import types
        from backend.app.config import get_settings

        settings = get_settings()
        if not settings.gemini_api_key:
            logger.error("[TTS:Gemini] No GEMINI_API_KEY configured")
            yield TTSChunk(audio_b64="", content_type="audio/wav", sample_rate=24000, is_final=True)
            return

        voice_name = voice if voice != "default" else self.DEFAULT_VOICE
        valid_ids = {v["id"] for v in self.VOICES}
        if voice_name not in valid_ids:
            logger.warning(f"[TTS:Gemini] Unknown voice '{voice_name}', using default")
            voice_name = self.DEFAULT_VOICE

        config = {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": voice_name}
                }
            },
        }

        try:
            client = genai.Client(api_key=settings.gemini_api_key)

            chunk_count = 0
            total_pcm = 0
            pcm_buffer = bytearray()

            async with client.aio.live.connect(
                model=self.MODEL, config=config
            ) as session:
                # Send text as a user turn
                await session.send_client_content(
                    turns={"role": "user", "parts": [{"text": text}]},
                    turn_complete=True,
                )

                # Receive streaming audio
                async for response in session.receive():
                    if response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.inline_data and isinstance(part.inline_data.data, bytes):
                                pcm_buffer.extend(part.inline_data.data)
                                total_pcm += len(part.inline_data.data)

                                # Yield WAV chunk when we have enough PCM accumulated
                                while len(pcm_buffer) >= self.MIN_PCM_CHUNK:
                                    segment = bytes(pcm_buffer[: self.MIN_PCM_CHUNK])
                                    del pcm_buffer[: self.MIN_PCM_CHUNK]

                                    wav_buf = io.BytesIO()
                                    with wave.open(wav_buf, "wb") as wf:
                                        wf.setnchannels(1)
                                        wf.setsampwidth(2)
                                        wf.setframerate(24000)
                                        wf.writeframes(segment)

                                    chunk_count += 1
                                    yield TTSChunk(
                                        audio_b64=base64.b64encode(wav_buf.getvalue()).decode("ascii"),
                                        content_type="audio/wav",
                                        sample_rate=24000,
                                        is_final=False,
                                    )

                    # Turn complete — flush remaining buffer
                    if response.server_content and response.server_content.turn_complete:
                        break

            # Flush any remaining PCM
            if pcm_buffer:
                wav_buf = io.BytesIO()
                with wave.open(wav_buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(bytes(pcm_buffer))

                chunk_count += 1
                yield TTSChunk(
                    audio_b64=base64.b64encode(wav_buf.getvalue()).decode("ascii"),
                    content_type="audio/wav",
                    sample_rate=24000,
                    is_final=False,
                )

            # Final marker
            yield TTSChunk(
                audio_b64="",
                content_type="audio/wav",
                sample_rate=24000,
                is_final=True,
            )
            logger.info(
                f"[TTS:Gemini] Streamed {chunk_count} WAV chunks "
                f"({total_pcm} bytes PCM) for {len(text)} chars, voice={voice_name}"
            )

        except Exception as e:
            logger.error(f"[TTS:Gemini] Synthesis failed: {e}")
            yield TTSChunk(audio_b64="", content_type="audio/wav", sample_rate=24000, is_final=True)

    def list_voices(self) -> list[dict]:
        return self.VOICES

    @property
    def provider_name(self) -> str:
        return "gemini"


# ── 4. Placeholder (silence — for dev/testing) ──────────

class PlaceholderTTSService(TTSService):
    """Returns silence. Useful for development without a real TTS backend."""

    async def synthesize(self, text: str, voice: str = "default") -> AsyncIterator[TTSChunk]:
        # Just yield a final marker immediately
        yield TTSChunk(audio_b64="", content_type="audio/pcm", sample_rate=16000, is_final=True)

    def list_voices(self) -> list[dict]:
        return [{"id": "silent", "name": "Silent (dev)", "gender": "Neutral", "locale": "en-US"}]

    @property
    def provider_name(self) -> str:
        return "placeholder"


# ── Factory ─────────────────────────────────────────────

_PROVIDERS: dict[str, type[TTSService]] = {
    "edge-tts": EdgeTTSService,
    "gtts": GoogleTTSService,
    "gemini": GeminiTTSService,
    "placeholder": PlaceholderTTSService,
    "none": PlaceholderTTSService,
}


def get_tts_service(provider: str = "edge-tts") -> TTSService:
    """Factory: returns TTS service for the given provider name."""
    cls = _PROVIDERS.get(provider, EdgeTTSService)
    return cls()


def get_available_providers() -> list[dict]:
    """Return list of available TTS providers with their voices."""
    result = []
    for name, cls in _PROVIDERS.items():
        if name == "none":
            continue
        instance = cls()
        result.append({
            "provider": name,
            "display_name": instance.provider_name,
            "voices": instance.list_voices(),
        })
    return result
