"""
Service: Turn-Taking — Module 3 (Hybrid VAD + End-of-Turn Detection)

Determines WHEN the AI should start responding using a hybrid approach:
  1. Heuristic: proper PCM16 RMS energy + silence duration (always active)
  2. Predictive: Silero VAD for speech probability (optional, enhances accuracy)

The heuristic has veto power — if silence < minimum threshold, the
predictive model won't trigger a turn. This prevents false triggers.

Adaptive endpointing:
  - Short utterance (<5 words estimated): 800ms silence = yield
  - Long utterance: 1.5s silence = yield
"""
import struct
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TurnPrediction:
    """Result of turn-taking analysis on an audio chunk."""
    is_speech: bool           # VAD: is there speech in this chunk?
    eot_probability: float    # Heuristic EoT probability (0.0–1.0)
    predictive_eot: float     # Predictive/ML EoT probability (0.0–1.0)
    should_ai_speak: bool     # Combined decision: should AI take the floor?

    @property
    def combined_eot(self) -> float:
        """Blend heuristic and predictive scores. Heuristic has veto power."""
        # If silence is below minimum, never trigger
        if self.eot_probability < 0.3:
            return 0.0
        # Blend: heuristic-weighted (reliable) + predictive (when available)
        if self.predictive_eot > 0.0:
            return 0.6 * self.eot_probability + 0.4 * self.predictive_eot
        return self.eot_probability


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


def _rms_energy_pcm16(audio_bytes: bytes) -> float:
    """
    Compute RMS energy from PCM16 audio bytes.
    PCM16: signed 16-bit little-endian integers, range [-32768, 32767].
    Returns normalized RMS in [0.0, 1.0].
    """
    if len(audio_bytes) < 2:
        return 0.0

    num_samples = len(audio_bytes) // 2
    samples = struct.unpack(f"<{num_samples}h", audio_bytes[:num_samples * 2])

    sum_sq = sum(s * s for s in samples)
    rms = (sum_sq / num_samples) ** 0.5

    # Normalize: max PCM16 value is 32768
    return min(rms / 32768.0, 1.0)


class HybridTurnTakingService(TurnTakingService):
    """
    Hybrid turn-taking: heuristic energy-based VAD + adaptive endpointing.

    Optionally enhanced by Silero VAD if available (installed separately).
    Falls back gracefully to energy-only if Silero is not installed.
    """

    # Energy thresholds (normalized RMS) with hysteresis to reduce flicker.
    SPEECH_START_THRESHOLD = 0.012
    SPEECH_STOP_THRESHOLD = 0.007
    SILERO_SPEECH_THRESHOLD = 0.5

    # Adaptive silence thresholds in milliseconds (time-based, not frame-based).
    SHORT_UTTERANCE_SILENCE_MS = 800
    LONG_UTTERANCE_SILENCE_MS = 1500
    SHORT_UTTERANCE_WORDS = 5      # Threshold for "short" utterance

    # ~150 WPM -> 2.5 words/second
    WORDS_PER_SECOND = 2.5
    MIN_SPEECH_MS = 300.0

    def __init__(self):
        self._silence_frames: int = 0
        self._speech_frames: int = 0
        self._silence_ms: float = 0.0
        self._speech_ms: float = 0.0
        self._estimated_words: float = 0.0
        self._energy_speech_active: bool = False
        self._silero_vad = None
        self._has_silero: bool = False

        # Try loading Silero VAD (optional dependency)
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self._silero_vad = model
            self._silero_get_speech_timestamps = utils[0]
            self._has_silero = True
            logger.info("[TurnTaking] Silero VAD loaded successfully")
        except Exception as e:
            logger.info(f"[TurnTaking] Silero VAD not available, using energy-only: {e}")

    @property
    def _silence_threshold_ms(self) -> int:
        """Adaptive threshold: shorter silence for short utterances."""
        if self._estimated_words < self.SHORT_UTTERANCE_WORDS:
            return self.SHORT_UTTERANCE_SILENCE_MS
        return self.LONG_UTTERANCE_SILENCE_MS

    @property
    def _silence_threshold(self) -> int:
        """Compatibility alias retained for existing logs/tests."""
        return self._silence_threshold_ms

    async def analyze_chunk(self, audio_bytes: bytes, sample_rate: int = 16000) -> TurnPrediction:
        if sample_rate < 8000 or sample_rate > 48000:
            sample_rate = 16000

        num_samples = len(audio_bytes) // 2
        chunk_duration_ms = (num_samples / sample_rate) * 1000.0 if num_samples else 0.0

        # ── 1. Heuristic: PCM16 RMS energy ──
        energy = _rms_energy_pcm16(audio_bytes)
        if self._energy_speech_active:
            is_speech_energy = energy > self.SPEECH_STOP_THRESHOLD
        else:
            is_speech_energy = energy > self.SPEECH_START_THRESHOLD

        # ── 2. Predictive: Silero VAD (if available) ──
        silero_prob = 0.0
        if self._has_silero and self._silero_vad is not None:
            try:
                import torch
                import time
                t_vad_start = time.time()
                num_samples = len(audio_bytes) // 2
                samples = struct.unpack(f"<{num_samples}h", audio_bytes[:num_samples * 2])
                tensor = torch.FloatTensor(samples) / 32768.0
                silero_prob = float(self._silero_vad(tensor, sample_rate))
                t_vad_dur = time.time() - t_vad_start
                if t_vad_dur > 0.05:
                    logger.warning(f"[Perf] Silero VAD took {t_vad_dur:.3f}s")
            except Exception:
                silero_prob = 0.0

        # ── 3. Combined speech detection ──
        is_speech = is_speech_energy or silero_prob > self.SILERO_SPEECH_THRESHOLD
        self._energy_speech_active = is_speech

        # ── 4. Update state ──
        if is_speech:
            self._speech_frames += 1
            self._speech_ms += chunk_duration_ms
            self._silence_frames = 0
            self._silence_ms = 0.0
            self._estimated_words += self.WORDS_PER_SECOND * (chunk_duration_ms / 1000.0)
        else:
            self._silence_frames += 1
            self._silence_ms += chunk_duration_ms

        # ── 5. Heuristic EoT: silence duration relative to adaptive threshold ──
        eot_prob = min(self._silence_ms / max(self._silence_threshold_ms, 1), 1.0)

        predictive_eot = 0.0
        # Silero outputs P(speech). For EoT, invert to P(non-speech).
        if not is_speech and self._has_silero:
            predictive_eot = max(0.0, min(1.0, 1.0 - silero_prob))

        # ── 6. Combined decision ──
        combined = TurnPrediction(
            is_speech=is_speech,
            eot_probability=eot_prob,
            predictive_eot=predictive_eot,
            should_ai_speak=False,
        )

        # Trigger only when silence confidence is high and enough prior speech exists.
        should_speak = combined.combined_eot > 0.8 and self._speech_ms >= self.MIN_SPEECH_MS
        combined.should_ai_speak = should_speak

        return combined

    async def reset(self) -> None:
        self._silence_frames = 0
        self._speech_frames = 0
        self._silence_ms = 0.0
        self._speech_ms = 0.0
        self._estimated_words = 0.0
        self._energy_speech_active = False
        # Reset Silero VAD state if available
        if self._has_silero and self._silero_vad is not None:
            try:
                self._silero_vad.reset_states()
            except Exception:
                pass


def get_turn_taking_service() -> TurnTakingService:
    """Factory: returns turn-taking service."""
    return HybridTurnTakingService()
