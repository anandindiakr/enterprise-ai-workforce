"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Star, Headphones, ShoppingCart, Users, DollarSign,
  Cpu, Megaphone, MessageSquare, Mic, Activity,
  Zap, Shield, Brain, ChevronRight, RefreshCw, PhoneOutgoing, X,
} from "lucide-react";
import { authHeaders } from "@/lib/auth";

/* Departments allowed to place a REAL outbound call via Vapi (must match
 * app/services/action_dispatcher.py `_OUTBOUND_CALL_DEPARTMENTS`). */
const OUTBOUND_CALL_DEPARTMENTS = new Set(["sales", "marketing", "customer_care"]);

/* ── Types ───────────────────────────────────────────────── */

interface AgentInfo {
  agent_name: string;
  department: string;
  description: string;
  model: string;
  capabilities: string[];
  tools: string[];
  voice_enabled: boolean;
  chat_enabled: boolean;
}

interface AgentsApiResponse {
  agents: AgentInfo[];
  total: number;
  active: number;
}

/* ── Department meta ─────────────────────────────────────── */

const DEPT_META: Record<string, {
  icon: React.ElementType;
  colorText: string;
  colorBg: string;
  colorBorder: string;
  gradient: string;
}> = {
  reception:    { icon: Star,        colorText: "text-amber-400",   colorBg: "bg-amber-500/10",   colorBorder: "border-amber-500/25",   gradient: "from-amber-500/10 to-transparent" },
  customer_care:{ icon: Headphones,  colorText: "text-cyan-400",    colorBg: "bg-cyan-500/10",    colorBorder: "border-cyan-500/25",    gradient: "from-cyan-500/10 to-transparent" },
  sales:        { icon: ShoppingCart,colorText: "text-emerald-400", colorBg: "bg-emerald-500/10", colorBorder: "border-emerald-500/25", gradient: "from-emerald-500/10 to-transparent" },
  hr:           { icon: Users,       colorText: "text-violet-400",  colorBg: "bg-violet-500/10",  colorBorder: "border-violet-500/25",  gradient: "from-violet-500/10 to-transparent" },
  finance:      { icon: DollarSign,  colorText: "text-rose-400",    colorBg: "bg-rose-500/10",    colorBorder: "border-rose-500/25",    gradient: "from-rose-500/10 to-transparent" },
  technology:   { icon: Cpu,         colorText: "text-blue-400",    colorBg: "bg-blue-500/10",    colorBorder: "border-blue-500/25",    gradient: "from-blue-500/10 to-transparent" },
  marketing:    { icon: Megaphone,   colorText: "text-orange-400",  colorBg: "bg-orange-500/10",  colorBorder: "border-orange-500/25",  gradient: "from-orange-500/10 to-transparent" },
};

const DEFAULT_META = { icon: Brain, colorText: "text-slate-400", colorBg: "bg-slate-500/10", colorBorder: "border-slate-500/25", gradient: "from-slate-500/10 to-transparent" };

/* ── Static fallback data ────────────────────────────────── */

const STATIC_AGENTS: AgentInfo[] = [
  { agent_name: "Alex",    department: "reception",     description: "Front-desk AI for routing, greetings, and visitor management.",           model: "gpt-4o-mini", capabilities: ["routing","scheduling","multilingual"], tools: ["calendar","email"],           voice_enabled: true, chat_enabled: true },
  { agent_name: "Care",    department: "customer_care", description: "Resolves support tickets, handles complaints, and manages escalations.",   model: "gpt-4o-mini", capabilities: ["ticketing","sentiment","knowledge-base"], tools: ["crm","knowledge"],        voice_enabled: true, chat_enabled: true },
  { agent_name: "Sam",     department: "sales",         description: "Drives pipeline, qualifies leads, and prepares commercial proposals.",      model: "gpt-4o-mini", capabilities: ["crm","proposals","pricing"],          tools: ["crm","email","calendar"],    voice_enabled: true, chat_enabled: true },
  { agent_name: "Harper",  department: "hr",            description: "Handles onboarding, HR policy Q&A, leave requests, and recruiting.",       model: "gpt-4o-mini", capabilities: ["onboarding","policy","recruiting"],     tools: ["hris","calendar"],           voice_enabled: true, chat_enabled: true },
  { agent_name: "Finley",  department: "finance",       description: "Processes invoices, budget reports, and financial reconciliation.",         model: "gpt-4o-mini", capabilities: ["invoicing","budgets","reporting"],      tools: ["erp","analytics"],           voice_enabled: true, chat_enabled: true },
  { agent_name: "Byte",    department: "technology",    description: "Diagnoses IT issues, manages tickets, and guides system configurations.",   model: "gpt-4o-mini", capabilities: ["diagnostics","devops","monitoring"],    tools: ["devops","knowledge"],        voice_enabled: true, chat_enabled: true },
  { agent_name: "Mara",    department: "marketing",     description: "Creates campaigns, writes copy, analyzes engagement, and manages brand.",   model: "gpt-4o-mini", capabilities: ["copywriting","campaigns","analytics"],  tools: ["analytics","email"],         voice_enabled: true, chat_enabled: true },
];

