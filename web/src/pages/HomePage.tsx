/**
 * HomePage — Session setup: pick topic, stance, and mode, then start.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDebateStore, SessionMode } from "../stores/debateStore";

const SAMPLE_TOPICS = [
  "Social media does more harm than good",
  "Artificial intelligence will replace most jobs",
  "University education should be free for all",
  "Climate change policies harm developing nations",
  "Remote work is better than office work",
];

export function HomePage() {
  const navigate = useNavigate();
  const setConfig = useDebateStore((s) => s.setConfig);
  const reset = useDebateStore((s) => s.reset);

  const [topic, setTopic] = useState("");
  const [position, setPosition] = useState<"for" | "against">("for");
  const [mode, setMode] = useState<SessionMode>("cloud");

  const handleStart = () => {
    if (!topic.trim()) return;
    reset();
    setConfig(topic.trim(), position, mode);
    navigate("/debate");
  };

  return (
    <div style={styles.page}>
      <div style={styles.hero}>
        <h1 style={styles.title}>⚡ AI Debate Coach</h1>
        <p style={styles.subtitle}>
          Practice your arguments against an AI sparring partner with real-time feedback.
        </p>
      </div>

      <div className="card" style={styles.form}>
        {/* Topic */}
        <label style={styles.label}>Debate Topic</label>
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Enter a debate topic..."
          style={styles.input}
        />

        {/* Quick picks */}
        <div style={styles.chips}>
          {SAMPLE_TOPICS.map((t) => (
            <button
              key={t}
              onClick={() => setTopic(t)}
              style={{
                ...styles.chip,
                background: topic === t ? "var(--accent)" : "var(--bg-secondary)",
                color: topic === t ? "white" : "var(--text-secondary)",
              }}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Position */}
        <label style={styles.label}>Your Stance</label>
        <div style={styles.toggleRow}>
          {(["for", "against"] as const).map((pos) => (
            <button
              key={pos}
              onClick={() => setPosition(pos)}
              className={position === pos ? "btn-primary" : "btn-secondary"}
              style={{ flex: 1 }}
            >
              {pos === "for" ? "👍 For" : "👎 Against"}
            </button>
          ))}
        </div>

        {/* Mode */}
        <label style={styles.label}>Processing Mode</label>
        <div style={styles.toggleRow}>
          <button
            onClick={() => setMode("cloud")}
            className={mode === "cloud" ? "btn-primary" : "btn-secondary"}
            style={{ flex: 1 }}
          >
            ☁️ Cloud (Higher Quality)
          </button>
          <button
            onClick={() => setMode("edge")}
            className={mode === "edge" ? "btn-primary" : "btn-secondary"}
            style={{ flex: 1 }}
          >
            📱 Edge (Lower Latency)
          </button>
        </div>

        {/* Start */}
        <button
          className="btn-primary"
          onClick={handleStart}
          disabled={!topic.trim()}
          style={{ marginTop: "16px", width: "100%", padding: "16px", fontSize: "1.1rem" }}
        >
          🎙️ Start Debate
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: "32px" },
  hero: { textAlign: "center", padding: "24px 0" },
  title: { fontSize: "2.5rem", marginBottom: "8px" },
  subtitle: { color: "var(--text-secondary)", fontSize: "1.1rem" },
  form: { display: "flex", flexDirection: "column", gap: "16px" },
  label: {
    fontSize: "0.85rem",
    color: "var(--text-secondary)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    fontWeight: 600,
  },
  input: {
    background: "var(--bg-secondary)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "14px 16px",
    fontSize: "1rem",
    color: "var(--text-primary)",
    outline: "none",
    width: "100%",
  },
  chips: { display: "flex", flexWrap: "wrap", gap: "8px" },
  chip: {
    padding: "8px 14px",
    borderRadius: "20px",
    fontSize: "0.8rem",
    border: "1px solid var(--border)",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  toggleRow: { display: "flex", gap: "12px" },
};
