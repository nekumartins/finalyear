/**
 * API configuration constants shared across the mobile app.
 */

// Change this to your machine's IP when testing on a physical device
export const API_BASE_URL = 'http://localhost:8000';
export const WS_URL = 'ws://localhost:8000/ws/debate';

// Audio recording settings (must match backend expectations)
export const AUDIO_CONFIG = {
  sampleRate: 16000,
  channels: 1,           // mono
  bitsPerSample: 16,     // PCM16
  chunkDurationMs: 100,  // send a chunk every 100ms
} as const;

// Heartbeat interval
export const PING_INTERVAL_MS = 15000;