/* ── Component ───────────────────────────────────────────── */

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentInfo[]>(STATIC_AGENTS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [callTarget, setCallTarget] = useState<AgentInfo | null>(null);
  const [callPhone, setCallPhone] = useState("");
  const [callReason, setCallReason] = useState("");
  const [callSubmitting, setCallSubmitting] = useState(false);
  const [callResult, setCallResult] = useState<{ success: boolean; summary: string } | null>(null);

  async function submitCall() {
    if (!callTarget || !callPhone.trim()) return;
    setCallSubmitting(true);
    setCallResult(null);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
      const res = await fetch(`${apiBase}/api/v1/vapi/outbound-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          phone_number: callPhone.trim(),
          reason: callReason.trim(),
          department: callTarget.department,
        }),
      });
      const data = await res.json().catch(() => ({}));
      setCallResult({
        success: res.ok && data.success !== false,
        summary: data.summary || (res.ok ? "Call placed." : "Could not place the call."),
      });
    } catch {
      setCallResult({ success: false, summary: "Network error — could not reach the backend." });
    } finally {
      setCallSubmitting(false);
    }
  }

  function closeCallModal() {
    setCallTarget(null);
    setCallPhone("");
    setCallReason("");
    setCallResult(null);
  }

  async function load(showRefresh = false) {
    if (showRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
      const res = await fetch(`${apiBase}/api/v1/agents`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: AgentsApiResponse = await res.json();
      setAgents(data.agents?.length ? data.agents : STATIC_AGENTS);
    } catch {
      // Silently fall back to static data — API may not have /agents endpoint yet
      setAgents(STATIC_AGENTS);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex h-14 flex-shrink-0 items-center justify-between border-b border-[#1f2937] bg-[#0a0f1a] px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20">
            <Brain className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100">AI Agent Roster</h1>
            <p className="text-[11px] text-slate-500">{agents.length} agents deployed across {Object.keys(DEPT_META).length} departments</p>
          </div>
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-1.5 text-xs text-slate-400 transition-all hover:border-[#374151] hover:text-slate-200 disabled:opacity-50"
        >
          <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Stats bar */}
      <div className="flex flex-shrink-0 gap-px border-b border-[#1f2937] bg-[#070d1a]">
        {[
          { label: "Total Agents",    value: agents.length,                          icon: Brain,    color: "text-slate-300" },
          { label: "Voice Enabled",   value: agents.filter(a => a.voice_enabled).length, icon: Mic,  color: "text-cyan-400"  },
          { label: "Chat Enabled",    value: agents.filter(a => a.chat_enabled).length,  icon: MessageSquare, color: "text-emerald-400" },
          { label: "Departments",     value: Object.keys(DEPT_META).length,           icon: Zap,     color: "text-amber-400" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="flex flex-1 items-center gap-2.5 px-5 py-3">
            <Icon className={`h-4 w-4 flex-shrink-0 ${color}`} />
            <div>
              <p className={`text-lg font-bold leading-none ${color}`}>{value}</p>
              <p className="mt-0.5 text-[10px] text-slate-600">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Agent grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#1f2937] border-t-amber-500" />
              <p className="text-sm text-slate-500">Loading agents…</p>
            </div>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {agents.map((agent) => {
              const meta = DEPT_META[agent.department] ?? DEFAULT_META;
              const Icon = meta.icon;
              return (
                <div
                  key={agent.agent_name}
                  className={`group relative overflow-hidden rounded-xl border ${meta.colorBorder} bg-[#0c111d] transition-all hover:border-opacity-60 hover:shadow-lg hover:shadow-black/20`}
                >
                  {/* Gradient accent */}
                  <div className={`absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r ${meta.gradient}`} />

                  {/* Card header */}
                  <div className="p-4 pb-3">
                    <div className="flex items-start justify-between">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${meta.colorBg} border ${meta.colorBorder}`}>
                        <Icon className={`h-5 w-5 ${meta.colorText}`} />
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-emerald-500 status-pulse" />
                        <span className="text-[10px] text-emerald-500">ACTIVE</span>
                      </div>
                    </div>

                    <h3 className="mt-3 font-semibold text-slate-100">{agent.agent_name}</h3>
                    <p className={`text-[11px] font-mono uppercase tracking-wider ${meta.colorText}`}>
                      {agent.department.replace("_", " ")}
                    </p>
                    <p className="mt-1.5 text-xs leading-relaxed text-slate-500 line-clamp-2">
                      {agent.description}
                    </p>
                  </div>

                  {/* Capabilities */}
                  <div className="border-t border-[#1f2937] px-4 py-2.5">
                    <p className="mb-1.5 text-[9px] uppercase tracking-widest text-slate-600">Capabilities</p>
                    <div className="flex flex-wrap gap-1">
                      {agent.capabilities.slice(0, 4).map((cap) => (
                        <span
                          key={cap}
                          className={`rounded-full px-1.5 py-0.5 text-[9px] font-mono ${meta.colorBg} ${meta.colorText} border ${meta.colorBorder}`}
                        >
                          {cap}
                        </span>
                      ))}
                      {agent.capabilities.length > 4 && (
                        <span className="rounded-full border border-[#1f2937] px-1.5 py-0.5 text-[9px] font-mono text-slate-600">
                          +{agent.capabilities.length - 4}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Footer: channels + actions */}
                  <div className="border-t border-[#1f2937] px-4 py-2.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {agent.chat_enabled && (
                          <span className="flex items-center gap-1 text-[10px] text-emerald-500">
                            <MessageSquare className="h-2.5 w-2.5" /> Chat
                          </span>
                        )}
                        {agent.voice_enabled && (
                          <span className="flex items-center gap-1 text-[10px] text-cyan-500">
                            <Mic className="h-2.5 w-2.5" /> Voice
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        {agent.chat_enabled && (
                          <Link
                            href={`/chat?dept=${agent.department}`}
                            className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-[10px] font-medium transition-all ${meta.colorBg} ${meta.colorText} border ${meta.colorBorder} hover:opacity-80`}
                          >
                            Chat <ChevronRight className="h-2.5 w-2.5" />
                          </Link>
                        )}
                        {agent.voice_enabled && (
                          <Link
                            href={`/voice?dept=${agent.department}`}
                            className="flex items-center gap-1 rounded-lg border border-[#1f2937] px-2.5 py-1 text-[10px] text-slate-500 transition-all hover:text-slate-300"
                          >
                            <Mic className="h-2.5 w-2.5" />
                          </Link>
                        )}
                        {OUTBOUND_CALL_DEPARTMENTS.has(agent.department) && (
                          <button
                            onClick={() => setCallTarget(agent)}
                            title="Place a real outbound call via Vapi"
                            className="flex items-center gap-1 rounded-lg border border-[#1f2937] px-2.5 py-1 text-[10px] text-slate-500 transition-all hover:border-emerald-500/40 hover:text-emerald-400"
                          >
                            <PhoneOutgoing className="h-2.5 w-2.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Model badge */}
                  <div className="absolute right-3 top-3.5">
                    <span className="rounded border border-[#1f2937] bg-[#070d1a] px-1.5 py-0.5 font-mono text-[9px] text-slate-600">
                      {agent.model}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Outbound call modal */}
      {callTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm rounded-xl border border-[#1f2937] bg-[#0c111d] p-5 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PhoneOutgoing className="h-4 w-4 text-emerald-400" />
                <h3 className="text-sm font-semibold text-slate-100">
                  Call lead as {callTarget.agent_name}
                </h3>
              </div>
              <button onClick={closeCallModal} className="text-slate-500 hover:text-slate-300">
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mb-3 text-[11px] text-slate-500">
              Places a real outbound phone call via Vapi using the {callTarget.department.replace("_", " ")} assistant.
            </p>
            <label className="mb-1 block text-[10px] uppercase tracking-wide text-slate-500">Phone number (E.164)</label>
            <input
              value={callPhone}
              onChange={(e) => setCallPhone(e.target.value)}
              placeholder="+6591234567"
              className="mb-3 w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-sm text-slate-200 outline-none focus:border-emerald-500/50"
            />
            <label className="mb-1 block text-[10px] uppercase tracking-wide text-slate-500">Reason (optional)</label>
            <input
              value={callReason}
              onChange={(e) => setCallReason(e.target.value)}
              placeholder="Follow up on demo request"
              className="mb-4 w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-sm text-slate-200 outline-none focus:border-emerald-500/50"
            />
            {callResult && (
              <div className={`mb-3 rounded-lg border px-3 py-2 text-[11px] ${callResult.success ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-rose-500/30 bg-rose-500/10 text-rose-300"}`}>
                {callResult.summary}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button onClick={closeCallModal} className="rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200">
                Close
              </button>
              <button
                onClick={submitCall}
                disabled={callSubmitting || !callPhone.trim()}
                className="flex items-center gap-1.5 rounded-lg bg-emerald-500/90 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {callSubmitting ? "Calling…" : "Place call"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
