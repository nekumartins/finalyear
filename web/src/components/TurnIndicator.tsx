/**
 * TurnIndicator — Animated pulsing ring around state icon with glass pill background.
 */
import React from "react";
import { useDebateStore, TurnSignal } from "../stores/debateStore";

const signalConfig: Record<TurnSignal, { label: string; color: string; icon: string; sublabel: string }> = {
  user_speaking: {
    label: "You're speaking",
    sublabel: "Say your argument clearly",
    color: "var(--success)",
    icon: "🎤",
  },
  user_will_yield: {
    label: "Wrapping up…",
    sublabel: "Finishing detection",
    color: "var(--warning)",
    icon: "⏳",
  },
  ai_should_speak: {
    label: "AI responding",
    sublabel: "Listen to the counter-argument",
    color: "var(--accent)",
    icon: "🤖",
  },
};

export function TurnIndicator() {
  const turnSignal = useDebateStore((s) => s.turnSignal);
  const confidence = useDebateStore((s) => s.turnConfidence);

  if (!turnSignal) return null;

  const config = signalConfig[turnSignal];

  return (
    <div style={styles.container}>
      {/* Pulsing ring + icon */}
      <div
        style={{
          ...styles.pulseRing,
          boxShadow: `0 0 0 0 ${config.color}60`,
          animation: "pulseRing 1.8s ease-out infinite",
          border: `2px solid ${config.color}80`,
        }}
      >
        <span style={styles.icon}>{config.icon}</span>
      </div>

      {/* Labels */}
      <div style={styles.labelGroup}>
        <span style={{ ...styles.label, color: config.color }}>{config.label}</span>
        <span style={styles.sublabel}>{config.sublabel}</span>
      </div>

      {/* Confidence bar */}
      <div style={styles.barOuter}>
        <div
          style={{
            ...styles.barInner,
            width: `${confidence * 100}%`,
            background: config.color,
            boxShadow: `0 0 8px ${config.color}80`,
          }}
        />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    padding: "12px 20px",
    borderRadius: "var(--radius)",
    background: "var(--bg-glass)",
    backdropFilter: "blur(16px)",
    WebkitBackdropFilter: "blur(16px)",
    border: "1px solid var(--border)",
    animation: "fadeSlideUp 0.3s ease",
  },
  pulseRing: {
    width: 40,
    height: 40,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    background: "var(--bg-glass)",
  },
  icon: {
    fontSize: "1.1rem",
    lineHeight: 1,
  },
  labelGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    minWidth: 0,
  },
  label: {
    fontSize: "0.9rem",
    fontWeight: 700,
  },
  sublabel: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
  },
  barOuter: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    background: "var(--border)",
    overflow: "hidden",
  },
  barInner: {
    height: "100%",
    borderRadius: 2,
    transition: "width 0.25s ease",
  },
};
