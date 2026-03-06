import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useDebateStore } from "../stores/debateStore";
import { Transcript } from "../components/Transcript";

export function SessionPage() {
    const { sessionId } = useParams<{ sessionId: string }>();
    const navigate = useNavigate();
    const { loadSession, topic, metrics, userPosition, mode } = useDebateStore();
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (sessionId) {
            loadSession(sessionId).then((ok) => {
                if (!ok) navigate("/history");
                setLoading(false);
            });
        }
    }, [sessionId, loadSession, navigate]);

    if (loading) {
        return (
            <div style={styles.loading}>
                <div className="spinner"></div>
                <p>Loading session...</p>
            </div>
        );
    }

    return (
        <div style={styles.page}>
            <div style={styles.header}>
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
            </div>

            <div style={styles.content}>
                <div style={styles.main}>
                    <Transcript />
                </div>

                <div style={styles.sidebar}>
                    <h3>Session Metrics</h3>
                    {metrics ? (
                        <div style={styles.metricsGrid}>
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

                    {/* Coaching Report Summary */}
                    {metrics?.coachingReport && (
                        <div style={{ marginTop: "20px" }}>
                            <h3 style={{ fontSize: "0.9rem", marginBottom: "10px" }}>🎯 Coaching</h3>
                            <div style={{
                                textAlign: "center",
                                padding: "12px",
                                background: "var(--bg-secondary)",
                                borderRadius: "10px",
                                marginBottom: "10px",
                            }}>
                                <div style={{ fontSize: "1.5rem", fontWeight: 800 }}>
                                    {metrics.coachingReport.overall_score}
                                </div>
                                <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
                                    Overall Score
                                </div>
                            </div>
                            <p style={{
                                fontSize: "0.8rem",
                                color: "var(--text-secondary)",
                                lineHeight: 1.5,
                                fontStyle: "italic",
                            }}>
                                {metrics.coachingReport.summary}
                            </p>
                        </div>
                    )}
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
    page: {
        height: "calc(100vh - 100px)",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
    },
    loading: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        color: "var(--text-secondary)",
    },
    header: {
        display: "flex",
        alignItems: "center",
        gap: "16px",
    },
    backBtn: {
        background: "none",
        border: "none",
        color: "var(--text-secondary)",
        cursor: "pointer",
        fontSize: "1rem",
        padding: "8px",
    },
    titleInfo: {
        display: "flex",
        flexDirection: "column",
    },
    topic: {
        fontSize: "1.2rem",
        margin: 0,
    },
    badge: {
        fontSize: "0.85rem",
        color: "var(--text-secondary)",
    },
    content: {
        display: "flex",
        flex: 1,
        gap: "24px",
        overflow: "hidden",
    },
    main: {
        flex: 1,
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        overflow: "hidden",
    },
    sidebar: {
        width: "280px",
        background: "var(--bg-card)",
        borderRadius: "var(--radius)",
        padding: "16px",
        border: "1px solid var(--border)",
    },
    metricsGrid: {
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: "12px",
        marginTop: "16px",
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
