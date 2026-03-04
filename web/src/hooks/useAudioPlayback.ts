/**
 * useAudioPlayback — Plays streamed MP3 audio chunks from TTS.
 *
 * Receives base64-encoded MP3 chunks via enqueue(), decodes them,
 * and plays sequentially through Web Audio API.
 *
 * Features:
 * - Queue-based: chunks play in order, no overlap
 * - Supports barge-in: stop() clears queue and halts playback
 * - Handles AudioContext resume (browser autoplay policy)
 */
import { useCallback, useRef, useState } from "react";

export function useAudioPlayback() {
  const [isPlaying, setIsPlaying] = useState(false);
  const contextRef = useRef<AudioContext | null>(null);
  const gainRef = useRef<GainNode | null>(null);
  const queueRef = useRef<ArrayBuffer[]>([]);
  const playingRef = useRef(false);
  const abortRef = useRef(false);

  const getContext = useCallback(() => {
    if (!contextRef.current || contextRef.current.state === "closed") {
      contextRef.current = new AudioContext();
      // Boost volume (2.5x) — Gemini TTS PCM output is quiet on mobile
      const gain = contextRef.current.createGain();
      gain.gain.value = 2.5;
      gain.connect(contextRef.current.destination);
      gainRef.current = gain;
    }
    return contextRef.current;
  }, []);

  const processQueue = useCallback(async () => {
    if (playingRef.current) return;
    playingRef.current = true;
    setIsPlaying(true);

    const ctx = getContext();

    // Resume suspended context (browser autoplay policy)
    if (ctx.state === "suspended") {
      await ctx.resume();
    }

    while (queueRef.current.length > 0 && !abortRef.current) {
      const chunk = queueRef.current.shift();
      if (!chunk || chunk.byteLength === 0) continue;

      try {
        const audioBuffer = await ctx.decodeAudioData(chunk.slice(0));
        await new Promise<void>((resolve, reject) => {
          if (abortRef.current) {
            resolve();
            return;
          }
          const source = ctx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(gainRef.current || ctx.destination);
          source.onended = () => resolve();
          source.start();
          // Store ref for potential stop
          (source as any).__resolve = resolve;
        });
      } catch (e) {
        // Skip un-decodable chunks (partial MP3 frames etc.)
        console.warn("[AudioPlayback] Chunk decode error:", e);
      }
    }

    playingRef.current = false;
    abortRef.current = false;
    setIsPlaying(false);
  }, [getContext]);

  /**
   * Enqueue a base64-encoded audio chunk for playback.
   * Pass empty string / is_final=true to signal end of stream.
   */
  const enqueue = useCallback(
    (audioB64: string) => {
      if (!audioB64) return; // Final marker or empty — ignore

      // Decode base64 → ArrayBuffer
      const binary = atob(audioB64);
      const buffer = new ArrayBuffer(binary.length);
      const view = new Uint8Array(buffer);
      for (let i = 0; i < binary.length; i++) {
        view[i] = binary.charCodeAt(i);
      }

      queueRef.current.push(buffer);

      // Kick off playback if not already running
      if (!playingRef.current) {
        processQueue();
      }
    },
    [processQueue]
  );

  /** Stop playback immediately and clear the queue (barge-in). */
  const stop = useCallback(() => {
    abortRef.current = true;
    queueRef.current = [];
    setIsPlaying(false);
  }, []);

  return { isPlaying, enqueue, stop };
}
