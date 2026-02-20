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

    # Energy thresholds (normalized RMS)
    SPEECH_THRESHOLD = 0.03        # Above this = speech detected (raised to reduce noise triggers)
    SILENCE_NOISE_FLOOR = 0.005    # Below this = definitely silence

    # Adaptive silence thresholds (number of chunks at 100ms each)
    SHORT_UTTERANCE_SILENCE = 12   # 1.2s for short utterances (raised from 800ms)
    LONG_UTTERANCE_SILENCE = 20    # 2.0s for longer arguments (raised from 1.5s)
    SHORT_UTTERANCE_WORDS = 5      # Threshold for "short" utterance

    # Estimated words per ~2s of audio (assuming ~150 WPM)
    WORDS_PER_CHUNK = 0.25  # rough estimate: 150 WPM / 60 / 10 chunks per second

    def __init__(self):
        self._silence_frames: int = 0
        self._speech_frames: int = 0
        self._estimated_words: int = 0
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
    def _silence_threshold(self) -> int:
        """Adaptive threshold: shorter silence for short utterances."""
        if self._estimated_words < self.SHORT_UTTERANCE_WORDS:
            return self.SHORT_UTTERANCE_SILENCE
        return self.LONG_UTTERANCE_SILENCE

    async def analyze_chunk(self, audio_bytes: bytes, sample_rate: int = 16000) -> TurnPrediction:
        # ── 1. Heuristic: PCM16 RMS energy ──
        energy = _rms_energy_pcm16(audio_bytes)
        is_speech_energy = energy > self.SPEECH_THRESHOLD

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
        is_speech = is_speech_energy or silero_prob > 0.5

        # ── 4. Update state ──
        if is_speech:
            self._speech_frames += 1
            self._silence_frames = 0
            self._estimated_words += self.WORDS_PER_CHUNK
        else:
            self._silence_frames += 1

        # ── 5. Heuristic EoT: silence duration relative to adaptive threshold ──
        eot_prob = min(self._silence_frames / max(self._silence_threshold, 1), 1.0)

        # ── 6. Combined decision ──
        combined = TurnPrediction(
            is_speech=is_speech,
            eot_probability=eot_prob,
            predictive_eot=silero_prob if not is_speech else 0.0,
            should_ai_speak=False,
        )

        # Only trigger if combined score is high enough AND we've heard some speech
        should_speak = combined.combined_eot > 0.8 and self._speech_frames > 5
        combined.should_ai_speak = should_speak

        return combined

    async def reset(self) -> None:
        self._silence_frames = 0
        self._speech_frames = 0
        self._estimated_words = 0
        # Reset Silero VAD state if available
        if self._has_silero and self._silero_vad is not None:
            try:
                self._silero_vad.reset_states()
            except Exception:
                pass


def get_turn_taking_service() -> TurnTakingService:
    """Factory: returns turn-taking service."""
    return HybridTurnTakingService()
