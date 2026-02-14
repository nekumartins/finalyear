"""
Tests: LatencyTracker — event recording and latency delta computation.
"""
import time
from unittest.mock import patch
from backend.app.services.latency_tracker import LatencyTracker


class TestLatencyTracker:
    def test_record_events(self):
        """Events are recorded with server timestamps."""
        tracker = LatencyTracker()
        tracker.record("audio_received")
        tracker.record("stt_result")

        report = tracker.get_report()
        assert report["total_events"] == 2
        assert len(report["events"]) == 2
        assert report["events"][0]["name"] == "audio_received"
        assert report["events"][1]["name"] == "stt_result"

    def test_server_timestamps_increase(self):
        """Server timestamps are monotonically increasing."""
        tracker = LatencyTracker()
        tracker.record("a")
        tracker.record("b")

        report = tracker.get_report()
        assert report["events"][1]["server_ms"] >= report["events"][0]["server_ms"]

    def test_client_timestamp_included_when_provided(self):
        """Client timestamps appear in report only when explicitly passed."""
        tracker = LatencyTracker()
        tracker.record("a", client_ts_ms=123.4)
        tracker.record("b")

        report = tracker.get_report()
        assert report["events"][0]["client_ms"] == 123.4
        assert "client_ms" not in report["events"][1]

    def test_stt_delta_computed(self):
        """avg_stt_latency_ms is computed from audio_received → stt_result pairs."""
        tracker = LatencyTracker()

        # Manually inject events with controlled timestamps
        from backend.app.services.latency_tracker import LatencyEvent
        tracker._events = [
            LatencyEvent(name="audio_received", timestamp_ms=0.0),
            LatencyEvent(name="stt_result", timestamp_ms=100.0),
            LatencyEvent(name="audio_received", timestamp_ms=200.0),
            LatencyEvent(name="stt_result", timestamp_ms=350.0),
        ]

        report = tracker.get_report()
        # Average of (100, 150) = 125
        assert report["deltas"]["avg_stt_latency_ms"] == 125.0

    def test_llm_deltas_computed(self):
        """LLM TTFT and total time deltas are computed correctly."""
        from backend.app.services.latency_tracker import LatencyEvent
        tracker = LatencyTracker()
        tracker._events = [
            LatencyEvent(name="llm_start", timestamp_ms=0.0),
            LatencyEvent(name="llm_first_token", timestamp_ms=50.0),
            LatencyEvent(name="llm_done", timestamp_ms=200.0),
        ]

        report = tracker.get_report()
        assert report["deltas"]["avg_llm_ttft_ms"] == 50.0
        assert report["deltas"]["avg_llm_total_ms"] == 200.0

    def test_e2e_delta(self):
        """End-to-end delta: audio_received → llm_first_token."""
        from backend.app.services.latency_tracker import LatencyEvent
        tracker = LatencyTracker()
        tracker._events = [
            LatencyEvent(name="audio_received", timestamp_ms=0.0),
            LatencyEvent(name="stt_result", timestamp_ms=80.0),
            LatencyEvent(name="llm_start", timestamp_ms=85.0),
            LatencyEvent(name="llm_first_token", timestamp_ms=150.0),
        ]

        report = tracker.get_report()
        assert report["deltas"]["avg_e2e_to_first_token_ms"] == 150.0

    def test_empty_tracker_report(self):
        """Empty tracker returns report with no events and no deltas."""
        tracker = LatencyTracker()
        report = tracker.get_report()
        assert report["total_events"] == 0
        assert report["events"] == []
        assert report["deltas"] == {}

    def test_reset_clears_events(self):
        """Reset clears all recorded events."""
        tracker = LatencyTracker()
        tracker.record("a")
        tracker.record("b")
        tracker.reset()

        report = tracker.get_report()
        assert report["total_events"] == 0

    def test_unpaired_events_produce_no_delta(self):
        """If there's a start event but no matching end event, no delta is computed."""
        from backend.app.services.latency_tracker import LatencyEvent
        tracker = LatencyTracker()
        tracker._events = [
            LatencyEvent(name="audio_received", timestamp_ms=0.0),
            # No stt_result — unpaired
        ]

        report = tracker.get_report()
        assert "avg_stt_latency_ms" not in report["deltas"]
