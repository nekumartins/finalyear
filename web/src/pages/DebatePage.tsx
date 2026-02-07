/**
 * DebatePage — Live debate session.
 *
 * Flow:
 * 1. Connects WebSocket + starts audio capture on mount
 * 2. Streams audio chunks → backend
 * 3. Receives turn signals, transcript updates, AI responses
 * 4. User clicks "End" → receives metrics → navigates to MetricsPage
 */
import React, { useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useDebateStore } from "../stores/debateStore";
import { useWebSocket } from "../hooks/useWebSocket";
import { useAudioCapture } from "../hooks/useAudioCapture";
import { Transcript } from "../components/Transcript";
import { TurnIndicator } from "../components/TurnIndicator";

export function DebatePage() {
  const navigate = useNavigate();
  const { topic, userPosition, mode, sessionId, status } = useDebateStore();
  const { startSession, sendAudioChunk, endSession, disconnect } = useWebSocket();

  // Audio chunk callback — sends to backend via WebSocket
  const onAudioChunk = useCallback(
    (chunkB64: string) => {
      const sid = useDebateStore.getState().sessionId;
      if (sid) sendAudioChunk(sid, chunkB64);
    },
    [sendAudioChunk]
  );

  const { isRecording, start: startAudio, stop: stopAudio } = useAudioCapture({
    onChunk: onAudioChunk,
  });

  // Start session on mount
  useEffect(() => {
    if (!topic) {
      navigate("/");
      return;
    }
    startSession(topic, userPosition, mode);
  }, []);

  // Start audio capture once session is active
  useEffect(() => {
    if (status === "active" && !isRecording) {
      startAudio();
    }
  }, [status, isRecording, startAudio]);

  // Navigate to metrics when session ends
  useEffect(() => {
    if (status === "ended") {
      navigate("/metrics");
    }
  }, [status, navigate]);

  const handleEnd = () => {
    stopAudio();
    if (sessionId) endSession(sessionId);
    // metrics will arrive via WebSocket → store → triggers navigation
    // fallback: navigate after timeout
    setTimeout(() => {
      if (useDebateStore.getState().status !== "ended") {
        navigate("/metrics");
      }
    }, 3000);
  };

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h2 style={styles.topic}>{topic}</h2>
          <span style={styles.badge}>
            {mode === "cloud" ? "☁️ Cloud" : "📱 Edge"} · You argue{" "}
            <strong>{userPosition}</strong>
          </span>
        </div>
        <button className="btn-danger" onClick={handleEnd}>
          ⏹️ End Debate
        </button>
      </div>

      {/* Turn indicator */}
      <TurnIndicator />

      {/* Status */}
      {status === "connecting" && (
        <div style={styles.connecting}>Connecting to debate server...</div>
      )}

      {/* Recording indicator */}
      {isRecording && (
        <div style={styles.recording}>
          <span style={styles.redDot} /> Recording — speak your argument
        </div>
      )}

      {/* Transcript */}
      <div style={styles.transcriptArea}>
        <Transcript />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    height: "calc(100vh - 130px)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  topic: { fontSize: "1.4rem", marginBottom: "4px" },
  badge: {
    fontSize: "0.85rem",
    color: "var(--text-secondary)",
  },
  connecting: {
    textAlign: "center",
    padding: "20px",
    color: "var(--warning)",
    fontSize: "1rem",
  },
  recording: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    color: "var(--danger)",
    fontSize: "0.9rem",
  },
  redDot: {
    display: "inline-block",
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "var(--danger)",
  },
  transcriptArea: {
    flex: 1,
    overflow: "hidden",
  },
};
