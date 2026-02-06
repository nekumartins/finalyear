"""
Service: LLM Debate Engine — Module 4 (Cloud) / Module 5 (Edge)

Generates AI counter-arguments during debate.
Cloud: GPT-4 via OpenAI API (streamed)
Edge:  Llama-2 via llama.cpp (built in Phase 7)
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator


DEBATE_SYSTEM_PROMPT = """You are an expert debate coach and sparring partner. 
The user is practicing debate on the topic: "{topic}".
The user argues "{position}".
Your role:
1. Listen to their argument carefully.
2. Respond with a strong, concise counter-argument from the opposing side.
3. Keep responses under 3 sentences for natural conversation flow.
4. Be challenging but constructive — help them improve.
5. If they make a strong point, acknowledge it briefly before countering.
"""


class LLMService(ABC):
    """Abstract LLM interface."""

    @abstractmethod
    async def generate_response_stream(
        self,
        user_text: str,
        topic: str,
        user_position: str,
        conversation_history: list[dict],
    ) -> AsyncGenerator[str, None]:
        """Yields streamed tokens of the AI counter-argument."""
        ...


class CloudLLMService(LLMService):
    """Cloud Path: OpenAI GPT-4 (placeholder — implemented in Phase 4)."""

    async def generate_response_stream(
        self, user_text, topic, user_position, conversation_history
    ):
        # TODO: Phase 4 — integrate OpenAI ChatCompletion streaming
        placeholder = "That's an interesting point, but consider this counter-argument..."
        for word in placeholder.split():
            yield word + " "

    async def generate_response_batch(
        self, user_text: str, topic: str, user_position: str, conversation_history: list[dict]
    ) -> str:
        """Non-streaming version for testing."""
        # TODO: Phase 4
        return "That's an interesting point, but consider this counter-argument..."


class EdgeLLMService(LLMService):
    """Edge Path: Llama-2 via llama.cpp (placeholder — implemented in Phase 7)."""

    async def generate_response_stream(
        self, user_text, topic, user_position, conversation_history
    ):
        # TODO: Phase 7 — integrate llama.cpp
        placeholder = "[edge LLM response placeholder]"
        for word in placeholder.split():
            yield word + " "


def get_llm_service(mode: str) -> LLMService:
    """Factory: returns the right LLM service based on session mode."""
    if mode == "edge":
        return EdgeLLMService()
    return CloudLLMService()
