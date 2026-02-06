"""
Service: Post-Session Metrics — Module 6

Computes delivery analytics from the session transcript:
- Words per minute (WPM)
- Filler word detection and count
- Average pause duration
- Turn count and talk ratio
"""
from backend.app.schemas.messages import TranscriptEntry

# Common filler words to detect
FILLER_WORDS = {
    "um", "uh", "like", "you know", "basically", "actually",
    "literally", "right", "so", "well", "i mean", "kind of",
    "sort of", "you see", "okay", "er", "ah",
}


class MetricsService:
    """Computes post-session debate delivery metrics."""

    def compute_metrics(
        self,
        entries: list[TranscriptEntry],
        session_duration_seconds: float,
    ) -> dict:
        user_entries = [e for e in entries if e.speaker == "user"]
        ai_entries = [e for e in entries if e.speaker == "ai"]

        user_text = " ".join(e.text for e in user_entries)
        ai_text = " ".join(e.text for e in ai_entries)

        user_words = user_text.split()
        ai_words = ai_text.split()

        # WPM
        user_duration_min = max(session_duration_seconds / 60, 0.01)
        user_wpm = len(user_words) / user_duration_min
        ai_wpm = len(ai_words) / user_duration_min

        # Filler words
        filler_counts = {}
        user_text_lower = user_text.lower()
        for filler in FILLER_WORDS:
            count = user_text_lower.count(filler)
            if count > 0:
                filler_counts[filler] = count
        total_fillers = sum(filler_counts.values())

        # Pauses between user utterances
        pauses = []
        sorted_user = sorted(user_entries, key=lambda e: e.start_ms)
        for i in range(1, len(sorted_user)):
            gap = sorted_user[i].start_ms - sorted_user[i - 1].end_ms
            if gap > 0:
                pauses.append(gap)
        avg_pause = sum(pauses) / max(len(pauses), 1)

        # Turn count & talk ratio
        turn_count = len(entries)
        user_talk_ms = sum(e.end_ms - e.start_ms for e in user_entries)
        total_talk_ms = sum(e.end_ms - e.start_ms for e in entries) or 1
        user_talk_ratio = user_talk_ms / total_talk_ms

        return {
            "duration_seconds": session_duration_seconds,
            "user_wpm": round(user_wpm, 1),
            "ai_wpm": round(ai_wpm, 1),
            "filler_word_count": total_fillers,
            "filler_words": filler_counts,
            "avg_pause_duration_ms": round(avg_pause, 1),
            "turn_count": turn_count,
            "user_talk_ratio": round(user_talk_ratio, 3),
        }


metrics_service = MetricsService()
