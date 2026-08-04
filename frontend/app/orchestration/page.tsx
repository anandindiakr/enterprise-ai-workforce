"use client";

/**
 * Live Orchestration — admin-only, real-time visual flow of what the
 * AI workforce is actually doing right now: which department is active,
 * which tool/action just fired, and any department-to-department handoff.
 *
 * Fed entirely by the existing `/api/v1/ws/events` WebSocket ("orchestration"
 * channel), which is populated by real broadcast calls in
 * `app/services/chat_service.py`, `app/services/action_dispatcher.py`, and
 * `app/api/routes/vapi.py` — every node/edge lighting up here corresponds to
 * a real backend event, not a simulation.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Network, Star, Headphones, ShoppingCart, Users, DollarSign,
  Cpu, Megaphone, PhoneIncoming, Wrench, ArrowLeftRight,
} from "lucide-react";
import { getUser } from "@/lib/auth";

interface OrchEvent {
  type: string;
  department?: string;
  from_department?: string;
  to_department?: string;
  connector?: string;
  tool?: string;
  success?: boolean;
  summary?: string;
  session_id?: string;
  channel?: string;
  phone_number?: string;
  ts?: number;
}

const DEPTS: { id: string; label: string; icon: React.ElementType; color: string; y: number }[] = [
  { id: "reception",     label: "Reception",     icon: Star,         color: "#f59e0b", y: 20 },
  { id: "customer_care", label: "Customer Care", icon: Headphones,   color: "#22d3ee", y: 100 },
  { id: "sales",         label: "Sales",         icon: ShoppingCart, color: "#34d399", y: 180 },
  { id: "hr",            label: "HR",            icon: Users,        color: "#a78bfa", y: 260 },
  { id: "finance",       label: "Finance",       icon: DollarSign,   color: "#fb7185", y: 340 },
  { id: "technology",    label: "Technology",    icon: Cpu,          color: "#60a5fa", y: 420 },
  { id: "marketing",     label: "Marketing",     icon: Megaphone,    color: "#fb923c", y: 500 },
];

const ACTIVE_MS = 4000;   // how long a "just happened" node/edge stays highlighted
const TOOL_TTL_MS = 7000; // how long a transient tool node stays on the canvas

function baseNodes(): Node[] {
  const source: Node = {
    id: "source",
    position: { x: 20, y: 260 },
    data: { label: "Callers / Chat Users" },
    style: {
      background: "#0c111d", border: "1px solid #1f2937", borderRadius: 12,
      color: "#94a3b8", fontSize: 11, padding: 10, width: 150,
    },
  };
  const depts: Node[] = DEPTS.map((d) => ({
    id: d.id,
    position: { x: 320, y: d.y },
    data: { label: d.label },
    style: {
      background: "#0c111d", border: `1px solid ${d.color}33`, borderRadius: 12,
      color: d.color, fontSize: 12, fontWeight: 600, padding: 10, width: 160,
    },
  }));
  return [source, ...depts];
}

export default function OrchestrationPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<OrchEvent[]>([]);
  const [activeUntil, setActiveUntil] = useState<Record<string, number>>({});
  const [toolNodes, setToolNodes] = useState<{ id: string; deptId: string; label: string; success: boolean; expiresAt: number }[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const user = getUser();
    if (user && !user.roles?.includes("admin")) {
      router.push("/");
      return;
    }
    setReady(true);
  }, [router]);

  const pushEvent = useCallback((evt: OrchEvent) => {
    setEvents((prev) => [{ ...evt, ts: evt.ts ?? Date.now() / 1000 }, ...prev].slice(0, 60));

    const now = Date.now();
    if (evt.type === "agent_active" && evt.department) {
      setActiveUntil((prev) => ({ ...prev, [evt.department!]: now + ACTIVE_MS, source: now + ACTIVE_MS }));
    }
    if (evt.type === "handoff" && evt.from_department && evt.to_department) {
      setActiveUntil((prev) => ({
        ...prev,
        [evt.from_department!]: now + ACTIVE_MS,
        [evt.to_department!]: now + ACTIVE_MS,
        [`${evt.from_department}->${evt.to_department}`]: now + ACTIVE_MS,
      }));
    }
    if (evt.type === "tool_call" || evt.type === "outbound_call") {
      const dept = evt.department || "reception";
      const id = `${dept}-${evt.tool || evt.type}-${now}`;
      setActiveUntil((prev) => ({ ...prev, [dept]: now + ACTIVE_MS }));
      setToolNodes((prev) => [
        ...prev,
        {
          id,
          deptId: dept,
          label: evt.tool ? `${evt.connector ?? ""}.${evt.tool}` : "outbound call",
          success: evt.success !== false,
          expiresAt: now + TOOL_TTL_MS,
        },
      ]);
    }
  }, []);

  // Connect to the real event bus.
  useEffect(() => {
    if (!ready) return;
    const wsBase = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080").replace(/^http/, "ws");
    const ws = new WebSocket(`${wsBase}/api/v1/ws/events`);
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({ channels: ["orchestration"] }));
    };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.channel === "orchestration" && msg.data) pushEvent(msg.data as OrchEvent);
      } catch { /* ignore malformed/ping frames */ }
    };
    return () => ws.close();
  }, [ready, pushEvent]);

  // Periodic sweep to expire highlights + transient tool nodes so the graph
  // returns to its calm/idle state a few seconds after activity stops.
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      setTick((t) => t + 1);
      setToolNodes((prev) => prev.filter((t) => t.expiresAt > Date.now()));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const nodes: Node[] = useMemo(() => {
    const now = Date.now();
    const nodesArr = baseNodes().map((n) => {
      const isActive = (activeUntil[n.id] ?? 0) > now;
      if (!isActive) return n;
      return {
        ...n,
        style: {
          ...n.style,
          boxShadow: "0 0 0 2px currentColor, 0 0 16px rgba(52,211,153,0.5)",
          background: "#111827",
        },
      };
    });
    const dynamicTools: Node[] = toolNodes.map((tn, i) => {
      const dept = DEPTS.find((d) => d.id === tn.deptId);
      const y = (dept?.y ?? 20) + 40 + (i % 3) * 4;
      return {
        id: tn.id,
        position: { x: 560, y },
        data: { label: `${tn.success ? "✓" : "✕"} ${tn.label}` },
        style: {
          background: tn.success ? "#0f1f17" : "#1f1013",
          border: `1px solid ${tn.success ? "#10b98155" : "#f4718155"}`,
          borderRadius: 10, color: tn.success ? "#6ee7b7" : "#fca5a5",
          fontSize: 10, padding: 8, width: 190,
        },
      };
    });
    return [...nodesArr, ...dynamicTools];
  }, [activeUntil, toolNodes]);

  const edges: Edge[] = useMemo(() => {
    const now = Date.now();
    const base: Edge[] = DEPTS.map((d) => ({
      id: `source-${d.id}`,
      source: "source",
      target: d.id,
      animated: (activeUntil[d.id] ?? 0) > now,
      style: { stroke: (activeUntil[d.id] ?? 0) > now ? d.color : "#1f2937" },
      markerEnd: { type: MarkerType.ArrowClosed, color: (activeUntil[d.id] ?? 0) > now ? d.color : "#1f2937" },
    }));
    const handoffs: Edge[] = events
      .filter((e) => e.type === "handoff" && e.from_department && e.to_department)
      .slice(0, 5)
      .map((e, i) => ({
        id: `handoff-${e.from_department}-${e.to_department}-${i}`,
        source: e.from_department!,
        target: e.to_department!,
        animated: (activeUntil[`${e.from_department}->${e.to_department}`] ?? 0) > now,
        style: { stroke: "#f59e0b", strokeDasharray: "4 3" },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#f59e0b" },
        label: "handoff",
        labelStyle: { fill: "#f59e0b", fontSize: 9 },
      }));
    const toolEdges: Edge[] = toolNodes.map((tn) => ({
      id: `tool-edge-${tn.id}`,
      source: tn.deptId,
      target: tn.id,
      style: { stroke: tn.success ? "#10b981" : "#f43f5e" },
    }));
    return [...base, ...handoffs, ...toolEdges];
  }, [activeUntil, events, toolNodes]);

  if (!ready) return null;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex h-14 flex-shrink-0 items-center justify-between border-b border-[#1f2937] bg-[#0a0f1a] px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <Network className="h-4 w-4 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100">Live Orchestration</h1>
            <p className="text-[11px] text-slate-500">Real-time view of every agent handoff, tool call, and outbound action</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-[11px]">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500 status-pulse" : "bg-slate-600"}`} />
          <span className={connected ? "text-emerald-400" : "text-slate-500"}>
            {connected ? "Live" : "Disconnected"}
          </span>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            proOptions={{ hideAttribution: true }}
            colorMode="dark"
          >
            <Background color="#1f2937" gap={24} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        {/* Live event feed */}
        <div className="w-80 flex-shrink-0 overflow-y-auto border-l border-[#1f2937] bg-[#070d1a] p-3">
          <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-600">Live Event Feed</p>
          {events.length === 0 && (
            <p className="text-xs text-slate-600">
              No activity yet — send a chat message or make a call to see it appear here in real time.
            </p>
          )}
          <div className="space-y-2">
            {events.map((e, i) => (
              <div key={i} className="rounded-lg border border-[#1f2937] bg-[#0c111d] p-2 text-[11px]">
                <div className="mb-1 flex items-center gap-1.5">
                  {e.type === "handoff" ? (
                    <ArrowLeftRight className="h-3 w-3 text-amber-400" />
                  ) : e.type === "tool_call" || e.type === "outbound_call" ? (
                    <Wrench className="h-3 w-3 text-cyan-400" />
                  ) : (
                    <PhoneIncoming className="h-3 w-3 text-emerald-400" />
                  )}
                  <span className="font-mono text-[10px] uppercase text-slate-500">{e.type}</span>
                </div>
                {e.type === "handoff" ? (
                  <p className="text-slate-300">{e.from_department} → {e.to_department}</p>
                ) : (
                  <p className="text-slate-300">
                    {e.department} {e.tool ? `· ${e.connector}.${e.tool}` : ""}
                  </p>
                )}
                {e.summary && <p className="mt-1 text-slate-500 line-clamp-2">{e.summary}</p>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
