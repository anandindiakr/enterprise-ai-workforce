"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import Link from "next/link";
import { authHeaders } from "@/lib/auth";
import {
  Send,
  Paperclip,
  Star,
  Headphones,
  ShoppingCart,
  Users,
  DollarSign,
  Cpu,
  Megaphone,
  Mic,
  RotateCcw,
  ChevronLeft,
  Info,
  Zap,
  Download,
  History,
  ArrowRightLeft,
  Plus,
} from "lucide-react";
import { formatTime } from "@/lib/utils";

/* ── Types ───────────────────────────────────────────────── */

type Role = "user" | "assistant";

interface Message {
  id: string;
  role: Role;
  content: string;
  timestamp: Date;
  dept?: string;
  file_name?: string;
}

interface UploadedFile {
  file_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
}

type WsState = "connecting" | "open" | "closed" | "error";

/* ── Department config ───────────────────────────────────── */

const DEPARTMENTS = [
  {
    id: "reception",
    label: "Reception",
    icon: Star,
    colorText: "text-amber-400",
    colorBg: "bg-amber-500/10",
    colorBorder: "border-amber-500/25",
    colorPill: "bg-amber-500/15 text-amber-300",
    greeting: "Hello! I'm your Receptionist. How can I direct you today?",
  },
  {
    id: "customer_care",
    label: "Customer Care",
    icon: Headphones,
    colorText: "text-cyan-400",
    colorBg: "bg-cyan-500/10",
    colorBorder: "border-cyan-500/25",
    colorPill: "bg-cyan-500/15 text-cyan-300",
    greeting: "Hi there! I'm from Customer Care. What issue can I help resolve?",
  },
  {
    id: "sales",
    label: "Sales",
    icon: ShoppingCart,
    colorText: "text-emerald-400",
    colorBg: "bg-emerald-500/10",
    colorBorder: "border-emerald-500/25",
    colorPill: "bg-emerald-500/15 text-emerald-300",
    greeting: "Welcome! I'm your Sales Agent. Ready to explore what we can offer you.",
  },
  {
    id: "hr",
    label: "HR",
    icon: Users,
    colorText: "text-violet-400",
    colorBg: "bg-violet-500/10",
    colorBorder: "border-violet-500/25",
    colorPill: "bg-violet-500/15 text-violet-300",
    greeting: "Hello! I'm the HR Agent. How can I assist with HR policies or processes?",
  },
  {
    id: "finance",
    label: "Finance",
    icon: DollarSign,
    colorText: "text-rose-400",
    colorBg: "bg-rose-500/10",
    colorBorder: "border-rose-500/25",
    colorPill: "bg-rose-500/15 text-rose-300",
    greeting: "Hi! I'm the Finance Agent. I can help with invoices, budgets, and reports.",
  },
  {
    id: "technology",
    label: "Technology",
    icon: Cpu,
    colorText: "text-blue-400",
    colorBg: "bg-blue-500/10",
    colorBorder: "border-blue-500/25",
    colorPill: "bg-blue-500/15 text-blue-300",
    greeting: "Hello! I'm the Technology Agent. What IT issue can I help you with?",
  },
  {
    id: "marketing",
    label: "Marketing",
    icon: Megaphone,
    colorText: "text-orange-400",
    colorBg: "bg-orange-500/10",
    colorBorder: "border-orange-500/25",
    colorPill: "bg-orange-500/15 text-orange-300",
    greeting: "Hi! I'm the Marketing Agent. Let's talk content, campaigns, and brand.",
  },
];

function getDept(id: string) {
  return DEPARTMENTS.find((d) => d.id === id) ?? DEPARTMENTS[0];
}

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

/* ── Component ───────────────────────────────────────────── */

