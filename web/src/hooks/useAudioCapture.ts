/**
 * useAudioCapture — Browser microphone capture via Web Audio API.
 *
 * Captures PCM16 mono 16kHz audio in 100ms chunks, encodes to base64,
 * and calls the provided callback with each chunk.
 *
 * Why 100ms chunks:
 * - Small enough for real-time turn-taking analysis (~200ms human reaction)
 * - Large enough to avoid excessive WebSocket overhead
 * - 16kHz mono PCM16 = 3,200 bytes per chunk = trivial bandwidth
 */
import { useCallback, useRef, useState } from "react";

interface AudioCaptureOptions {
  onChunk: (chunkB64: string) => void;
  sampleRate?: number;
  chunkDurationMs?: number;
}

export function useAudioCapture({
  onChunk,
  sampleRate = 16000,
  chunkDurationMs = 100,
}: AudioCaptureOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  const start = useCallback(async () => {
    try {
      // Request microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;
      setHasPermission(true);

      // Create audio context
      const ctx = new AudioContext({ sampleRate });
      contextRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);

      // ScriptProcessorNode for chunk extraction
      // bufferSize = sampleRate * chunkDurationMs / 1000
      const bufferSize = Math.pow(
        2,
        Math.ceil(Math.log2(sampleRate * (chunkDurationMs / 1000)))
      );
      const processor = ctx.createScriptProcessor(bufferSize, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        const float32 = event.inputBuffer.getChannelData(0);

        // Convert Float32 → PCM16
        const pcm16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
          const s = Math.max(-1, Math.min(1, float32[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        // Encode to base64
        const bytes = new Uint8Array(pcm16.buffer);
        const binary = Array.from(bytes)
          .map((b) => String.fromCharCode(b))
          .join("");
        const b64 = btoa(binary);

        onChunk(b64);
      };

      source.connect(processor);
      processor.connect(ctx.destination);
      setIsRecording(true);
    } catch (err) {
      console.error("[Audio] Failed to start capture:", err);
      setHasPermission(false);
    }
  }, [onChunk, sampleRate, chunkDurationMs]);

  const stop = useCallback(() => {
    processorRef.current?.disconnect();
    contextRef.current?.close();
    streamRef.current?.getTracks().forEach((t) => t.stop());

    processorRef.current = null;
    contextRef.current = null;
    streamRef.current = null;
    setIsRecording(false);
  }, []);

  return { isRecording, hasPermission, start, stop };
}
