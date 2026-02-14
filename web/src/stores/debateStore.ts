/**
 * Debate Store (Zustand)
 *
 * Central state for the entire debate session lifecycle:
 * - Session config (topic, mode, position)
 * - Live transcript
 * - AI response stream
 * - Turn-taking signals
 * - Post-session metrics
 */
import { create } from "zustand";

export type SessionMode = "cloud" | "edge";
export type SessionStatus = "idle" | "connecting" | "active" | "ended";
export type Speaker = "user" | "ai";
export type TurnSignal = "user_speaking" | "user_will_yield" | "ai_should_speak";

export interface TranscriptEntry {
  speaker: Speaker;
  text: string;
  startMs: number;
  endMs: number;
}

export interface SessionMetrics {
  durationSeconds: number;
  userWpm: number;
  aiWpm: number;
  fillerWordCount: number;
  fillerWords: Record<string, number>;
  avgPauseDurationMs: number;
  turnCount: number;
  userTalkRatio: number;
}

interface DebateState {
  // Session config
  topic: string;
  userPosition: string;
  mode: SessionMode;
  sessionId: string | null;
  status: SessionStatus;

  // Live data
  transcript: TranscriptEntry[];
  currentUserText: string;
  currentAiText: string;
  turnSignal: TurnSignal | null;
  turnConfidence: number;

  // Post-session
  metrics: SessionMetrics | null;

  // Actions
  setConfig: (topic: string, position: string, mode: SessionMode) => void;
  setSessionId: (id: string) => void;
  setStatus: (status: SessionStatus) => void;
  appendTranscript: (entry: TranscriptEntry) => void;
  setCurrentUserText: (text: string) => void;
  appendAiText: (token: string) => void;
  finalizeAiResponse: () => void;
  setTurnSignal: (signal: TurnSignal, confidence: number) => void;
  setMetrics: (metrics: SessionMetrics) => void;
  loadSession: (sessionId: string) => Promise<boolean>;
  reset: () => void;
}

const initialState = {
  topic: "",
  userPosition: "for",
  mode: "cloud" as SessionMode,
  sessionId: null as string | null,
  status: "idle" as SessionStatus,
  transcript: [] as TranscriptEntry[],
  currentUserText: "",
  currentAiText: "",
  turnSignal: null as TurnSignal | null,
  turnConfidence: 0,
  metrics: null as SessionMetrics | null,
};

export const useDebateStore = create<DebateState>((set, get) => ({
  ...initialState,

  setConfig: (topic, userPosition, mode) =>
    set({ topic, userPosition, mode }),

  setSessionId: (sessionId) =>
    set({ sessionId }),

  setStatus: (status) =>
    set({ status }),

  appendTranscript: (entry) =>
    set((s) => ({ transcript: [...s.transcript, entry] })),

  setCurrentUserText: (text) =>
    set({ currentUserText: text }),

  appendAiText: (token) =>
    set((s) => ({ currentAiText: s.currentAiText + token })),

  finalizeAiResponse: () => {
    const { currentAiText, transcript } = get();
    if (currentAiText.trim()) {
      const now = Date.now();
      set({
        transcript: [
          ...transcript,
          {
            speaker: "ai",
            text: currentAiText.trim(),
            startMs: now - currentAiText.length * 20, // approximate
            endMs: now,
          },
        ],
        currentAiText: "",
      });
    }
  },

  setTurnSignal: (signal, confidence) =>
    set({ turnSignal: signal, turnConfidence: confidence }),

  setMetrics: (metrics) =>
    set({ metrics, status: "ended" }),

  loadSession: async (sessionId) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/sessions/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return false;
      const data = await res.json();

      set({
        sessionId: data.id,
        topic: data.topic,
        mode: data.mode,
        userPosition: data.user_position,
        status: "ended", // Valid state for viewing history
        transcript: data.transcript || [],
        metrics: {
          durationSeconds: data.duration_seconds,
          userWpm: data.user_wpm,
          aiWpm: data.ai_wpm,
          fillerWordCount: data.filler_word_count,
          fillerWords: data.filler_words || {},
          avgPauseDurationMs: data.avg_pause_duration_ms,
          turnCount: data.turn_count,
          userTalkRatio: data.user_talk_ratio,
        },
      });
      return true;
    } catch (e) {
      console.error("Failed to load session", e);
      return false;
    }
  },

  reset: () => set(initialState),
}));
