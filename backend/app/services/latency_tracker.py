"""
Service: Latency Tracker — End-to-end pipeline instrumentation.

Records timestamps at each stage of the real-time pipeline:
  audio_received → stt_partial → stt_final → llm_first_token → llm_done

Used to measure and expose latency breakdowns per session.
"""
import time
from dataclasses import dataclass, field


@dataclass
class LatencyEvent:
    name: str
    timestamp_ms: float          # server time (monotonic)
    client_ts_ms: float | None = None  # client-reported time, if available


class LatencyTracker:
    """Records pipeline events and computes latency deltas."""

    def __init__(self):
        self._events: list[LatencyEvent] = []
        self._origin: float = time.monotonic() * 1000  # session start

    def record(self, event_name: str, client_ts_ms: float | None = None) -> None:
        """Record a named event with current timestamp."""
        self._events.append(LatencyEvent(
            name=event_name,
            timestamp_ms=time.monotonic() * 1000 - self._origin,
            client_ts_ms=client_ts_ms,
        ))

    def get_report(self) -> dict:
        """Return a structured latency report for the session."""
        events = [
            {
                "name": e.name,
                "server_ms": round(e.timestamp_ms, 1),
                **({"client_ms": e.client_ts_ms} if e.client_ts_ms is not None else {}),
            }
            for e in self._events
        ]

        # Compute key deltas from the most recent turn
        deltas = {}
        event_map: dict[str, list[float]] = {}
        for e in self._events:
            event_map.setdefault(e.name, []).append(e.timestamp_ms)

        # Average STT latency: audio_received → stt_result
        stt_latencies = self._compute_deltas("audio_received", "stt_result")
        if stt_latencies:
            deltas["avg_stt_latency_ms"] = round(
                sum(stt_latencies) / len(stt_latencies), 1
            )

        # LLM time-to-first-token
        ttft = self._compute_deltas("llm_start", "llm_first_token")
        if ttft:
            deltas["avg_llm_ttft_ms"] = round(sum(ttft) / len(ttft), 1)

        # LLM total generation time
        llm_total = self._compute_deltas("llm_start", "llm_done")
        if llm_total:
            deltas["avg_llm_total_ms"] = round(sum(llm_total) / len(llm_total), 1)

        # End-to-end: audio_received → llm_first_token
        e2e = self._compute_deltas("audio_received", "llm_first_token")
        if e2e:
            deltas["avg_e2e_to_first_token_ms"] = round(sum(e2e) / len(e2e), 1)

        return {
            "events": events,
            "deltas": deltas,
            "total_events": len(self._events),
        }

    def _compute_deltas(self, start_name: str, end_name: str) -> list[float]:
        """Pair up consecutive start→end events and return deltas."""
        starts = [e.timestamp_ms for e in self._events if e.name == start_name]
        ends = [e.timestamp_ms for e in self._events if e.name == end_name]
        # Pair by index (each start pairs with the next end after it)
        deltas = []
        end_idx = 0
        for s in starts:
            while end_idx < len(ends) and ends[end_idx] <= s:
                end_idx += 1
            if end_idx < len(ends):
                deltas.append(ends[end_idx] - s)
                end_idx += 1
        return deltas

    def reset(self) -> None:
        """Reset for a new session."""
        self._events.clear()
        self._origin = time.monotonic() * 1000
