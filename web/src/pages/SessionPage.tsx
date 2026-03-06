import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useDebateStore, type CoachingReport } from "../stores/debateStore";
import { Transcript } from "../components/Transcript";

/* ── Coaching report section (full detail) ── */
function CoachingDetail({ report }: { report: CoachingReport }) {
  const scoreColor = (s: number) => s >= 75 ? "var(--success)" : s >= 50 ? "var(--warning)" : "var(--danger)";
  return (
    <div style={{ marginTop: 20 }}>
      <h3 style={sidebarStyles.heading}>🎯 Coaching Report</h3>

      {/* Score */}
      <div style={sidebarStyles.scoreBox}>
        <div style={{ fontSize: "2rem", fontWeight: 800, color: scoreColor(report.overall_score) }}>
          {report.overall_score}
        </div>
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Overall Score
        </div>
        {report.argument_quality != null && (
          <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 6 }}>
            Argument quality: <strong>{report.argument_quality}</strong>/10
          </div>
        )}
      </div>

      {/* Summary */}
      <p style={sidebarStyles.summary}>{report.summary}</p>

      {/* Strengths */}
      {report.strengths.length > 0 && (
        <div style={sidebarStyles.listBlock}>
          <h4 style={sidebarStyles.listLabel}>💪 Strengths</h4>
          {report.strengths.map((s, i) => (
            <div key={i} style={sidebarStyles.listItem}>
              <span style={{ color: "var(--success)", fontWeight: 700, flexShrink: 0 }}>✓</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      )}

      {/* Improvements */}
      {report.improvements.length > 0 && (
        <div style={sidebarStyles.listBlock}>
          <h4 style={sidebarStyles.listLabel}>📈 To Improve</h4>
          {report.improvements.map((s, i) => (
            <div key={i} style={sidebarStyles.listItem}>
              <span style={{ color: "var(--warning)", fontWeight: 700, flexShrink: 0 }}>→</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      )}

      {/* Fallacies */}
      {report.fallacies.length > 0 && (
        <div style={sidebarStyles.listBlock}>
          <h4 style={sidebarStyles.listLabel}>⚠️ Fallacies</h4>
          {report.fallacies.map((s, i) => (
            <div key={i} style={sidebarStyles.listItem}>
              <span style={{
                color: "var(--danger)", fontWeight: 700, flexShrink: 0,
                width: 18, height: 18, borderRadius: "50%",
                background: "rgba(248,113,113,0.15)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "0.7rem",
              }}>!</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      )}

      {/* Tips */}
      {report.tips.length > 0 && (
        <div style={sidebarStyles.listBlock}>
          <h4 style={sidebarStyles.listLabel}>💡 Tips</h4>
          {report.tips.map((s, i) => (
            <div key={i} style={{
              ...sidebarStyles.listItem,
              padding: "8px 12px", borderRadius: 8,
              background: "rgba(124,111,239,0.06)",
              border: "1px solid rgba(124,111,239,0.15)",
            }}>
              <span style={{
                width: 20, height: 20, borderRadius: "50%",
                background: "var(--gradient)", color: "white",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "0.65rem", fontWeight: 700, flexShrink: 0,
              }}>{i + 1}</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const sidebarStyles: Record<string, React.CSSProperties> = {
  heading: { fontSize: "0.9rem", marginBottom: 12 },
  scoreBox: {
    textAlign: "center", padding: 14,
    background: "var(--bg-secondary)", borderRadius: 10,
    marginBottom: 12,
  },
  summary: {
    fontSize: "0.8rem", color: "var(--text-secondary)",
    lineHeight: 1.5, fontStyle: "italic", marginBottom: 16,
  },
  listBlock: { marginBottom: 14 },
  listLabel: {
    fontSize: "0.78rem", fontWeight: 700,
    color: "var(--text-primary)", marginBottom: 8,
  },
  listItem: {
    display: "flex", gap: 8, alignItems: "flex-start",
    fontSize: "0.8rem", lineHeight: 1.45,
    color: "var(--text-secondary)", marginBottom: 6,
  },
};

export function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { loadSession, topic, metrics, userPosition, mode } = useDebateStore();
  const [loading, setLoading] = useState(true);
  const [adjacentIds, setAdjacentIds] = useState<{ prev: string | null; next: string | null }>({ prev: null, next: null });

  // Load session + figure out prev/next
  useEffect(() => {
    if (!sessionId) return;
    loadSession(sessionId).then((ok) => {
      if (!ok) navigate("/history");
      setLoading(false);
    });

    // Fetch session list to compute prev/next
    const token = localStorage.getItem("token");
    fetch("/api/sessions?limit=100", {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.ok ? r.json() : [])
      .then((sessions: { id: string }[]) => {
        const idx = sessions.findIndex((s) => s.id === sessionId);
        if (idx !== -1) {
          setAdjacentIds({
            prev: idx < sessions.length - 1 ? sessions[idx + 1].id : null, // older
            next: idx > 0 ? sessions[idx - 1].id : null, // newer
          });
        }
      })
      .catch(() => {});
  }, [sessionId, loadSession, navigate]);

  const practiceAgain = useCallback(() => {
    if (topic) {
      const { setConfig } = useDebateStore.getState();
      setConfig(topic, userPosition, mode as any);
      navigate("/debate");
    }
  }, [topic, userPosition, mode, navigate]);

  if (loading) {
    return (
      <div style={styles.loading}>
        <div className="spinner"></div>
        <p>Loading session...</p>
      </div>
    );
  }

  return (
    <div className="session-page">
      <div className="session-header">
        <button style={styles.backBtn} onClick={() => navigate("/history")}>
          ← Back
        </button>
        <div style={styles.titleInfo}>
          <h2 style={styles.topic}>{topic}</h2>
          <span style={styles.badge}>
            {mode === "cloud" ? "☁️ Cloud" : "📱 Edge"} · You argued{" "}
            <strong>{userPosition}</strong>
          </span>
        </div>
        {/* Prev / Next nav */}
        <div style={styles.navBtns}>
          {adjacentIds.prev && (
            <button style={styles.navBtn} onClick={() => navigate(`/history/${adjacentIds.prev}`)}>
              ← Older
            </button>
          )}
          {adjacentIds.next && (
            <button style={styles.navBtn} onClick={() => navigate(`/history/${adjacentIds.next}`)}>
              Newer →
            </button>
          )}
        </div>
      </div>

      <div className="session-content">
        <div className="session-main">
          <Transcript />
        </div>

        <div className="session-sidebar">
          <h3>Session Metrics</h3>
          {metrics ? (
            <div className="session-metrics-grid">
              <MetricItem label="Duration" value={`${Math.round(metrics.durationSeconds)}s`} />
              <MetricItem label="Your Speed" value={`${Math.round(metrics.userWpm)} WPM`} />
              <MetricItem label="AI Speed" value={`${Math.round(metrics.aiWpm)} WPM`} />
              <MetricItem label="Turns" value={metrics.turnCount} />
              <MetricItem label="Filler Words" value={metrics.fillerWordCount} />
              <MetricItem label="Talk Ratio" value={`${Math.round(metrics.userTalkRatio * 100)}%`} />
            </div>
          ) : (
            <p style={{ color: "var(--text-secondary)" }}>No metrics available</p>
          )}

          {/* Full coaching report */}
          {metrics?.coachingReport && (
            <CoachingDetail report={metrics.coachingReport} />
          )}

          {/* Practice again CTA */}
          <button
            className="btn-primary"
            style={{ marginTop: 20, width: "100%", padding: "10px 16px", fontSize: "0.85rem" }}
            onClick={practiceAgain}
          >
            🔄 Practice This Topic Again
          </button>
        </div>
      </div>
    </div>
  );
}

function MetricItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={styles.metric}>
      <span style={styles.metricLabel}>{label}</span>
      <span style={styles.metricValue}>{value}</span>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  loading: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    color: "var(--text-secondary)",
  },
  backBtn: {
    background: "none",
    border: "none",
    color: "var(--text-secondary)",
    cursor: "pointer",
    fontSize: "1rem",
    padding: "8px",
    flexShrink: 0,
  },
  titleInfo: {
    display: "flex",
    flexDirection: "column",
    flex: 1,
    minWidth: 0,
  },
  topic: {
    fontSize: "1.2rem",
    margin: 0,
  },
  badge: {
    fontSize: "0.85rem",
    color: "var(--text-secondary)",
  },
  navBtns: {
    display: "flex",
    gap: 8,
    flexShrink: 0,
  },
  navBtn: {
    background: "var(--bg-glass)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    color: "var(--text-secondary)",
    fontSize: "0.78rem",
    padding: "6px 12px",
    cursor: "pointer",
  },
  metric: {
    display: "flex",
    flexDirection: "column",
    background: "var(--bg-secondary)",
    padding: "8px",
    borderRadius: "8px",
  },
  metricLabel: {
    fontSize: "0.75rem",
    color: "var(--text-secondary)",
    marginBottom: "4px",
  },
  metricValue: {
    fontSize: "1rem",
    fontWeight: 600,
  },
};
