/**
 * Shared WebSocket Message Types — TypeScript mirror of backend Pydantic schemas.
 * 
 * KEEP IN SYNC with: backend/app/schemas/messages.py
 * Both sides use the "type" field as the message discriminator.
 */

// ─── Enums ───────────────────────────────────────────

export type SessionMode = 'cloud' | 'edge';
export type Speaker = 'user' | 'ai';
export type TurnSignal = 'user_will_yield' | 'user_speaking' | 'ai_should_speak';

// ─── Client → Server ─────────────────────────────────

export interface StartSessionMsg {
  type: 'start_session';
  mode: SessionMode;
  topic: string;
  user_position: string;
}

export interface AudioChunkMsg {
  type: 'audio_chunk';
  session_id: string;
  chunk_b64: string;
  timestamp_ms: number;
  sample_rate: number;
}

export interface EndSessionMsg {
  type: 'end_session';
  session_id: string;
}

export interface PingMsg {
  type: 'ping';
}

// ─── Server → Client ─────────────────────────────────

export interface SessionCreatedMsg {
  type: 'session_created';
  session_id: string;
  topic: string;
  mode: SessionMode;
}

export interface TranscriptUpdateMsg {
  type: 'transcript_update';
  session_id: string;
  text: string;
  is_final: boolean;
  speaker: Speaker;
}

export interface AiResponseChunkMsg {
  type: 'ai_response_chunk';
  session_id: string;
  text: string;
  is_final: boolean;
}

export interface TurnSignalMsg {
  type: 'turn_signal';
  session_id: string;
  signal: TurnSignal;
  confidence: number;
}

export interface TranscriptEntry {
  speaker: Speaker;
  text: string;
  start_ms: number;
  end_ms: number;
}

export interface SessionMetricsMsg {
  type: 'session_metrics';
  session_id: string;
  duration_seconds: number;
  user_wpm: number;
  ai_wpm: number;
  filler_word_count: number;
  filler_words: Record<string, number>;
  avg_pause_duration_ms: number;
  turn_count: number;
  user_talk_ratio: number;
  transcript: TranscriptEntry[];
  latency_report: {
    events: Array<{ name: string; server_ms: number; client_ms?: number }>;
    deltas: Record<string, number>;
    total_events: number;
  };
}

export interface ErrorMsg {
  type: 'error';
  code: string;
  message: string;
}

export interface PongMsg {
  type: 'pong';
}

// ─── Union Types ─────────────────────────────────────

export type ClientMessage =
  | StartSessionMsg
  | AudioChunkMsg
  | EndSessionMsg
  | PingMsg;

export type ServerMessage =
  | SessionCreatedMsg
  | TranscriptUpdateMsg
  | AiResponseChunkMsg
  | TurnSignalMsg
  | SessionMetricsMsg
  | ErrorMsg
  | PongMsg;
