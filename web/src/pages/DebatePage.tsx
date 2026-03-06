/**
 * DebatePage — Live debate session with premium header, waveform indicator, and glass layout.
 *
 * Flow:
 * 1. Connects WebSocket + starts audio capture on mount
 * 2. Streams audio chunks → backend
 * 3. Receives turn signals, transcript updates, AI responses
 * 4. User clicks "End" → receives metrics → navigates to MetricsPage
 */
import React, { useEffect, useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDebateStore } from "../stores/debateStore";
import { useAppStore } from "../stores/appStore";
import { useWebSocket } from "../hooks/useWebSocket";
import { useAudioCapture } from "../hooks/useAudioCapture";
import { useAudioPlayback } from "../hooks/useAudioPlayback";
import { Transcript } from "../components/Transcript";
import { TurnIndicator } from "../components/TurnIndicator";

/** Animated waveform bars shown while recording */
function WaveformBars() {
  const bars = [0.4, 0.8, 0.5, 1.0, 0.6, 0.9, 0.45, 0.75, 0.55, 0.85];
  return (
    <div style={styles.waveform}>
      {bars.map((h, i) => (
        <div
          key={i}
          style={{
            ...styles.waveBar,
            animationDelay: `${i * 0.08}s`,
            height: `${h * 28}px`,
          }}
        />
      ))}
    </div>
  );
}

/** Elapsed timer displayed in the header */
function ElapsedTimer({ startTime }: { startTime: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(
      () => setElapsed(Math.floor((Date.now() - startTime) / 1000)),
      1000
    );
    return () => clearInterval(id);
  }, [startTime]);
  const m = Math.floor(elapsed / 60).toString().padStart(2, "0");
  const s = (elapsed % 60).toString().padStart(2, "0");
  return <span style={styles.timerText}>{m}:{s}</span>;
}

