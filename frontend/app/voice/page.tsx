"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { authHeaders } from "@/lib/auth";
import { BrowserVAD } from "@/lib/vad";
import {
  Mic, MicOff, PhoneOff,
  Star, Headphones, ShoppingCart, Users, DollarSign, Cpu, Megaphone,
  ChevronLeft, Volume2, Radio, Activity, Zap, AlertCircle, CheckCircle,
} from "lucide-react";
import { formatTime, formatDuration } from "@/lib/utils";

/* ── Types ───────────────────────────────────────────────── */

type VoiceState  = "idle" | "listening" | "processing" | "speaking";
type InputMode   = "ptt" | "vad" | "ws";

interface TranscriptLine {
  id:        string;
  speaker:   "user" | "agent";
  text:      string;
  timestamp: Date;
  provider?: string;
}

interface ProviderStatus {
  stt:    { active: string | null };
  tts:    { active: string | null };
  telephony: { twilio: { configured: boolean }; livekit: { configured: boolean } };
}

/* ── Constants ───────────────────────────────────────────── */

const DEPARTMENTS = [
  { id: "reception",    label: "Reception",     icon: Star,        colorText: "text-amber-400",   colorBg: "bg-amber-500/10",   colorBorder: "border-amber-500/25",   accentRgb: "245,158,11"  },
  { id: "customer_care",label: "Customer Care", icon: Headphones,  colorText: "text-cyan-400",    colorBg: "bg-cyan-500/10",    colorBorder: "border-cyan-500/25",    accentRgb: "6,182,212"   },
  { id: "sales",        label: "Sales",         icon: ShoppingCart,colorText: "text-emerald-400", colorBg: "bg-emerald-500/10", colorBorder: "border-emerald-500/25", accentRgb: "16,185,129"  },
  { id: "hr",           label: "HR",            icon: Users,       colorText: "text-violet-400",  colorBg: "bg-violet-500/10",  colorBorder: "border-violet-500/25",  accentRgb: "167,139,250" },
  { id: "finance",      label: "Finance",       icon: DollarSign,  colorText: "text-rose-400",    colorBg: "bg-rose-500/10",    colorBorder: "border-rose-500/25",    accentRgb: "251,113,133" },
  { id: "technology",   label: "Technology",    icon: Cpu,         colorText: "text-blue-400",    colorBg: "bg-blue-500/10",    colorBorder: "border-blue-500/25",    accentRgb: "96,165,250"  },
  { id: "marketing",    label: "Marketing",     icon: Megaphone,   colorText: "text-orange-400",  colorBg: "bg-orange-500/10",  colorBorder: "border-orange-500/25",  accentRgb: "251,146,60"  },
];

const STATE_LABEL: Record<VoiceState, string> = {
  idle: "IDLE", listening: "LISTENING", processing: "PROCESSING", speaking: "SPEAKING",
};
const STATE_COLOR: Record<VoiceState, string> = {
  idle: "text-slate-500", listening: "text-amber-400", processing: "text-cyan-400", speaking: "text-emerald-400",
};

function genId() { return Math.random().toString(36).slice(2, 10); }
function getDept(id: string) { return DEPARTMENTS.find((d) => d.id === id) ?? DEPARTMENTS[0]; }

/* ── Component ───────────────────────────────────────────── */

