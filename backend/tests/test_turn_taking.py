"""
Tests: HybridTurnTakingService — RMS energy, silence tracking, adaptive endpointing.
"""
import struct
import pytest
from backend.app.services.turn_taking_service import (
    HybridTurnTakingService,
    TurnPrediction,
    _rms_energy_pcm16,
)


class TestRmsEnergy:
    def test_silence_has_zero_energy(self, silence_audio):
        """Pure silence (all zeros) should return 0.0 RMS energy."""
        assert _rms_energy_pcm16(silence_audio) == 0.0

    def test_loud_audio_has_high_energy(self, loud_audio):
        """Half-amplitude square wave should have ~0.5 RMS energy."""
        energy = _rms_energy_pcm16(loud_audio)
        assert 0.4 < energy < 0.6

    def test_empty_audio_returns_zero(self):
        """Empty bytes or single byte returns 0.0."""
        assert _rms_energy_pcm16(b"") == 0.0
        assert _rms_energy_pcm16(b"\x00") == 0.0

    def test_max_amplitude_returns_one(self):
        """Full amplitude PCM16 should return ~1.0."""
        # 100 samples of max positive amplitude
        audio = struct.pack(f"<{100}h", *([32767] * 100))
        energy = _rms_energy_pcm16(audio)
        assert energy > 0.99

    def test_energy_is_normalized(self, loud_audio):
        """Result is always in [0.0, 1.0]."""
        energy = _rms_energy_pcm16(loud_audio)
        assert 0.0 <= energy <= 1.0


class TestHybridTurnTaking:
    @pytest.fixture
    def service(self):
        """Create service without Silero VAD (energy-only mode)."""
        svc = HybridTurnTakingService()
        svc._has_silero = False
        svc._silero_vad = None
        return svc

    @pytest.mark.asyncio
    async def test_silence_increments_silence_frames(self, service, silence_audio):
        """Silence chunks increment the silence frame counter."""
        await service.analyze_chunk(silence_audio)
        assert service._silence_frames == 1

    @pytest.mark.asyncio
    async def test_speech_resets_silence_counter(self, service, loud_audio, silence_audio):
        """Speech after silence resets silence counter to 0."""
        await service.analyze_chunk(silence_audio)
        await service.analyze_chunk(silence_audio)
        assert service._silence_frames == 2

        await service.analyze_chunk(loud_audio)
        assert service._silence_frames == 0
        assert service._speech_frames == 1

    @pytest.mark.asyncio
    async def test_speech_detected_for_loud_audio(self, service, loud_audio):
        """Loud audio is detected as speech."""
        prediction = await service.analyze_chunk(loud_audio)
        assert prediction.is_speech is True

    @pytest.mark.asyncio
    async def test_silence_not_detected_as_speech(self, service, silence_audio):
        """Silence is not detected as speech."""
        prediction = await service.analyze_chunk(silence_audio)
        assert prediction.is_speech is False

    @pytest.mark.asyncio
    async def test_eot_probability_increases_with_silence(self, service, silence_audio, loud_audio):
        """EoT probability increases with consecutive silence chunks."""
        # First, have some speech so eot can trigger
        for _ in range(5):
            await service.analyze_chunk(loud_audio)

        p1 = await service.analyze_chunk(silence_audio)
        p2 = await service.analyze_chunk(silence_audio)
        assert p2.eot_probability > p1.eot_probability

    @pytest.mark.asyncio
    async def test_adaptive_short_utterance_threshold(self, service, loud_audio, silence_audio):
        """Short utterances (<5 words estimated) use 800ms (8 chunk) threshold."""
        # Simulate 2 speech chunks (< 5 estimated words)
        await service.analyze_chunk(loud_audio)
        await service.analyze_chunk(loud_audio)
        assert service._estimated_words < 5
        assert service._silence_threshold == 8

    @pytest.mark.asyncio
    async def test_adaptive_long_utterance_threshold(self, service, loud_audio):
        """Long utterances (≥5 words estimated) use 1.5s (15 chunk) threshold."""
        # Simulate many speech chunks to accumulate words
        for _ in range(25):
            await service.analyze_chunk(loud_audio)
        assert service._estimated_words >= 5
        assert service._silence_threshold == 15

    @pytest.mark.asyncio
    async def test_should_ai_speak_after_enough_silence(self, service, loud_audio, silence_audio):
        """AI should speak after sustained silence following speech."""
        # Generate speech
        for _ in range(5):
            await service.analyze_chunk(loud_audio)

        # Then enough silence to trigger
        prediction = None
        for _ in range(20):
            prediction = await service.analyze_chunk(silence_audio)

        assert prediction is not None
        assert prediction.should_ai_speak is True

    @pytest.mark.asyncio
    async def test_no_trigger_without_prior_speech(self, service, silence_audio):
        """AI should NOT speak if there was no prior speech (just silence)."""
        for _ in range(20):
            prediction = await service.analyze_chunk(silence_audio)

        assert prediction.should_ai_speak is False

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, service, loud_audio):
        """Reset clears all internal counters."""
        for _ in range(5):
            await service.analyze_chunk(loud_audio)
        assert service._speech_frames > 0

        await service.reset()
        assert service._speech_frames == 0
        assert service._silence_frames == 0
        assert service._estimated_words == 0


class TestTurnPrediction:
    def test_combined_eot_veto_below_threshold(self):
        """Heuristic EoT < 0.3 vetoes all predictions."""
        p = TurnPrediction(is_speech=False, eot_probability=0.2, predictive_eot=0.9, should_ai_speak=False)
        assert p.combined_eot == 0.0

    def test_combined_eot_heuristic_only(self):
        """When no predictive score, combined equals heuristic."""
        p = TurnPrediction(is_speech=False, eot_probability=0.8, predictive_eot=0.0, should_ai_speak=False)
        assert p.combined_eot == 0.8

    def test_combined_eot_blended(self):
        """Combined blends 60% heuristic + 40% predictive."""
        p = TurnPrediction(is_speech=False, eot_probability=0.8, predictive_eot=0.6, should_ai_speak=False)
        expected = 0.6 * 0.8 + 0.4 * 0.6  # 0.48 + 0.24 = 0.72
        assert abs(p.combined_eot - expected) < 0.01
