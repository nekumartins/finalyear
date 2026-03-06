"""
Service: AI Coaching Report Generator

After a debate session ends, this service analyses the full transcript
and session metrics, then generates a structured coaching report using
the same Groq/Llama LLM. The report adapts based on the user's chosen
coaching goal (confidence / speed / structure).

Output schema (JSON):
{
  "overall_score": 72,                     // 0-100 composite score
  "argument_quality": 7,                   // 1-10 LLM-judged
  "strengths": ["Clear opening thesis", ...],
  "improvements": ["Lacked evidence in rebuttal 2", ...],
  "fallacies": ["Straw man in turn 4"],    // empty if none detected
  "tips": ["Try the Toulmin model...", ...], // personalized to coaching goal
  "summary": "You showed strong conviction but ..."
}
"""
import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from backend.app.config import get_settings
from backend.app.schemas.messages import TranscriptEntry

logger = logging.getLogger(__name__)

COACHING_GOAL_PROMPTS = {
    "confidence": (
        "The user wants to build CONFIDENCE in debate. Focus your tips on: "
        "assertive delivery, conviction in their voice, handling pressure, "
        "recovering from weak moments, and projecting authority."
    ),
    "speed": (
        "The user wants to improve PACING and speed. Focus your tips on: "
        "speaking rate control, reducing long pauses, maintaining flow, "
        "eliminating filler words, and keeping a steady rhythm."
    ),
    "structure": (
        "The user wants to improve ARGUMENT STRUCTURE. Focus your tips on: "
        "logical flow (claim→evidence→reasoning), smooth transitions, "
        "addressing the opponent's points before countering, and "
        "building toward a clear conclusion."
    ),
}

COACHING_SYSTEM_PROMPT = """You are an expert debate coach analyzing a completed debate session.

The user debated the topic: "{topic}"
The user argued: "{position}"
{goal_instruction}

Session stats:
- Duration: {duration}s
- User WPM: {user_wpm}
- Filler word count: {filler_count} (words: {filler_words})
- Turn count: {turn_count}
- User talk ratio: {talk_ratio}%
- Avg pause between utterances: {avg_pause}ms

Full transcript (USER = the debater being coached, AI = opponent):
{transcript_text}

Analyze this debate and return a JSON object with EXACTLY this structure:
{{
  "overall_score": <integer 0-100>,
  "argument_quality": <integer 1-10>,
  "strengths": [<2-4 specific strength strings>],
  "improvements": [<2-4 specific improvement strings>],
  "fallacies": [<list of logical fallacies detected, empty array if none>],
  "tips": [<2-3 actionable tips personalized to their coaching goal>],
  "summary": "<2-3 sentence overall assessment>"
}}

RULES:
- Be specific. Reference actual things they said, not generic advice.
- The overall_score should reflect: argument quality (40%), delivery/fluency (30%), engagement/structure (30%).
- A score of 50 is average. 70+ is good. 85+ is excellent.
- If the transcript is very short (<3 turns), note that more practice is needed.
- Return ONLY the JSON object, no markdown fences, no explanation.
"""


def _format_transcript(entries: list[TranscriptEntry]) -> str:
    """Format transcript entries into readable text."""
    lines = []
    for entry in entries:
        speaker = "USER" if entry.speaker == "user" else "AI"
        lines.append(f"[{speaker}]: {entry.text}")
    return "\n".join(lines) if lines else "(empty transcript)"


class CoachingService:
    """Generates AI coaching reports from completed debate sessions."""

    MAX_RETRIES = 2
    RETRY_DELAY_S = 1.0

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )
        self.model = "llama-3.3-70b-versatile"

    async def generate_report(
        self,
        transcript: list[TranscriptEntry],
        metrics: dict,
        topic: str,
        user_position: str,
        coaching_goal: str = "confidence",
    ) -> Optional[dict]:
        """
        Generate a structured coaching report from the session data.
        Returns the parsed JSON report dict, or None on failure.
        """
        goal_instruction = COACHING_GOAL_PROMPTS.get(
            coaching_goal,
            COACHING_GOAL_PROMPTS["confidence"],
        )

        filler_words_str = ", ".join(
            f'"{w}" ×{c}'
            for w, c in sorted(
                metrics.get("filler_words", {}).items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ) or "none"

        prompt = COACHING_SYSTEM_PROMPT.format(
            topic=topic,
            position=user_position,
            goal_instruction=goal_instruction,
            duration=round(metrics.get("duration_seconds", 0)),
            user_wpm=round(metrics.get("user_wpm", 0)),
            filler_count=metrics.get("filler_word_count", 0),
            filler_words=filler_words_str,
            turn_count=metrics.get("turn_count", 0),
            talk_ratio=round(metrics.get("user_talk_ratio", 0) * 100),
            avg_pause=round(metrics.get("avg_pause_duration_ms", 0)),
            transcript_text=_format_transcript(transcript),
        )

        import asyncio

        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": "Generate the coaching report JSON now."},
                    ],
                    max_tokens=600,
                    temperature=0.4,  # Lower temp for structured output
                )

                raw = response.choices[0].message.content.strip()

                # Strip markdown fences if the LLM adds them
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                    if raw.endswith("```"):
                        raw = raw[:-3]
                    raw = raw.strip()

                report = json.loads(raw)

                # Validate required fields
                required = {"overall_score", "argument_quality", "strengths",
                           "improvements", "fallacies", "tips", "summary"}
                if not required.issubset(report.keys()):
                    missing = required - report.keys()
                    logger.warning(f"[Coaching] Missing fields: {missing}")
                    # Fill missing with defaults
                    report.setdefault("overall_score", 50)
                    report.setdefault("argument_quality", 5)
                    report.setdefault("strengths", [])
                    report.setdefault("improvements", [])
                    report.setdefault("fallacies", [])
                    report.setdefault("tips", [])
                    report.setdefault("summary", "Session completed.")

                # Clamp score
                report["overall_score"] = max(0, min(100, int(report["overall_score"])))
                report["argument_quality"] = max(1, min(10, int(report["argument_quality"])))

                logger.info(
                    f"[Coaching] Report generated: score={report['overall_score']}, "
                    f"quality={report['argument_quality']}"
                )
                return report

            except json.JSONDecodeError as e:
                logger.warning(f"[Coaching] JSON parse error (attempt {attempt + 1}): {e}")
                last_error = e
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY_S * (2 ** attempt))
                    continue

            except Exception as e:
                error_str = str(e)
                last_error = e

                if "429" in error_str or "rate_limit" in error_str.lower():
                    if attempt < self.MAX_RETRIES:
                        delay = self.RETRY_DELAY_S * (2 ** attempt)
                        logger.warning(f"[Coaching] Rate limited, retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue

                logger.error(f"[Coaching] Generation failed: {e}")
                return None

        logger.error(f"[Coaching] All attempts failed: {last_error}")
        return None


coaching_service = CoachingService()
