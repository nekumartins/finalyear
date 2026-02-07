/**
 * MetricsCard — Displays a single metric with label and value.
 */
import React from "react";

interface MetricsCardProps {
  label: string;
  value: string | number;
  icon: string;
  color?: string;
}

export function MetricsCard({ label, value, icon, color = "var(--accent)" }: MetricsCardProps) {
  return (
    <div style={styles.card}>
      <div style={{ ...styles.icon, color }}>{icon}</div>
      <div style={styles.value}>{value}</div>
      <div style={styles.label}>{label}</div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "8px",
    textAlign: "center",
  },
  icon: { fontSize: "1.5rem" },
  value: { fontSize: "1.75rem", fontWeight: 700 },
  label: { fontSize: "0.85rem", color: "var(--text-secondary)" },
};
