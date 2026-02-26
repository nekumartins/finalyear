/**
 * HistoryPage — Lists past debate sessions with richer cards, mode badge, and empty state CTA.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

interface SessionSummary {
  id: string;
  topic: string;
  mode: string;
  started_at: string | null;
  duration_seconds: number | null;
  user_wpm: number | null;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(secs: number) {
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function HistoryPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetch("/api/sessions")
      .then((r) => r.json())
      .then((data) => {
        setSessions(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={styles.loadingWrap}>
        <div className="spinner" />
        <span style={{ color: "var(--text-secondary)" }}>Loading sessions…</span>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      {/* Page header */}
      <div style={styles.pageHeader}>
        <div>
          <h1 style={styles.pageTitle}>Session History</h1>
          <p style={styles.pageSubtitle}>Review your past debates and track improvement</p>
        </div>
        <button
          className="btn-primary"
          onClick={() => navigate("/")}
          style={styles.newBtn}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style={{ verticalAlign: "middle" }}>
            <path d="M12 5v14M5 12h14" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
          New Debate
        </button>
      </div>

      {sessions.length === 0 ? (
        /* ── Empty state ── */
        <div style={styles.empty}>
          <div style={styles.emptyIllustration}>
            <svg width="72" height="72" viewBox="0 0 100 100" fill="none">
              <circle cx="50" cy="50" r="46" stroke="var(--border)" strokeWidth="3" />
              <path d="M34 62c0-8.8 7.2-16 16-16s16 7.2 16 16" stroke="var(--border)" strokeWidth="3" strokeLinecap="round" />
              <circle cx="50" cy="38" r="8" stroke="var(--border)" strokeWidth="3" />
            </svg>
          </div>
          <h2 style={styles.emptyTitle}>No sessions yet</h2>
          <p style={styles.emptyDesc}>
            Complete a debate session and it will appear here with full analytics.
          </p>
          <button className="btn-primary" onClick={() => navigate("/")}>
            Start your first debate
          </button>
        </div>
      ) : (
        /* ── Session list ── */
        <div style={styles.list}>
          {sessions.map((s, idx) => (
            <div
              key={s.id}
              className="glass"
              style={{ ...styles.card, animationDelay: `${idx * 0.06}s` }}
              onClick={() => (window.location.href = `/history/${s.id}`)}
            >
              {/* Top row */}
              <div style={styles.cardTop}>
                <div style={styles.cardIndex}>#{idx + 1}</div>
                <h3 style={styles.cardTopic}>{s.topic}</h3>
                <span
                  style={{
                    ...styles.modeBadge,
                    background:
                      s.mode === "cloud"
                        ? "rgba(124,111,239,0.15)"
                        : "rgba(91,142,240,0.15)",
                    border:
                      s.mode === "cloud"
                        ? "1px solid rgba(124,111,239,0.3)"
                        : "1px solid rgba(91,142,240,0.3)",
                    color:
                      s.mode === "cloud" ? "var(--accent)" : "var(--accent-2)",
                  }}
                >
                  {s.mode === "cloud" ? "☁️ Cloud" : "⚡ Edge"}
                </span>
              </div>

              {/* Meta row */}
              <div style={styles.cardMeta}>
                {s.started_at && (
                  <span style={styles.metaItem}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ verticalAlign: "middle", marginRight: 4 }}>
                      <rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="2" />
                      <path d="M8 2v4M16 2v4M3 10h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                    {formatDate(s.started_at)}
                  </span>
                )}
                {s.duration_seconds != null && (
                  <span style={styles.metaItem}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ verticalAlign: "middle", marginRight: 4 }}>
                      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
                      <path d="M12 7v5l3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                    {formatDuration(s.duration_seconds)}
                  </span>
                )}
                {s.user_wpm != null && (
                  <span style={styles.metaItem}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ verticalAlign: "middle", marginRight: 4 }}>
                      <path d="M12 18.5A6.5 6.5 0 1112 5.5a6.5 6.5 0 010 13z" stroke="currentColor" strokeWidth="2" />
                      <path d="M12 12l-2-2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                    {Math.round(s.user_wpm)} WPM
                  </span>
                )}
              </div>

              {/* Chevron */}
              <svg
                style={styles.chevron}
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
              >
                <path
                  d="M9 6l6 6-6 6"
                  stroke="var(--text-muted)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "28px",
    animation: "fadeSlideUp 0.4s ease",
  },
  loadingWrap: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "16px",
    padding: "80px 0",
    color: "var(--text-secondary)",
  },
  pageHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
    flexWrap: "wrap",
    gap: "12px",
  },
  pageTitle: {
    fontSize: "1.9rem",
    fontWeight: 800,
    letterSpacing: "-0.02em",
  },
  pageSubtitle: {
    color: "var(--text-secondary)",
    marginTop: "4px",
    fontSize: "0.9rem",
  },
  newBtn: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "10px 20px",
    fontSize: "0.875rem",
  },
  list: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  card: {
    display: "flex",
    alignItems: "center",
    gap: "16px",
    padding: "18px 22px",
    cursor: "pointer",
    transition: "transform 0.2s, box-shadow 0.2s, border-color 0.2s",
    animation: "fadeSlideUp 0.35s ease both",
    position: "relative",
  },
  cardTop: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flex: 1,
    flexWrap: "wrap",
    minWidth: 0,
  },
  cardIndex: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
    fontWeight: 700,
    minWidth: "26px",
  },
  cardTopic: {
    fontSize: "0.95rem",
    fontWeight: 600,
    flex: 1,
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    letterSpacing: "-0.01em",
  },
  modeBadge: {
    fontSize: "0.72rem",
    fontWeight: 700,
    padding: "4px 10px",
    borderRadius: "20px",
    flexShrink: 0,
    whiteSpace: "nowrap",
  },
  cardMeta: {
    display: "flex",
    gap: "16px",
    flexShrink: 0,
    flexWrap: "wrap",
  },
  metaItem: {
    fontSize: "0.78rem",
    color: "var(--text-muted)",
    display: "flex",
    alignItems: "center",
    whiteSpace: "nowrap",
  },
  chevron: {
    flexShrink: 0,
    transition: "transform 0.2s",
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
  emptyIllustration: {
    opacity: 0.4,
    marginBottom: "8px",
  },
  emptyTitle: {
    fontSize: "1.4rem",
    fontWeight: 700,
  },
  emptyDesc: {
    color: "var(--text-secondary)",
    maxWidth: "360px",
    lineHeight: 1.65,
  },
};
