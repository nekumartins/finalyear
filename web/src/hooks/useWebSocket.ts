/**
 * useWebSocket — Manages the persistent WebSocket connection to the backend.
 *
 * Handles:
 * - Connect/disconnect lifecycle
 * - Sending typed messages (audio chunks, session control)
 * - Parsing incoming messages and dispatching to Zustand store
 * - Auto-reconnect on disconnect
 */
import { useCallback, useEffect, useRef } from "react";
import { useDebateStore } from "../stores/debateStore";

const WS_URL = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/debate`;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const {
    setSessionId,
    setStatus,
    setCurrentUserText,
    appendAiText,
    finalizeAiResponse,
    setTurnSignal,
    setMetrics,
  } = useDebateStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] Connected");
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
      } catch (e) {
        console.error("[WS] Parse error:", e);
      }
    };

    ws.onclose = () => {
      console.log("[WS] Disconnected");
      // Auto-reconnect after 2s if session was active
      const status = useDebateStore.getState().status;
      if (status === "active") {
        reconnectTimer.current = setTimeout(connect, 2000);
      }
    };

    ws.onerror = (err) => {
      console.error("[WS] Error:", err);
    };
  }, []);

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  const send = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    } else {
      console.warn("[WS] Cannot send — not connected");
    }
  }, []);

  // ── Typed send helpers ──

  const startSession = useCallback(
    (topic: string, userPosition: string, mode: "cloud" | "edge") => {
      setStatus("connecting");
      connect();
      // Wait for connection before sending
      const checkAndSend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          send({
            type: "start_session",
            topic,
            user_position: userPosition,
            mode,
          });
        } else {
          setTimeout(checkAndSend, 100);
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
      });
    },
    [send]
  );

  const endSession = useCallback(
    (sessionId: string) => {
      send({ type: "end_session", session_id: sessionId });
    },
    [send]
  );

  // ── Message handler ──

  const handleMessage = (msg: Record<string, unknown>) => {
    switch (msg.type) {
      case "session_created":
        setSessionId(msg.session_id as string);
        setStatus("active");
        break;

      case "transcript_update":
        setCurrentUserText(msg.text as string);
        break;

      case "ai_response_chunk":
        if (msg.is_final) {
          finalizeAiResponse();
        } else {
          appendAiText(msg.text as string);
        }
        break;

      case "turn_signal":
        setTurnSignal(
          msg.signal as "user_speaking" | "user_will_yield" | "ai_should_speak",
          msg.confidence as number
        );
        break;

      case "session_metrics":
        setMetrics({
          durationSeconds: msg.duration_seconds as number,
          userWpm: msg.user_wpm as number,
          aiWpm: msg.ai_wpm as number,
          fillerWordCount: msg.filler_word_count as number,
          fillerWords: msg.filler_words as Record<string, number>,
          avgPauseDurationMs: msg.avg_pause_duration_ms as number,
          turnCount: msg.turn_count as number,
          userTalkRatio: msg.user_talk_ratio as number,
        });
        break;

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
