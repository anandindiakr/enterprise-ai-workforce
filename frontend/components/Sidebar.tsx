"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  Mic,
  Star,
  Headphones,
  ShoppingCart,
  Users,
  DollarSign,
  Cpu,
  Megaphone,
  ChevronLeft,
  ChevronRight,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/chat", icon: MessageSquare, label: "Chat Console" },
  { href: "/voice", icon: Mic, label: "Voice Console" },
];

const DEPARTMENTS = [
  { id: "reception", label: "Reception", icon: Star, color: "text-amber-400" },
  { id: "customer_care", label: "Customer Care", icon: Headphones, color: "text-cyan-400" },
  { id: "sales", label: "Sales", icon: ShoppingCart, color: "text-emerald-400" },
  { id: "hr", label: "HR", icon: Users, color: "text-violet-400" },
  { id: "finance", label: "Finance", icon: DollarSign, color: "text-rose-400" },
  { id: "technology", label: "Technology", icon: Cpu, color: "text-blue-400" },
  { id: "marketing", label: "Marketing", icon: Megaphone, color: "text-orange-400" },
];

export function Sidebar() {
  const path = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "relative flex flex-col border-r border-[#1f2937] bg-[#070d1a] transition-all duration-300",
        collapsed ? "w-[60px]" : "w-[220px]"
      )}
    >
      {/* Logo */}
      <div
        className={cn(
          "flex h-14 items-center border-b border-[#1f2937] px-4 flex-shrink-0",
          collapsed ? "justify-center" : "gap-2.5"
        )}
      >
        <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-amber-500">
          <Zap className="h-4 w-4 text-black" strokeWidth={2.5} />
        </div>
        {!collapsed && (
          <span
            className="font-display text-[13px] font-bold tracking-widest text-slate-100"
            style={{ fontFamily: "var(--font-syne)" }}
          >
            WORKFORCE
          </span>
        )}
      </div>

      {/* Main nav */}
      <nav className="flex-shrink-0 space-y-1 px-2 pt-4">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = path === href;
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-all",
                collapsed ? "justify-center" : "",
                active
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                  : "text-slate-400 hover:bg-[#111827] hover:text-slate-200"
              )}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Departments */}
      {!collapsed && (
        <div className="mt-6 flex-1 overflow-y-auto px-4">
          <p className="mb-2 text-[10px] uppercase tracking-[0.15em] text-slate-600">
            Departments
          </p>
          <div className="space-y-0.5">
            {DEPARTMENTS.map(({ id, label, icon: Icon, color }) => (
              <Link
                key={id}
                href={`/chat?dept=${id}`}
                className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-xs text-slate-500 transition-colors hover:bg-[#111827] hover:text-slate-300"
              >
                <Icon className={cn("h-3 w-3 flex-shrink-0", color)} />
                <span>{label}</span>
                <span className="ml-auto h-1.5 w-1.5 flex-shrink-0 rounded-full bg-emerald-500 status-pulse" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Footer status */}
      <div className="mt-auto border-t border-[#1f2937] p-3">
        {!collapsed && (
          <div className="mb-2 flex items-center gap-2 px-1">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 status-pulse" />
            <span className="font-mono text-[10px] text-slate-500">ALL SYSTEMS NOMINAL</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className={cn(
            "flex items-center justify-center rounded-lg border border-[#1f2937] p-1.5 text-slate-500 transition-colors hover:border-[#374151] hover:text-slate-300",
            collapsed ? "w-full" : "w-full"
          )}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-3.5 w-3.5" />
          ) : (
            <div className="flex w-full items-center gap-2 text-xs">
              <ChevronLeft className="h-3.5 w-3.5 flex-shrink-0" />
              <span>Collapse</span>
            </div>
          )}
        </button>
      </div>
    </aside>
  );
}
