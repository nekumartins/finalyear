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
  overall_score: number | null;
  coaching_goal: string | null;
}

function formatDuration(secs: number | null): string {
  if (secs == null) return "-";
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/* ── Tiny score circle ── */
function ScoreDot({ score }: { score: number }) {
  const color = score >= 75 ? "var(--success)" : score >= 50 ? "var(--warning)" : "var(--danger)";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      width: 30, height: 30, borderRadius: "50%",
      background: `color-mix(in srgb, ${color} 15%, transparent)`,
      border: `2px solid ${color}`,
      fontSize: "0.7rem", fontWeight: 800, color, flexShrink: 0,
    }}>
      {score}
    </span>
  );
}

/* ── SVG sparkline ── */
function Sparkline({ scores }: { scores: number[] }) {
  if (scores.length < 2) return null;
  const h = 48, w = 200;
  const min = Math.min(...scores) - 5;
  const max = Math.max(...scores) + 5;
  const range = max - min || 1;
  const gap = w / (scores.length - 1);

  const pts = scores.map((s, i) => ({
    x: i * gap,
    y: h - ((s - min) / range) * h,
  }));
  const line = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const area = `${line} L${pts[pts.length - 1].x},${h} L0,${h} Z`;

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ overflow: "visible" }}>
      <defs>
        <linearGradient id="sparkGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#7c6fef" />
          <stop offset="100%" stopColor="#5b8ef0" />
        </linearGradient>
        <linearGradient id="sparkFill" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="rgba(124,111,239,0.25)" />
          <stop offset="100%" stopColor="rgba(124,111,239,0)" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#sparkFill)" />
      <path d={line} fill="none" stroke="url(#sparkGrad)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r="4" fill="var(--accent)" stroke="var(--bg-primary)" strokeWidth="2" />
    </svg>
  );
}

/* ── Smart greeting logic ── */
function computeGreeting(firstName: string, sessions: SessionSummary[], coachingGoal: string) {
  const now = new Date();
  const hour = now.getHours();
  const timeGreeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  if (sessions.length === 0) {
    return {
      headline: `${timeGreeting}, ${firstName}`,
      subtitle: "Ready for your first debate? Let's find out where you stand.",
      emoji: "👋",
    };
  }

  const latest = sessions[0];
  const scored = sessions.filter((s) => s.overall_score != null);

  // Streak: consecutive days with sessions (including today)
  const daySet = new Set(
    sessions.filter((s) => s.started_at).map((s) => new Date(s.started_at!).toDateString())
  );
  let streak = 0;
  const d = new Date();
  while (daySet.has(d.toDateString())) {
    streak++;
    d.setDate(d.getDate() - 1);
  }

  // Trend: compare last 3 scored averages vs prior 3
  let trendText = "";
  if (scored.length >= 4) {
    const recent3 = scored.slice(0, 3).reduce((a, s) => a + s.overall_score!, 0) / 3;
    const older = scored.slice(3, 6);
    const prior3 = older.reduce((a, s) => a + (s.overall_score ?? 0), 0) / older.length;
    const delta = Math.round(recent3 - prior3);
    if (delta > 3) trendText = `Your scores are up ${delta} points — keep the momentum!`;
    else if (delta < -3) trendText = `Scores dipped ${Math.abs(delta)} points recently — a focused session can turn it around.`;
  }

  // Days since last session
  const daysSince = latest.started_at
    ? Math.floor((now.getTime() - new Date(latest.started_at).getTime()) / 86400000)
    : null;

  const goalLabel = coachingGoal === "confidence" ? "confidence" : coachingGoal === "speed" ? "pacing" : "argument flow";
  let subtitle = "";
  if (daysSince != null && daysSince >= 3) {
    subtitle = `It's been ${daysSince} days since your last session. Your ${goalLabel} skills miss you!`;
  } else if (trendText) {
    subtitle = trendText;
  } else if (latest.overall_score != null) {
    const topicSnippet = latest.topic.length > 35 ? latest.topic.slice(0, 35) + "…" : latest.topic;
    subtitle = `Last session: scored ${latest.overall_score} on "${topicSnippet}" — ready to beat it?`;
  } else {
    subtitle = "Pick up where you left off — every round sharpens your edge.";
  }

  let emoji = "🎯";
  if (streak >= 5) emoji = "🔥";
  else if (streak >= 3) emoji = "⚡";
  else if (daysSince != null && daysSince >= 3) emoji = "💪";

  const headline = streak >= 2
    ? `${timeGreeting}, ${firstName} — ${streak}-day streak!`
    : `${timeGreeting}, ${firstName}`;

  return { headline, subtitle, emoji };
}

