"use client";

import { useEffect, useRef, useState } from "react";
import { Bell, X, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { getToken } from "@/lib/auth";

interface EscalationNote {
  id: string;
  department: string;
  message: string;
  timestamp: string;
}

export function NotificationBell() {
  const [notes, setNotes] = useState<EscalationNote[]>([]);
  const [open, setOpen] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    const base = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");
    const wsBase = base.replace(/^http/, "ws");
    const url = `${wsBase}/api/v1/ws/events?token=${encodeURIComponent(token)}`;

    let ws: WebSocket;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          // events_ws.py wraps every event as {"channel":"escalations","data":{...}}
          // Unwrap the envelope; fall back to raw format for forward-compat.
          const payload: Record<string, unknown> =
            (msg.channel && msg.data) ? msg.data : msg;

          if (payload?.type === "new_escalation" || payload?.type === "escalation") {
            setNotes((prev) => [
              {
                id: String(payload.id ?? Date.now()),
                department: String(payload.department ?? "Unknown"),
                // backend field is "reason", not "message"
                message: String(payload.reason ?? payload.message ?? "New escalation received"),
                // backend field is "created_at", not "timestamp"
                timestamp: String(payload.created_at ?? payload.timestamp ?? new Date().toISOString()),
              },
              ...prev.slice(0, 19),
            ]);
          }
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onclose = () => {
        // Reconnect after 5s if the page is still mounted
        retryTimer = setTimeout(connect, 5000);
      };
    }

    connect();
    return () => {
      retryTimer && clearTimeout(retryTimer);
      ws?.close();
    };
  }, []);

  const unread = notes.length;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-[#111827] hover:text-slate-200"
        title="Notifications"
      >
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />
          {/* Dropdown */}
          <div className="absolute right-0 top-10 z-50 w-80 rounded-xl border border-[#1f2937] bg-[#070d1a] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#1f2937] px-4 py-2.5">
              <span className="text-sm font-semibold text-slate-200">Notifications</span>
              <div className="flex items-center gap-3">
                {notes.length > 0 && (
                  <button
                    onClick={() => setNotes([])}
                    className="text-[11px] text-slate-500 hover:text-slate-300"
                  >
                    Clear all
                  </button>
                )}
                <button
                  onClick={() => setOpen(false)}
                  className="text-slate-500 hover:text-slate-300"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div className="max-h-72 overflow-y-auto">
              {notes.length === 0 ? (
                <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
                  <Bell className="h-6 w-6 text-slate-700" />
                  <p className="text-xs text-slate-500">No new notifications</p>
                </div>
              ) : (
                notes.map((n) => (
                  <Link
                    key={n.id}
                    href="/escalations"
                    onClick={() => setOpen(false)}
                    className="flex items-start gap-3 border-b border-[#111827] px-4 py-3 text-xs transition-colors hover:bg-[#0f1929]"
                  >
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-red-400" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-red-400">New Escalation</p>
                      <p className="mt-0.5 truncate text-slate-400">{n.message}</p>
                      <p className="mt-1 text-slate-600">
                        {n.department} &middot;{" "}
                        {new Date(n.timestamp).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </Link>
                ))
              )}
            </div>

            {notes.length > 0 && (
              <div className="border-t border-[#1f2937] px-4 py-2">
                <Link
                  href="/escalations"
                  onClick={() => setOpen(false)}
                  className="text-xs text-amber-400 hover:text-amber-300"
                >
                  View all escalations →
                </Link>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
