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

    this.ctx = new AudioContext({ sampleRate: this.sampleRate });
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

    // ScriptProcessor gives frame-level PCM access (deprecated but widely supported)
    const bufSize = Math.floor(this.ctx.sampleRate * 0.02); // 20 ms frames
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

    // MediaRecorder captures the full utterance as a Blob
    this._startRecorder();
  }

  /** Stop VAD and release all resources. */
  stop(): void {
    this.silenceTimer && clearTimeout(this.silenceTimer);
    this.processor?.disconnect();
    this.source?.disconnect();
    this.mediaRecorder?.stop();
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
      this._restartRecorder();
      this.onSpeech?.();
    }
  }

  private _onSilenceFrame(): void {
    if (!this.isSpeaking) return;
    if (this.silenceTimer) return;
    this.silenceTimer = setTimeout(() => {
      this.isSpeaking   = false;
      this.silenceTimer = null;
      this._flushRecording();
    }, this.silenceMs);
  }

  private _startRecorder(): void {
    if (!this.stream) return;
    const mimeType = this._bestMime();
    try {
      this.mediaRecorder  = new MediaRecorder(this.stream, { mimeType });
      this.recordedChunks = [];
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) this.recordedChunks.push(e.data);
      };
      this.mediaRecorder.start(100); // collect every 100 ms
    } catch {
      this.mediaRecorder = null;
    }
  }

  private _restartRecorder(): void {
    this.mediaRecorder?.stop();
    this.recordedChunks = [];
    this._startRecorder();
  }

  private _flushRecording(): void {
    if (!this.mediaRecorder) {
      this.onSilence?.(new Blob());
      return;
    }
    this.mediaRecorder.stop();
    // ondataavailable flushes remaining data, then we build the Blob
    setTimeout(() => {
      const mimeType = this._bestMime();
      const blob = new Blob(this.recordedChunks, { type: mimeType });
      this.recordedChunks = [];
      this.onSilence?.(blob);
      this._startRecorder();
    }, 150);
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