export default function VoicePage() {
  const [deptId,          setDeptId]         = useState("reception");
  const [voiceState,      setVoiceState]     = useState<VoiceState>("idle");
  const [inputMode,       setInputMode]      = useState<InputMode>("ptt");
  const [transcript,      setTranscript]     = useState<TranscriptLine[]>([]);
  const [duration,        setDuration]       = useState(0);
  const [sessionId,       setSessionId]      = useState("");
  const [isRecording,     setIsRecording]    = useState(false);
  const [sessionActive,   setSessionActive]  = useState(false);
  const [audioLevel,      setAudioLevel]     = useState(0);     // 0-1
  const [vadSpeaking,     setVadSpeaking]    = useState(false);
  const [wsConnected,     setWsConnected]    = useState(false);
  const [providers,       setProviders]      = useState<ProviderStatus | null>(null);
  const [providerError,   setProviderError]  = useState<string | null>(null);

  const transcriptBottomRef = useRef<HTMLDivElement>(null);
  const timerRef            = useRef<ReturnType<typeof setInterval> | null>(null);
  const mediaRecorderRef    = useRef<MediaRecorder | null>(null);
  const audioChunksRef      = useRef<Blob[]>([]);
  const vadRef              = useRef<BrowserVAD | null>(null);
  const wsRef               = useRef<WebSocket | null>(null);
  const wsAudioCtxRef       = useRef<AudioContext | null>(null);
  const audioQueueRef       = useRef<string[]>([]);   // FIFO of object URLs
  const audioPlayingRef     = useRef<boolean>(false);

  const dept = getDept(deptId);
  const Icon = dept.icon;

  /* Init */
  useEffect(() => { setSessionId(genId()); }, []);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const d = p.get("dept");
    if (d && DEPARTMENTS.some((x) => x.id === d)) setDeptId(d);
  }, []);
  useEffect(() => {
    transcriptBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  /* Fetch provider config */
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    fetch(`${base}/api/v1/voice/config`)
      .then((r) => r.json())
      .then((d) => setProviders(d))
      .catch(() => setProviderError("Could not reach API"));
  }, []);

  /* Timer */
  useEffect(() => {
    if (sessionActive) {
      timerRef.current = setInterval(() => setDuration((s) => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [sessionActive]);

  /* Cleanup on unmount */
  useEffect(() => () => {
    vadRef.current?.stop();
    wsRef.current?.close();
  }, []);

  /* ── Session control ─────────────────────────────────────── */

  const startSession = useCallback(() => {
    setSessionActive(true);
    setDuration(0);
    setVoiceState("idle");
    setTranscript([{
      id: genId(), speaker: "agent",
      text: `Hello! You're connected to ${getDept(deptId).label}. How can I help you today?`,
      timestamp: new Date(),
    }]);
    if (inputMode === "vad") _startVAD();
    if (inputMode === "ws")  _startWS();
  }, [deptId, inputMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const endSession = useCallback(() => {
    setSessionActive(false);
    setVoiceState("idle");
    setIsRecording(false);
    setVadSpeaking(false);
    setAudioLevel(0);
    setWsConnected(false);
    mediaRecorderRef.current?.stop();
    vadRef.current?.stop();
    vadRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    setTranscript((prev) => [...prev, {
      id: genId(), speaker: "agent",
      text: "Session ended. Thank you for using the AI Workforce Platform.",
      timestamp: new Date(),
    }]);
  }, []);

  /* ── PTT mode ────────────────────────────────────────────── */

  const startRecording = useCallback(async () => {
    if (!sessionActive || isRecording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      audioChunksRef.current   = [];
      mr.ondataavailable = (e) => audioChunksRef.current.push(e.data);
      mr.onstop = () => { stream.getTracks().forEach((t) => t.stop()); _processAudio(); };
      mr.start();
      setIsRecording(true);
      setVoiceState("listening");
    } catch {
      _appendLine("agent", "⚠️ Microphone access denied. Please allow microphone permissions.");
    }
  }, [sessionActive, isRecording]); // eslint-disable-line react-hooks/exhaustive-deps

  const stopRecording = useCallback(() => {
    if (!isRecording) return;
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
    setVoiceState("processing");
  }, [isRecording]);

  /* ── VAD mode ────────────────────────────────────────────── */

  const _startVAD = useCallback(() => {
    const vad = new BrowserVAD({
      threshold:  0.012,
      silenceMs:  900,
      onLevel:    (l) => setAudioLevel(l),
      onSpeech:   () => { setVadSpeaking(true); setVoiceState("listening"); },
      onSilence:  (blob) => {
        setVadSpeaking(false);
        setVoiceState("processing");
        _processBlob(blob);
      },
    });
    vad.start().catch(() => {
      _appendLine("agent", "⚠️ Microphone access denied for VAD mode.");
      setInputMode("ptt");
    });
    vadRef.current = vad;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── WebSocket mode ─────────────────────────────────────── */

  const _startWS = useCallback(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    const wsBase  = apiBase.replace(/^http/, "ws");
    const ws      = new WebSocket(`${wsBase}/api/v1/ws/voice/${sessionId}`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      _startWsAudioPump(ws);
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "vad") {
          setAudioLevel(Math.max(0, Math.min(1, (msg.energy_db + 60) / 60)));
          setVadSpeaking(msg.is_speech);
          if (msg.is_speech) setVoiceState("listening");
        } else if (msg.type === "transcript") {
          if (msg.is_final) _appendLine("user", msg.text);
        } else if (msg.type === "agent") {
          setVoiceState("speaking");
          _appendLine("agent", msg.text);
        } else if (msg.type === "audio") {
          _playBase64Audio(msg.data, msg.mime ?? "audio/mpeg");
        } else if (msg.type === "transfer") {
          // Department transfer — update the active department indicator
          const newDept = msg.department as string;
          if (newDept && DEPARTMENTS.some((d) => d.id === newDept)) {
            setDeptId(newDept);
            const label = DEPARTMENTS.find((d) => d.id === newDept)?.label ?? newDept;
            _appendLine("agent", `[ Transferred to ${label} ]`);
          }
        } else if (msg.type === "error") {
          _appendLine("agent", `⚠️ ${msg.message}`);
          setVoiceState("idle");
        } else if (msg.type === "ping") {
          // keep-alive — no action needed
        }
      } catch {}
    };

    ws.onerror = () => {
      setWsConnected(false);
      _appendLine("agent", "⚠️ WebSocket connection error. Falling back to PTT mode.");
      setInputMode("ptt");
    };

    ws.onclose = () => { setWsConnected(false); setVoiceState("idle"); };
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  function _startWsAudioPump(ws: WebSocket) {
    navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true } })
      .then((stream) => {
        const ctx = new AudioContext({ sampleRate: 16000 });
        wsAudioCtxRef.current = ctx;
        const src = ctx.createMediaStreamSource(stream);
        const proc = ctx.createScriptProcessor(1024, 1, 1);
        proc.onaudioprocess = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const f32  = e.inputBuffer.getChannelData(0);
          const i16  = new Int16Array(f32.length);
          for (let i = 0; i < f32.length; i++) {
            const s = Math.max(-1, Math.min(1, f32[i]));
            i16[i]  = s < 0 ? s * 0x8000 : s * 0x7fff;
          }
          ws.send(i16.buffer);
        };
        src.connect(proc);
        proc.connect(ctx.destination);
      })
      .catch(() => { _appendLine("agent", "⚠️ Microphone access denied."); setInputMode("ptt"); });
  }

  /* ── Audio processing (PTT / VAD REST mode) ─────────────── */

  const _processAudio = useCallback(() => {
    const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
    _processBlob(blob);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /** Speak `text` with the given department voice; resolves when playback ends. */
  const _speak = useCallback(async (text: string, dept: string) => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    setVoiceState("speaking");
    try {
      const ttsRes = await fetch(`${base}/api/v1/voice/speak/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ text, department: dept }),
      });
      if (!ttsRes.ok) return;
      const audioBlob = await ttsRes.blob();
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);
      await new Promise<void>((resolve) => {
        audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
        audio.onerror = () => { URL.revokeObjectURL(url); resolve(); };
        audio.play().catch(() => resolve());
      });
    } catch { /* ignore TTS failure */ }
  }, []);

  /**
   * Run one agent turn for `userText` against `fromDept`.
   * If the agent routes the conversation elsewhere, play the handoff phrase,
   * switch departments, and let the NEW department actually respond out loud
   * (so e.g. HR greets and continues the conversation after a transfer).
   * `depth` guards against transfer loops.
   */
  const _agentTurn = useCallback(async (userText: string, fromDept: string, depth = 0) => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    try {
      const chatRes = await fetch(`${base}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ message: userText, department: fromDept, session_id: sessionId }),
      });
      const chatData = await chatRes.json();

      const transferredTo: string | null =
        chatData?.transferred_to ?? chatData?.transferredTo ?? null;
      const isTransfer = !!(
        transferredTo &&
        transferredTo !== fromDept &&
        depth < 2 &&
        DEPARTMENTS.some((d) => d.id === transferredTo)
      );

      if (isTransfer) {
        const target = transferredTo as string;
        const label  = DEPARTMENTS.find((d) => d.id === target)?.label ?? target;
        _appendLine("agent", `[ Transferred to ${label} ]`);
        setDeptId(target);
        // 1) Spoken handoff from the current agent.
        await _speak(`I'm connecting you to our ${label} team now. One moment please.`, fromDept);
        // 2) New department picks up the SAME request and actually responds out loud.
        await _agentTurn(userText, target, depth + 1);
        return;
      }

      const reply =
        chatData?.message?.content ?? chatData?.response ?? "I processed your request.";
      _appendLine("agent", reply);
      await _speak(reply, fromDept);
    } catch {
      _appendLine("agent", "⚠️ Could not reach the API.");
    } finally {
      setVoiceState("idle");
    }
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const _processBlob = useCallback((blob: Blob) => {
    if (blob.size < 1000) { setVoiceState("idle"); return; }
    const base     = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    const form     = new FormData();
    const phId     = genId();
    form.append("audio",      blob, "recording.webm");
    form.append("department", deptId);
    form.append("session_id", sessionId);

    _appendLineId(phId, "user", "🎤 Transcribing…");

    fetch(`${base}/api/v1/voice/transcribe`, { method: "POST", headers: authHeaders(), body: form })
      .then((r) => r.json())
      .then(async (data: any) => {
        const text = data.transcript ?? "Could not transcribe.";
        _updateLine(phId, text);
        setVoiceState("processing");
        await _agentTurn(text, deptId);
      })
      .catch(() => {
        _updateLine(phId, "⚠️ Could not reach the API.");
        setVoiceState("idle");
      });
  }, [deptId, sessionId, _agentTurn]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Helpers ─────────────────────────────────────────────── */

  function _appendLine(speaker: "user" | "agent", text: string, provider?: string) {
    setTranscript((p) => [...p, { id: genId(), speaker, text, timestamp: new Date(), provider }]);
  }
  function _appendLineId(id: string, speaker: "user" | "agent", text: string) {
    setTranscript((p) => [...p, { id, speaker, text, timestamp: new Date() }]);
  }
  function _updateLine(id: string, text: string) {
    setTranscript((p) => p.map((l) => l.id === id ? { ...l, text } : l));
  }

  /** Play queued audio clips strictly one after another (no overlap). */
  function _drainAudioQueue() {
    if (audioPlayingRef.current) return;
    const url = audioQueueRef.current.shift();
    if (!url) { setVoiceState("idle"); return; }
    audioPlayingRef.current = true;
    setVoiceState("speaking");
    const audio = new Audio(url);
    const next = () => {
      URL.revokeObjectURL(url);
      audioPlayingRef.current = false;
      _drainAudioQueue();          // play the next clip, if any
    };
    audio.onended = next;
    audio.onerror = next;
    audio.play().catch(next);
  }

  function _playBase64Audio(b64: string, mime: string) {
    try {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const blob  = new Blob([bytes], { type: mime });
      const url   = URL.createObjectURL(blob);
      audioQueueRef.current.push(url);   // enqueue; play sequentially
      _drainAudioQueue();
    } catch { setVoiceState("idle"); }
  }

  /* ── Render ──────────────────────────────────────────────── */

  const canChangeMode = !sessionActive;
  const showAudioMeter = sessionActive && (inputMode === "vad" || inputMode === "ws" || isRecording);

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Left panel ─────────────────────────────────────── */}
      <aside className="flex w-[200px] flex-shrink-0 flex-col border-r border-[#1f2937] bg-[#070d1a]">
        <div className="flex h-12 items-center border-b border-[#1f2937] px-3">
          <Link href="/" className="flex items-center gap-1.5 text-xs text-slate-500 transition-colors hover:text-slate-300">
            <ChevronLeft className="h-3.5 w-3.5" />Dashboard
          </Link>
        </div>

        {/* Departments */}
        <div className="flex-1 overflow-y-auto px-2 py-3">
          <p className="mb-2 px-2 font-mono text-[10px] uppercase tracking-widest text-slate-600">Department</p>
          {DEPARTMENTS.map((d) => {
            const DIcon  = d.icon;
            const active = d.id === deptId;
            return (
              <button key={d.id} onClick={() => { if (!sessionActive) setDeptId(d.id); }}
                disabled={sessionActive}
                className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs transition-all ${
                  active ? `${d.colorBg} ${d.colorText} border ${d.colorBorder}` :
                  sessionActive ? "cursor-not-allowed text-slate-700" :
                  "text-slate-500 hover:bg-[#111827] hover:text-slate-300"
                }`}
              >
                <DIcon className="h-3.5 w-3.5 flex-shrink-0" /><span className="truncate">{d.label}</span>
              </button>
            );
          })}
        </div>

        {/* Mode selector */}
        <div className="border-t border-[#1f2937] p-3 space-y-2">
          <p className="font-mono text-[9px] uppercase tracking-widest text-slate-600">Input Mode</p>
          {([
            { m: "ptt", label: "Push-to-Talk", icon: Mic     },
            { m: "vad", label: "Auto-Detect",  icon: Activity },
            { m: "ws",  label: "Streaming WS", icon: Radio    },
          ] as {m: InputMode; label: string; icon: any}[]).map(({ m, label, icon: MIcon }) => (
            <button key={m} disabled={!canChangeMode}
              onClick={() => setInputMode(m)}
              className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-[11px] transition-all ${
                inputMode === m
                  ? `${dept.colorBg} ${dept.colorText} border ${dept.colorBorder}`
                  : canChangeMode ? "text-slate-500 hover:bg-[#111827] hover:text-slate-300" : "cursor-not-allowed text-slate-700"
              }`}
            >
              <MIcon className="h-3 w-3 flex-shrink-0" />{label}
            </button>
          ))}
        </div>

        {/* Provider status */}
        <div className="border-t border-[#1f2937] p-3 space-y-1.5">
          <p className="font-mono text-[9px] uppercase tracking-widest text-slate-600">Providers</p>
          {providers ? (
            <>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-slate-600">STT</span>
                {providers.stt.active ? (
                  <span className="flex items-center gap-1 text-[9px] text-emerald-500"><CheckCircle className="h-2.5 w-2.5" />{providers.stt.active}</span>
                ) : (
                  <span className="flex items-center gap-1 text-[9px] text-red-500"><AlertCircle className="h-2.5 w-2.5" />None</span>
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-slate-600">TTS</span>
                {providers.tts.active ? (
                  <span className="flex items-center gap-1 text-[9px] text-emerald-500"><CheckCircle className="h-2.5 w-2.5" />{providers.tts.active}</span>
                ) : (
                  <span className="flex items-center gap-1 text-[9px] text-red-500"><AlertCircle className="h-2.5 w-2.5" />None</span>
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-slate-600">Phone</span>
                {providers.telephony.twilio.configured ? (
                  <span className="text-[9px] text-emerald-500">Twilio</span>
                ) : (
                  <span className="text-[9px] text-slate-700">Not set</span>
                )}
              </div>
            </>
          ) : (
            <p className="text-[9px] text-slate-700">{providerError ?? "Loading…"}</p>
          )}
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex h-12 flex-shrink-0 items-center justify-between border-b border-[#1f2937] bg-[#0a0f1a] px-5">
          <div className="flex items-center gap-2.5">
            <div className={`rounded-md p-1.5 ${dept.colorBg} border ${dept.colorBorder}`}>
              <Icon className={`h-4 w-4 ${dept.colorText}`} />
            </div>
            <span className="text-sm font-medium text-slate-100">{dept.label} — Voice</span>
            {inputMode === "ws" && wsConnected && (
              <span className="flex items-center gap-1 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[9px] text-emerald-400">
                <Radio className="h-2.5 w-2.5 animate-pulse" /> WS
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Link href={`/chat?dept=${deptId}`} className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-1.5 text-xs text-slate-400 transition-all hover:border-[#374151] hover:text-slate-200">
              Switch to Chat
            </Link>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Voice controls */}
          <div className="flex w-[340px] flex-shrink-0 flex-col items-center justify-center gap-8 border-r border-[#1f2937] bg-[#070d1a] px-8 py-10">
            {/* State */}
            <div className="text-center">
              <p className={`font-mono text-xs uppercase tracking-[0.2em] ${STATE_COLOR[voiceState]}`}>
                {STATE_LABEL[voiceState]}
              </p>
              {sessionActive && (
                <p className="mt-1 font-mono text-2xl font-bold text-slate-300">{formatDuration(duration)}</p>
              )}
            </div>

            {/* Audio level meter */}
            {showAudioMeter && (
              <div className="flex h-6 w-full items-end gap-0.5 px-2">
                {Array.from({ length: 24 }).map((_, i) => {
                  const threshold = (i + 1) / 24;
                  const active    = audioLevel >= threshold;
                  const hue       = active
                    ? i < 16 ? "bg-emerald-500" : i < 21 ? "bg-yellow-500" : "bg-red-500"
                    : "bg-[#1f2937]";
                  return (
                    <div
                      key={i}
                      className={`flex-1 rounded-sm transition-all duration-75 ${hue}`}
                      style={{ height: `${30 + i * 2.5}%` }}
                    />
                  );
                })}
              </div>
            )}

            {/* Main button */}
            <div className="relative flex items-center justify-center">
              {(voiceState === "listening" || voiceState === "speaking" || vadSpeaking) && (
                <>
                  {[0, 0.66, 1.33].map((delay) => (
                    <div key={delay} className="voice-ring"
                      style={{ borderColor: `rgba(${dept.accentRgb},${0.4 - delay * 0.1})`, animationDelay: `${delay}s` }}
                    />
                  ))}
                </>
              )}

              <button
                onClick={() => {
                  if (!sessionActive) { startSession(); return; }
                  if (inputMode === "ptt") {
                    if (!isRecording) startRecording(); else stopRecording();
                  }
                }}
                disabled={voiceState === "processing" || (inputMode !== "ptt" && sessionActive)}
                className={`relative z-10 flex h-28 w-28 flex-shrink-0 items-center justify-center rounded-full border-2 transition-all ${
                  !sessionActive
                    ? `${dept.colorBg} ${dept.colorBorder} ${dept.colorText} hover:opacity-80`
                    : isRecording
                    ? "border-red-500/50 bg-red-500/15 text-red-400 hover:bg-red-500/25"
                    : voiceState === "processing"
                    ? "cursor-wait border-cyan-500/40 bg-cyan-500/10 text-cyan-400"
                    : voiceState === "speaking"
                    ? `${dept.colorBorder} ${dept.colorBg} ${dept.colorText}`
                    : inputMode !== "ptt" && sessionActive
                    ? `cursor-default ${dept.colorBorder} ${dept.colorBg} ${dept.colorText}`
                    : `${dept.colorBorder} ${dept.colorBg} ${dept.colorText} hover:opacity-80`
                }`}
                style={(voiceState === "listening" || voiceState === "speaking")
                  ? { boxShadow: `0 0 32px rgba(${dept.accentRgb},0.3)` } : undefined}
              >
                {voiceState === "processing" ? (
                  <span className="flex gap-1"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /></span>
                ) : !sessionActive ? (
                  <Mic className="h-9 w-9" />
                ) : inputMode === "vad" ? (
                  <Activity className={`h-9 w-9 ${vadSpeaking ? "animate-pulse" : ""}`} />
                ) : inputMode === "ws" ? (
                  <Radio className={`h-9 w-9 ${wsConnected ? "animate-pulse" : ""}`} />
                ) : isRecording ? (
                  <MicOff className="h-9 w-9" />
                ) : voiceState === "speaking" ? (
                  <Volume2 className="h-9 w-9" />
                ) : (
                  <Mic className="h-9 w-9" />
                )}
              </button>
            </div>

            {/* Waveform bars (PTT / VAD active) */}
            <div className={`flex h-8 items-end gap-0 transition-opacity ${(isRecording || vadSpeaking) ? "opacity-100" : "opacity-0"}`}>
              {Array.from({ length: 12 }).map((_, i) => (
                <span key={i} className="wave-bar" style={{ animationDelay: `${(i % 4) * 0.1}s` }} />
              ))}
            </div>

            {/* Hint */}
            <div className="text-center">
              {!sessionActive ? (
                <p className="text-xs text-slate-500">Click to start a voice session</p>
              ) : inputMode === "vad" ? (
                <p className="text-xs text-slate-500">Auto-detecting speech via VAD…</p>
              ) : inputMode === "ws" ? (
                <p className={`text-xs ${wsConnected ? "text-emerald-500" : "text-amber-500"}`}>
                  {wsConnected ? "Streaming — speak naturally" : "Connecting WebSocket…"}
                </p>
              ) : isRecording ? (
                <p className="text-xs text-amber-400">Recording… click to stop</p>
              ) : voiceState === "processing" ? (
                <p className="text-xs text-cyan-400">Processing…</p>
              ) : voiceState === "speaking" ? (
                <p className="text-xs text-emerald-400">Agent speaking…</p>
              ) : (
                <p className="text-xs text-slate-500">Click mic to speak</p>
              )}
            </div>

            {sessionActive && (
              <button onClick={endSession}
                className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-6 py-2.5 text-sm text-red-400 transition-all hover:bg-red-500/20">
                <PhoneOff className="h-4 w-4" />End Session
              </button>
            )}
          </div>

          {/* Transcript */}
          <div className="flex flex-1 flex-col overflow-hidden">
            <div className="flex h-10 flex-shrink-0 items-center justify-between border-b border-[#1f2937] bg-[#0a0f1a] px-5">
              <p className="font-mono text-[11px] uppercase tracking-widest text-slate-600">Live Transcript</p>
              {transcript.length > 0 && (
                <button onClick={() => setTranscript([])} className="text-[11px] text-slate-600 transition-colors hover:text-slate-400">Clear</button>
              )}
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
              {transcript.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                  <Mic className="h-8 w-8 text-slate-700" />
                  <p className="text-sm text-slate-600">Start a session to see the live transcript</p>
                </div>
              ) : (
                transcript.map((line) => {
                  const isUser = line.speaker === "user";
                  return (
                    <div key={line.id} className={`flex gap-3 slide-up ${isUser ? "flex-row-reverse" : ""}`}>
                      <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                        isUser ? "bg-slate-700 text-slate-300" : `${dept.colorBg} ${dept.colorText} border ${dept.colorBorder}`
                      }`}>
                        {isUser ? "U" : <Icon className="h-3 w-3" />}
                      </div>
                      <div className={`flex max-w-[80%] flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
                        <p className={`rounded-xl px-3 py-2 text-sm leading-relaxed ${
                          isUser ? "rounded-tr-sm bg-amber-500/10 text-slate-100"
                                 : "rounded-tl-sm border border-[#1f2937] bg-[#0c111d] text-slate-200"
                        }`}>{line.text}</p>
                        <span className="px-1 font-mono text-[10px] text-slate-600">
                          {formatTime(line.timestamp)}
                          {!isUser && line.provider && <span className={`ml-2 ${dept.colorText} opacity-50`}>{line.provider}</span>}
                          {!isUser && <span className={`ml-2 ${dept.colorText} opacity-60`}>{dept.label}</span>}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={transcriptBottomRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
