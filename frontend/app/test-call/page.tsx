"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { authHeaders } from "@/lib/auth";
import { Phone, PhoneOff, Mic, AlertCircle, Info, Volume2 } from "lucide-react";

/* ── Types ───────────────────────────────────────────────── */

type CallStatus = "idle" | "connecting" | "in-call" | "ended" | "error";

interface TranscriptLine {
  id: string;
  speaker: "user" | "agent";
  text: string;
  ts: Date;
}

interface WebCallConfig {
  configured: boolean;
  publicKey: string;
  assistantId: string;
}

/* ── Helpers ─────────────────────────────────────────────── */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

const STATUS_META: Record<CallStatus, { label: string; color: string }> = {
  idle:       { label: "READY",          color: "text-slate-500" },
  connecting: { label: "CONNECTING…",    color: "text-cyan-400" },
  "in-call":  { label: "IN CALL",        color: "text-emerald-400" },
  ended:      { label: "CALL ENDED",     color: "text-slate-400" },
  error:      { label: "ERROR",          color: "text-red-400" },
};

/* ── Component ───────────────────────────────────────────── */

export default function TestCallPage() {
  const [config, setConfig]       = useState<WebCallConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [status, setStatus]       = useState<CallStatus>("idle");
  const [error, setError]         = useState<string | null>(null);
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [duration, setDuration]   = useState(0);

  const vapiRef = useRef<any>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  /* Fetch the web-call config (public key + assistant id) from our backend */
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/vapi/web-call-config`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setConfig)
      .catch((e) => setConfigError(String(e.message ?? e)));
  }, []);

  /* Duration timer while in a call */
  useEffect(() => {
    if (status === "in-call") {
      timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
      if (status === "ended" || status === "error") setDuration(0);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [status]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  /* Clean up the SDK instance on unmount */
  useEffect(() => {
    return () => {
      try { vapiRef.current?.stop(); } catch { /* noop */ }
    };
  }, []);

  const startCall = useCallback(async () => {
    if (!config?.configured || !config.publicKey || !config.assistantId) return;
    setError(null);
    setTranscript([]);
    setStatus("connecting");

    try {
      // Browser-only SDK — dynamic import keeps it out of SSR
      const { default: Vapi } = await import("@vapi-ai/web");
      const vapi = new Vapi(config.publicKey, {
        apiResponseDelayMs: 2000,
      } as any);
      vapiRef.current = vapi;

      vapi.on("call-start", () => setStatus("in-call"));
      vapi.on("call-end", () => {
        setStatus("ended");
        setAgentSpeaking(false);
      });
      vapi.on("speech-start", () => setAgentSpeaking(true));
      vapi.on("speech-end", () => setAgentSpeaking(false));
      vapi.on("error", (e: unknown) => {
        setError(e instanceof Error ? e.message : String(e?.valueOf() ?? e));
        setStatus("error");
      });
      vapi.on("message", (message: any) => {
        if (message?.type === "transcript" && message?.transcriptType === "final") {
          const role = message.role === "user" ? "user" : "agent";
          setTranscript((prev) => [
            ...prev,
            { id: genId(), speaker: role, text: message.transcript ?? "", ts: new Date() },
          ]);
        }
      });

      await vapi.start(config.assistantId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus("error");
    }
  }, [config]);

  const endCall = useCallback(() => {
    try { vapiRef.current?.stop(); } catch { /* noop */ }
    setStatus("ended");
    setAgentSpeaking(false);
  }, []);

  const mm = String(Math.floor(duration / 60)).padStart(2, "0");
  const ss = String(duration % 60).padStart(2, "0");

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Test Call</h1>
          <p className="mt-1 text-sm text-slate-500">
            Talk to the live phone receptionist from your browser — same assistant that answers {`+65 6470 8728`}.
          </p>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-[#1f2937] bg-[#0b1220] px-4 py-2">
          <span className={`h-2 w-2 rounded-full ${status === "in-call" ? "bg-emerald-500 status-pulse" : status === "connecting" ? "bg-cyan-400 status-pulse" : "bg-slate-600"}`} />
          <span className={`font-mono text-xs font-semibold tracking-wider ${STATUS_META[status].color}`}>
            {STATUS_META[status].label}
          </span>
          {status === "in-call" && (
            <span className="font-mono text-xs text-slate-400">{mm}:{ss}</span>
          )}
        </div>
      </div>

      {/* Not configured notice */}
      {config && !config.configured && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-300">
          <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <div className="space-y-1">
            <p className="font-medium">Browser test calls aren&apos;t configured yet.</p>
            <p className="text-amber-300/80">
              Ask your admin to add the Vapi <span className="font-mono">PUBLIC</span> API key
              (Vapi dashboard → API Keys → Public section) as{" "}
              <span className="font-mono">VAPI_PUBLIC_KEY</span> in the server environment, then reload this page.
            </p>
          </div>
        </div>
      )}

      {configError && (
        <div className="flex items-start gap-3 rounded-lg border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-300">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>Could not load test-call settings: {configError}</span>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-300">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Call controls */}
      {config?.configured && (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-[#1f2937] bg-[#0b1220] p-8">
          <button
            onClick={status === "in-call" || status === "connecting" ? endCall : startCall}
            disabled={status === "connecting"}
            className={`flex h-20 w-20 items-center justify-center rounded-full transition-all ${
              status === "in-call" || status === "connecting"
                ? "bg-red-500 hover:bg-red-600"
                : "bg-emerald-500 hover:bg-emerald-600"
            } ${status === "connecting" ? "cursor-wait opacity-70" : ""}`}
            aria-label={status === "in-call" ? "End call" : "Start call"}
          >
            {status === "in-call" || status === "connecting" ? (
              <PhoneOff className="h-8 w-8 text-white" />
            ) : (
              <Phone className="h-8 w-8 text-white" />
            )}
          </button>
          <p className="text-sm text-slate-400">
            {status === "in-call"
              ? agentSpeaking
                ? "Receptionist is speaking — go ahead and interrupt her, she should stop and listen."
                : "Listening… speak naturally."
              : status === "connecting"
              ? "Requesting microphone…"
              : "Click to start a live conversation with the receptionist."}
          </p>
          {status === "in-call" && (
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1.5"><Mic className="h-3.5 w-3.5" /> Your mic is live</span>
              <span className="flex items-center gap-1.5"><Volume2 className="h-3.5 w-3.5" /> Audio plays here</span>
            </div>
          )}
        </div>
      )}

      {/* Live transcript */}
      {(transcript.length > 0 || status === "in-call") && (
        <div className="rounded-xl border border-[#1f2937] bg-[#0b1220]">
          <div className="border-b border-[#1f2937] px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Live transcript</p>
          </div>
          <div className="max-h-96 space-y-3 overflow-y-auto p-4">
            {transcript.length === 0 && (
              <p className="text-sm text-slate-600">Waiting for the receptionist to greet you…</p>
            )}
            {transcript.map((line) => (
              <div key={line.id} className={`flex ${line.speaker === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                    line.speaker === "user"
                      ? "bg-amber-500/15 text-amber-100"
                      : "bg-[#141c2e] text-slate-200"
                  }`}
                >
                  {line.text}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>
      )}

      {/* What to test */}
      {config?.configured && status === "idle" && (
        <div className="rounded-xl border border-[#1f2937] bg-[#0b1220] p-4 text-sm text-slate-400">
          <p className="mb-2 font-medium text-slate-300">Things to try during the call:</p>
          <ul className="list-inside list-disc space-y-1">
            <li>Interrupt her mid-sentence — she should stop and listen (full-duplex)</li>
            <li>Ask about a product we don&apos;t sell — she must NOT invent one</li>
            <li>Ask to be transferred to Sales — she should announce the transfer first</li>
            <li>Give a phone number — she should repeat it back digit by digit</li>
          </ul>
        </div>
      )}
    </div>
  );
}