export function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
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

  const firstName = user?.name?.split(" ")[0] ?? "Debater";
  const greeting = useMemo(() => computeGreeting(firstName, sessions, coachingGoal), [firstName, sessions, coachingGoal]);

  const stats = useMemo(() => {
    const total = sessions.length;
    const totalMinutes = sessions.reduce((a, s) => a + ((s.duration_seconds ?? 0) / 60), 0);
    const wpmArr = sessions.filter((s) => s.user_wpm != null).map((s) => s.user_wpm!);
    const avgWpm = wpmArr.length ? Math.round(wpmArr.reduce((a, b) => a + b, 0) / wpmArr.length) : 0;
    const scored = sessions.filter((s) => s.overall_score != null);
    const bestScore = scored.length ? Math.max(...scored.map((s) => s.overall_score!)) : null;
    const bestWpm = wpmArr.length ? Math.max(...wpmArr) : null;
    const recentScores = scored.slice(0, 10).map((s) => s.overall_score!).reverse();
    return { total, totalMinutes: Math.round(totalMinutes), avgWpm, bestScore, bestWpm, recentScores };
  }, [sessions]);

  return (
    <div style={styles.page}>
      {/* ── Hero greeting ── */}
      <section className="glass" style={styles.hero}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={styles.kicker}>{greeting.emoji} Dashboard</p>
          <h1 style={styles.title}>{greeting.headline}</h1>
          <p style={styles.subtitle}>{greeting.subtitle}</p>
        </div>
        <div style={styles.heroActions}>
          <button className="btn-primary" onClick={() => navigate("/new-debate")}>Start Debate</button>
        </div>
      </section>

      {/* ── Stats row ── */}
      <section className="dashboard-stats-row">
        <div className="glass" style={styles.statCard}>
          <span style={styles.statLabel}>Sessions</span>
          <strong style={styles.statValue}>{stats.total}</strong>
        </div>
        <div className="glass" style={styles.statCard}>
          <span style={styles.statLabel}>Practice Time</span>
          <strong style={styles.statValue}>{stats.totalMinutes} min</strong>
        </div>
        <div className="glass" style={styles.statCard}>
          <span style={styles.statLabel}>Avg WPM</span>
          <strong style={styles.statValue}>{stats.avgWpm || "-"}</strong>
        </div>
        {stats.bestScore != null && (
          <div className="glass" style={styles.statCard}>
            <span style={styles.statLabel}>🏆 Best Score</span>
            <strong style={{ ...styles.statValue, color: "var(--success)" }}>{stats.bestScore}</strong>
          </div>
        )}
        {stats.bestWpm != null && (
          <div className="glass" style={styles.statCard}>
            <span style={styles.statLabel}>⚡ Top WPM</span>
            <strong style={{ ...styles.statValue, color: "var(--accent-2)" }}>{Math.round(stats.bestWpm)}</strong>
          </div>
        )}
      </section>

      {/* ── Score trend sparkline ── */}
      {stats.recentScores.length >= 2 && (
        <section className="glass" style={styles.sparkPanel}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h2 style={styles.panelTitle}>Score Trend</h2>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Last {stats.recentScores.length} sessions</span>
          </div>
          <Sparkline scores={stats.recentScores} />
        </section>
      )}

      {/* ── Recent sessions ── */}
      <section className="glass" style={styles.panel}>
        <div style={styles.panelHeader}>
          <h2 style={styles.panelTitle}>Recent Sessions</h2>
          <button style={styles.linkBtn} onClick={() => navigate("/history")}>View all</button>
        </div>

        {loading ? (
          <div style={styles.loadingRow}><div className="spinner" /> Loading sessions…</div>
        ) : sessions.length === 0 ? (
          <div style={styles.empty}>
            <p>No sessions yet — start your first debate to see your progress here.</p>
          </div>
        ) : (
          <div style={styles.sessionList}>
            {sessions.slice(0, 6).map((s) => (
              <button key={s.id} className="dashboard-session-row" onClick={() => navigate(`/history/${s.id}`)}>
                <div style={styles.sessionInfo}>
                  <strong style={styles.sessionTopic}>{s.topic}</strong>
                  <span style={styles.sessionMeta}>
                    {s.started_at ? new Date(s.started_at).toLocaleDateString() : "Unknown date"} · {formatDuration(s.duration_seconds)}
                    {s.user_wpm != null ? ` · ${Math.round(s.user_wpm)} WPM` : ""}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {s.overall_score != null && <ScoreDot score={s.overall_score} />}
                  <span style={styles.sessionMode}>{s.mode === "cloud" ? "☁️" : "⚡"}</span>
                </div>
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
    fontSize: "clamp(1.3rem, 3vw, 1.8rem)",
    letterSpacing: "-0.02em",
    marginTop: "4px",
    lineHeight: 1.3,
  },
  subtitle: {
    marginTop: "8px",
    color: "var(--text-secondary)",
    fontSize: "0.9rem",
    lineHeight: 1.5,
  },
  heroActions: {
    display: "flex",
    gap: "10px",
    flexShrink: 0,
  },
  statCard: {
    padding: "14px 16px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  statLabel: {
    color: "var(--text-secondary)",
    fontSize: "0.72rem",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 600,
  },
  statValue: {
    fontSize: "1.5rem",
    letterSpacing: "-0.02em",
    fontWeight: 700,
  },
  sparkPanel: {
    padding: "20px",
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
    cursor: "pointer",
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
    fontSize: "0.9rem",
  },
  sessionList: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  sessionInfo: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    minWidth: 0,
    flex: 1,
  },
  sessionTopic: {
    fontSize: "0.9rem",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  sessionMeta: {
    fontSize: "0.78rem",
    color: "var(--text-secondary)",
  },
  sessionMode: {
    fontSize: "1rem",
  },
};
