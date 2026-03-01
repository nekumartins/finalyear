/**
 * MetricsCard — Glass card with coloured icon circle, large value, muted label.
 */
import React from "react";

interface MetricsCardProps {
  label: string;
  value: string | number;
  icon: string;
  color?: string;
}

export function MetricsCard({ label, value, icon, color = "var(--accent)" }: MetricsCardProps) {
  // Convert CSS var to a usable rgba for the icon background
  const bgAlpha = "0.12";
  const iconBg = color.startsWith("var(--") ? `${color.replace(")", `-rgb, ${bgAlpha})`).replace("var(--", "rgba(var(--")}` : `${color}20`;

  return (
    <div style={styles.card}>
      <div style={{ ...styles.iconWrap, background: `rgba(0,0,0,0)`, border: `1px solid ${color}40` }}>
        <div style={{ ...styles.iconCircle, background: `${color}1a`, boxShadow: `0 0 12px ${color}40` }}>
          <span style={{ ...styles.iconText, color }}>{icon}</span>
        </div>
      </div>
      <div style={{ ...styles.value, textShadow: `0 0 20px ${color}60` }}>{value}</div>
      <div style={styles.label}>{label}</div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "var(--bg-glass)",
    backdropFilter: "blur(16px)",
    WebkitBackdropFilter: "blur(16px)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "16px 12px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "8px",
    textAlign: "center",
    transition: "transform 0.2s, border-color 0.2s",
    cursor: "default",
    minWidth: 0,
    overflow: "hidden",
  },
  iconWrap: {
    borderRadius: "50%",
    padding: "2px",
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  iconText: {
    fontSize: "1.4rem",
    lineHeight: 1,
  },
  value: {
    fontSize: "clamp(1.25rem, 4vw, 2rem)",
    fontWeight: 800,
    letterSpacing: "-0.02em",
    color: "var(--text-primary)",
    wordBreak: "break-word",
    overflowWrap: "anywhere",
    lineHeight: 1.1,
    width: "100%",
    textAlign: "center",
  },
  label: {
    fontSize: "0.78rem",
    color: "var(--text-secondary)",
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
};
