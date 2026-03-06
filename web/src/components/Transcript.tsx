/**
 * Transcript — Live scrolling chat-bubble transcript with avatar circles and typing indicator.
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
      <div style={styles.header}>
        <span style={styles.title}>Live Transcript</span>
        <span style={styles.count}>{transcript.length} turns</span>
      </div>

      <div style={styles.scrollArea}>
        {transcript.map((entry, i) => (
          <TranscriptBubble key={i} entry={entry} />
        ))}

        {/* Live AI streaming (shown before new user speech — AI turn started first) */}
        {currentAiText && (
          <TranscriptBubble
            entry={{ speaker: "ai", text: currentAiText, startMs: 0, endMs: 0 }}
            isPartial
          />
        )}

        {/* Live user text (partial STT) */}
        {currentUserText && (
          <TranscriptBubble
            entry={{ speaker: "user", text: currentUserText, startMs: 0, endMs: 0 }}
            isPartial
          />
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function TranscriptBubble({
  entry,
  isPartial = false,
}: {
  entry: TranscriptEntry;
  isPartial?: boolean;
}) {
  const isUser = entry.speaker === "user";

  return (
    <div
      style={{
        ...styles.row,
        flexDirection: isUser ? "row-reverse" : "row",
        animation: "fadeSlideUp 0.25s ease",
      }}
    >
      {/* Avatar */}
      <div
        style={{
          ...styles.avatar,
          background: isUser ? "var(--gradient)" : "var(--bg-card)",
          border: isUser ? "none" : "1px solid var(--border)",
          boxShadow: isUser ? "0 0 14px var(--accent-glow)" : "none",
        }}
      >
        {isUser ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="8" r="4" fill="white" />
            <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" stroke="white" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <rect x="3" y="3" width="18" height="18" rx="3" stroke="#8888aa" strokeWidth="2" />
            <circle cx="9" cy="10" r="1.5" fill="#8888aa" />
            <circle cx="15" cy="10" r="1.5" fill="#8888aa" />
            <path d="M9 15c.7 1 1.3 1.5 3 1.5s2.3-.5 3-1.5" stroke="#8888aa" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        )}
      </div>

      {/* Bubble */}
      <div className="transcript-bubble-col" style={{ alignSelf: isUser ? "flex-end" : "flex-start" }}>
        <span style={{ ...styles.speakerLabel, textAlign: isUser ? "right" : "left" }}>
          {isUser ? "You" : "AI Coach"}
          {isPartial && " · "}
          {isPartial && <span style={styles.partialTag}>live</span>}
        </span>
        <div
          style={{
            ...styles.bubble,
            background: isUser
              ? "linear-gradient(135deg, #7c6fef 0%, #5b8ef0 100%)"
              : "var(--bg-card)",
            border: isUser ? "none" : "1px solid var(--border)",
            color: isUser ? "white" : "var(--text-primary)",
            alignSelf: isUser ? "flex-end" : "flex-start",
            opacity: isPartial ? 0.75 : 1,
          }}
        >
          <p className="transcript-bubble-text">{entry.text}</p>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    background: "var(--bg-glass)",
    backdropFilter: "blur(16px)",
    WebkitBackdropFilter: "blur(16px)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    overflow: "hidden",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 20px",
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
  },
  title: {
    fontSize: "0.75rem",
    color: "var(--text-secondary)",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.07em",
  },
  count: {
    fontSize: "0.72rem",
    color: "var(--text-muted)",
    background: "var(--bg-glass)",
    border: "1px solid var(--border)",
    padding: "2px 8px",
    borderRadius: "20px",
  },
  scrollArea: {
    flex: 1,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    padding: "20px",
  },
  row: {
    display: "flex",
    gap: "10px",
    alignItems: "flex-end",
  },
  avatar: {
    width: 30,
    height: 30,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  speakerLabel: {
    fontSize: "0.72rem",
    color: "var(--text-muted)",
    fontWeight: 500,
    display: "block",
  },
  partialTag: {
    display: "inline-block",
    background: "var(--accent)",
    color: "white",
    fontSize: "0.68rem",
    padding: "1px 5px",
    borderRadius: "4px",
    fontWeight: 700,
    letterSpacing: "0.05em",
  },
  bubble: {
    padding: "10px 14px",
    borderRadius: "14px",
    boxShadow: "0 2px 12px rgba(0,0,0,0.25)",
  },
};
