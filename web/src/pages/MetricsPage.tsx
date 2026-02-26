/**
 * MetricsPage — Post-session analytics dashboard with score ring, glass cards, styled transcript.
 */
import React from "react";
import { useNavigate } from "react-router-dom";
import { useDebateStore } from "../stores/debateStore";
import { MetricsCard } from "../components/MetricsCard";

/** Animated circular progress ring for talk ratio */
function TalkRatioRing({ ratio }: { ratio: number }) {
  const pct = Math.round(ratio * 100);
  const r = 52;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - ratio);

  return (
    <div style={ringStyles.wrapper}>
      <svg width="140" height="140" viewBox="0 0 140 140">
        {/* Track */}
        <circle cx="70" cy="70" r={r} fill="none" stroke="var(--border)" strokeWidth="10" />
        {/* Progress */}
        <circle
          cx="70"
          cy="70"
          r={r}
          fill="none"
          stroke="url(#ringGrad)"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 70 70)"
          style={{ transition: "stroke-dashoffset 1s ease" }}
        />
        <defs>
          <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#a78bfa" />
            <stop offset="100%" stopColor="#5b8ef0" />
          </linearGradient>
        </defs>
        {/* Center text */}
        <text
          x="70"
          y="64"
          textAnchor="middle"
          fill="var(--text-primary)"
          fontSize="26"
          fontWeight="800"
          fontFamily="Plus Jakarta Sans, sans-serif"
        >
          {pct}%
        </text>
        <text
          x="70"
          y="82"
          textAnchor="middle"
          fill="var(--text-muted)"
          fontSize="11"
          fontFamily="Plus Jakarta Sans, sans-serif"
        >
          Talk Ratio
        </text>
      </svg>
    </div>
  );
}

const ringStyles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "24px",
    background: "var(--bg-glass)",
    backdropFilter: "blur(16px)",
    WebkitBackdropFilter: "blur(16px)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-lg)",
    boxShadow: "0 0 40px rgba(124,111,239,0.1)",
  },
};

