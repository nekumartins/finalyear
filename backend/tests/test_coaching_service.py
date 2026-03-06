"""
Tests: CoachingService — AI coaching report generation.

Covers the feature added in commit 2d80c3f:
  - Transcript formatting
  - Coaching-goal prompt selection
  - System prompt assembly
  - JSON parsing & validation (valid / malformed / missing fields)
  - Score clamping (boundaries)
  - Retry logic on JSON parse errors and rate limits
  - Graceful failure (returns None, doesn't crash)
"""
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.schemas.messages import TranscriptEntry
from backend.app.services.coaching_service import (
    CoachingService,
    COACHING_GOAL_PROMPTS,
    COACHING_SYSTEM_PROMPT,
    _format_transcript,
)


# ─── Fixtures ────────────────────────────────────────────────

VALID_REPORT = {
    "overall_score": 72,
    "argument_quality": 7,
    "strengths": ["Clear opening thesis", "Good use of evidence"],
    "improvements": ["Lacked rebuttal evidence", "Needs better transitions"],
    "fallacies": ["Straw man in turn 4"],
    "tips": ["Try the Toulmin model for structuring arguments"],
    "summary": "You showed strong conviction but need more evidence.",
}


@pytest.fixture
def sample_transcript() -> list[TranscriptEntry]:
    return [
        TranscriptEntry(speaker="user", text="I believe renewable energy is the future", start_ms=0, end_ms=3000),
        TranscriptEntry(speaker="ai", text="But what about reliability issues", start_ms=3500, end_ms=5000),
        TranscriptEntry(speaker="user", text="Solar and wind have improved storage", start_ms=5500, end_ms=8000),
        TranscriptEntry(speaker="ai", text="Nuclear is more reliable", start_ms=8500, end_ms=10000),
    ]


@pytest.fixture
def sample_metrics() -> dict:
    return {
        "duration_seconds": 10.0,
        "user_wpm": 120.0,
        "filler_word_count": 3,
        "filler_words": {"um": 2, "like": 1},
        "turn_count": 4,
        "user_talk_ratio": 0.55,
        "avg_pause_duration_ms": 500.0,
    }


def _mock_llm_response(content: str) -> MagicMock:
    """Build a mock OpenAI ChatCompletion response."""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ─── _format_transcript ─────────────────────────────────────

class TestFormatTranscript:
    def test_formats_user_and_ai(self, sample_transcript):
        result = _format_transcript(sample_transcript)
        assert "[USER]:" in result
        assert "[AI]:" in result
        assert "renewable energy" in result

    def test_empty_transcript(self):
        assert _format_transcript([]) == "(empty transcript)"

    def test_speaker_labels_correct(self):
        entries = [
            TranscriptEntry(speaker="user", text="Hello", start_ms=0, end_ms=1000),
            TranscriptEntry(speaker="ai", text="Hi there", start_ms=1000, end_ms=2000),
        ]
        result = _format_transcript(entries)
        lines = result.strip().split("\n")
        assert lines[0].startswith("[USER]:")
        assert lines[1].startswith("[AI]:")


# ─── Coaching Goal Prompts ────────────────────────────────────

class TestCoachingGoalPrompts:
    def test_all_three_goals_defined(self):
        assert set(COACHING_GOAL_PROMPTS.keys()) == {"confidence", "speed", "structure"}

    def test_confidence_prompt_mentions_key_themes(self):
        prompt = COACHING_GOAL_PROMPTS["confidence"]
        assert "CONFIDENCE" in prompt
        assert "assertive" in prompt.lower()

    def test_speed_prompt_mentions_key_themes(self):
        prompt = COACHING_GOAL_PROMPTS["speed"]
        assert "PACING" in prompt
        assert "filler" in prompt.lower()

    def test_structure_prompt_mentions_key_themes(self):
        prompt = COACHING_GOAL_PROMPTS["structure"]
        assert "STRUCTURE" in prompt
        assert "evidence" in prompt.lower()


# ─── CoachingService.generate_report — happy path ────────────

