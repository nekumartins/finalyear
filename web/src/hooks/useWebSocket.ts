/**
 * useWebSocket — Manages the persistent WebSocket connection to the backend.
 *
 * Handles:
 * - Connect/disconnect lifecycle
 * - Sending typed messages (audio chunks, session control)
 * - Parsing incoming messages and dispatching to Zustand store
 * - Auto-reconnect with exponential backoff
 * - Client-side heartbeat (ping every 15s)
 */
import { useCallback, useEffect, useRef } from "react";
import { useDebateStore } from "../stores/debateStore";

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const getWsOrigin = () => {
  // Optional explicit override (useful when frontend/backend are on different hosts).
  const explicitWs = import.meta.env.VITE_WS_URL as string | undefined;
  if (explicitWs) return trimTrailingSlash(explicitWs);

  // Derive WS origin from configured backend HTTP URL when provided.
  const backendUrl = import.meta.env.VITE_BACKEND_URL as string | undefined;
  if (backendUrl) {
    const parsed = new URL(backendUrl, window.location.origin);
    const protocol = parsed.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${parsed.host}`;
  }

  // Default to current origin in production (single-container deploy).
  return `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
};

const getWsUrl = () => {
  const base = `${getWsOrigin()}/ws/debate`;
  const token = localStorage.getItem("token");
  return token ? `${base}?token=${token}` : base;
};

// Stability constants (Phase 7)
const HEARTBEAT_INTERVAL_MS = 15_000;     // Ping every 15s
const RECONNECT_BASE_DELAY_MS = 1_000;    // Start at 1s
const RECONNECT_MAX_DELAY_MS = 30_000;    // Cap at 30s
const MAX_RECONNECT_ATTEMPTS = 10;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const heartbeatTimer = useRef<ReturnType<typeof setInterval>>();
  const reconnectAttempts = useRef(0);
  const intentionalCloseRef = useRef(false);

  // Track last session info for resume
  const lastSessionRef = useRef<{
    sessionId: string;
    topic: string;
    userPosition: string;
    mode: "cloud" | "edge";
  } | null>(null);

  const {
    setSessionId,
    setStatus,
    setCurrentUserText,
    appendAiText,
    finalizeAiResponse,
    setTurnSignal,
    setMetrics,
  } = useDebateStore();

  // ── Heartbeat ─────────────────────────────────────

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatTimer.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, HEARTBEAT_INTERVAL_MS);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = undefined;
    }
  }, []);

  // ── Connection ────────────────────────────────────

  const connect = useCallback(() => {
    const state = wsRef.current?.readyState;
    if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) return;

    intentionalCloseRef.current = false;
    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;
    let wasOpened = false; // Track if this WS ever completed handshake

    ws.onopen = () => {
      if (wsRef.current !== ws) return;
      wasOpened = true;
      console.log("[WS] Connected");
      reconnectAttempts.current = 0;
      startHeartbeat();
    };

    ws.onmessage = (event) => {
      if (wsRef.current !== ws) return;
      try {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
      } catch (e) {
        console.error("[WS] Parse error:", e);
      }
    };

    ws.onclose = (event) => {
      if (wsRef.current !== ws) return;
      wsRef.current = null;
      stopHeartbeat();

      if (intentionalCloseRef.current) {
        intentionalCloseRef.current = false;
        const status = useDebateStore.getState().status;
        if (status !== "ended") setStatus("idle");
        return;
      }

      // Suppress logs for StrictMode phantom connections (never fully opened)
      if (!wasOpened) return;
      const reason = event.reason ? `, reason=${event.reason}` : "";
      console.log(`[WS] Disconnected (code=${event.code}${reason})`);

      // Auto-reconnect with exponential backoff if session was active
      const status = useDebateStore.getState().status;
      if (status === "active" && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        setStatus("connecting");
        const delay = Math.min(
          RECONNECT_BASE_DELAY_MS * Math.pow(2, reconnectAttempts.current),
          RECONNECT_MAX_DELAY_MS
        );
        reconnectAttempts.current += 1;
        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
        reconnectTimer.current = setTimeout(() => {
          connect();
          // Re-announce session on reconnect — use resume_session so the backend
          // doesn't wipe session state (transcript, STT buffers, history).
          if (lastSessionRef.current) {
            const { sessionId, topic, userPosition, mode } = lastSessionRef.current;
            const checkAndResend = () => {
              if (wsRef.current?.readyState === WebSocket.OPEN) {
                // If we have an existing session ID, try to resume it
                const msgType = sessionId ? "resume_session" : "start_session";
                wsRef.current.send(
                  JSON.stringify({
                    type: msgType,
                    session_id: sessionId || undefined,
                    topic,
                    user_position: userPosition,
                    mode,
                  })
                );
              } else {
                setTimeout(checkAndResend, 100);
              }
            };
            checkAndResend();
          }
        }, delay);
      } else if (status === "active" || status === "connecting") {
        setStatus("idle");
        console.error("[WS] Reconnect attempts exhausted");
      }
    };

    ws.onerror = () => {
      if (wsRef.current !== ws || intentionalCloseRef.current) return;
      // Suppress error for StrictMode phantom connections
      if (!wasOpened) return;
      console.error("[WS] Connection error");
    };
  }, [setStatus, startHeartbeat, stopHeartbeat]);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearTimeout(reconnectTimer.current);
    stopHeartbeat();
    reconnectAttempts.current = MAX_RECONNECT_ATTEMPTS; // Prevent auto-reconnect
    wsRef.current?.close();
    lastSessionRef.current = null;
  }, [stopHeartbeat]);

  const send = useCallback((
    msg: Record<string, unknown>,
    options?: { suppressDisconnectedWarning?: boolean },
  ) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    } else {
      if (!options?.suppressDisconnectedWarning) {
        console.warn("[WS] Cannot send — not connected");
      }
    }
  }, []);

  // ── Typed send helpers ──

  const startSession = useCallback(
    (topic: string, userPosition: string, mode: "cloud" | "edge", ttsProvider?: string, ttsVoice?: string, coachingGoal?: string) => {
      // Save for reconnection
      lastSessionRef.current = { sessionId: "", topic, userPosition, mode };

      setStatus("connecting");
      connect();
      // Wait for connection before sending
      let attempts = 0;
      const checkAndSend = () => {
        if (!wsRef.current) return; // Stop if disconnected/unmounted

        if (wsRef.current.readyState === WebSocket.OPEN) {
          send({
            type: "start_session",
            topic,
            user_position: userPosition,
            mode,
            tts_provider: ttsProvider || "edge-tts",
            tts_voice: ttsVoice || "default",
            coaching_goal: coachingGoal || "confidence",
          });
        } else if (attempts < 50) { // Timeout after ~5s
          attempts++;
          setTimeout(checkAndSend, 100);
        } else {
          console.error("[WS] Connection timeout - could not start session");
        }
      };
      checkAndSend();
    },
    [connect, send, setStatus]
  );

  const sendAudioChunk = useCallback(
    (sessionId: string, chunkB64: string) => {
      send({
        type: "audio_chunk",
        session_id: sessionId,
        chunk_b64: chunkB64,
        timestamp_ms: Date.now(),
        sample_rate: 16000,
      }, { suppressDisconnectedWarning: true });
    },
    [send]
  );

  const endSession = useCallback(
    (sessionId: string) => {
      send({ type: "end_session", session_id: sessionId });
      lastSessionRef.current = null; // Don't reconnect after intentional end
    },
    [send]
  );

  // ── Message handler ──

  const handleMessage = (msg: Record<string, unknown>) => {
    switch (msg.type) {
      case "session_created":
        setSessionId(msg.session_id as string);
        setStatus("active");
        // Update stored session ID for reconnect
        if (lastSessionRef.current) {
          lastSessionRef.current.sessionId = msg.session_id as string;
        }
        break;

      case "transcript_update":
        // Both interim and final STT results just update the live preview.
        // The user turn is committed to the transcript only when the AI
        // actually starts responding (on first ai_response_chunk), which
        // prevents duplicate entries from cumulative is_final updates.
        setCurrentUserText(msg.text as string || "");
        break;

      case "ai_response_chunk": {
        // On the first AI token, commit the user's accumulated text as a
        // single transcript entry — this ensures proper turn alternation.
        const pendingState = useDebateStore.getState();
        if (pendingState.currentUserText.trim() && !pendingState.currentAiText) {
          const uText = pendingState.currentUserText.trim();
          const now = Date.now();
          pendingState.appendTranscript({
            speaker: "user",
            text: uText,
            startMs: now - uText.length * 20,
            endMs: now,
          });
          setCurrentUserText("");
        }

        if (msg.is_final) {
          finalizeAiResponse();
        } else {
          appendAiText(msg.text as string);
        }
        break;
      }

      case "turn_signal":
        setTurnSignal(
          msg.signal as "user_speaking" | "user_will_yield" | "ai_should_speak",
          msg.confidence as number
        );
        break;

      case "tts_audio": {
        // Dispatch to external handler (set by DebatePage)
        const handler = (window as any).__ttsAudioHandler;
        if (handler) handler(msg.audio_b64 as string, msg.is_final as boolean);
        break;
      }

      case "session_metrics": {
        // Commit any remaining user text before ending
        const endState = useDebateStore.getState();
        if (endState.currentUserText.trim()) {
          const uText = endState.currentUserText.trim();
          const now = Date.now();
          endState.appendTranscript({
            speaker: "user",
            text: uText,
            startMs: now - uText.length * 20,
            endMs: now,
          });
          setCurrentUserText("");
        }

        setMetrics({
          durationSeconds: msg.duration_seconds as number,
          userWpm: msg.user_wpm as number,
          aiWpm: msg.ai_wpm as number,
          fillerWordCount: msg.filler_word_count as number,
          fillerWords: msg.filler_words as Record<string, number>,
          avgPauseDurationMs: msg.avg_pause_duration_ms as number,
          turnCount: msg.turn_count as number,
          userTalkRatio: msg.user_talk_ratio as number,
          coachingReport: (msg.coaching_report as any) ?? null,
        });
        break;
      }

      case "error":
        console.error("[WS] Server error:", msg.message);
        break;

      case "pong":
        break;

      default:
        console.warn("[WS] Unknown message type:", msg.type);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => disconnect();
  }, [disconnect]);

  return { connect, disconnect, startSession, sendAudioChunk, endSession, send };
}
