/**
 * HomePage — Session setup with premium hero, animated topic cards, styled toggles.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDebateStore, SessionMode } from "../stores/debateStore";

const SAMPLE_TOPICS = [
  { text: "Social media does more harm than good", emoji: "📱" },
  { text: "Artificial intelligence will replace most jobs", emoji: "🤖" },
  { text: "University education should be free for all", emoji: "🎓" },
  { text: "Climate change policies harm developing nations", emoji: "🌍" },
  { text: "Remote work is better than office work", emoji: "🏡" },
];

const STATS = [
  { value: "5", label: "Debate Topics" },
  { value: "Real-time", label: "AI Feedback" },
  { value: "Instant", label: "Turn Analysis" },
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
      {/* ── Hero ── */}
      <div style={styles.hero}>
        <div style={styles.heroBadge}>
          <span style={styles.heroBadgeDot} />
          AI-Powered Debate Practice
        </div>
        <h1 style={styles.heroTitle}>
          <span className="gradient-text">Sharpen Your</span>
          <br />
          Argument Skills
        </h1>
        <p style={styles.heroSubtitle}>
          Go head-to-head with an AI sparring partner. Get real-time analysis,
          pacing feedback, and instant scoring.
        </p>
        {/* Stats bar */}
        <div style={styles.statsBar}>
          {STATS.map((s) => (
            <div key={s.label} style={styles.statItem}>
              <span style={styles.statValue}>{s.value}</span>
              <span style={styles.statLabel}>{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Setup Card ── */}
      <div className="glass" style={styles.form}>
        {/* Topic input */}
        <div>
          <label style={styles.label}>Debate Topic</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Type your own topic, or pick one below…"
            onKeyDown={(e) => e.key === "Enter" && handleStart()}
          />
        </div>

        {/* Topic cards */}
        <div style={styles.topicGrid}>
          {SAMPLE_TOPICS.map((t) => {
            const isSelected = topic === t.text;
            return (
              <button
                key={t.text}
                onClick={() => setTopic(t.text)}
                style={{
                  ...styles.topicCard,
                  background: isSelected
                    ? "rgba(124,111,239,0.18)"
                    : "var(--bg-glass)",
                  border: isSelected
                    ? "1px solid rgba(124,111,239,0.5)"
                    : "1px solid var(--border)",
                  boxShadow: isSelected
                    ? "0 0 18px rgba(124,111,239,0.2)"
                    : "none",
                  transform: isSelected ? "translateY(-2px)" : "translateY(0)",
                }}
              >
                <span style={styles.topicEmoji}>{t.emoji}</span>
                <span style={styles.topicText}>{t.text}</span>
              </button>
            );
          })}
        </div>

        {/* Stance */}
        <div>
          <label style={styles.label}>Your Stance</label>
          <div style={styles.toggleRow}>
            {(["for", "against"] as const).map((pos) => (
              <button
                key={pos}
                onClick={() => setPosition(pos)}
                style={{
                  ...styles.toggleBtn,
                  background:
                    position === pos
                      ? pos === "for"
                        ? "rgba(52,211,153,0.15)"
                        : "rgba(248,113,113,0.15)"
                      : "var(--bg-glass)",
                  border:
                    position === pos
                      ? pos === "for"
                        ? "1px solid rgba(52,211,153,0.4)"
                        : "1px solid rgba(248,113,113,0.4)"
                      : "1px solid var(--border)",
                  color:
                    position === pos
                      ? pos === "for"
                        ? "var(--success)"
                        : "var(--danger)"
                      : "var(--text-secondary)",
                }}
              >
                <span style={styles.toggleIcon}>{pos === "for" ? "👍" : "👎"}</span>
                <div>
                  <div style={styles.toggleLabel}>
                    {pos === "for" ? "In Favour" : "Against"}
                  </div>
                  <div style={styles.toggleDesc}>
                    {pos === "for"
                      ? "Argue for the motion"
                      : "Argue against it"}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Mode */}
        <div>
          <label style={styles.label}>Processing Mode</label>
          <div style={styles.toggleRow}>
            <button
              onClick={() => setMode("cloud")}
              style={{
                ...styles.toggleBtn,
                background:
                  mode === "cloud"
                    ? "rgba(124,111,239,0.15)"
                    : "var(--bg-glass)",
                border:
                  mode === "cloud"
                    ? "1px solid rgba(124,111,239,0.4)"
                    : "1px solid var(--border)",
                color:
                  mode === "cloud" ? "var(--accent)" : "var(--text-secondary)",
              }}
            >
              <span style={styles.toggleIcon}>☁️</span>
              <div>
                <div style={styles.toggleLabel}>Cloud</div>
                <div style={styles.toggleDesc}>Higher quality, Deepgram STT</div>
              </div>
            </button>
            <button
              onClick={() => setMode("edge")}
              style={{
                ...styles.toggleBtn,
                background:
                  mode === "edge"
                    ? "rgba(91,142,240,0.15)"
                    : "var(--bg-glass)",
                border:
                  mode === "edge"
                    ? "1px solid rgba(91,142,240,0.4)"
                    : "1px solid var(--border)",
                color:
                  mode === "edge" ? "var(--accent-2)" : "var(--text-secondary)",
              }}
            >
              <span style={styles.toggleIcon}>⚡</span>
              <div>
                <div style={styles.toggleLabel}>Edge</div>
                <div style={styles.toggleDesc}>Lower latency, local Whisper</div>
              </div>
            </button>
          </div>
        </div>

        {/* Start button */}
        <button
          className="btn-primary"
          onClick={handleStart}
          disabled={!topic.trim()}
          style={styles.startBtn}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
            <circle cx="12" cy="12" r="10" stroke="white" strokeWidth="2" />
            <path d="M12 8v4M12 8c-1.1 0-2 .9-2 2v4" stroke="white" strokeWidth="2" strokeLinecap="round" />
            <circle cx="12" cy="16" r="1" fill="white" />
          </svg>
          Start Debate
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "40px",
    animation: "fadeSlideUp 0.4s ease",
  },
  hero: {
    textAlign: "center",
    padding: "20px 0 0",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "16px",
  },
  heroBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 16px",
    borderRadius: "20px",
    background: "rgba(124,111,239,0.1)",
    border: "1px solid rgba(124,111,239,0.25)",
    fontSize: "0.78rem",
    fontWeight: 600,
    color: "var(--accent)",
    letterSpacing: "0.04em",
  },
  heroBadgeDot: {
    display: "inline-block",
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "var(--accent)",
    boxShadow: "0 0 6px var(--accent)",
    animation: "pulseRing 1.8s infinite",
  },
  heroTitle: {
    fontSize: "clamp(2.2rem, 5vw, 3.5rem)",
    fontWeight: 800,
    lineHeight: 1.15,
    letterSpacing: "-0.03em",
  },
  heroSubtitle: {
    color: "var(--text-secondary)",
    fontSize: "1.05rem",
    maxWidth: "520px",
    lineHeight: 1.65,
  },
  statsBar: {
    display: "flex",
    gap: "0",
    background: "var(--bg-glass)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    overflow: "hidden",
    marginTop: "8px",
  },
  statItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    padding: "14px 28px",
    borderRight: "1px solid var(--border)",
    gap: "2px",
  },
  statValue: {
    fontSize: "1rem",
    fontWeight: 700,
    color: "var(--text-primary)",
  },
  statLabel: {
    fontSize: "0.72rem",
    color: "var(--text-muted)",
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
    padding: "32px",
  },
  label: {
    display: "block",
    fontSize: "0.78rem",
    color: "var(--text-secondary)",
    textTransform: "uppercase",
    letterSpacing: "0.07em",
    fontWeight: 600,
    marginBottom: "10px",
  },
  topicGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
    gap: "10px",
  },
  topicCard: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: "8px",
    padding: "14px 16px",
    borderRadius: "var(--radius)",
    cursor: "pointer",
    textAlign: "left",
    transition: "all 0.2s ease",
    backdropFilter: "blur(8px)",
  },
  topicEmoji: {
    fontSize: "1.4rem",
  },
  topicText: {
    fontSize: "0.83rem",
    color: "var(--text-secondary)",
    lineHeight: 1.45,
    fontWeight: 500,
  },
  toggleRow: {
    display: "flex",
    gap: "12px",
  },
  toggleBtn: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    gap: "14px",
    padding: "14px 18px",
    borderRadius: "var(--radius)",
    cursor: "pointer",
    transition: "all 0.2s ease",
    textAlign: "left",
    backdropFilter: "blur(8px)",
  },
  toggleIcon: {
    fontSize: "1.5rem",
    flexShrink: 0,
  },
  toggleLabel: {
    fontSize: "0.9rem",
    fontWeight: 700,
    lineHeight: 1.3,
  },
  toggleDesc: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
    marginTop: "2px",
  },
  startBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    padding: "16px",
    fontSize: "1rem",
    fontWeight: 700,
    borderRadius: "var(--radius)",
    marginTop: "4px",
  },
};
