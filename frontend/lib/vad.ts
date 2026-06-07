/**
 * Browser-side Voice Activity Detection using the Web Audio API.
 *
 * Uses a ScriptProcessor (or AudioWorklet fallback) to measure RMS energy
 * of incoming microphone audio and emit speech / silence events.
 *
 * Usage:
 *   const vad = new BrowserVAD({ onSpeech, onSilence, onLevel });
 *   await vad.start();
 *   // … user speaks …
 *   vad.stop();
 */

export interface VADOptions {
  /** Called when speech is detected */
  onSpeech?: () => void;
  /** Called when silence is detected after speech */
  onSilence?: (audioBlob: Blob) => void;
  /** Called every frame with the current audio level 0-1 */
  onLevel?: (level: number) => void;
  /** RMS energy threshold 0-1 to classify as speech (default 0.01) */
  threshold?: number;
  /** Milliseconds of silence before onSilence fires (default 900 ms) */
  silenceMs?: number;
  /** Audio sample rate (default 16 000 Hz) */
  sampleRate?: number;
}

export class BrowserVAD {
  private ctx: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: ScriptProcessorNode | null = null;
  private stream: MediaStream | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private recordedChunks: BlobPart[] = [];

  private isSpeaking = false;
  private silenceTimer: ReturnType<typeof setTimeout> | null = null;
  private closing = false;

  private readonly threshold: number;
  private readonly silenceMs: number;
  private readonly sampleRate: number;
  private readonly onSpeech?: () => void;
  private readonly onSilence?: (blob: Blob) => void;
  private readonly onLevel?: (level: number) => void;

  constructor(opts: VADOptions = {}) {
    this.threshold  = opts.threshold  ?? 0.01;
    this.silenceMs  = opts.silenceMs  ?? 900;
    this.sampleRate = opts.sampleRate ?? 16_000;
    this.onSpeech   = opts.onSpeech;
    this.onSilence  = opts.onSilence;
    this.onLevel    = opts.onLevel;
  }

  /** Request mic access and start VAD. */
  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: this.sampleRate,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    // Do NOT force a sampleRate on the AudioContext: many devices only support
    // their native rate (usually 44.1/48 kHz) and throw `NotSupportedError`
    // when 16 kHz is requested — which silently killed auto-detect. The RMS
    // energy calc below is sample-rate independent, and the captured blob is
    // resampled server-side, so the context rate does not matter here.
    this.ctx = new AudioContext();
    // After `await getUserMedia` the user-gesture context can be lost, leaving
    // the AudioContext in a "suspended" state where `onaudioprocess` never
    // fires — which makes auto-detect appear completely dead. Resume it.
    if (this.ctx.state === "suspended") {
      try {
        await this.ctx.resume();
      } catch {
        /* best-effort; some browsers resume lazily on first audio */
      }
    }
    this.source = this.ctx.createMediaStreamSource(this.stream);

    // ScriptProcessor REQUIRES a power-of-two buffer size (256/512/1024/…).
    // A computed "20 ms frame" (e.g. 320 @16k or 960 @48k) is NOT a power of
    // two and makes createScriptProcessor throw `IndexSizeError`, which used
    // to crash start() and fall back to Push-to-Talk. Use a fixed 1024.
    const bufSize = 1024;
    this.processor = this.ctx.createScriptProcessor(bufSize, 1, 1);

    this.processor.onaudioprocess = (e) => {
      const input  = e.inputBuffer.getChannelData(0);
      const rms    = this._rms(input);
      const level  = Math.min(rms * 10, 1); // normalise to 0-1

      this.onLevel?.(level);

      if (rms > this.threshold) {
        this._onSpeechFrame();
      } else {
        this._onSilenceFrame();
      }
    };

    this.source.connect(this.processor);
    this.processor.connect(this.ctx.destination);

    // NOTE: we do NOT start a recorder here. A fresh recorder is created per
    // utterance in `_beginUtterance()` the moment speech is first detected, so
    // every captured blob is a complete, standalone webm with a valid header.
  }

  /** Stop VAD and release all resources. */
  stop(): void {
    this.closing = true;
    this.silenceTimer && clearTimeout(this.silenceTimer);
    this.processor?.disconnect();
    this.source?.disconnect();
    try {
      if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
        this.mediaRecorder.stop();
      }
    } catch {
      /* ignore */
    }
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.ctx       = null;
    this.processor = null;
    this.source    = null;
    this.stream    = null;
    this.isSpeaking = false;
  }

  get speaking(): boolean {
    return this.isSpeaking;
  }

  // ── Private ──────────────────────────────────────────────────────────────

  private _rms(data: Float32Array): number {
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
    return Math.sqrt(sum / data.length);
  }

  private _onSpeechFrame(): void {
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
    if (!this.isSpeaking) {
      this.isSpeaking = true;
      this._beginUtterance();
      this.onSpeech?.();
    }
  }

  private _onSilenceFrame(): void {
    if (!this.isSpeaking) return;
    if (this.silenceTimer) return;
    this.silenceTimer = setTimeout(() => {
      this.isSpeaking   = false;
      this.silenceTimer = null;
      this._endUtterance();
    }, this.silenceMs);
  }

  /**
   * Start a brand-new MediaRecorder for a single utterance. We do NOT pass a
   * timeslice to `start()`, so the recorder buffers internally and emits ONE
   * `ondataavailable` on `stop()`. The blob is then assembled in `onstop`,
   * guaranteeing a complete, standalone webm container with a valid header
   * (the old stop/restart-with-timeslice approach produced headerless opus
   * fragments that Deepgram decoded to an empty transcript).
   */
  private _beginUtterance(): void {
    if (!this.stream) return;
    const mimeType = this._bestMime();
    try {
      this.recordedChunks = [];
      this.mediaRecorder  = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) this.recordedChunks.push(e.data);
      };
      this.mediaRecorder.onstop = () => {
        const type = mimeType || "audio/webm";
        const blob = new Blob(this.recordedChunks, { type });
        this.recordedChunks = [];
        // Suppress emission during session teardown so a final stray blob
        // doesn't trigger another transcribe/agent turn after the user hangs up.
        if (!this.closing) this.onSilence?.(blob);
      };
      this.mediaRecorder.start(); // no timeslice → single clean clip on stop()
    } catch {
      this.mediaRecorder = null;
    }
  }

  /** Stop the current utterance recorder; `onstop` builds and emits the blob. */
  private _endUtterance(): void {
    try {
      if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
        this.mediaRecorder.stop();
      }
    } catch {
      /* ignore */
    }
  }

  private _bestMime(): string {
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
    return candidates.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
  }
}

/** Convert a MediaRecorder Blob to raw PCM-16 bytes via Web Audio API. */
export async function blobToPcm16(blob: Blob, targetSampleRate = 16_000): Promise<ArrayBuffer> {
  const arrayBuf = await blob.arrayBuffer();
  const ctx      = new OfflineAudioContext(1, 1, targetSampleRate);
  const decoded  = await ctx.decodeAudioData(arrayBuf);

  const frames   = decoded.length;
  const offline  = new OfflineAudioContext(1, frames, targetSampleRate);
  const src      = offline.createBufferSource();
  src.buffer     = decoded;
  src.connect(offline.destination);
  src.start(0);

  const rendered = await offline.startRendering();
  const float32  = rendered.getChannelData(0);

  // Float32 → Int16 (PCM16 LE)
  const pcm16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s     = Math.max(-1, Math.min(1, float32[i]));
    pcm16[i]    = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return pcm16.buffer;
}
