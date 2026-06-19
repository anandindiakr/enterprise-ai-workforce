"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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
  LogOut,
  User,
  Brain,
  Settings,
  BarChart3,
  AlertTriangle,
  ClipboardList,
  BookOpen,
  GitBranch,
  Plug,
  UserCog,
  Activity,
  Lock,
  Building2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { clearAuth, getUser, type AuthUser } from "@/lib/auth";

const NAV = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/chat", icon: MessageSquare, label: "Chat Console" },
  { href: "/voice", icon: Mic, label: "Voice Console" },
  { href: "/agents", icon: Brain, label: "Agents" },
  { href: "/workflows", icon: GitBranch, label: "Workflows" },
  { href: "/analytics", icon: BarChart3, label: "Analytics" },
  { href: "/escalations", icon: AlertTriangle, label: "Escalations" },
  { href: "/knowledge", icon: BookOpen, label: "Knowledge Base" },
  { href: "/integrations", icon: Plug, label: "Integrations", adminOnly: true },
  { href: "/monitoring", icon: Activity, label: "System Monitor", adminOnly: true },
  { href: "/audit", icon: ClipboardList, label: "Audit Log", adminOnly: true },
  { href: "/admin/users", icon: UserCog, label: "User Management", adminOnly: true },
  { href: "/tenants", icon: Building2, label: "Tenants", adminOnly: true },
  { href: "/portal", icon: LayoutDashboard, label: "My Portal" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

const DEPARTMENTS = [
  { id: "reception",    label: "Reception",     icon: Star,         color: "text-amber-400"  },
  { id: "customer_care",label: "Customer Care", icon: Headphones,   color: "text-cyan-400"   },
  { id: "sales",        label: "Sales",         icon: ShoppingCart, color: "text-emerald-400"},
  { id: "hr",           label: "HR",            icon: Users,        color: "text-violet-400" },
  { id: "finance",      label: "Finance",       icon: DollarSign,   color: "text-rose-400"   },
  { id: "technology",   label: "Technology",    icon: Cpu,          color: "text-blue-400"   },
  { id: "marketing",    label: "Marketing",     icon: Megaphone,    color: "text-orange-400" },
];

export function Sidebar() {
  const path     = usePathname();
  const router   = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);

  /* Load user from localStorage on mount (client only) */
  useEffect(() => {
    setUser(getUser());
  }, []);

  function handleLogout() {
    clearAuth();
    router.push("/login");
  }

  /* Don't render sidebar on the login page */
  if (path === "/login") return null;

  return (
    <aside
      className={cn(
        "relative flex h-screen flex-col border-r border-[#1f2937] bg-[#070d1a] transition-all duration-300",
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

      {/* Scrollable nav + departments */}
      <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin scrollbar-track-transparent scrollbar-thumb-[#1f2937]">
        {/* Main nav */}
        <nav className="space-y-1 px-2 pt-4">
          {NAV.filter(({ adminOnly }) => !adminOnly || user?.roles?.includes("admin")).map(({ href, icon: Icon, label, adminOnly }) => {
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
                {!collapsed && (
                  <>
                    <span className="flex-1">{label}</span>
                    {adminOnly && <Lock className="h-2.5 w-2.5 flex-shrink-0 text-amber-600/50" />}
                  </>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Departments */}
        {!collapsed && (
          <div className="mt-6 px-4 pb-4">
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
      </div>

      {/* Footer: user info + logout — pinned at bottom */}
      <div className="flex-shrink-0 border-t border-[#1f2937] p-3 space-y-2">
        {!collapsed && user && (
          <div className="flex items-center gap-2 rounded-lg bg-[#111827] px-2.5 py-2">
            <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-amber-500/20">
              <User className="h-3 w-3 text-amber-400" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-[11px] font-medium text-slate-300">{user.username}</p>
              <p className="font-mono text-[9px] uppercase tracking-wider text-slate-600">{user.roles[0] ?? "user"}</p>
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              className="text-slate-600 transition-colors hover:text-red-400"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {collapsed && (
          <button
            onClick={handleLogout}
            title="Sign out"
            className="flex w-full items-center justify-center rounded-lg border border-[#1f2937] p-1.5 text-slate-600 transition-colors hover:border-red-500/30 hover:text-red-400"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        )}

        {!collapsed && (
          <div className="flex items-center gap-2 px-1">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 status-pulse" />
            <span className="font-mono text-[10px] text-slate-500">ALL SYSTEMS NOMINAL</span>
          </div>
        )}

        <button
          onClick={() => setCollapsed((c) => !c)}
          className="flex w-full items-center justify-center rounded-lg border border-[#1f2937] p-1.5 text-slate-500 transition-colors hover:border-[#374151] hover:text-slate-300"
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
