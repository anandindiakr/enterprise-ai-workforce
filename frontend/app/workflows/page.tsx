"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getToken, authHeaders } from "@/lib/auth";
import {
  Zap,
  Play,
  ChevronRight,
  Clock,
  Users,
  DollarSign,
  Cpu,
  Megaphone,
  Headphones,
  Star,
  ShoppingCart,
  CheckCircle,
  Loader2,
  AlertTriangle,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

const DEPT_COLORS: Record<string, string> = {
  hr:            "text-violet-400 bg-violet-500/10 border-violet-500/20",
  sales:         "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  technology:    "text-blue-400 bg-blue-500/10 border-blue-500/20",
  finance:       "text-rose-400 bg-rose-500/10 border-rose-500/20",
  marketing:     "text-orange-400 bg-orange-500/10 border-orange-500/20",
  customer_care: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  reception:     "text-amber-400 bg-amber-500/10 border-amber-500/20",
};

const DEPT_ICONS: Record<string, React.ElementType> = {
  hr:            Users,
  sales:         ShoppingCart,
  technology:    Cpu,
  finance:       DollarSign,
  marketing:     Megaphone,
  customer_care: Headphones,
  reception:     Star,
};

interface WorkflowTemplate {
  id: string;
  name: string;
  department: string;
  description: string;
  steps: string[];
  category: string;
  estimated_minutes: number;
}

interface RunResult {
  workflow_id: string;
  output: string;
  succeeded: boolean;
  duration_ms: number;
  agents_involved: string[];
}

export default function WorkflowsPage() {
  const router = useRouter();
  const [workflows, setWorkflows]   = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading]       = useState(true);
  const [running, setRunning]       = useState<string | null>(null);
  const [result, setResult]         = useState<{ wf: string; data: RunResult } | null>(null);
  const [taskInput, setTaskInput]   = useState<Record<string, string>>({});
  const [error, setError]           = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/workflows`, { headers: authHeaders() });
      const data = await res.json();
      setWorkflows(data.workflows ?? []);
    } catch {
      setError("Failed to load workflows");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    load();
  }, [load, router]);

  async function runWorkflow(wf: WorkflowTemplate) {
    setRunning(wf.id);
    setResult(null);
    setError("");
    try {
      const task = taskInput[wf.id] || wf.description;
      const res = await fetch(`${API}/api/v1/workflows`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          task,
          department: wf.department,
          user_id: "admin",
          context: { workflow_template: wf.id },
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      setResult({ wf: wf.id, data });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Workflow execution failed");
    } finally {
      setRunning(null);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#030712]">
      {/* Header */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#1f2937] px-6">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-amber-400" />
          <span className="font-mono text-sm font-semibold uppercase tracking-widest text-slate-300">
            Workflow Automation
          </span>
        </div>
        <span className="rounded-full border border-[#1f2937] px-3 py-0.5 font-mono text-[10px] text-slate-500">
          {workflows.length} templates
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {/* Error banner */}
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-400">
            <AlertTriangle className="h-3.5 w-3.5" />
            {error}
          </div>
        )}

        {/* Result banner */}
        {result && (
          <div className="mb-6 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
            <div className="mb-1 flex items-center gap-2 text-xs font-semibold text-emerald-400">
              <CheckCircle className="h-3.5 w-3.5" />
              Workflow completed in {result.data.duration_ms}ms
            </div>
            <p className="whitespace-pre-wrap text-xs leading-relaxed text-slate-300">
              {typeof result.data.output === "string"
                ? result.data.output
                : JSON.stringify(result.data.output, null, 2)}
            </p>
            {result.data.agents_involved?.length > 0 && (
              <p className="mt-2 text-[10px] text-slate-500">
                Agents: {result.data.agents_involved.join(", ")}
              </p>
            )}
          </div>
        )}

        {loading ? (
          <div className="flex h-48 items-center justify-center gap-2 text-slate-500 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading workflows…
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {workflows.map((wf) => {
              const colorCls = DEPT_COLORS[wf.department] ?? "text-slate-400 bg-slate-500/10 border-slate-500/20";
              const Icon = DEPT_ICONS[wf.department] ?? Zap;
              const isRunning = running === wf.id;

              return (
                <div
                  key={wf.id}
                  className="flex flex-col rounded-xl border border-[#1f2937] bg-[#070d1a] p-5 gap-4"
                >
                  {/* Title row */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${colorCls}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-slate-200">{wf.name}</p>
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">{wf.category}</p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1 text-[10px] text-slate-600">
                      <Clock className="h-3 w-3" />
                      ~{wf.estimated_minutes}m
                    </div>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-slate-400 leading-relaxed">{wf.description}</p>

                  {/* Steps */}
                  <div className="space-y-1">
                    {wf.steps.map((step, i) => (
                      <div key={i} className="flex items-center gap-2 text-[11px] text-slate-500">
                        <ChevronRight className="h-3 w-3 shrink-0 text-slate-700" />
                        {step}
                      </div>
                    ))}
                  </div>

                  {/* Task input */}
                  <textarea
                    rows={2}
                    placeholder={`Custom task (optional) — default: "${wf.description}"`}
                    value={taskInput[wf.id] ?? ""}
                    onChange={(e) => setTaskInput((p) => ({ ...p, [wf.id]: e.target.value }))}
                    className="w-full resize-none rounded-lg border border-[#1f2937] bg-[#030712] px-3 py-2 text-xs text-slate-300 placeholder-slate-700 outline-none focus:border-amber-500/40"
                  />

                  {/* Run button */}
                  <button
                    onClick={() => runWorkflow(wf)}
                    disabled={isRunning || running !== null}
                    className="flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-xs font-semibold text-black transition-all hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isRunning ? (
                      <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Running…</>
                    ) : (
                      <><Play className="h-3.5 w-3.5" /> Run Workflow</>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
