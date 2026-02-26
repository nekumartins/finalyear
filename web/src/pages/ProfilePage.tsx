import React, { useEffect, useMemo, useState } from "react";
import { useAuthStore } from "../stores/authStore";
import { useAppStore } from "../stores/appStore";

interface SessionSummary {
  id: string;
  topic: string;
  user_wpm: number | null;
}

export function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const storedProfileName = useAppStore((s) => s.profileName);
  const setProfileName = useAppStore((s) => s.setProfileName);
  const [nameInput, setNameInput] = useState(storedProfileName || user?.name || "");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    fetch("/api/sessions?limit=30", {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setSessions(Array.isArray(data) ? data : []));
  }, []);

  const profileName = storedProfileName || user?.name || "Debater";

  const stats = useMemo(() => {
    const count = sessions.length;
    const avgWpmValues = sessions.filter((s) => s.user_wpm != null).map((s) => s.user_wpm as number);
    const avgWpm = avgWpmValues.length
      ? Math.round(avgWpmValues.reduce((a, b) => a + b, 0) / avgWpmValues.length)
      : 0;
    return { count, avgWpm };
  }, [sessions]);

  return (
    <div style={styles.page}>
      <div className="glass" style={styles.headerCard}>
        <div style={styles.avatar}>{profileName.slice(0, 2).toUpperCase()}</div>
        <div style={styles.identity}>
          <h1 style={styles.name}>{profileName}</h1>
          <p style={styles.meta}>{user?.email || "No email"} · {user?.auth_provider || "local"}</p>
        </div>
      </div>

      <div style={styles.grid}>
        <section className="glass" style={styles.panel}>
          <h2 style={styles.panelTitle}>Public Profile</h2>
          <p style={styles.help}>This name is shown across your dashboard and local session summaries.</p>
          <label style={styles.label}>Display Name</label>
          <input
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            placeholder="Set your display name"
          />
          <button
            className="btn-primary"
            style={{ width: "fit-content", marginTop: "12px" }}
            onClick={() => setProfileName(nameInput.trim())}
          >
            Save Profile
          </button>
        </section>

        <section className="glass" style={styles.panel}>
          <h2 style={styles.panelTitle}>Performance Snapshot</h2>
          <div style={styles.metricList}>
            <div style={styles.metricRow}><span>Total Sessions</span><strong>{stats.count}</strong></div>
            <div style={styles.metricRow}><span>Average WPM</span><strong>{stats.avgWpm || "-"}</strong></div>
            <div style={styles.metricRow}><span>Account Type</span><strong>{user?.auth_provider || "local"}</strong></div>
          </div>
        </section>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
    animation: "fadeSlideUp 0.35s ease",
  },
  headerCard: {
    padding: "22px",
    display: "flex",
    alignItems: "center",
    gap: "14px",
  },
  avatar: {
    width: "56px",
    height: "56px",
    borderRadius: "14px",
    background: "var(--gradient)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "1rem",
    fontWeight: 800,
  },
  identity: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  name: {
    fontSize: "1.4rem",
    letterSpacing: "-0.02em",
  },
  meta: {
    color: "var(--text-secondary)",
    fontSize: "0.85rem",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "12px",
  },
  panel: {
    padding: "18px",
  },
  panelTitle: {
    fontSize: "1rem",
    marginBottom: "8px",
  },
  help: {
    color: "var(--text-secondary)",
    fontSize: "0.86rem",
    marginBottom: "12px",
  },
  label: {
    display: "block",
    marginBottom: "7px",
    color: "var(--text-secondary)",
    fontSize: "0.8rem",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  metricList: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    marginTop: "10px",
  },
  metricRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "10px 12px",
    border: "1px solid var(--border)",
    borderRadius: "10px",
    background: "var(--bg-glass)",
    fontSize: "0.9rem",
  },
};
