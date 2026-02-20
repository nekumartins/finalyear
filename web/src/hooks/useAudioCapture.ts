/**
 * useAudioCapture — Browser microphone capture via Web Audio API.
 *
 * Captures PCM16 mono 16kHz audio in 100ms chunks, encodes to base64,
 * and calls the provided callback with each chunk.
 *
 * IMPORTANT: Browsers may ignore the requested sampleRate constraint
 * and give the hardware default (44100 or 48000 Hz). This hook detects
 * the mismatch and resamples to the target rate before encoding.
 */
import { useCallback, useRef, useState } from "react";

interface AudioCaptureOptions {
  onChunk: (chunkB64: string) => void;
  sampleRate?: number;
  chunkDurationMs?: number;
}

/**
 * Downsample Float32 audio from srcRate to dstRate using linear interpolation.
 */
function resample(input: Float32Array, srcRate: number, dstRate: number): Float32Array {
  if (srcRate === dstRate) return input;
  const ratio = srcRate / dstRate;
  const outputLength = Math.round(input.length / ratio);
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i++) {
    const srcIndex = i * ratio;
    const low = Math.floor(srcIndex);
    const high = Math.min(low + 1, input.length - 1);
    const frac = srcIndex - low;
    output[i] = input[low] * (1 - frac) + input[high] * frac;
  }
  return output;
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

      // Create audio context at hardware default rate.
      // Firefox requires AudioContext to match hardware rate for MediaStreamSource.
      // We resample to target rate (16kHz) in the onaudioprocess callback.
      const ctx = new AudioContext();
      contextRef.current = ctx;
      const actualRate = ctx.sampleRate;

      console.info(
        `[Audio] Hardware rate: ${actualRate}Hz, target: ${sampleRate}Hz — ${actualRate !== sampleRate ? "will resample" : "no resample needed"
        }`
      );

      const source = ctx.createMediaStreamSource(stream);

      // ScriptProcessorNode for chunk extraction
      // bufferSize based on ACTUAL rate to get ~chunkDurationMs of audio
      const bufferSize = Math.pow(
        2,
        Math.ceil(Math.log2(actualRate * (chunkDurationMs / 1000)))
      );
      const processor = ctx.createScriptProcessor(bufferSize, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        let float32 = event.inputBuffer.getChannelData(0);

        // Resample to target rate if browser gave a different rate
        if (actualRate !== sampleRate) {
          float32 = resample(float32, actualRate, sampleRate);
        }

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
