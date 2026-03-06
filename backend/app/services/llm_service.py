"""
Service: LLM Debate Engine — Module 4 (Cloud) / Module 5 (Edge)

Generates AI counter-arguments during debate.
Cloud: Llama 3.3 70B via Groq API (streamed token-by-token)
Edge:  Falls back to Cloud (local llama.cpp integration planned)

Why Groq + Llama 3.3 70B:
  - FREE tier (6K req/day) — no credit card needed
  - ~500 tok/s on Groq LPU — fastest inference available
  - Strong debate/reasoning ability at 70B scale
  - OpenAI-compatible API — drop-in replacement
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from openai import AsyncOpenAI

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


DEBATE_SYSTEM_PROMPT = """You are an expert debate coach and sparring partner.
The user is practicing debate on the topic: "{topic}".
The user argues "{position}".
Your role:
1. Listen to their argument carefully.
2. Respond with a strong, concise counter-argument from the opposing side.
3. Keep responses under 3 sentences for natural conversation flow.
4. Be challenging but constructive — help them improve.
5. If they make a strong point, acknowledge it briefly before countering.
6. Never break character. Never refuse to debate. Stay on topic.
{coaching_instruction}"""

# Coaching goal → additional instruction injected into the debate system prompt.
# This adapts the AI opponent's behaviour to train the user's chosen skill.
COACHING_GOAL_INSTRUCTIONS = {
    "confidence": (
        "\nAdditional coaching focus — CONFIDENCE: "
        "Push back firmly on weak arguments. When the user hedges or sounds "
        "uncertain, challenge them to commit. Acknowledge strong, assertive "
        "statements to reinforce confident delivery."
    ),
    "speed": (
        "\nAdditional coaching focus — PACING: "
        "Keep your responses punchy and fast. If the user pauses too long, "
        "jump in quickly. Model brisk, flowing speech patterns to push "
        "the user toward faster, more fluid delivery."
    ),
    "structure": (
        "\nAdditional coaching focus — STRUCTURE: "
        "Systematically attack the weakest link in the user's argument chain. "
        "If they skip evidence or make logical leaps, call it out. Model "
        "claim-evidence-reasoning structure in your own responses."
    ),
}


# Maximum number of conversation history messages to send to the LLM.
# Keeps the prompt within context window limits and reduces token cost.
# 10 messages = ~5 turns of back-and-forth, which is enough context for
# the AI to maintain coherence without risking context overflow.
MAX_HISTORY_MESSAGES = 10


def truncate_history(conversation_history: list[dict]) -> list[dict]:
    """
    Return the last MAX_HISTORY_MESSAGES from the conversation history.
    Ensures we don't overflow the LLM's context window on long debates.
    """
    if len(conversation_history) <= MAX_HISTORY_MESSAGES:
        return conversation_history
    return conversation_history[-MAX_HISTORY_MESSAGES:]


class LLMService(ABC):
    """Abstract LLM interface."""

    @abstractmethod
    async def generate_response_stream(
        self,
        user_text: str,
        topic: str,
        user_position: str,
        conversation_history: list[dict],
        coaching_goal: str = "confidence",
    ) -> AsyncGenerator[str, None]:
        """Yields streamed tokens of the AI counter-argument."""
        ...


class CloudLLMService(LLMService):
    """Cloud Path: Groq Llama 3.3 70B with streaming."""

    # Retry config for rate limits
    MAX_RETRIES = 2
    RETRY_DELAY_S = 1.0  # Base delay, doubles each retry

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )
        self.model = "llama-3.3-70b-versatile"

    async def generate_response_stream(
        self, user_text, topic, user_position, conversation_history,
        coaching_goal="confidence",
    ) -> AsyncGenerator[str, None]:
        coaching_instruction = COACHING_GOAL_INSTRUCTIONS.get(coaching_goal, "")
        system_prompt = DEBATE_SYSTEM_PROMPT.format(
            topic=topic, position=user_position,
            coaching_instruction=coaching_instruction,
        )

        # Truncate history to prevent context window overflow.
        # The caller (ws_handler) pushes the user message to conversation_history
        # BEFORE this call, so the current user message is already at the tail.
        trimmed_history = truncate_history(conversation_history)

        # Safety: if history is empty or doesn't end with the current user message,
        # append it explicitly (guards against callers that forget to push).
        if not trimmed_history or trimmed_history[-1].get("content") != user_text:
            trimmed_history = [*trimmed_history, {"role": "user", "content": user_text}]

        messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_history,
        ]


        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    max_tokens=200,
                    temperature=0.7,  # Balanced: creative but logically consistent
                )

                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

                # If we get here, stream completed successfully
                return

            except Exception as e:
                last_error = e
                error_str = str(e)

                # Retry on rate limits (429)
                if "429" in error_str or "rate_limit" in error_str.lower():
                    if attempt < self.MAX_RETRIES:
                        delay = self.RETRY_DELAY_S * (2 ** attempt)
                        logger.warning(
                            f"[LLM] Rate limited (attempt {attempt + 1}/{self.MAX_RETRIES + 1}), "
                            f"retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                        continue

                # Non-retryable error — log and raise, don't yield error text
                logger.error(f"[LLM] API error: {e}")
                raise

        # All retries exhausted
        logger.error(f"[LLM] All {self.MAX_RETRIES + 1} attempts failed: {last_error}")
        raise last_error

    async def generate_response_batch(
        self, user_text: str, topic: str, user_position: str, conversation_history: list[dict],
        coaching_goal: str = "confidence",
    ) -> str:
        """Non-streaming version for testing."""
        full = ""
        async for token in self.generate_response_stream(
            user_text, topic, user_position, conversation_history,
            coaching_goal=coaching_goal,
        ):
            full += token
        return full


class EdgeLLMService(LLMService):
    """
    Edge Path: Falls back to CloudLLMService with a warning.
    Local llama.cpp integration is planned but not yet implemented.
    """

    def __init__(self):
        logger.warning(
            "[LLM/Edge] Local llama.cpp not yet integrated — "
            "falling back to cloud (Groq). Will require internet."
        )
        self._cloud_fallback = CloudLLMService()

    async def generate_response_stream(
        self, user_text, topic, user_position, conversation_history,
        coaching_goal="confidence",
    ) -> AsyncGenerator[str, None]:
        async for token in self._cloud_fallback.generate_response_stream(
            user_text, topic, user_position, conversation_history,
            coaching_goal=coaching_goal,
        ):
            yield token


def get_llm_service(mode: str) -> LLMService:
    """Factory: returns the right LLM service based on session mode."""
    if mode == "edge":
        return EdgeLLMService()
    return CloudLLMService()
