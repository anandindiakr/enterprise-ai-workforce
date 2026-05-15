"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Mic,
  MicOff,
  PhoneOff,
  Star,
  Headphones,
  ShoppingCart,
  Users,
  DollarSign,
  Cpu,
  Megaphone,
  ChevronLeft,
  Volume2,
} from "lucide-react";
import { formatTime, formatDuration } from "@/lib/utils";

/* ── Types ───────────────────────────────────────────────── */

type VoiceState = "idle" | "listening" | "processing" | "speaking";

interface TranscriptLine {
  id: string;
  speaker: "user" | "agent";
  text: string;
  timestamp: Date;
}

/* ── Department config ───────────────────────────────────── */

const DEPARTMENTS = [
  { id: "reception",    label: "Reception",     icon: Star,        colorText: "text-amber-400",   colorBg: "bg-amber-500/10",   colorBorder: "border-amber-500/25",   accentRgb: "245,158,11" },
  { id: "customer_care",label: "Customer Care", icon: Headphones,  colorText: "text-cyan-400",    colorBg: "bg-cyan-500/10",    colorBorder: "border-cyan-500/25",    accentRgb: "6,182,212"  },
  { id: "sales",        label: "Sales",         icon: ShoppingCart,colorText: "text-emerald-400", colorBg: "bg-emerald-500/10", colorBorder: "border-emerald-500/25", accentRgb: "16,185,129" },
  { id: "hr",           label: "HR",            icon: Users,       colorText: "text-violet-400",  colorBg: "bg-violet-500/10",  colorBorder: "border-violet-500/25",  accentRgb: "167,139,250"},
  { id: "finance",      label: "Finance",       icon: DollarSign,  colorText: "text-rose-400",    colorBg: "bg-rose-500/10",    colorBorder: "border-rose-500/25",    accentRgb: "251,113,133"},
  { id: "technology",   label: "Technology",    icon: Cpu,         colorText: "text-blue-400",    colorBg: "bg-blue-500/10",    colorBorder: "border-blue-500/25",    accentRgb: "96,165,250" },
  { id: "marketing",    label: "Marketing",     icon: Megaphone,   colorText: "text-orange-400",  colorBg: "bg-orange-500/10",  colorBorder: "border-orange-500/25",  accentRgb: "251,146,60" },
];

function getDept(id: string) {
  return DEPARTMENTS.find((d) => d.id === id) ?? DEPARTMENTS[0];
}

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

const STATE_LABEL: Record<VoiceState, string> = {
  idle:       "IDLE",
  listening:  "LISTENING",
  processing: "PROCESSING",
  speaking:   "SPEAKING",
};

const STATE_COLOR: Record<VoiceState, string> = {
  idle:       "text-slate-500",
  listening:  "text-amber-400",
  processing: "text-cyan-400",
  speaking:   "text-emerald-400",
};

/* ── Component ───────────────────────────────────────────── */

