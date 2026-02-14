"""
Shared fixtures for backend tests.
"""
import struct
import pytest
from backend.app.schemas.messages import TranscriptEntry


@pytest.fixture
def silence_audio() -> bytes:
    """100ms of PCM16 silence at 16kHz (1600 samples of zeros)."""
    return b"\x00\x00" * 1600


@pytest.fixture
def loud_audio() -> bytes:
    """100ms of PCM16 loud tone at 16kHz (1600 samples, half-amplitude sine-ish)."""
    # Use a simple square wave at ~half amplitude for predictable RMS
    amplitude = 16384  # half of 32768
    return struct.pack(f"<{1600}h", *([amplitude, -amplitude] * 800))


@pytest.fixture
def sample_transcript() -> list[TranscriptEntry]:
    """A short 4-entry debate transcript for metrics testing."""
    return [
        TranscriptEntry(speaker="user", text="I believe climate change is real", start_ms=0, end_ms=3000),
        TranscriptEntry(speaker="ai", text="That is a strong opening", start_ms=3500, end_ms=5000),
        TranscriptEntry(speaker="user", text="um like basically the science is clear you know", start_ms=5500, end_ms=9000),
        TranscriptEntry(speaker="ai", text="Good point but consider the counterargument", start_ms=9500, end_ms=12000),
    ]
