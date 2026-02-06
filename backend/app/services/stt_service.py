"""
Service: STT (Speech-to-Text) — Module 4 (Cloud) / Module 5 (Edge)

This is the INTERFACE. Concrete implementations plug in based on session mode.
Cloud: OpenAI Whisper API (streaming)
Edge:  Vosk on-device (built in Phase 7)
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class STTService(ABC):
    """Abstract STT interface — all implementations must follow this."""

    @abstractmethod
    async def transcribe_stream(
        self, audio_chunks: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[dict, None]:
        """
        Yields incremental transcription results:
        {"text": "...", "is_final": bool}
        """
        ...

    @abstractmethod
    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        """Transcribe a complete audio buffer. Used for post-session."""
        ...


class CloudSTTService(STTService):
    """Cloud Path: OpenAI Whisper API (placeholder — implemented in Phase 3)."""

    async def transcribe_stream(self, audio_chunks):
        # TODO: Phase 3 — integrate OpenAI Whisper streaming
        async for chunk in audio_chunks:
            yield {"text": "[cloud STT placeholder]", "is_final": False}

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        # TODO: Phase 3
        return "[cloud STT batch placeholder]"


class EdgeSTTService(STTService):
    """Edge Path: Vosk (placeholder — implemented in Phase 7)."""

    async def transcribe_stream(self, audio_chunks):
        # TODO: Phase 7 — integrate Vosk
        async for chunk in audio_chunks:
            yield {"text": "[edge STT placeholder]", "is_final": False}

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        # TODO: Phase 7
        return "[edge STT batch placeholder]"


def get_stt_service(mode: str) -> STTService:
    """Factory: returns the right STT service based on session mode."""
    if mode == "edge":
        return EdgeSTTService()
    return CloudSTTService()
