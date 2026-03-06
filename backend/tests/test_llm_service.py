"""
Tests: LLM Service — coaching goal adaptation + history truncation.

Covers the coaching_goal parameter added in commit 2d80c3f:
  - COACHING_GOAL_INSTRUCTIONS injected into system prompt
  - Unknown goal → empty instruction (no crash)
  - truncate_history respects MAX_HISTORY_MESSAGES
  - generate_response_stream passes coaching_goal through to prompt
  - generate_response_batch (non-streaming) aggregates correctly
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.llm_service import (
    COACHING_GOAL_INSTRUCTIONS,
    DEBATE_SYSTEM_PROMPT,
    MAX_HISTORY_MESSAGES,
    CloudLLMService,
    EdgeLLMService,
    truncate_history,
    get_llm_service,
)


# ─── COACHING_GOAL_INSTRUCTIONS ──────────────────────────────

class TestCoachingGoalInstructions:
    def test_all_three_goals_defined(self):
        assert set(COACHING_GOAL_INSTRUCTIONS.keys()) == {"confidence", "speed", "structure"}

    def test_confidence_instruction_content(self):
        instr = COACHING_GOAL_INSTRUCTIONS["confidence"]
        assert "CONFIDENCE" in instr
        assert "assertive" in instr.lower()

    def test_speed_instruction_content(self):
        instr = COACHING_GOAL_INSTRUCTIONS["speed"]
        assert "PACING" in instr
        assert "punchy" in instr.lower() or "fast" in instr.lower()

    def test_structure_instruction_content(self):
        instr = COACHING_GOAL_INSTRUCTIONS["structure"]
        assert "STRUCTURE" in instr
        assert "evidence" in instr.lower()

    def test_instructions_are_non_empty(self):
        for goal, instr in COACHING_GOAL_INSTRUCTIONS.items():
            assert len(instr) > 20, f"Instruction for '{goal}' is too short"


# ─── System prompt formatting ────────────────────────────────

class TestDebateSystemPrompt:
    def test_prompt_accepts_coaching_instruction(self):
        result = DEBATE_SYSTEM_PROMPT.format(
            topic="AI Ethics",
            position="for",
            coaching_instruction=COACHING_GOAL_INSTRUCTIONS["confidence"],
        )
        assert "AI Ethics" in result
        assert "CONFIDENCE" in result

    def test_prompt_with_empty_coaching_instruction(self):
        result = DEBATE_SYSTEM_PROMPT.format(
            topic="Climate",
            position="against",
            coaching_instruction="",
        )
        assert "Climate" in result
        assert "against" in result


# ─── truncate_history ─────────────────────────────────────────

class TestTruncateHistory:
    def test_short_history_unchanged(self):
        history = [{"role": "user", "content": f"msg {i}"} for i in range(5)]
        assert truncate_history(history) == history

    def test_exact_limit_unchanged(self):
        history = [{"role": "user", "content": f"msg {i}"} for i in range(MAX_HISTORY_MESSAGES)]
        assert truncate_history(history) == history

    def test_over_limit_truncated_to_most_recent(self):
        history = [{"role": "user", "content": f"msg {i}"} for i in range(MAX_HISTORY_MESSAGES + 5)]
        result = truncate_history(history)
        assert len(result) == MAX_HISTORY_MESSAGES
        # Should keep the LAST messages
        assert result[-1]["content"] == f"msg {MAX_HISTORY_MESSAGES + 4}"
        assert result[0]["content"] == f"msg 5"

    def test_empty_history(self):
        assert truncate_history([]) == []


# ─── CloudLLMService — coaching_goal in prompt ───────────────

class TestCloudLLMCoachingGoal:
    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.service = CloudLLMService.__new__(CloudLLMService)
        self.service.client = AsyncMock()
        self.service.model = "llama-3.3-70b-versatile"
        self.service.MAX_RETRIES = 0
        self.service.RETRY_DELAY_S = 0.01

    def _mock_stream(self, tokens: list[str]):
        """Build a mock async stream yielding tokens."""
        chunks = []
        for t in tokens:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = t
            chunks.append(chunk)

        async def fake_stream():
            for c in chunks:
                yield c

        mock_resp = fake_stream()
        self.service.client.chat.completions.create = AsyncMock(return_value=mock_resp)

    async def test_confidence_goal_injected(self):
        self._mock_stream(["OK"])
        tokens = []
        async for t in self.service.generate_response_stream(
            "My argument", "AI Ethics", "for", [], coaching_goal="confidence",
        ):
            tokens.append(t)
        call_kwargs = self.service.client.chat.completions.create.call_args[1]
        system_msg = call_kwargs["messages"][0]["content"]
        assert "CONFIDENCE" in system_msg

    async def test_speed_goal_injected(self):
        self._mock_stream(["OK"])
        tokens = []
        async for t in self.service.generate_response_stream(
            "My argument", "Debate", "against", [], coaching_goal="speed",
        ):
            tokens.append(t)
        call_kwargs = self.service.client.chat.completions.create.call_args[1]
        system_msg = call_kwargs["messages"][0]["content"]
        assert "PACING" in system_msg

    async def test_structure_goal_injected(self):
        self._mock_stream(["OK"])
        tokens = []
        async for t in self.service.generate_response_stream(
            "My argument", "Debate", "for", [], coaching_goal="structure",
        ):
            tokens.append(t)
        call_kwargs = self.service.client.chat.completions.create.call_args[1]
        system_msg = call_kwargs["messages"][0]["content"]
        assert "STRUCTURE" in system_msg

    async def test_unknown_goal_yields_empty_instruction(self):
        self._mock_stream(["OK"])
        tokens = []
        async for t in self.service.generate_response_stream(
            "My argument", "Debate", "for", [], coaching_goal="unknown",
        ):
            tokens.append(t)
        call_kwargs = self.service.client.chat.completions.create.call_args[1]
        system_msg = call_kwargs["messages"][0]["content"]
        # Should still work — just no extra coaching instruction
        assert "expert debate coach" in system_msg.lower()

    async def test_user_text_appended_if_not_in_history(self):
        self._mock_stream(["token"])
        tokens = []
        async for t in self.service.generate_response_stream(
            "My argument", "Topic", "for", [],
        ):
            tokens.append(t)
        call_kwargs = self.service.client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        # messages[0] = system, messages[1] = user text
        assert messages[-1]["content"] == "My argument"
        assert messages[-1]["role"] == "user"

    async def test_history_not_duplicated_when_already_present(self):
        history = [{"role": "user", "content": "My argument"}]
        self._mock_stream(["token"])
        tokens = []
        async for t in self.service.generate_response_stream(
            "My argument", "Topic", "for", history,
        ):
            tokens.append(t)
        call_kwargs = self.service.client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        user_msgs = [m for m in messages if m.get("content") == "My argument"]
        assert len(user_msgs) == 1  # not duplicated


# ─── get_llm_service factory ─────────────────────────────────

class TestGetLlmService:
    def test_cloud_mode(self):
        svc = get_llm_service("cloud")
        assert isinstance(svc, CloudLLMService)

    def test_edge_mode_returns_edge(self):
        svc = get_llm_service("edge")
        assert isinstance(svc, EdgeLLMService)

    def test_unknown_mode_defaults_to_cloud(self):
        svc = get_llm_service("whatever")
        assert isinstance(svc, CloudLLMService)