export default function ChatPage() {
  const [deptId, setDeptId] = useState("reception");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [wsState, setWsState] = useState<WsState>("closed");
  const [typing, setTyping] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [pastSessions, setPastSessions] = useState<{id:string;department:string;title:string|null;created_at:string}[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const dept = getDept(deptId);
  const Icon = dept.icon;

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
      const res = await fetch(`${apiBase}/api/v1/chat/upload?session_id=${sessionId || ""}`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
      const data: UploadedFile = await res.json();
      setUploadedFile(data);
    } catch {
      alert("File upload failed. Please try again.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  /* Generate sessionId on mount */
  useEffect(() => {
    setSessionId(genId());
  }, []);

  /* Read ?dept= from URL on mount */
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const d = p.get("dept");
    if (d && DEPARTMENTS.some((x) => x.id === d)) setDeptId(d);
  }, []);

  /* Auto-scroll */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  /* Inject greeting when department changes */
  useEffect(() => {
    const d = getDept(deptId);
    setMessages([
      {
        id: genId(),
        role: "assistant",
        content: d.greeting,
        timestamp: new Date(),
        dept: deptId,
      },
    ]);
    setTyping(false);
  }, [deptId]);

  /* WebSocket connection */
  const connect = useCallback(() => {
    wsRef.current?.close();
    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8080";
    setWsState("connecting");

    const ws = new WebSocket(`${wsBase}/api/v1/ws/chat/${sessionId}`);
    wsRef.current = ws;

    ws.onopen = () => setWsState("open");
    ws.onclose = () => setWsState("closed");
    ws.onerror = () => setWsState("error");

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string) as any;
        setTyping(false);
        if (data.type === "typing") {
          setTyping(true);
          return;
        }
        // Backend sends full ChatResponse: { message: { content: string, ... }, ... }
        const text: string =
          typeof data?.message?.content === "string"
            ? data.message.content
            : typeof data?.content === "string"
            ? data.content
            : typeof data?.message === "string"
            ? data.message
            : String(ev.data);
        setMessages((prev) => [
          ...prev,
          { id: genId(), role: "assistant", content: text, timestamp: new Date(), dept: deptId },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: genId(),
            role: "assistant",
            content: String(ev.data),
            timestamp: new Date(),
            dept: deptId,
          },
        ]);
      }
    };
  }, [sessionId, deptId]);

  /* Auto-connect on mount */
  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  /* Fetch past sessions */
  const fetchHistory = useCallback(async () => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    try {
      const res = await fetch(`${apiBase}/api/v1/chat/sessions?limit=20`, {
        headers: authHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data) ? data : (data.sessions ?? []);
      setPastSessions(list);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  /* Load a past session */
  const loadSession = useCallback(async (sid: string, dept: string) => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    try {
      const res = await fetch(`${apiBase}/api/v1/chat/sessions/${sid}`, {
        headers: authHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      setDeptId(dept);
      setSessionId(sid);
      setMessages(
        (data.messages ?? []).map((m: {id:string;role:string;content:string;department:string;created_at:string}) => ({
          id: m.id,
          role: m.role as Role,
          content: m.content,
          timestamp: new Date(m.created_at),
          dept: m.department,
        }))
      );
      setShowHistory(false);
    } catch { /* ignore */ }
  }, []);

  /* Send message */
  const sendMessage = useCallback(() => {
    const text = input.trim();
    if (!text && !uploadedFile) return;

    const displayText = uploadedFile
      ? `${text}${text ? "\n" : ""}[Attached: ${uploadedFile.filename}]`
      : text;

    const userMsg: Message = {
      id: genId(),
      role: "user",
      content: displayText,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    const currentFile = uploadedFile;
    setUploadedFile(null);
    setTyping(true);

    const fileIds = currentFile ? [currentFile.file_id] : undefined;

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ message: text || "[File attached]", department: deptId, session_id: sessionId, file_ids: fileIds })
      );
    } else {
      /* Fallback: SSE streaming REST */
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
      const streamingId = genId();

      fetch(`${apiBase}/api/v1/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ message: text || "[File attached]", department: deptId, session_id: sessionId, streaming: true, file_ids: fileIds }),
      })
        .then(async (res) => {
          if (!res.ok || !res.body) {
            throw new Error(`HTTP ${res.status}`);
          }
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          let streamingMsgAdded = false;

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";

            for (const line of lines) {
              if (!line.startsWith("data: ")) continue;
              try {
                const evt = JSON.parse(line.slice(6)) as any;
                if (evt.type === "typing") {
                  setTyping(true);
                } else if (evt.type === "token") {
                  setTyping(false);
                  if (!streamingMsgAdded) {
                    setMessages((prev) => [
                      ...prev,
                      { id: streamingId, role: "assistant", content: evt.token, timestamp: new Date(), dept: deptId },
                    ]);
                    streamingMsgAdded = true;
                  } else {
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === streamingId ? { ...m, content: m.content + evt.token } : m
                      )
                    );
                  }
                } else if (evt.type === "done") {
                  setTyping(false);
                  const finalText = evt.response?.message?.content ?? "";
                  if (finalText) {
                    setMessages((prev) =>
                      prev.map((m) => (m.id === streamingId ? { ...m, content: finalText } : m))
                    );
                  }
                } else if (evt.type === "error") {
                  setTyping(false);
                  setMessages((prev) => [
                    ...prev,
                    { id: genId(), role: "assistant", content: `⚠️ ${evt.message}`, timestamp: new Date(), dept: deptId },
                  ]);
                }
              } catch {}
            }
          }
        })
        .catch(() => {
          setTyping(false);
          setMessages((prev) => [
            ...prev,
            {
              id: genId(),
              role: "assistant",
              content: "⚠️ Could not reach the API. Please check your connection.",
              timestamp: new Date(),
              dept: deptId,
            },
          ]);
        });
    }
  }, [input, deptId, sessionId]);

  /* Keyboard handler */
  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  /* Status badge */
  const wsLabel: Record<WsState, { label: string; color: string }> = {
    connecting: { label: "Connecting…", color: "text-amber-400" },
    open: { label: "Connected", color: "text-emerald-400" },
    closed: { label: "Disconnected", color: "text-slate-500" },
    error: { label: "Error", color: "text-red-400" },
  };
  const wsInfo = wsLabel[wsState];

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Left panel: dept selector ──────────────────────── */}
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
          <div className="mb-2 flex items-center justify-between px-2">
            <p className="font-mono text-[10px] uppercase tracking-widest text-slate-600">
              Department
            </p>
            <button
              onClick={() => { setShowHistory(!showHistory); if (!showHistory) fetchHistory(); }}
              className={`rounded p-0.5 transition-colors ${showHistory ? "text-violet-400" : "text-slate-500 hover:text-slate-300"}`}
              title="Chat history"
            >
              <History className="h-3.5 w-3.5" />
            </button>
          </div>

          {showHistory ? (
            <div>
              <div className="mb-1 flex items-center justify-between px-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-widest">Recent sessions</span>
                <button
                  onClick={() => { setShowHistory(false); setSessionId(genId()); setMessages([{id:genId(),role:"assistant",content:getDept(deptId).greeting,timestamp:new Date(),dept:deptId}]); }}
                  className="text-[10px] text-violet-400 hover:text-violet-300 flex items-center gap-0.5"
                >
                  <Plus className="h-3 w-3" /> New
                </button>
              </div>
              {pastSessions.length === 0 ? (
                <p className="text-[11px] text-slate-600 px-2 py-4 text-center">No past sessions</p>
              ) : (
                pastSessions.map((s) => {
                  const d = getDept(s.department);
                  return (
                    <button
                      key={s.id}
                      onClick={() => loadSession(s.id, s.department)}
                      className="w-full text-left rounded-lg px-2 py-2 mb-0.5 hover:bg-[#111827] transition-colors"
                    >
                      <p className={`text-[11px] font-medium truncate ${d.colorText}`}>{d.label}</p>
                      <p className="text-[10px] text-slate-500 truncate">{s.title ?? s.id.slice(0,8)}</p>
                      <p className="text-[9px] text-slate-600 mt-0.5">{new Date(s.created_at).toLocaleDateString()}</p>
                    </button>
                  );
                })
              )}
            </div>
          ) : (
            DEPARTMENTS.map((d) => {
              const DIcon = d.icon;
              const active = d.id === deptId;
              return (
                <button
                  key={d.id}
                  onClick={() => setDeptId(d.id)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs transition-all ${
                    active
                      ? `${d.colorBg} ${d.colorText} border ${d.colorBorder}`
                      : "text-slate-500 hover:bg-[#111827] hover:text-slate-300"
                  }`}
                >
                  <DIcon className="h-3.5 w-3.5 flex-shrink-0" />
                  <span className="truncate">{d.label}</span>
                </button>
              );
            })
          )}
        </div>

        {/* Session info */}
        <div className="border-t border-[#1f2937] p-3">
          <div className="rounded-lg border border-[#1f2937] bg-[#0c111d] p-2.5">
            <p className="mb-1 font-mono text-[9px] uppercase tracking-widest text-slate-600">
              Session
            </p>
            <p className="font-mono text-[10px] text-slate-400">{sessionId}</p>
            <div className="mt-1.5 flex items-center gap-1">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  wsState === "open"
                    ? "bg-emerald-500 status-pulse"
                    : wsState === "connecting"
                    ? "bg-amber-500"
                    : "bg-slate-600"
                }`}
              />
              <span className={`font-mono text-[10px] ${wsInfo.color}`}>{wsInfo.label}</span>
              {wsState !== "open" && wsState !== "connecting" && (
                <button
                  onClick={connect}
                  className="ml-auto rounded p-0.5 text-slate-500 hover:text-slate-300"
                  title="Reconnect"
                >
                  <RotateCcw className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main chat area ─────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Chat header */}
        <div className="flex h-12 flex-shrink-0 items-center justify-between border-b border-[#1f2937] bg-[#0a0f1a] px-5">
          <div className="flex items-center gap-2.5">
            <div className={`rounded-md p-1.5 ${dept.colorBg} border ${dept.colorBorder}`}>
              <Icon className={`h-4 w-4 ${dept.colorText}`} />
            </div>
            <div>
              <span className="text-sm font-medium text-slate-100">{dept.label} Agent</span>
              <span className="ml-2 text-[11px] text-slate-500">AI-powered</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Agent Handoff dropdown */}
            <div className="relative group">
              <button className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 transition-all hover:border-[#374151] hover:text-slate-200">
                <ArrowRightLeft className="h-3 w-3" /> Transfer
              </button>
              <div className="absolute right-0 top-full mt-1 w-44 rounded-lg border border-[#1f2937] bg-[#0a0f1a] shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                <p className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-widest text-slate-600">Transfer to</p>
                {DEPARTMENTS.filter((d) => d.id !== deptId).map((d) => (
                  <button
                    key={d.id}
                    onClick={() => {
                      const note: Message = { id: genId(), role: "assistant", content: `Transferring you to the ${d.label} department…`, timestamp: new Date(), dept: deptId };
                      setMessages((prev) => [...prev, note]);
                      setDeptId(d.id);
                    }}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-xs transition-colors hover:bg-[#111827] ${d.colorText}`}
                  >
                    <d.icon className="h-3 w-3" /> {d.label}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={() => {
                const txt = messages
                  .map((m) => `[${m.timestamp.toISOString()}] ${m.role.toUpperCase()}: ${m.content}`)
                  .join("\n\n");
                const blob = new Blob([txt], { type: "text/plain" });
                const url  = URL.createObjectURL(blob);
                const a    = document.createElement("a");
                a.href     = url;
                a.download = `conversation-${deptId}-${new Date().toISOString().slice(0,10)}.txt`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              disabled={messages.length === 0}
              title="Export conversation"
              className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-emerald-500/30 hover:text-emerald-400 disabled:opacity-30"
            >
              <Download className="h-3 w-3" /> Export
            </button>
            <Link
              href={`/voice?dept=${deptId}`}
              className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-1.5 text-xs text-slate-400 transition-all hover:border-[#374151] hover:text-slate-200"
            >
              <Mic className="h-3 w-3" />
              Switch to Voice
            </Link>
            <button className="rounded-lg border border-[#1f2937] p-1.5 text-slate-500 transition-colors hover:text-slate-300">
              <Info className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 px-6 py-5">
          {messages.map((msg) => {
            const isUser = msg.role === "user";
            const d = msg.dept ? getDept(msg.dept) : dept;
            return (
              <div
                key={msg.id}
                className={`flex gap-3 slide-up ${isUser ? "flex-row-reverse" : ""}`}
              >
                {/* Avatar */}
                <div
                  className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    isUser
                      ? "bg-slate-700 text-slate-300"
                      : `${d.colorBg} ${d.colorText} border ${d.colorBorder}`
                  }`}
                >
                  {isUser ? "U" : <d.icon className="h-3.5 w-3.5" />}
                </div>

                {/* Bubble */}
                <div className={`max-w-[72%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      isUser
                        ? "rounded-tr-sm bg-amber-500/15 text-slate-100"
                        : "rounded-tl-sm border border-[#1f2937] bg-[#0c111d] text-slate-200"
                    }`}
                  >
                    {isUser ? (
                      <p>{String(msg.content ?? "")}</p>
                    ) : (
                      <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-headings:text-slate-100">
                        <ReactMarkdown>{typeof msg.content === "string" ? msg.content : String(msg.content ?? "")}</ReactMarkdown>
                      </div>
                    )}
                  </div>
                  <span className="px-1 font-mono text-[10px] text-slate-600">
                    {formatTime(msg.timestamp)}
                    {!isUser && (
                      <span className={`ml-2 ${d.colorText} opacity-70`}>{d.label}</span>
                    )}
                  </span>
                </div>
              </div>
            );
          })}

          {/* Typing indicator */}
          {typing && (
            <div className="flex gap-3 slide-up">
              <div
                className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border ${dept.colorBg} ${dept.colorBorder}`}
              >
                <Icon className={`h-3.5 w-3.5 ${dept.colorText}`} />
              </div>
              <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm border border-[#1f2937] bg-[#0c111d] px-4 py-3">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div className="flex-shrink-0 border-t border-[#1f2937] bg-[#070d1a] px-5 py-4">
          <div className="flex items-end gap-3">
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".txt,.csv,.md,.json,.pdf,.png,.jpg,.jpeg,.gif,.webp"
              onChange={handleFileSelect}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="mb-2 text-slate-500 transition-colors hover:text-slate-300 disabled:opacity-40"
              title="Attach file"
            >
              {uploading ? (
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
              ) : (
                <Paperclip className="h-4 w-4" />
              )}
            </button>

            <div className="relative flex-1">
              {/* File attachment badge */}
              {uploadedFile && (
                <div className="mb-1 flex items-center gap-1.5 rounded-lg bg-indigo-900/40 border border-indigo-700/50 px-2.5 py-1 text-xs text-indigo-300">
                  <Paperclip className="h-3 w-3" />
                  <span className="truncate max-w-[200px]">{uploadedFile.filename}</span>
                  <button onClick={() => setUploadedFile(null)} className="ml-auto text-indigo-400 hover:text-white">×</button>
                </div>
              )}
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={`Message ${dept.label} Agent…`}
                rows={1}
                className="w-full resize-none rounded-xl border border-[#1f2937] bg-[#0c111d] px-4 py-3 pr-12 text-sm text-slate-100 placeholder-slate-600 transition-colors focus:border-[#374151] focus:outline-none focus:ring-0"
                style={{ maxHeight: "120px" }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
                }}
              />
            </div>

            <button
              onClick={sendMessage}
              disabled={!input.trim() && !uploadedFile}
              className={`mb-2 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-all ${
                (input.trim() || uploadedFile)
                  ? "bg-amber-500 text-black hover:bg-amber-400"
                  : "bg-[#111827] text-slate-600 cursor-not-allowed"
              }`}
            >
              <Send className="h-4 w-4" />
            </button>
          </div>

          <p className="mt-2 text-center font-mono text-[10px] text-slate-700">
            <Zap className="mr-1 inline h-2.5 w-2.5 text-amber-500/50" />
            Powered by Swarms · Press <kbd className="rounded bg-[#1f2937] px-1 text-slate-500">Enter</kbd> to send, <kbd className="rounded bg-[#1f2937] px-1 text-slate-500">Shift+Enter</kbd> for new line
          </p>
        </div>
      </div>
    </div>
  );
}
