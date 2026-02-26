import React from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "../stores/appStore";

export function SettingsPage() {
  const navigate = useNavigate();
  const {
    preferredMode,
    preferredPosition,
    coachingGoal,
    emailUpdates,
    compactMetrics,
    setPreferredMode,
    setPreferredPosition,
    setCoachingGoal,
    setEmailUpdates,
    setCompactMetrics,
    resetOnboarding,
  } = useAppStore();

  return (
    <div style={styles.page}>
      <section className="glass" style={styles.panel}>
        <h1 style={styles.title}>Settings</h1>
        <p style={styles.subtitle}>Control your default coaching and app behavior.</p>
      </section>

      <section className="glass" style={styles.panel}>
        <h2 style={styles.heading}>Debate Defaults</h2>
        <div style={styles.rowGroup}>
          <label style={styles.label}>Preferred Mode</label>
          <div style={styles.inlineChoices}>
            <button
              style={{ ...styles.pillBtn, ...(preferredMode === "cloud" ? styles.activePill : {}) }}
              onClick={() => setPreferredMode("cloud")}
            >
              ☁️ Cloud
            </button>
            <button
              style={{ ...styles.pillBtn, ...(preferredMode === "edge" ? styles.activePill2 : {}) }}
              onClick={() => setPreferredMode("edge")}
            >
              ⚡ Edge
            </button>
          </div>
        </div>

        <div style={styles.rowGroup}>
          <label style={styles.label}>Default Stance</label>
          <div style={styles.inlineChoices}>
            <button
              style={{ ...styles.pillBtn, ...(preferredPosition === "for" ? styles.successPill : {}) }}
              onClick={() => setPreferredPosition("for")}
            >
              👍 For
            </button>
            <button
              style={{ ...styles.pillBtn, ...(preferredPosition === "against" ? styles.dangerPill : {}) }}
              onClick={() => setPreferredPosition("against")}
            >
              👎 Against
            </button>
          </div>
        </div>

        <div style={styles.rowGroup}>
          <label style={styles.label}>Coaching Goal</label>
          <select value={coachingGoal} onChange={(e) => setCoachingGoal(e.target.value as "confidence" | "speed" | "structure")}> 
            <option value="confidence">Confidence</option>
            <option value="speed">Pacing</option>
            <option value="structure">Argument Flow</option>
          </select>
        </div>
      </section>

      <section className="glass" style={styles.panel}>
        <h2 style={styles.heading}>App Preferences</h2>
        <div style={styles.toggleRow}>
          <div>
            <strong style={styles.toggleTitle}>Email Updates</strong>
            <p style={styles.toggleDesc}>Receive feature update summaries.</p>
          </div>
          <button style={styles.toggleBtn} onClick={() => setEmailUpdates(!emailUpdates)}>
            {emailUpdates ? "On" : "Off"}
          </button>
        </div>

        <div style={styles.toggleRow}>
          <div>
            <strong style={styles.toggleTitle}>Compact Metrics</strong>
            <p style={styles.toggleDesc}>Prefer denser layout on metrics and history pages.</p>
          </div>
          <button style={styles.toggleBtn} onClick={() => setCompactMetrics(!compactMetrics)}>
            {compactMetrics ? "On" : "Off"}
          </button>
        </div>
      </section>

      <section className="glass" style={styles.panel}>
        <h2 style={styles.heading}>Onboarding</h2>
        <p style={styles.subtitle}>Restart the onboarding wizard to redefine your defaults.</p>
        <button
          className="btn-secondary"
          onClick={() => {
            resetOnboarding();
            navigate("/onboarding");
          }}
        >
          Restart Onboarding
        </button>
      </section>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    animation: "fadeSlideUp 0.35s ease",
  },
  panel: {
    padding: "18px",
  },
  title: {
    fontSize: "1.45rem",
    letterSpacing: "-0.02em",
  },
  heading: {
    fontSize: "1rem",
    marginBottom: "12px",
  },
  subtitle: {
    color: "var(--text-secondary)",
    fontSize: "0.88rem",
  },
  rowGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    marginBottom: "14px",
  },
  label: {
    color: "var(--text-secondary)",
    fontSize: "0.75rem",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 600,
  },
  inlineChoices: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
  },
  pillBtn: {
    border: "1px solid var(--border)",
    background: "var(--bg-glass)",
    color: "var(--text-primary)",
    borderRadius: "999px",
    padding: "8px 13px",
    fontSize: "0.85rem",
    fontWeight: 600,
  },
  activePill: {
    border: "1px solid rgba(124,111,239,0.45)",
    color: "var(--accent)",
    background: "rgba(124,111,239,0.14)",
  },
  activePill2: {
    border: "1px solid rgba(91,142,240,0.45)",
    color: "var(--accent-2)",
    background: "rgba(91,142,240,0.14)",
  },
  successPill: {
    border: "1px solid rgba(52,211,153,0.45)",
    color: "var(--success)",
    background: "rgba(52,211,153,0.14)",
  },
  dangerPill: {
    border: "1px solid rgba(248,113,113,0.45)",
    color: "var(--danger)",
    background: "rgba(248,113,113,0.14)",
  },
  toggleRow: {
    border: "1px solid var(--border)",
    borderRadius: "10px",
    background: "var(--bg-glass)",
    padding: "10px 12px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "10px",
    gap: "12px",
  },
  toggleTitle: {
    fontSize: "0.9rem",
  },
  toggleDesc: {
    fontSize: "0.8rem",
    color: "var(--text-secondary)",
    marginTop: "2px",
  },
  toggleBtn: {
    minWidth: "58px",
    borderRadius: "999px",
    padding: "8px 10px",
    border: "1px solid var(--border)",
    background: "var(--bg-secondary)",
    color: "var(--text-primary)",
    fontSize: "0.8rem",
    fontWeight: 700,
  },
};
