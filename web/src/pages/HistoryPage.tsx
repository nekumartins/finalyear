/**
 * HistoryPage — Lists past debate sessions from the API.
 */
import React, { useEffect, useState } from "react";

interface SessionSummary {
  id: string;
  topic: string;
  mode: string;
  started_at: string | null;
  duration_seconds: number | null;
  user_wpm: number | null;
}

export function HistoryPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

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
    return <p style={{ color: "var(--text-secondary)" }}>Loading sessions...</p>;
  }

  if (sessions.length === 0) {
    return (
      <div style={styles.empty}>
        <h2>No sessions yet</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          Complete a debate session and it will appear here.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ marginBottom: "24px" }}>📋 Session History</h1>
      <div style={styles.list}>
        {sessions.map((s) => (
          <div
            key={s.id}
            className="card"
            style={styles.card}
            onClick={() => window.location.href = `/history/${s.id}`} // using full reload for simplicity or useNavigate
          >
            <div style={styles.row}>
              <h3 style={styles.topic}>{s.topic}</h3>
              <span style={styles.modeBadge}>
                {s.mode === "cloud" ? "☁️" : "📱"} {s.mode}
              </span>
            </div>
            <div style={styles.meta}>
              {s.started_at && (
                <span>{new Date(s.started_at).toLocaleString()}</span>
              )}
              {s.duration_seconds && (
                <span>⏱️ {Math.round(s.duration_seconds)}s</span>
              )}
              {s.user_wpm && <span>🗣️ {Math.round(s.user_wpm)} WPM</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  list: { display: "flex", flexDirection: "column", gap: "12px" },
  card: { cursor: "pointer" },
  row: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" },
  topic: { fontSize: "1.05rem" },
  modeBadge: {
    fontSize: "0.8rem",
    padding: "4px 10px",
    borderRadius: "12px",
    background: "var(--bg-secondary)",
    color: "var(--text-secondary)",
  },
  meta: {
    display: "flex",
    gap: "16px",
    fontSize: "0.85rem",
    color: "var(--text-secondary)",
  },
  empty: { textAlign: "center", padding: "60px 0" },
};
