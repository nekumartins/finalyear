"""
Service: Text-to-Speech — Converts AI text responses to audio.

This module defines the abstract interface and provides a placeholder
implementation. Real TTS backends (Google Cloud TTS, Edge TTS, Coqui,
Piper, etc.) should implement the TTSService ABC.

The pipeline integration is optional — when enabled, AI response text
is fed to the TTS service and the resulting audio is streamed back to
the client alongside the text tokens.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class TTSChunk:
    """A chunk of synthesized audio ready for streaming."""
    audio_bytes: bytes          # PCM16 mono audio
    sample_rate: int = 16000    # Hz
    duration_ms: float = 0.0    # Duration of this chunk
    is_final: bool = False      # True for the last chunk in a synthesis run


class TTSService(ABC):
    """Abstract text-to-speech interface."""

    @abstractmethod
    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        """
        Synthesize full text to audio (non-streaming).
        Returns PCM16 mono audio bytes.
        """
        ...

    @abstractmethod
    async def synthesize_stream(self, text: str, voice: str = "default") -> AsyncIterator[TTSChunk]:
        """
        Stream synthesis: yields audio chunks as they become available.
        Useful for low-latency playback while text is still being generated.
        """
        ...

    @abstractmethod
    async def synthesize_token_stream(
        self, token_stream: AsyncIterator[str], voice: str = "default"
    ) -> AsyncIterator[TTSChunk]:
        """
        Accepts a stream of text tokens (from LLM) and yields audio chunks.
        This is the most latency-optimal path: TTS generates audio as soon
        as enough text accumulates (sentence-level buffering).
        """
        ...

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output audio sample rate in Hz."""
        ...


class PlaceholderTTSService(TTSService):
    """
    Placeholder TTS that returns silence.

    Useful for development/testing without a real TTS backend.
    Replace with a real implementation (e.g., Google Cloud TTS, Edge TTS).
    """

    SAMPLE_RATE = 16000

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        # Return ~100ms of silence per 10 chars (rough approximation)
        duration_ms = max(100, len(text) * 10)
        num_samples = int(self.SAMPLE_RATE * duration_ms / 1000)
        return b"\x00\x00" * num_samples  # PCM16 silence

    async def synthesize_stream(self, text: str, voice: str = "default") -> AsyncIterator[TTSChunk]:
        # Simulate streaming: yield one chunk per sentence
        sentences = [s.strip() for s in text.replace(".", ".\n").split("\n") if s.strip()]
        for i, sentence in enumerate(sentences):
            duration_ms = max(100, len(sentence) * 10)
            num_samples = int(self.SAMPLE_RATE * duration_ms / 1000)
            yield TTSChunk(
                audio_bytes=b"\x00\x00" * num_samples,
                sample_rate=self.SAMPLE_RATE,
                duration_ms=duration_ms,
                is_final=(i == len(sentences) - 1),
            )
            await asyncio.sleep(duration_ms / 1000)  # Simulate processing time

    async def synthesize_token_stream(
        self, token_stream: AsyncIterator[str], voice: str = "default"
    ) -> AsyncIterator[TTSChunk]:
        """Buffer tokens into sentences, then synthesize each sentence."""
        buffer = ""
        sentence_ends = {".", "!", "?", "\n"}

        async for token in token_stream:
            buffer += token

            # Check if we have a complete sentence
            if any(buffer.rstrip().endswith(p) for p in sentence_ends) and len(buffer) > 10:
                sentence = buffer.strip()
                buffer = ""
                duration_ms = max(100, len(sentence) * 10)
                num_samples = int(self.SAMPLE_RATE * duration_ms / 1000)
                yield TTSChunk(
                    audio_bytes=b"\x00\x00" * num_samples,
                    sample_rate=self.SAMPLE_RATE,
                    duration_ms=duration_ms,
                    is_final=False,
                )
                await asyncio.sleep(0.05)  # Simulate processing

        # Flush remaining buffer
        if buffer.strip():
            duration_ms = max(100, len(buffer) * 10)
            num_samples = int(self.SAMPLE_RATE * duration_ms / 1000)
            yield TTSChunk(
                audio_bytes=b"\x00\x00" * num_samples,
                sample_rate=self.SAMPLE_RATE,
                duration_ms=duration_ms,
                is_final=True,
            )

    @property
    def sample_rate(self) -> int:
        return self.SAMPLE_RATE


def get_tts_service(mode: str = "cloud") -> TTSService:
    """Factory: returns TTS service for the given mode."""
    # TODO: Implement real TTS backends
    # if mode == "cloud":
    #     return GoogleCloudTTSService()
    # elif mode == "edge":
    #     return PiperTTSService()
    return PlaceholderTTSService()
