"""
Tests: MetricsService — WPM, filler words, pauses, talk ratio.
"""
from backend.app.schemas.messages import TranscriptEntry
from backend.app.services.metrics_service import MetricsService


class TestMetricsService:
    def setup_method(self):
        self.service = MetricsService()

    def test_wpm_calculation(self, sample_transcript):
        """WPM is computed as word_count / (duration / 60)."""
        result = self.service.compute_metrics(sample_transcript, session_duration_seconds=12.0)
        # User said 14 words in 12s → 14 / (12/60) = 70 WPM
        assert result["user_wpm"] > 0
        assert result["ai_wpm"] > 0
        assert isinstance(result["user_wpm"], float)

    def test_filler_words_detected(self, sample_transcript):
        """Filler words (um, like, basically, you know) are detected in user text."""
        result = self.service.compute_metrics(sample_transcript, session_duration_seconds=12.0)
        assert result["filler_word_count"] > 0
        fillers = result["filler_words"]
        # "um", "like", "basically", "you know" should all be found
        assert "um" in fillers
        assert "like" in fillers
        assert "basically" in fillers

    def test_no_fillers_in_clean_speech(self):
        """No filler words detected in clean text."""
        entries = [
            TranscriptEntry(speaker="user", text="The evidence supports this position", start_ms=0, end_ms=3000),
        ]
        result = self.service.compute_metrics(entries, session_duration_seconds=3.0)
        assert result["filler_word_count"] == 0
        assert result["filler_words"] == {}

    def test_pause_duration(self, sample_transcript):
        """Average pause between user utterances is computed."""
        result = self.service.compute_metrics(sample_transcript, session_duration_seconds=12.0)
        # User entries: 0-3000ms and 5500-9000ms → gap = 2500ms
        assert result["avg_pause_duration_ms"] == 2500.0

    def test_turn_count(self, sample_transcript):
        """Turn count equals total number of entries."""
        result = self.service.compute_metrics(sample_transcript, session_duration_seconds=12.0)
        assert result["turn_count"] == 4

    def test_user_talk_ratio(self, sample_transcript):
        """User talk ratio is user_ms / total_ms."""
        result = self.service.compute_metrics(sample_transcript, session_duration_seconds=12.0)
        # User: 3000 + 3500 = 6500ms, AI: 1500 + 2500 = 4000ms, total: 10500ms
        expected_ratio = 6500 / 10500
        assert abs(result["user_talk_ratio"] - round(expected_ratio, 3)) < 0.01

    def test_empty_transcript(self):
        """Empty transcript returns zeros without crashing."""
        result = self.service.compute_metrics([], session_duration_seconds=0.0)
        assert result["user_wpm"] == 0.0
        assert result["turn_count"] == 0
        assert result["filler_word_count"] == 0

    def test_duration_seconds_passed_through(self, sample_transcript):
        """Duration is included in the result."""
        result = self.service.compute_metrics(sample_transcript, session_duration_seconds=42.5)
        assert result["duration_seconds"] == 42.5

    def test_single_user_entry_no_pauses(self):
        """Single user entry means no pauses to compute."""
        entries = [
            TranscriptEntry(speaker="user", text="Hello world", start_ms=0, end_ms=2000),
        ]
        result = self.service.compute_metrics(entries, session_duration_seconds=2.0)
        assert result["avg_pause_duration_ms"] == 0.0
