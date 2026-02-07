/**
 * MetricsPage — Post-session analytics dashboard.
 */
import React from "react";
import { useNavigate } from "react-router-dom";
import { useDebateStore } from "../stores/debateStore";
import { MetricsCard } from "../components/MetricsCard";

export function MetricsPage() {
  const navigate = useNavigate();
  const { metrics, topic, transcript } = useDebateStore();

  if (!metrics) {
    return (
      <div style={styles.empty}>
        <h2>No session data yet</h2>
        <p>Complete a debate session to see your metrics.</p>
        <button className="btn-primary" onClick={() => navigate("/")}>
          Start a Debate
        </button>
      </div>
    );
  }

  const minutes = Math.floor(metrics.durationSeconds / 60);
  const seconds = Math.round(metrics.durationSeconds % 60);

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>📊 Session Metrics</h1>
      <p style={styles.topic}>Topic: {topic}</p>

      {/* Metrics grid */}
      <div style={styles.grid}>
        <MetricsCard icon="⏱️" label="Duration" value={`${minutes}m ${seconds}s`} />
        <MetricsCard icon="🗣️" label="Your WPM" value={Math.round(metrics.userWpm)} color="var(--success)" />
        <MetricsCard icon="🤖" label="AI WPM" value={Math.round(metrics.aiWpm)} />
        <MetricsCard
          icon="🔄"
          label="Turns"
          value={metrics.turnCount}
          color="var(--accent)"
        />
        <MetricsCard
          icon="😬"
          label="Filler Words"
          value={metrics.fillerWordCount}
          color={metrics.fillerWordCount > 10 ? "var(--danger)" : "var(--success)"}
        />
        <MetricsCard
          icon="⏸️"
          label="Avg Pause"
          value={`${Math.round(metrics.avgPauseDurationMs)}ms`}
        />
        <MetricsCard
          icon="📊"
          label="Talk Ratio"
          value={`${Math.round(metrics.userTalkRatio * 100)}%`}
          color="var(--warning)"
        />
      </div>

      {/* Filler word breakdown */}
      {Object.keys(metrics.fillerWords).length > 0 && (
        <div className="card" style={{ marginTop: "24px" }}>
          <h3 style={styles.sectionTitle}>Filler Word Breakdown</h3>
          <div style={styles.fillerGrid}>
            {Object.entries(metrics.fillerWords)
              .sort(([, a], [, b]) => b - a)
              .map(([word, count]) => (
                <div key={word} style={styles.fillerItem}>
                  <span style={styles.fillerWord}>"{word}"</span>
                  <span style={styles.fillerCount}>×{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Transcript review */}
      {transcript.length > 0 && (
        <div className="card" style={{ marginTop: "24px" }}>
          <h3 style={styles.sectionTitle}>Full Transcript</h3>
          <div style={styles.transcriptList}>
            {transcript.map((entry, i) => (
              <div key={i} style={styles.transcriptEntry}>
                <span style={styles.transcriptSpeaker}>
                  {entry.speaker === "user" ? "🎤 You" : "🤖 AI"}
                </span>
                <p style={styles.transcriptText}>{entry.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={styles.actions}>
        <button className="btn-primary" onClick={() => navigate("/")}>
          🎙️ New Debate
        </button>
        <button className="btn-secondary" onClick={() => navigate("/history")}>
          📋 View History
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { display: "flex", flexDirection: "column" },
  title: { fontSize: "1.8rem", marginBottom: "4px" },
  topic: { color: "var(--text-secondary)", marginBottom: "24px" },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
    gap: "16px",
  },
  sectionTitle: {
    marginBottom: "12px",
    color: "var(--text-secondary)",
    fontSize: "0.9rem",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  fillerGrid: { display: "flex", flexWrap: "wrap", gap: "12px" },
  fillerItem: {
    display: "flex",
    gap: "8px",
    alignItems: "center",
    padding: "8px 14px",
    borderRadius: "var(--radius)",
    background: "var(--bg-secondary)",
  },
  fillerWord: { color: "var(--warning)", fontStyle: "italic" },
  fillerCount: { fontWeight: 700 },
  transcriptList: { display: "flex", flexDirection: "column", gap: "12px" },
  transcriptEntry: { display: "flex", flexDirection: "column", gap: "2px" },
  transcriptSpeaker: { fontSize: "0.8rem", color: "var(--text-secondary)" },
  transcriptText: { fontSize: "0.95rem" },
  actions: { display: "flex", gap: "12px", marginTop: "32px" },
  empty: { textAlign: "center", padding: "60px 0", display: "flex", flexDirection: "column", gap: "16px", alignItems: "center" },
};