class TestGenerateReportSuccess:
    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.service = CoachingService.__new__(CoachingService)
        self.service.client = AsyncMock()
        self.service.model = "llama-3.3-70b-versatile"
        self.service.MAX_RETRIES = 2
        self.service.RETRY_DELAY_S = 0.01  # fast retries for tests

    async def test_returns_valid_report(self, sample_transcript, sample_metrics):
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(VALID_REPORT))
        )
        report = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="Renewable energy", user_position="for",
            coaching_goal="confidence",
        )
        assert report is not None
        assert report["overall_score"] == 72
        assert report["argument_quality"] == 7
        assert len(report["strengths"]) == 2
        assert len(report["tips"]) >= 1

    async def test_strips_markdown_fences(self, sample_transcript, sample_metrics):
        fenced = f"```json\n{json.dumps(VALID_REPORT)}\n```"
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(fenced)
        )
        report = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="AI ethics", user_position="against",
        )
        assert report is not None
        assert report["overall_score"] == 72

    async def test_fallback_goal_uses_confidence(self, sample_transcript, sample_metrics):
        """Unknown coaching goal falls back to 'confidence' prompt."""
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(VALID_REPORT))
        )
        report = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="Topic", user_position="for",
            coaching_goal="nonexistent_goal",
        )
        assert report is not None

    async def test_calls_llm_with_correct_model(self, sample_transcript, sample_metrics):
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(VALID_REPORT))
        )
        await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="Topic", user_position="for",
        )
        call_kwargs = self.service.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "llama-3.3-70b-versatile"
        assert call_kwargs["temperature"] == 0.4
        assert call_kwargs["max_tokens"] == 600


# ─── Score clamping ──────────────────────────────────────────

class TestScoreClamping:
    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.service = CoachingService.__new__(CoachingService)
        self.service.client = AsyncMock()
        self.service.model = "test"
        self.service.MAX_RETRIES = 0
        self.service.RETRY_DELAY_S = 0.01

    async def test_clamps_score_above_100(self, sample_transcript, sample_metrics):
        report = {**VALID_REPORT, "overall_score": 150, "argument_quality": 12}
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(report))
        )
        result = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        assert result["overall_score"] == 100
        assert result["argument_quality"] == 10

    async def test_clamps_score_below_0(self, sample_transcript, sample_metrics):
        report = {**VALID_REPORT, "overall_score": -5, "argument_quality": 0}
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(report))
        )
        result = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        assert result["overall_score"] == 0
        assert result["argument_quality"] == 1

    async def test_edge_scores_untouched(self, sample_transcript, sample_metrics):
        report = {**VALID_REPORT, "overall_score": 0, "argument_quality": 1}
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(report))
        )
        result = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        assert result["overall_score"] == 0
        assert result["argument_quality"] == 1


# ─── Missing fields → defaults filled in ─────────────────────

class TestMissingFieldDefaults:
    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.service = CoachingService.__new__(CoachingService)
        self.service.client = AsyncMock()
        self.service.model = "test"
        self.service.MAX_RETRIES = 0
        self.service.RETRY_DELAY_S = 0.01

    async def test_missing_fields_get_defaults(self, sample_transcript, sample_metrics):
        partial = {"overall_score": 60, "summary": "Decent job."}
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(partial))
        )
        result = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        assert result is not None
        assert result["overall_score"] == 60
        assert result["argument_quality"] == 5  # default
        assert result["strengths"] == []  # default
        assert result["improvements"] == []
        assert result["fallacies"] == []
        assert result["tips"] == []


# ─── Retry logic ─────────────────────────────────────────────

