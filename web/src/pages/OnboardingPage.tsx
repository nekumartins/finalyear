import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "../stores/appStore";
import type { SessionMode } from "../stores/debateStore";

type DebatePosition = "for" | "against";
type CoachingGoal = "confidence" | "speed" | "structure";

const goalOptions: Array<{ id: CoachingGoal; title: string; desc: string; icon: string }> = [
  {
    id: "confidence",
    title: "Confidence",
    desc: "Practice speaking assertively under pressure.",
    icon: "🎯",
  },
  {
    id: "speed",
    title: "Pacing",
    desc: "Improve speaking rhythm and response timing.",
    icon: "⏱️",
  },
  {
    id: "structure",
    title: "Argument Flow",
    desc: "Build tighter reasoning and rebuttal structure.",
    icon: "🧠",
  },
];

export function OnboardingPage() {
  const navigate = useNavigate();
  const onboardingCompleted = useAppStore((s) => s.onboardingCompleted);
  const completeOnboarding = useAppStore((s) => s.completeOnboarding);
  const [preferredMode, setPreferredMode] = useState<SessionMode>("cloud");
  const [preferredPosition, setPreferredPosition] = useState<DebatePosition>("for");
  const [coachingGoal, setCoachingGoal] = useState<CoachingGoal>("confidence");

  useEffect(() => {
    if (onboardingCompleted) {
      navigate("/dashboard");
    }
  }, [onboardingCompleted, navigate]);

  const summary = useMemo(() => {
    const modeLabel = preferredMode === "cloud" ? "Cloud" : "Edge";
    const positionLabel = preferredPosition === "for" ? "for" : "against";
    const goalLabel = goalOptions.find((g) => g.id === coachingGoal)?.title ?? "Confidence";
    return `${modeLabel} mode, argue ${positionLabel}, focus on ${goalLabel}.`;
  }, [preferredMode, preferredPosition, coachingGoal]);

  const handleContinue = () => {
    completeOnboarding({ preferredMode, preferredPosition, coachingGoal });
    navigate("/dashboard");
  };

  return (
    <div style={styles.page}>
      <div className="glass" style={styles.card}>
        <div style={styles.header}>
          <div style={styles.kicker}>Welcome</div>
          <h1 style={styles.title}>Set Up Your Debate Workspace</h1>
          <p style={styles.subtitle}>
            Choose your defaults once. You can change these later in Settings.
          </p>
        </div>

        <div style={styles.section}>
          <label style={styles.label}>Preferred Processing Mode</label>
          <div style={styles.choiceRow}>
            <button
              style={{ ...styles.choice, ...(preferredMode === "cloud" ? styles.choiceActive : {}) }}
              onClick={() => setPreferredMode("cloud")}
            >
              ☁️ Cloud
              <span style={styles.choiceMeta}>Higher quality transcription</span>
            </button>
            <button
              style={{ ...styles.choice, ...(preferredMode === "edge" ? styles.choiceActive2 : {}) }}
              onClick={() => setPreferredMode("edge")}
            >
              ⚡ Edge
              <span style={styles.choiceMeta}>Lower latency local mode</span>
            </button>
          </div>
        </div>

        <div style={styles.section}>
          <label style={styles.label}>Default Stance</label>
          <div style={styles.choiceRow}>
            <button
              style={{ ...styles.choice, ...(preferredPosition === "for" ? styles.choiceSuccess : {}) }}
              onClick={() => setPreferredPosition("for")}
            >
              👍 For
              <span style={styles.choiceMeta}>You defend the motion</span>
            </button>
            <button
              style={{ ...styles.choice, ...(preferredPosition === "against" ? styles.choiceDanger : {}) }}
              onClick={() => setPreferredPosition("against")}
            >
              👎 Against
              <span style={styles.choiceMeta}>You challenge the motion</span>
            </button>
          </div>
        </div>

        <div style={styles.section}>
          <label style={styles.label}>Primary Coaching Goal</label>
          <div style={styles.goalGrid}>
            {goalOptions.map((goal) => (
              <button
                key={goal.id}
                style={{ ...styles.goalCard, ...(coachingGoal === goal.id ? styles.goalCardActive : {}) }}
                onClick={() => setCoachingGoal(goal.id)}
              >
                <span style={styles.goalIcon}>{goal.icon}</span>
                <span style={styles.goalTitle}>{goal.title}</span>
                <span style={styles.goalDesc}>{goal.desc}</span>
              </button>
            ))}
          </div>
        </div>

        <div style={styles.footer}>
          <p style={styles.summary}>{summary}</p>
          <button className="btn-primary" style={styles.cta} onClick={handleContinue}>
            Enter Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    padding: "40px 20px",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },
  card: {
    width: "100%",
    maxWidth: "920px",
    padding: "34px",
    display: "flex",
    flexDirection: "column",
    gap: "26px",
  },
  header: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  kicker: {
    fontSize: "0.72rem",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "var(--accent)",
    fontWeight: 700,
  },
  title: {
    fontSize: "clamp(1.5rem, 3vw, 2.2rem)",
    letterSpacing: "-0.02em",
  },
  subtitle: {
    color: "var(--text-secondary)",
    maxWidth: "560px",
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  label: {
    fontSize: "0.75rem",
    textTransform: "uppercase",
    letterSpacing: "0.07em",
    color: "var(--text-secondary)",
    fontWeight: 600,
  },
  choiceRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "10px",
  },
  choice: {
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    background: "var(--bg-glass)",
    color: "var(--text-primary)",
    minHeight: "82px",
    textAlign: "left",
    padding: "14px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    fontSize: "0.95rem",
    fontWeight: 700,
  },
  choiceMeta: {
    fontSize: "0.78rem",
    color: "var(--text-secondary)",
    fontWeight: 500,
  },
  choiceActive: {
    border: "1px solid rgba(124,111,239,0.45)",
    background: "rgba(124,111,239,0.16)",
    color: "var(--accent)",
  },
  choiceActive2: {
    border: "1px solid rgba(91,142,240,0.45)",
    background: "rgba(91,142,240,0.16)",
    color: "var(--accent-2)",
  },
  choiceSuccess: {
    border: "1px solid rgba(52,211,153,0.45)",
    background: "rgba(52,211,153,0.14)",
    color: "var(--success)",
  },
  choiceDanger: {
    border: "1px solid rgba(248,113,113,0.45)",
    background: "rgba(248,113,113,0.14)",
    color: "var(--danger)",
  },
  goalGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "10px",
  },
  goalCard: {
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    background: "var(--bg-glass)",
    color: "var(--text-primary)",
    textAlign: "left",
    padding: "14px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    minHeight: "124px",
  },
  goalCardActive: {
    border: "1px solid rgba(124,111,239,0.45)",
    background: "rgba(124,111,239,0.16)",
    boxShadow: "0 0 18px rgba(124,111,239,0.2)",
  },
  goalIcon: {
    fontSize: "1.25rem",
  },
  goalTitle: {
    fontWeight: 700,
    fontSize: "0.92rem",
  },
  goalDesc: {
    color: "var(--text-secondary)",
    fontSize: "0.8rem",
    lineHeight: 1.4,
  },
  footer: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "14px",
    flexWrap: "wrap",
    paddingTop: "8px",
    borderTop: "1px solid var(--border)",
  },
  summary: {
    color: "var(--text-secondary)",
    fontSize: "0.9rem",
  },
  cta: {
    minWidth: "190px",
  },
};
