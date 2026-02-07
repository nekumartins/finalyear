/**
 * TurnIndicator — Visual feedback for turn-taking state.
 * Shows who's speaking and when the AI is about to respond.
 */
import React from "react";
import { useDebateStore, TurnSignal } from "../stores/debateStore";

const signalConfig: Record<TurnSignal, { label: string; color: string; icon: string }> = {
  user_speaking: { label: "You're speaking", color: "var(--success)", icon: "🎤" },
  user_will_yield: { label: "Wrapping up...", color: "var(--warning)", icon: "⏳" },
  ai_should_speak: { label: "AI responding", color: "var(--accent)", icon: "🤖" },
};

export function TurnIndicator() {
  const turnSignal = useDebateStore((s) => s.turnSignal);
  const confidence = useDebateStore((s) => s.turnConfidence);

  if (!turnSignal) return null;

  const config = signalConfig[turnSignal];

  return (
    <div style={styles.container}>
      <div style={{ ...styles.dot, background: config.color }} />
      <span style={styles.icon}>{config.icon}</span>
      <span style={styles.label}>{config.label}</span>
      <div style={styles.barOuter}>
        <div
          style={{
            ...styles.barInner,
            width: `${confidence * 100}%`,
            background: config.color,
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
    gap: "10px",
    padding: "10px 16px",
    borderRadius: "var(--radius)",
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: "50%",
    animation: "pulse 1.5s infinite",
  },
  icon: { fontSize: "1.1rem" },
  label: { fontSize: "0.9rem", color: "var(--text-secondary)" },
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
    transition: "width 0.2s ease",
  },
};
