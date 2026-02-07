/**
 * Transcript — Live scrolling transcript of the debate.
 */
import React, { useEffect, useRef } from "react";
import { useDebateStore, TranscriptEntry } from "../stores/debateStore";

export function Transcript() {
  const transcript = useDebateStore((s) => s.transcript);
  const currentUserText = useDebateStore((s) => s.currentUserText);
  const currentAiText = useDebateStore((s) => s.currentAiText);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, currentUserText, currentAiText]);

  return (
    <div style={styles.container}>
      <h3 style={styles.title}>Live Transcript</h3>
      <div style={styles.scrollArea}>
        {transcript.map((entry, i) => (
          <TranscriptBubble key={i} entry={entry} />
        ))}

        {/* Live user text (partial STT) */}
        {currentUserText && (
          <div style={{ ...styles.bubble, ...styles.userBubble, opacity: 0.7 }}>
            <span style={styles.speaker}>🎤 You (speaking...)</span>
            <p>{currentUserText}</p>
          </div>
        )}

        {/* Live AI text (streaming) */}
        {currentAiText && (
          <div style={{ ...styles.bubble, ...styles.aiBubble, opacity: 0.7 }}>
            <span style={styles.speaker}>🤖 AI (responding...)</span>
            <p>{currentAiText}</p>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function TranscriptBubble({ entry }: { entry: TranscriptEntry }) {
  const isUser = entry.speaker === "user";
  return (
    <div
      style={{
        ...styles.bubble,
        ...(isUser ? styles.userBubble : styles.aiBubble),
      }}
    >
      <span style={styles.speaker}>
        {isUser ? "🎤 You" : "🤖 AI"}
      </span>
      <p>{entry.text}</p>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
  },
  title: {
    marginBottom: "12px",
    color: "var(--text-secondary)",
    fontSize: "0.85rem",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  scrollArea: {
    flex: 1,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    paddingRight: "8px",
  },
  bubble: {
    padding: "12px 16px",
    borderRadius: "var(--radius)",
    maxWidth: "85%",
  },
  userBubble: {
    alignSelf: "flex-end",
    background: "var(--accent)",
    color: "white",
  },
  aiBubble: {
    alignSelf: "flex-start",
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
  },
  speaker: {
    fontSize: "0.75rem",
    opacity: 0.7,
    display: "block",
    marginBottom: "4px",
  },
};