class TestRetryLogic:
    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.service = CoachingService.__new__(CoachingService)
        self.service.client = AsyncMock()
        self.service.model = "test"
        self.service.MAX_RETRIES = 2
        self.service.RETRY_DELAY_S = 0.01

    async def test_retries_on_json_parse_error_then_succeeds(
        self, sample_transcript, sample_metrics
    ):
        bad_resp = _mock_llm_response("not valid json {{{")
        good_resp = _mock_llm_response(json.dumps(VALID_REPORT))
        self.service.client.chat.completions.create = AsyncMock(
            side_effect=[bad_resp, good_resp]
        )
        result = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        assert result is not None
        assert result["overall_score"] == 72
        assert self.service.client.chat.completions.create.call_count == 2

    async def test_retries_on_rate_limit_then_succeeds(
        self, sample_transcript, sample_metrics
    ):
        rate_limit_err = Exception("429 rate_limit_exceeded")
        good_resp = _mock_llm_response(json.dumps(VALID_REPORT))
        self.service.client.chat.completions.create = AsyncMock(
            side_effect=[rate_limit_err, good_resp]
        )
        result = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        assert result is not None
        assert self.service.client.chat.completions.create.call_count == 2

    async def test_all_retries_exhausted_returns_none(
        self, sample_transcript, sample_metrics
    ):
        bad_resp = _mock_llm_response("broken json")
        self.service.client.chat.completions.create = AsyncMock(
            return_value=bad_resp
        )
        result = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        assert result is None
        assert self.service.client.chat.completions.create.call_count == 3  # 1 + 2 retries


# ─── Non-retryable errors ───────────────────────────────────

class TestNonRetryableErrors:
    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.service = CoachingService.__new__(CoachingService)
        self.service.client = AsyncMock()
        self.service.model = "test"
        self.service.MAX_RETRIES = 2
        self.service.RETRY_DELAY_S = 0.01

    async def test_api_error_returns_none_immediately(
        self, sample_transcript, sample_metrics
    ):
        self.service.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        result = await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        assert result is None
        # Non-retryable → only 1 call, no retries
        assert self.service.client.chat.completions.create.call_count == 1


# ─── System prompt assembly ──────────────────────────────────

class TestPromptAssembly:
    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.service = CoachingService.__new__(CoachingService)
        self.service.client = AsyncMock()
        self.service.model = "test"
        self.service.MAX_RETRIES = 0
        self.service.RETRY_DELAY_S = 0.01

    async def test_prompt_includes_topic_and_position(
        self, sample_transcript, sample_metrics
    ):
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(VALID_REPORT))
        )
        await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="Space exploration", user_position="against",
            coaching_goal="structure",
        )
        call_args = self.service.client.chat.completions.create.call_args[1]
        system_msg = call_args["messages"][0]["content"]
        assert "Space exploration" in system_msg
        assert "against" in system_msg
        assert "STRUCTURE" in system_msg

    async def test_prompt_includes_metrics(
        self, sample_transcript, sample_metrics
    ):
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(VALID_REPORT))
        )
        await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        call_args = self.service.client.chat.completions.create.call_args[1]
        system_msg = call_args["messages"][0]["content"]
        assert "120" in system_msg  # user_wpm
        assert "4" in system_msg  # turn_count

    async def test_prompt_includes_filler_words(
        self, sample_transcript, sample_metrics
    ):
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(VALID_REPORT))
        )
        await self.service.generate_report(
            sample_transcript, sample_metrics,
            topic="T", user_position="for",
        )
        call_args = self.service.client.chat.completions.create.call_args[1]
        system_msg = call_args["messages"][0]["content"]
        assert '"um"' in system_msg
        assert '"like"' in system_msg

    async def test_empty_filler_words_shows_none(
        self, sample_transcript
    ):
        metrics = {"duration_seconds": 5, "user_wpm": 100,
                   "filler_word_count": 0, "filler_words": {},
                   "turn_count": 2, "user_talk_ratio": 0.5,
                   "avg_pause_duration_ms": 300}
        self.service.client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response(json.dumps(VALID_REPORT))
        )
        await self.service.generate_report(
            sample_transcript, metrics,
            topic="T", user_position="for",
        )
        call_args = self.service.client.chat.completions.create.call_args[1]
        system_msg = call_args["messages"][0]["content"]
        assert "none" in system_msg