export function MetricsPage() {
  const navigate = useNavigate();
  const { metrics, topic, transcript } = useDebateStore();

  if (!metrics) {
    return (
      <div style={styles.empty}>
        <div style={styles.emptyIcon}>📊</div>
        <h2 style={styles.emptyTitle}>No session data yet</h2>
        <p style={styles.emptyDesc}>Complete a debate session to see your metrics here.</p>
        <button className="btn-primary" onClick={() => navigate("/new-debate")}>
          Start a Debate
        </button>
      </div>
    );
  }

  const minutes = Math.floor(metrics.durationSeconds / 60);
  const seconds = Math.round(metrics.durationSeconds % 60);

  return (
    <div style={styles.page}>
      {/* ── Top: score hero + metric grid side by side ── */}
      <div style={styles.heroRow}>
        {/* Ring */}
        <TalkRatioRing ratio={metrics.userTalkRatio} />

        {/* Metric cards */}
        <div style={styles.grid}>
          <MetricsCard icon="⏱️" label="Duration" value={`${minutes}m ${seconds}s`} />
          <MetricsCard icon="🗣️" label="Your WPM" value={Math.round(metrics.userWpm)} color="var(--success)" />
          <MetricsCard icon="🤖" label="AI WPM" value={Math.round(metrics.aiWpm)} />
          <MetricsCard icon="🔄" label="Turns" value={metrics.turnCount} color="var(--accent)" />
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
        </div>
      </div>

      {/* Header */}
      <div style={styles.titleRow}>
        <div>
          <h1 style={styles.pageTitle}>Session Metrics</h1>
          <p style={styles.topicLabel}>{topic}</p>
        </div>
        <div style={styles.actions}>
          <button className="btn-primary" onClick={() => navigate("/new-debate")}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style={{ verticalAlign: "middle", marginRight: 6 }}>
              <circle cx="12" cy="12" r="10" stroke="white" strokeWidth="2" />
              <path d="M10 8l4 4-4 4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            New Debate
          </button>
          <button className="btn-secondary" onClick={() => navigate("/history")}>
            View History
          </button>
        </div>
      </div>

      {/* ── Filler word breakdown ── */}
      {Object.keys(metrics.fillerWords).length > 0 && (
        <div className="glass" style={styles.section}>
          <h3 style={styles.sectionTitle}>Filler Word Breakdown</h3>
          <div style={styles.fillerGrid}>
            {Object.entries(metrics.fillerWords)
              .sort(([, a], [, b]) => b - a)
              .map(([word, count]) => (
                <div key={word} style={styles.fillerPill}>
                  <span style={styles.fillerWord}>"{word}"</span>
                  <span style={styles.fillerCount}>×{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* ── Transcript chat log ── */}
      {transcript.length > 0 && (
        <div className="glass" style={styles.section}>
          <h3 style={styles.sectionTitle}>Full Transcript</h3>
          <div style={styles.transcriptList}>
            {transcript.map((entry, i) => {
              const isUser = entry.speaker === "user";
              return (
                <div
                  key={i}
                  style={{
                    ...styles.transcriptRow,
                    flexDirection: isUser ? "row-reverse" : "row",
                  }}
                >
                  <div
                    style={{
                      ...styles.transcriptAvatar,
                      background: isUser ? "var(--gradient)" : "var(--bg-card)",
                      border: isUser ? "none" : "1px solid var(--border)",
                    }}
                  >
                    {isUser ? "Y" : "A"}
                  </div>
                  <div
                    style={{
                      ...styles.transcriptBubble,
                      background: isUser
                        ? "linear-gradient(135deg,#7c6fef,#5b8ef0)"
                        : "var(--bg-card)",
                      border: isUser ? "none" : "1px solid var(--border)",
                      color: isUser ? "white" : "var(--text-primary)",
                      alignSelf: isUser ? "flex-end" : "flex-start",
                    }}
                  >
                    <span style={styles.transcriptSpeaker}>
                      {isUser ? "You" : "AI Coach"}
                    </span>
                    <p style={styles.transcriptText}>{entry.text}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
    animation: "fadeSlideUp 0.4s ease",
  },
  titleRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
    flexWrap: "wrap",
    gap: "16px",
  },
  pageTitle: {
    fontSize: "1.8rem",
    fontWeight: 800,
    letterSpacing: "-0.02em",
  },
  topicLabel: {
    color: "var(--text-secondary)",
    fontSize: "0.9rem",
    marginTop: "4px",
  },
  heroRow: {
    display: "flex",
    gap: "24px",
    alignItems: "stretch",
    flexWrap: "wrap",
  },
  grid: {
    flex: 1,
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: "12px",
    minWidth: "300px",
  },
  actions: {
    display: "flex",
    gap: "10px",
    alignItems: "center",
  },
  section: {
    padding: "24px",
  },
  sectionTitle: {
    fontSize: "0.78rem",
    color: "var(--text-secondary)",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.07em",
    marginBottom: "16px",
  },
  fillerGrid: {
    display: "flex",
    flexWrap: "wrap",
    gap: "10px",
  },
  fillerPill: {
    display: "flex",
    gap: "8px",
    alignItems: "center",
    padding: "7px 14px",
    borderRadius: "20px",
    background: "rgba(251,191,36,0.1)",
    border: "1px solid rgba(251,191,36,0.25)",
  },
  fillerWord: {
    color: "var(--warning)",
    fontStyle: "italic",
    fontWeight: 600,
    fontSize: "0.875rem",
  },
  fillerCount: {
    fontWeight: 700,
    fontSize: "0.875rem",
    color: "var(--text-primary)",
  },
  transcriptList: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  transcriptRow: {
    display: "flex",
    gap: "10px",
    alignItems: "flex-end",
  },
  transcriptAvatar: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.75rem",
    fontWeight: 700,
    color: "white",
    flexShrink: 0,
  },
  transcriptBubble: {
    maxWidth: "70%",
    padding: "10px 14px",
    borderRadius: "14px",
    boxShadow: "0 2px 10px rgba(0,0,0,0.2)",
  },
  transcriptSpeaker: {
    fontSize: "0.7rem",
    fontWeight: 600,
    opacity: 0.7,
    display: "block",
    marginBottom: "4px",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  transcriptText: {
    fontSize: "0.875rem",
    lineHeight: 1.55,
    margin: 0,
  },
  empty: {
    textAlign: "center",
    padding: "80px 0",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    alignItems: "center",
    animation: "fadeSlideUp 0.4s ease",
  },
  emptyIcon: {
    fontSize: "4rem",
    filter: "grayscale(0.3)",
  },
  emptyTitle: {
    fontSize: "1.5rem",
    fontWeight: 700,
  },
  emptyDesc: {
    color: "var(--text-secondary)",
    maxWidth: "360px",
  },
};
