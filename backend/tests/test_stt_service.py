"""
Unit Tests: STT Service — hallucination filter, BatchSTTService sequencing,
flush completeness, and factory routing.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.app.services.stt_service import (
    _filter_hallucination,
    BatchSTTService,
    DeepgramSTTService,
    GroqSTTService,
    LocalSTTService,
    get_stt_service,
)


# ═══════════════════════════════════════════════════════════
# Hallucination Filter
# ═══════════════════════════════════════════════════════════


class TestHallucinationFilter:
    """Verifies the hallucination filter blocks phantom phrases but passes real speech."""

    def test_blocks_whisper_phantoms(self):
        """Known Whisper phantom outputs should be blocked."""
        assert _filter_hallucination("my teeth") is None
        # With or without trailing punctuation, these should be blocked
        assert _filter_hallucination("one, two, three, go.") is None
        assert _filter_hallucination("one, two, three, go") is None
        assert _filter_hallucination("that is my life.") is None
        assert _filter_hallucination("That is my life") is None
        assert _filter_hallucination("it's time to present.") is None
        assert _filter_hallucination("...") is None
        assert _filter_hallucination("…") is None

    def test_blocks_filler_sounds(self):
        """Pure filler sounds (not words) should be blocked."""
        assert _filter_hallucination("um") is None
        assert _filter_hallucination("uh") is None
        assert _filter_hallucination("hmm") is None
        assert _filter_hallucination("er") is None

    def test_passes_real_debate_words(self):
        """Real speech words must NOT be blocked."""
        assert _filter_hallucination("yes") == "yes"
        assert _filter_hallucination("no") == "no"
        assert _filter_hallucination("okay") == "okay"
        assert _filter_hallucination("so") == "so"
        assert _filter_hallucination("right") == "right"
        assert _filter_hallucination("well") == "well"
        assert _filter_hallucination("you know") == "you know"
        assert _filter_hallucination("I mean") == "I mean"
        assert _filter_hallucination("thank you") == "thank you"

    def test_passes_real_sentences(self):
        """Normal debate transcriptions should pass through."""
        assert _filter_hallucination("I believe climate change is real") == "I believe climate change is real"
        assert _filter_hallucination("No, that's wrong because") == "No, that's wrong because"

    def test_blocks_empty_and_tiny(self):
        """Empty and single-char strings should be blocked."""
        assert _filter_hallucination("") is None
        assert _filter_hallucination(" ") is None
        assert _filter_hallucination("a") is None

    def test_strips_whitespace(self):
        """Output should be stripped of leading/trailing whitespace."""
        assert _filter_hallucination("  hello world  ") == "hello world"


# ═══════════════════════════════════════════════════════════
# BatchSTTService — Sequencing & Flush
# ═══════════════════════════════════════════════════════════


class MockBatchSTT(BatchSTTService):
    """Concrete subclass for testing the base class logic."""

    BUFFER_THRESHOLD = 100  # Small threshold for testing

    def __init__(self, responses: list[str | None] = None, delays: list[float] = None):
        super().__init__()
        self._responses = responses or []
        self._delays = delays or []
        self._call_count = 0

    async def _transcribe_pcm(self, pcm_bytes: bytes) -> str | None:
        idx = self._call_count
        self._call_count += 1
        if idx < len(self._delays):
            await asyncio.sleep(self._delays[idx])
        if idx < len(self._responses):
            return self._responses[idx]
        return f"chunk-{idx}"

    async def transcribe_batch(self, audio_bytes: bytes) -> str:
        return "batch result"


class TestBatchSTTServiceSequencing:
    """Verifies that results come back in submission order even with variable latencies."""

    @pytest.mark.asyncio
    async def test_results_arrive_in_order(self):
        """Even if later chunks finish first, results should be in submission order."""
        # chunk 0 takes 0.3s, chunk 1 takes 0.05s, chunk 2 takes 0.1s
        stt = MockBatchSTT(
            responses=["first", "second", "third"],
            delays=[0.3, 0.05, 0.1],
        )

        # Submit 3 chunks that each exceed the buffer threshold
        await stt.transcribe_chunk(b"\x00" * 100)
        await stt.transcribe_chunk(b"\x00" * 100)
        await stt.transcribe_chunk(b"\x00" * 100)

        # Wait for all tasks to complete
        await asyncio.sleep(0.5)

        results = []
        while True:
            r = await stt.get_result()
            if r is None:
                break
            results.append(r["text"])

        assert results == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_flush_does_not_drop_small_buffers(self):
        """flush() should transcribe any remaining audio, even tiny amounts."""
        stt = MockBatchSTT(responses=["final word"])

        # Add less than BUFFER_THRESHOLD bytes
        await stt.transcribe_chunk(b"\x00" * 50)

        # Flush should still transcribe it
        result = await stt.flush()
        assert result is not None
        assert "final word" in result["text"]

    @pytest.mark.asyncio
    async def test_flush_collects_pending_results(self):
        """flush() should wait for in-flight tasks and return all results."""
        stt = MockBatchSTT(
            responses=["part one", "part two"],
            delays=[0.1, 0.1],
        )

        # Submit one full chunk
        await stt.transcribe_chunk(b"\x00" * 100)
        # Add a partial buffer
        await stt.transcribe_chunk(b"\x00" * 50)

        # Flush: should transcribe partial + wait for in-flight
        result = await stt.flush()
        assert result is not None
        assert "part one" in result["text"]
        assert "part two" in result["text"]

    @pytest.mark.asyncio
    async def test_close_cancels_tasks(self):
        """close() should cancel all pending tasks without errors."""
        stt = MockBatchSTT(
            responses=["slow"],
            delays=[5.0],  # Very slow task
        )

        # Start a chunk that fires a slow background task
        await stt.transcribe_chunk(b"\x00" * 100)

        # Should not hang — close cancels the slow task
        await asyncio.wait_for(stt.close(), timeout=2.0)

    @pytest.mark.asyncio
    async def test_get_full_transcript(self):
        """Full transcript should accumulate across chunks."""
        stt = MockBatchSTT(responses=["hello world", "foo bar"])
        await stt.transcribe_chunk(b"\x00" * 100)
        await stt.transcribe_chunk(b"\x00" * 100)
        await asyncio.sleep(0.1)
        assert "hello world" in stt.get_full_transcript()
        assert "foo bar" in stt.get_full_transcript()


# ═══════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════


class TestSTTFactory:
    """Verifies get_stt_service returns the correct provider."""

    @patch("backend.app.services.stt_service.get_settings")
    def test_cloud_deepgram_with_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            stt_provider="deepgram",
            deepgram_api_key="test-key",
        )
        service = get_stt_service("cloud")
        assert isinstance(service, DeepgramSTTService)

    @patch("backend.app.services.stt_service.get_settings")
    def test_cloud_deepgram_without_key_falls_back_to_groq(self, mock_settings):
        mock_settings.return_value = MagicMock(
            stt_provider="deepgram",
            deepgram_api_key="",
            groq_api_key="test",
            groq_base_url="https://api.groq.com/openai/v1",
        )
        try:
            service = get_stt_service("cloud")
            assert isinstance(service, GroqSTTService)
        except ImportError:
            pytest.skip("openai not available in test environment")

    @patch("backend.app.services.stt_service.get_settings")
    def test_cloud_groq(self, mock_settings):
        mock_settings.return_value = MagicMock(
            stt_provider="groq",
            groq_api_key="test",
            groq_base_url="https://api.groq.com/openai/v1",
        )
        try:
            service = get_stt_service("cloud")
            assert isinstance(service, GroqSTTService)
        except ImportError:
            pytest.skip("openai not available in test environment")

    @patch("backend.app.services.stt_service.get_settings")
    def test_edge_mode(self, mock_settings):
        """Edge mode should try to return LocalSTTService."""
        mock_settings.return_value = MagicMock(
            faster_whisper_model="base",
        )
        try:
            service = get_stt_service("edge")
            assert isinstance(service, LocalSTTService)
        except (ImportError, Exception):
            pytest.skip("faster-whisper not available in test environment")