export default function VoicePage() {
  const [deptId, setDeptId] = useState("reception");
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [duration, setDuration] = useState(0);
  // Generate sessionId client-side only to avoid SSR hydration mismatch
  const [sessionId, setSessionId] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [sessionActive, setSessionActive] = useState(false);

  const transcriptBottomRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const dept = getDept(deptId);
  const Icon = dept.icon;

  /* Generate sessionId on mount (client only) */
  useEffect(() => {
    setSessionId(genId());
  }, []);

  /* Read ?dept= from URL */
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const d = p.get("dept");
    if (d && DEPARTMENTS.some((x) => x.id === d)) setDeptId(d);
  }, []);

  /* Auto-scroll transcript */
  useEffect(() => {
    transcriptBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  /* Session timer */
  useEffect(() => {
    if (sessionActive) {
      timerRef.current = setInterval(() => setDuration((s) => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [sessionActive]);

  /* Start session */
  const startSession = useCallback(() => {
    setSessionActive(true);
    setDuration(0);
    setTranscript([
      {
        id: genId(),
        speaker: "agent",
        text: `Hello! You're connected to the ${getDept(deptId).label} department. How can I help you today?`,
        timestamp: new Date(),
      },
    ]);
    setVoiceState("idle");
  }, [deptId]);

  /* End session */
  const endSession = useCallback(() => {
    setSessionActive(false);
    setVoiceState("idle");
    setIsRecording(false);
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setTranscript((prev) => [
      ...prev,
      {
        id: genId(),
        speaker: "agent",
        text: "Session ended. Thank you for using the AI Workforce Platform.",
        timestamp: new Date(),
      },
    ]);
  }, []);

  /* Push-to-talk: start recording */
  const startRecording = useCallback(async () => {
    if (!sessionActive || isRecording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      audioChunksRef.current = [];
      mr.ondataavailable = (e) => audioChunksRef.current.push(e.data);
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        processAudio();
      };
      mr.start();
      setIsRecording(true);
      setVoiceState("listening");
    } catch {
      setTranscript((prev) => [
        ...prev,
        {
          id: genId(),
          speaker: "agent",
          text: "⚠️ Microphone access denied. Please allow microphone permissions.",
          timestamp: new Date(),
        },
      ]);
    }
  }, [sessionActive, isRecording]); // eslint-disable-line react-hooks/exhaustive-deps

  /* Stop recording */
  const stopRecording = useCallback(() => {
    if (!isRecording) return;
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
    setVoiceState("processing");
  }, [isRecording]);

  /* Process audio (STT → agent → TTS simulation) */
  const processAudio = useCallback(() => {
    setVoiceState("processing");
    const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });

    /* Send to backend STT endpoint */
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    const formData = new FormData();
    formData.append("audio", blob, "recording.webm");
    formData.append("department", deptId);
    formData.append("session_id", sessionId);

    const userPlaceholderId = genId();
    setTranscript((prev) => [
      ...prev,
      { id: userPlaceholderId, speaker: "user", text: "🎤 Processing speech…", timestamp: new Date() },
    ]);

    fetch(`${apiBase}/api/v1/voice/transcribe`, {
      method: "POST",
      body: formData,
    })
      .then((r) => r.json())
      .then((data) => {
        const transcribed = (data as { transcript?: string }).transcript ?? "Could not transcribe audio.";
        setTranscript((prev) =>
          prev.map((l) =>
            l.id === userPlaceholderId ? { ...l, text: transcribed } : l
          )
        );
        return fetch(`${apiBase}/api/v1/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: transcribed, department: deptId, session_id: sessionId }),
        });
      })
      .then((r) => r.json())
      .then((data) => {
        setVoiceState("speaking");
        const reply =
          (data as { response?: string; message?: string }).response ??
          (data as { response?: string; message?: string }).message ??
          "I processed your request.";
        setTranscript((prev) => [
          ...prev,
          { id: genId(), speaker: "agent", text: reply, timestamp: new Date() },
        ]);
        setTimeout(() => setVoiceState("idle"), 2000);
      })
      .catch(() => {
        setVoiceState("idle");
        setTranscript((prev) =>
          prev.map((l) =>
            l.id === userPlaceholderId ? { ...l, text: "⚠️ Could not reach the API." } : l
          )
        );
      });
  }, [deptId, sessionId]);

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Left panel ─────────────────────────────────────── */}
      <aside className="flex w-[200px] flex-shrink-0 flex-col border-r border-[#1f2937] bg-[#070d1a]">
        {/* Back */}
        <div className="flex h-12 items-center border-b border-[#1f2937] px-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-xs text-slate-500 transition-colors hover:text-slate-300"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Dashboard
          </Link>
        </div>

        {/* Dept list */}
        <div className="flex-1 overflow-y-auto px-2 py-3">
          <p className="mb-2 px-2 font-mono text-[10px] uppercase tracking-widest text-slate-600">
            Department
          </p>
          {DEPARTMENTS.map((d) => {
            const DIcon = d.icon;
            const active = d.id === deptId;
            return (
              <button
                key={d.id}
                onClick={() => {
                  if (sessionActive) return;
                  setDeptId(d.id);
                }}
                disabled={sessionActive}
                className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs transition-all ${
                  active
                    ? `${d.colorBg} ${d.colorText} border ${d.colorBorder}`
                    : sessionActive
                    ? "cursor-not-allowed text-slate-700"
                    : "text-slate-500 hover:bg-[#111827] hover:text-slate-300"
                }`}
              >
                <DIcon className="h-3.5 w-3.5 flex-shrink-0" />
                <span className="truncate">{d.label}</span>
              </button>
            );
          })}
        </div>

        {/* Session info */}
        <div className="border-t border-[#1f2937] p-3">
          <div className="rounded-lg border border-[#1f2937] bg-[#0c111d] p-2.5">
            <p className="mb-1 font-mono text-[9px] uppercase tracking-widest text-slate-600">
              Session
            </p>
            <p className="font-mono text-[10px] text-slate-400">{sessionId}</p>
            {sessionActive && (
              <p className="mt-1 font-mono text-[11px] text-amber-400">
                {formatDuration(duration)}
              </p>
            )}
          </div>
          {sessionActive && (
            <p className="mt-2 text-[10px] text-slate-600">Change department unavailable during active session.</p>
          )}
        </div>
      </aside>

      {/* ── Main voice area ─────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex h-12 flex-shrink-0 items-center justify-between border-b border-[#1f2937] bg-[#0a0f1a] px-5">
          <div className="flex items-center gap-2.5">
            <div className={`rounded-md p-1.5 ${dept.colorBg} border ${dept.colorBorder}`}>
              <Icon className={`h-4 w-4 ${dept.colorText}`} />
            </div>
            <span className="text-sm font-medium text-slate-100">{dept.label} — Voice</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href={`/chat?dept=${deptId}`}
              className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-1.5 text-xs text-slate-400 transition-all hover:border-[#374151] hover:text-slate-200"
            >
              Switch to Chat
            </Link>
          </div>
        </div>

        {/* Content: two sections */}
        <div className="flex flex-1 overflow-hidden">
          {/* Voice control column */}
          <div className="flex w-[340px] flex-shrink-0 flex-col items-center justify-center border-r border-[#1f2937] bg-[#070d1a] px-8 py-10 gap-8">
            {/* State label */}
            <div className="text-center">
              <p className={`font-mono text-xs uppercase tracking-[0.2em] ${STATE_COLOR[voiceState]}`}>
                {STATE_LABEL[voiceState]}
              </p>
              {sessionActive && (
                <p className="mt-1 font-mono text-2xl font-bold text-slate-300">
                  {formatDuration(duration)}
                </p>
              )}
            </div>

            {/* Main voice button */}
            <div className="relative flex items-center justify-center">
              {/* Ripple rings (only when listening/speaking) */}
              {(voiceState === "listening" || voiceState === "speaking") && (
                <>
                  <div
                    className="voice-ring"
                    style={{
                      borderColor: `rgba(${dept.accentRgb},0.4)`,
                      animationDelay: "0s",
                    }}
                  />
                  <div
                    className="voice-ring"
                    style={{
                      borderColor: `rgba(${dept.accentRgb},0.3)`,
                      animationDelay: "0.66s",
                    }}
                  />
                  <div
                    className="voice-ring"
                    style={{
                      borderColor: `rgba(${dept.accentRgb},0.2)`,
                      animationDelay: "1.33s",
                    }}
                  />
                </>
              )}

              <button
                onClick={() => {
                  if (!sessionActive) {
                    startSession();
                    return;
                  }
                  if (!isRecording) {
                    startRecording();
                  } else {
                    stopRecording();
                  }
                }}
                disabled={voiceState === "processing"}
                className={`relative z-10 flex h-28 w-28 flex-shrink-0 items-center justify-center rounded-full border-2 transition-all ${
                  !sessionActive
                    ? `${dept.colorBg} ${dept.colorBorder} ${dept.colorText} hover:opacity-80`
                    : isRecording
                    ? "border-red-500/50 bg-red-500/15 text-red-400 hover:bg-red-500/25"
                    : voiceState === "processing"
                    ? "cursor-wait border-cyan-500/40 bg-cyan-500/10 text-cyan-400"
                    : voiceState === "speaking"
                    ? `${dept.colorBorder} ${dept.colorBg} ${dept.colorText}`
                    : `${dept.colorBorder} ${dept.colorBg} ${dept.colorText} hover:opacity-80`
                }`}
                style={
                  voiceState === "listening" || voiceState === "speaking"
                    ? { boxShadow: `0 0 32px rgba(${dept.accentRgb},0.25)` }
                    : undefined
                }
              >
                {voiceState === "processing" ? (
                  <span className="flex gap-1">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </span>
                ) : !sessionActive ? (
                  <Mic className="h-9 w-9" />
                ) : isRecording ? (
                  <MicOff className="h-9 w-9" />
                ) : voiceState === "speaking" ? (
                  <Volume2 className="h-9 w-9" />
                ) : (
                  <Mic className="h-9 w-9" />
                )}
              </button>
            </div>

            {/* Waveform (visible when listening) */}
            <div
              className={`flex h-8 items-end gap-0 transition-opacity ${
                isRecording ? "opacity-100" : "opacity-0"
              }`}
            >
              {Array.from({ length: 12 }).map((_, i) => (
                <span
                  key={i}
                  className="wave-bar"
                  style={{ animationDelay: `${(i % 4) * 0.1}s` }}
                />
              ))}
            </div>

            {/* Instructions */}
            <div className="text-center">
              {!sessionActive ? (
                <p className="text-xs text-slate-500">
                  Click the button to start a voice session
                </p>
              ) : isRecording ? (
                <p className="text-xs text-amber-400">Recording… click to stop</p>
              ) : voiceState === "processing" ? (
                <p className="text-xs text-cyan-400">Processing your request…</p>
              ) : voiceState === "speaking" ? (
                <p className="text-xs text-emerald-400">Agent is speaking…</p>
              ) : (
                <p className="text-xs text-slate-500">
                  Click mic to speak, release to send
                </p>
              )}
            </div>

            {/* End session button */}
            {sessionActive && (
              <button
                onClick={endSession}
                className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-6 py-2.5 text-sm text-red-400 transition-all hover:bg-red-500/20"
              >
                <PhoneOff className="h-4 w-4" />
                End Session
              </button>
            )}
          </div>

          {/* Transcript */}
          <div className="flex flex-1 flex-col overflow-hidden">
            <div className="flex h-10 flex-shrink-0 items-center justify-between border-b border-[#1f2937] bg-[#0a0f1a] px-5">
              <p className="font-mono text-[11px] uppercase tracking-widest text-slate-600">
                Live Transcript
              </p>
              {transcript.length > 0 && (
                <button
                  onClick={() => setTranscript([])}
                  className="text-[11px] text-slate-600 transition-colors hover:text-slate-400"
                >
                  Clear
                </button>
              )}
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
              {transcript.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                  <Mic className="h-8 w-8 text-slate-700" />
                  <p className="text-sm text-slate-600">
                    Start a session to see the live transcript here
                  </p>
                </div>
              ) : (
                transcript.map((line) => {
                  const isUser = line.speaker === "user";
                  return (
                    <div
                      key={line.id}
                      className={`flex gap-3 slide-up ${isUser ? "flex-row-reverse" : ""}`}
                    >
                      <div
                        className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                          isUser
                            ? "bg-slate-700 text-slate-300"
                            : `${dept.colorBg} ${dept.colorText} border ${dept.colorBorder}`
                        }`}
                      >
                        {isUser ? "U" : <Icon className="h-3 w-3" />}
                      </div>
                      <div
                        className={`flex max-w-[80%] flex-col gap-1 ${
                          isUser ? "items-end" : "items-start"
                        }`}
                      >
                        <p
                          className={`rounded-xl px-3 py-2 text-sm leading-relaxed ${
                            isUser
                              ? "rounded-tr-sm bg-amber-500/10 text-slate-100"
                              : "rounded-tl-sm border border-[#1f2937] bg-[#0c111d] text-slate-200"
                          }`}
                        >
                          {line.text}
                        </p>
                        <span className="px-1 font-mono text-[10px] text-slate-600">
                          {formatTime(line.timestamp)}
                          {!isUser && (
                            <span className={`ml-2 ${dept.colorText} opacity-60`}>
                              {dept.label}
                            </span>
                          )}
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
