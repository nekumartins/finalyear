import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { useAppStore } from "../stores/appStore";

interface SessionSummary {
  id: string;
  topic: string;
  mode: "cloud" | "edge";
  started_at: string | null;
  duration_seconds: number | null;
  user_wpm: number | null;
}

function formatDuration(secs: number | null): string {
  if (secs == null) return "-";
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const preferredMode = useAppStore((s) => s.preferredMode);
  const coachingGoal = useAppStore((s) => s.coachingGoal);

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    fetch("/api/sessions?limit=50", {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setSessions(Array.isArray(data) ? data : []))
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    const total = sessions.length;
    const totalMinutes = sessions.reduce((acc, s) => acc + ((s.duration_seconds ?? 0) / 60), 0);
    const avgWpmRaw = sessions
      .filter((s) => s.user_wpm != null)
      .reduce((acc, s) => acc + (s.user_wpm ?? 0), 0);
    const avgWpmCount = sessions.filter((s) => s.user_wpm != null).length || 1;
    return {
      total,
      totalMinutes: Math.round(totalMinutes),
      avgWpm: Math.round(avgWpmRaw / avgWpmCount),
    };
  }, [sessions]);

  const firstName = user?.name?.split(" ")[0] ?? "Debater";

  return (
    <div style={styles.page}>
      <section className="glass" style={styles.hero}>
        <div>
          <p style={styles.kicker}>Dashboard</p>
          <h1 style={styles.title}>Welcome back, {firstName}</h1>
          <p style={styles.subtitle}>
            Preferred mode: <strong>{preferredMode}</strong> · Coaching focus: <strong>{coachingGoal}</strong>
          </p>
        </div>
        <div style={styles.heroActions}>
          <button className="btn-primary" onClick={() => navigate("/new-debate")}>Start Debate</button>
          <button className="btn-secondary" onClick={() => navigate("/onboarding")}>Update Onboarding</button>
        </div>
      </section>

      <section style={styles.statGrid}>
        <div className="glass" style={styles.statCard}>
          <span style={styles.statLabel}>Sessions Completed</span>
          <strong style={styles.statValue}>{stats.total}</strong>
        </div>
        <div className="glass" style={styles.statCard}>
          <span style={styles.statLabel}>Practice Time</span>
          <strong style={styles.statValue}>{stats.totalMinutes} min</strong>
        </div>
        <div className="glass" style={styles.statCard}>
          <span style={styles.statLabel}>Average WPM</span>
          <strong style={styles.statValue}>{Number.isFinite(stats.avgWpm) ? stats.avgWpm : "-"}</strong>
        </div>
      </section>

      <section className="glass" style={styles.panel}>
        <div style={styles.panelHeader}>
          <h2 style={styles.panelTitle}>Recent Sessions</h2>
          <button style={styles.linkBtn} onClick={() => navigate("/history")}>View all</button>
        </div>

        {loading ? (
          <div style={styles.loadingRow}><div className="spinner" /> Loading sessions…</div>
        ) : sessions.length === 0 ? (
          <div style={styles.empty}>No sessions yet. Start your first debate to populate your dashboard.</div>
        ) : (
          <div style={styles.sessionList}>
            {sessions.slice(0, 6).map((s) => (
              <button key={s.id} style={styles.sessionRow} onClick={() => navigate(`/history/${s.id}`)}>
                <div style={styles.sessionInfo}>
                  <strong style={styles.sessionTopic}>{s.topic}</strong>
                  <span style={styles.sessionMeta}>
                    {s.started_at ? new Date(s.started_at).toLocaleDateString() : "Unknown date"} · {formatDuration(s.duration_seconds)}
                  </span>
                </div>
                <span style={styles.sessionMode}>{s.mode === "cloud" ? "☁️" : "⚡"}</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "18px",
    animation: "fadeSlideUp 0.35s ease",
  },
  hero: {
    padding: "24px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "20px",
    flexWrap: "wrap",
  },
  kicker: {
    fontSize: "0.75rem",
    textTransform: "uppercase",
    letterSpacing: "0.07em",
    color: "var(--accent)",
    fontWeight: 700,
  },
  title: {
    fontSize: "clamp(1.4rem, 3vw, 2rem)",
    letterSpacing: "-0.02em",
    marginTop: "4px",
  },
  subtitle: {
    marginTop: "8px",
    color: "var(--text-secondary)",
    fontSize: "0.92rem",
  },
  heroActions: {
    display: "flex",
    gap: "10px",
  },
  statGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
  },
  statCard: {
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  statLabel: {
    color: "var(--text-secondary)",
    fontSize: "0.78rem",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 600,
  },
  statValue: {
    fontSize: "1.6rem",
    letterSpacing: "-0.02em",
  },
  panel: {
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  panelHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "10px",
  },
  panelTitle: {
    fontSize: "1.05rem",
  },
  linkBtn: {
    background: "transparent",
    color: "var(--accent)",
    fontSize: "0.86rem",
    border: "1px solid rgba(124,111,239,0.28)",
    borderRadius: "20px",
    padding: "7px 12px",
  },
  loadingRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    color: "var(--text-secondary)",
    minHeight: "60px",
  },
  empty: {
    color: "var(--text-secondary)",
    minHeight: "60px",
    display: "flex",
    alignItems: "center",
  },
  sessionList: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  sessionRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    border: "1px solid var(--border)",
    borderRadius: "12px",
    background: "var(--bg-glass)",
    padding: "12px 14px",
    textAlign: "left",
  },
  sessionInfo: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    minWidth: 0,
  },
  sessionTopic: {
    fontSize: "0.9rem",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    maxWidth: "64vw",
  },
  sessionMeta: {
    fontSize: "0.78rem",
    color: "var(--text-secondary)",
  },
  sessionMode: {
    fontSize: "1rem",
  },
};
