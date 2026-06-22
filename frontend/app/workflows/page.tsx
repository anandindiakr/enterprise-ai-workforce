"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getToken, getUser, authHeaders } from "@/lib/auth";
import {
  Zap, Play, ChevronRight, Clock, Users, DollarSign, Cpu,
  Megaphone, Headphones, Star, ShoppingCart, CheckCircle,
  Loader2, AlertTriangle, Info, ArrowRight, BookOpen,
  ChevronDown, ChevronUp, Sparkles, GitBranch, Settings,
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

// ─── Visual flow diagram for a single workflow card ──────────────────────────

function StepFlow({ steps, dept }: { steps: string[]; dept: string }) {
  const colorClass = DEPT_COLORS[dept] ?? "text-slate-400 bg-slate-500/10 border-slate-500/20";
  return (
    <div className="mt-3 space-y-1">
      {steps.map((step, i) => (
        <div key={i} className="flex flex-col items-start">
          <div className={`flex items-center gap-2 w-full rounded-lg border px-3 py-2 ${colorClass}`}>
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-black/30 text-[10px] font-bold">
              {i + 1}
            </span>
            <span className="text-xs font-medium flex-1">{step}</span>
            <Sparkles className="h-3 w-3 opacity-40 shrink-0" />
          </div>
          {i < steps.length - 1 && (
            <div className="ml-2.5 my-0.5 w-0.5 h-3 bg-slate-700 rounded-full" />
          )}
        </div>
      ))}
      <div className="flex items-center gap-2 mt-1 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2">
        <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0" />
        <span className="text-xs text-emerald-300 font-medium">Result delivered</span>
      </div>
    </div>
  );
}

// ─── Explainer banner ─────────────────────────────────────────────────────────

function ExplainerBanner() {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-6 rounded-xl border border-amber-500/20 bg-amber-500/5">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-amber-400" />
          <span className="text-sm font-semibold text-amber-300">What are Workflows — and how do I use them?</span>
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-5 text-sm text-slate-300 border-t border-amber-500/10">

          {/* What are workflows */}
          <div className="pt-4">
            <p className="font-semibold text-white mb-2">What is a Workflow?</p>
            <p className="text-slate-400 leading-relaxed">
              A Workflow is a pre-built sequence of AI-powered tasks that runs automatically end-to-end.
              Instead of chatting with an agent manually, you describe a goal and the system assigns the right
              AI agents, executes each step in order, and returns a structured result — all in minutes.
            </p>
          </div>

          {/* How it works diagram */}
          <div>
            <p className="font-semibold text-white mb-3">How It Works</p>
            <div className="flex flex-wrap items-center gap-2">
              {[
                { icon: Settings,    label: "You choose a template",  color: "text-amber-400",   bg: "bg-amber-500/10  border-amber-500/20" },
                { icon: GitBranch,   label: "Optionally customise task", color: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/20" },
                { icon: Zap,         label: "AI agents execute steps", color: "text-blue-400",    bg: "bg-blue-500/10   border-blue-500/20" },
                { icon: CheckCircle, label: "Result returned to you",  color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
              ].map(({ icon: Icon, label, color, bg }, i, arr) => (
                <div key={label} className="flex items-center gap-2">
                  <div className={`flex flex-col items-center gap-1.5 rounded-xl border p-3 w-32 text-center ${bg}`}>
                    <Icon className={`h-5 w-5 ${color}`} />
                    <span className={`text-[11px] font-medium leading-tight ${color}`}>{label}</span>
                  </div>
                  {i < arr.length - 1 && <ArrowRight className="h-4 w-4 text-slate-600 shrink-0" />}
                </div>
              ))}
            </div>
          </div>

          {/* How to customise */}
          <div>
            <p className="font-semibold text-white mb-2">How to Customise a Workflow</p>
            <ol className="space-y-2 text-slate-400 list-none">
              {[
                { n: "1", text: "Browse the templates below and find the one that matches your goal (HR, Sales, Finance, etc.)." },
                { n: "2", text: "Read the step list to understand what the AI will do automatically." },
                { n: "3", text: "In the text box, write your specific task. For example, instead of the default \"auto-qualify leads\", type \"qualify leads from the Salesforce export attached in Slack today\"." },
                { n: "4", text: "Click Run Workflow — the AI agents will execute all steps and return a structured result." },
                { n: "5", text: "The result appears in the green panel above the templates. You can copy it, share it, or use it as input for the next workflow." },
              ].map(({ n, text }) => (
                <li key={n} className="flex gap-3">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-500/20 text-[10px] font-bold text-amber-400">{n}</span>
                  <span className="leading-relaxed">{text}</span>
                </li>
              ))}
            </ol>
          </div>

          {/* Tips */}
          <div className="rounded-lg border border-slate-700 bg-slate-800/60 p-3">
            <p className="text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-blue-400" /> Tips
            </p>
            <ul className="space-y-1 text-xs text-slate-400 list-disc list-inside">
              <li>Leave the task box empty to run the default template task.</li>
              <li>Each step inside a workflow is handled by a department-specific AI agent.</li>
              <li>Longer tasks are fine — the text box is resizable, drag the bottom-right corner.</li>
              <li>Workflows automatically escalate to a human if the AI is not confident.</li>
              <li>You can chain workflows: use the output of one as the input for another.</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Workflow card ────────────────────────────────────────────────────────────

function WorkflowCard({
  wf, isRunning, anyRunning, taskInput, onTaskChange, onRun, resultId,
}: {
  wf: WorkflowTemplate;
  isRunning: boolean;
  anyRunning: boolean;
  taskInput: string;
  onTaskChange: (v: string) => void;
  onRun: () => void;
  resultId: string | null;
}) {
  const [showSteps, setShowSteps] = useState(false);
  const colorCls = DEPT_COLORS[wf.department] ?? "text-slate-400 bg-slate-500/10 border-slate-500/20";
  const Icon = DEPT_ICONS[wf.department] ?? Zap;

  return (
    <div className="flex flex-col rounded-xl border border-[#1f2937] bg-[#070d1a] p-5 gap-4">

      {/* Title row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${colorCls}`}>
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-200 leading-tight">{wf.name}</p>
            <p className="text-[10px] uppercase tracking-wider text-slate-500 mt-0.5">{wf.category}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1 text-[10px] text-slate-600 mt-0.5">
          <Clock className="h-3 w-3" />
          ~{wf.estimated_minutes}m
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-slate-400 leading-relaxed">{wf.description}</p>

      {/* Steps toggle */}
      <button
        onClick={() => setShowSteps(!showSteps)}
        className="flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-slate-300 transition-colors self-start"
      >
        {showSteps ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        {showSteps ? "Hide" : "Show"} steps ({wf.steps.length})
      </button>

      {/* Step flow — visual */}
      {showSteps && <StepFlow steps={wf.steps} dept={wf.department} />}

      {/* Task input — larger, resizable */}
      <div>
        <label className="block text-[11px] text-slate-500 mb-1.5 font-medium">
          Custom task description{" "}
          <span className="text-slate-700 font-normal">(optional — leave blank to use default)</span>
        </label>
        <textarea
          rows={5}
          placeholder={`Default: "${wf.description}"\n\nOr describe your specific task here. Be as detailed as you like — e.g. "Onboard John Smith joining HR on Monday. Set up accounts for Slack, Jira and Gmail. Schedule intro with team lead at 10am."`}
          value={taskInput}
          onChange={(e) => onTaskChange(e.target.value)}
          className="w-full resize-y rounded-lg border border-[#1f2937] bg-[#030712] px-3 py-2.5 text-xs text-slate-300 placeholder-slate-700/80 outline-none focus:border-amber-500/40 leading-relaxed min-h-[80px]"
        />
      </div>

      {/* Run button */}
      <button
        onClick={onRun}
        disabled={isRunning || anyRunning}
        className="flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-semibold text-black transition-all hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isRunning ? (
          <><Loader2 className="h-4 w-4 animate-spin" /> Running…</>
        ) : (
          <><Play className="h-4 w-4" /> Run Workflow</>
        )}
      </button>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function WorkflowsPage() {
  const router = useRouter();
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading]     = useState(true);
  const [running, setRunning]     = useState<string | null>(null);
  const [result, setResult]       = useState<{ wf: string; data: RunResult } | null>(null);
  const [taskInput, setTaskInput] = useState<Record<string, string>>({});
  const [error, setError]         = useState("");

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
      const task = taskInput[wf.id]?.trim() || wf.description;
      const res = await fetch(`${API}/api/v1/workflows`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          task,
          department: wf.department,
          user_id: getUser()?.username ?? "admin",
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
      {/* Top bar */}
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

        {/* Explainer */}
        <ExplainerBanner />

        {/* Error banner */}
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-400">
            <AlertTriangle className="h-3.5 w-3.5" />
            {error}
          </div>
        )}

        {/* Result panel */}
        {result && (
          <div className="mb-6 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-emerald-400">
              <CheckCircle className="h-3.5 w-3.5" />
              Workflow completed in {result.data.duration_ms}ms
            </div>
            <pre className="whitespace-pre-wrap text-xs leading-relaxed text-slate-300 font-sans">
              {typeof result.data.output === "string"
                ? result.data.output
                : JSON.stringify(result.data.output, null, 2)}
            </pre>
            {result.data.agents_involved?.length > 0 && (
              <p className="mt-3 text-[10px] text-slate-500">
                Agents involved: {result.data.agents_involved.join(", ")}
              </p>
            )}
          </div>
        )}

        {/* Workflow grid */}
        {loading ? (
          <div className="flex h-48 items-center justify-center gap-2 text-slate-500 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading workflows…
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {workflows.map((wf) => (
              <WorkflowCard
                key={wf.id}
                wf={wf}
                isRunning={running === wf.id}
                anyRunning={running !== null}
                taskInput={taskInput[wf.id] ?? ""}
                onTaskChange={(v) => setTaskInput((p) => ({ ...p, [wf.id]: v }))}
                onRun={() => runWorkflow(wf)}
                resultId={result?.wf ?? null}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
