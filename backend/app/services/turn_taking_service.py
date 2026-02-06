"""
Service: Turn-Taking — Module 3 (VAD + End-of-Turn Detection)

Determines WHEN the AI should start responding:
- Silero VAD: Is the user currently speaking?
- EoT Detector: Is the user about to finish their turn?

This replaces the naive "wait for N seconds of silence" approach.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TurnPrediction:
    """Result of turn-taking analysis on an audio chunk."""
    is_speech: bool           # VAD: is there speech in this chunk?
    eot_probability: float    # EoT: probability user is finishing (0.0–1.0)
    should_ai_speak: bool     # Combined decision: should AI take the floor?


class TurnTakingService(ABC):
    """Abstract turn-taking interface."""

    @abstractmethod
    async def analyze_chunk(self, audio_bytes: bytes, sample_rate: int = 16000) -> TurnPrediction:
        """Analyze a single audio chunk and predict turn state."""
        ...

    @abstractmethod
    async def reset(self) -> None:
        """Reset internal state for a new session."""
        ...


class PlaceholderTurnTakingService(TurnTakingService):
    """
    Placeholder: simple energy-based VAD.
    Replaced in Phase 5 with Silero VAD + GRU EoT model.
    """
    def __init__(self):
        self._silence_frames = 0
        self._silence_threshold = 15  # ~1.5s of silence at 100ms chunks

    async def analyze_chunk(self, audio_bytes: bytes, sample_rate: int = 16000) -> TurnPrediction:
        # Simple energy check (placeholder)
        energy = sum(abs(b - 128) for b in audio_bytes) / max(len(audio_bytes), 1)
        is_speech = energy > 10  # arbitrary threshold

        if not is_speech:
            self._silence_frames += 1
        else:
            self._silence_frames = 0

        # After enough silence, signal AI should speak
        eot_prob = min(self._silence_frames / self._silence_threshold, 1.0)
        should_speak = eot_prob > 0.8

        return TurnPrediction(
            is_speech=is_speech,
            eot_probability=eot_prob,
            should_ai_speak=should_speak,
        )

    async def reset(self) -> None:
        self._silence_frames = 0


def get_turn_taking_service() -> TurnTakingService:
    """Factory: returns turn-taking service. Upgraded in Phase 5."""
    return PlaceholderTurnTakingService()