export function DebatePage() {
  const navigate = useNavigate();
  const { topic, userPosition, mode, sessionId, status } = useDebateStore();
  const { ttsProvider, ttsVoice, coachingGoal } = useAppStore();
  const { startSession, sendAudioChunk, endSession } = useWebSocket();
  const { isPlaying: isAiSpeaking, enqueue: enqueueAudio, stop: stopTtsAudio } = useAudioPlayback();
  const [sessionStart] = useState(Date.now());

  // Audio chunk callback — sends to backend via WebSocket
  const onAudioChunk = useCallback(
    (chunkB64: string) => {
      const sid = useDebateStore.getState().sessionId;
      if (sid) sendAudioChunk(sid, chunkB64);
    },
    [sendAudioChunk]
  );

  const { isRecording, start: startAudio, stop: stopMic } = useAudioCapture({
    onChunk: onAudioChunk,
  });
  // Register global TTS audio handler for the WebSocket hook
  useEffect(() => {
    (window as any).__ttsAudioHandler = (audioB64: string, isFinal: boolean) => {
      if (audioB64) enqueueAudio(audioB64);
    };
    return () => {
      delete (window as any).__ttsAudioHandler;
    };
  }, [enqueueAudio]);
  // Start session on mount
  useEffect(() => {
    if (!topic) {
      navigate("/new-debate");
      return;
    }
    startSession(topic, userPosition, mode, ttsProvider, ttsVoice, coachingGoal);
  }, []);

  // Start audio capture once session is active
  useEffect(() => {
    if (status === "active" && !isRecording) {
      startAudio();
    }
  }, [status, isRecording, startAudio]);

  // Stop audio capture whenever session is not actively streaming.
  useEffect(() => {
    if (status !== "active" && isRecording) {
      stopMic();
    }
  }, [status, isRecording, stopMic]);

  // Ensure mic resources are always released on page unmount.
  useEffect(() => {
    return () => {
      stopMic();
    };
  }, [stopMic]);

  // Navigate to metrics when session ends
  useEffect(() => {
    if (status === "ended") {
      navigate("/metrics");
    }
  }, [status, navigate]);

  const handleEnd = () => {
    stopMic();
    stopTtsAudio();
    if (sessionId) endSession(sessionId);
    setTimeout(() => {
      if (useDebateStore.getState().status !== "ended") {
        navigate("/metrics");
      }
    }, 3000);
  };

  return (
    <div style={styles.page}>
      {/* ── Header card ── */}
      <div className="glass" style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.topicRow}>
            <h2 style={styles.topic}>{topic}</h2>
            <span
              style={{
                ...styles.stanceBadge,
                background:
                  userPosition === "for"
                    ? "rgba(52,211,153,0.15)"
                    : "rgba(248,113,113,0.15)",
                border:
                  userPosition === "for"
                    ? "1px solid rgba(52,211,153,0.35)"
                    : "1px solid rgba(248,113,113,0.35)",
                color:
                  userPosition === "for" ? "var(--success)" : "var(--danger)",
              }}
            >
              {userPosition === "for" ? "👍" : "👎"} You argue{" "}
              <strong>{userPosition}</strong>
            </span>
          </div>
          <div style={styles.headerMeta}>
            <span style={styles.modePill}>
              {mode === "cloud" ? "☁️ Cloud" : "⚡ Edge"}
            </span>
            <span style={styles.timerWrap}>
              <ElapsedTimer startTime={sessionStart} />
            </span>
          </div>
        </div>

        <button className="btn-danger" onClick={handleEnd} style={styles.endBtn}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
            <rect x="4" y="4" width="16" height="16" rx="2" fill="currentColor" />
          </svg>
          End Debate
        </button>
      </div>

      {/* ── Status / recording row ── */}
      {status === "connecting" && (
        <div style={styles.connectingBanner}>
          <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
          Connecting to debate server…
        </div>
      )}

      {isRecording && (
        <div style={styles.recordingBanner}>
          <WaveformBars />
          <span style={styles.recordingText}>Recording — speak your argument</span>
        </div>
      )}

      {isAiSpeaking && (
        <div style={styles.aiSpeakingBanner}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round">
            <path d="M11 5L6 9H2v6h4l5 4V5z" />
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
          </svg>
          <span style={styles.aiSpeakingText}>AI is speaking…</span>
        </div>
      )}

      {/* ── Turn indicator ── */}
      <TurnIndicator />

      {/* ── Transcript (fills remaining height) ── */}
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
    gap: "14px",
    height: "calc(100vh - 130px)",
    animation: "fadeSlideUp 0.35s ease",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 18px",
    gap: "12px",
    flexShrink: 0,
    flexWrap: "wrap",
  },
  headerLeft: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    minWidth: 0,
    flex: 1,
  },
  topicRow: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
  },
  topic: {
    fontSize: "1.2rem",
    fontWeight: 700,
    letterSpacing: "-0.01em",
    margin: 0,
  },
  stanceBadge: {
    fontSize: "0.78rem",
    fontWeight: 600,
    padding: "4px 12px",
    borderRadius: "20px",
    flexShrink: 0,
  },
  headerMeta: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  modePill: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
    background: "var(--bg-glass)",
    border: "1px solid var(--border)",
    padding: "3px 10px",
    borderRadius: "20px",
  },
  timerWrap: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  timerText: {
    fontFamily: "monospace",
    fontSize: "0.85rem",
    color: "var(--text-secondary)",
    fontWeight: 600,
    letterSpacing: "0.05em",
  },
  endBtn: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexShrink: 0,
    padding: "10px 20px",
    fontSize: "0.875rem",
  },
  connectingBanner: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "14px 20px",
    borderRadius: "var(--radius)",
    background: "rgba(251,191,36,0.08)",
    border: "1px solid rgba(251,191,36,0.2)",
    color: "var(--warning)",
    fontSize: "0.9rem",
    fontWeight: 500,
    animation: "fadeSlideUp 0.3s ease",
    flexShrink: 0,
  },
  recordingBanner: {
    display: "flex",
    alignItems: "center",
    gap: "16px",
    padding: "12px 20px",
    borderRadius: "var(--radius)",
    background: "rgba(248,113,113,0.08)",
    border: "1px solid rgba(248,113,113,0.2)",
    animation: "fadeSlideUp 0.3s ease",
    flexShrink: 0,
  },
  waveform: {
    display: "flex",
    alignItems: "center",
    gap: "3px",
    height: "28px",
  },
  waveBar: {
    width: "3px",
    borderRadius: "2px",
    background: "var(--danger)",
    animation: "waveBar 0.8s ease-in-out infinite",
    transformOrigin: "bottom",
  },
  recordingText: {
    fontSize: "0.875rem",
    color: "var(--danger)",
    fontWeight: 600,
  },
  aiSpeakingBanner: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "12px 20px",
    borderRadius: "var(--radius)",
    background: "rgba(124,111,239,0.08)",
    border: "1px solid rgba(124,111,239,0.2)",
    animation: "fadeSlideUp 0.3s ease",
    flexShrink: 0,
  },
  aiSpeakingText: {
    fontSize: "0.875rem",
    color: "var(--accent)",
    fontWeight: 600,
  },
  transcriptArea: {
    flex: 1,
    minHeight: 0,
    overflow: "hidden",
  },
};
