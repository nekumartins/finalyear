"""
Service: LLM Debate Engine — Module 4 (Cloud) / Module 5 (Edge)

Generates AI counter-arguments during debate.
Cloud: Llama 3.3 70B via Groq API (streamed token-by-token)
Edge:  Llama-2 via llama.cpp (built in Phase 7)

Why Groq + Llama 3.3 70B:
  - FREE tier (6K req/day) — no credit card needed
  - ~500 tok/s on Groq LPU — fastest inference available
  - Strong debate/reasoning ability at 70B scale
  - OpenAI-compatible API — drop-in replacement
"""
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
    """Cloud Path: Groq Llama 3.3 70B with streaming."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )
        self.model = "llama-3.3-70b-versatile"  # Free on Groq, strong at debate

    async def generate_response_stream(
        self, user_text, topic, user_position, conversation_history
    ) -> AsyncGenerator[str, None]:
        system_prompt = DEBATE_SYSTEM_PROMPT.format(
            topic=topic, position=user_position
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *conversation_history,
            {"role": "user", "content": user_text},
        ]

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                max_tokens=200,  # Keep responses concise for conversation flow
                temperature=0.8,  # Slightly creative for diverse arguments
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

        except Exception as e:
            logger.error(f"[LLM] OpenAI API error: {e}")
            yield f"[Error: {e}]"

    async def generate_response_batch(
        self, user_text: str, topic: str, user_position: str, conversation_history: list[dict]
    ) -> str:
        """Non-streaming version for testing."""
        full = ""
        async for token in self.generate_response_stream(
            user_text, topic, user_position, conversation_history
        ):
            full += token
        return full


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
