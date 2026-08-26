"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getToken, authHeaders, getUser } from "@/lib/auth";
import {
  UserCog, Plus, Trash2, Pencil, RefreshCw, X,
  Check, Shield, User, Mail, Key, AlertCircle,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ── Types ──────────────────────────────────────────────────────────────────────

interface UserRecord {
  id: string;
  username: string;
  email: string;
  full_name?: string | null;
  roles: string[];
  is_active: boolean;
  created_at?: string;
}

// ── Role badge ─────────────────────────────────────────────────────────────────

function RoleBadge({ role }: { role: string }) {
  const map: Record<string, string> = {
    admin:    "bg-red-500/15 text-red-400 border-red-500/30",
    operator: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    user:     "bg-blue-500/15 text-blue-400 border-blue-500/30",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${map[role] ?? "bg-slate-700/40 text-slate-400 border-slate-700"}`}>
      {role}
    </span>
  );
}

// ── User form modal ────────────────────────────────────────────────────────────

interface UserFormProps {
  mode: "create" | "edit";
  initial?: Partial<UserRecord>;
  onClose: () => void;
  onSaved: () => void;
}

function UserFormModal({ mode, initial, onClose, onSaved }: UserFormProps) {
  const [username,  setUsername]  = useState(initial?.username  ?? "");
  const [email,     setEmail]     = useState(initial?.email     ?? "");
  const [fullName,  setFullName]  = useState(initial?.full_name ?? "");
  const [password,  setPassword]  = useState("");
  const [role,      setRole]      = useState(initial?.roles?.[0] ?? "user");
  const [isActive,  setIsActive]  = useState(initial?.is_active ?? true);
  const [saving,    setSaving]    = useState(false);
  const [err,       setErr]       = useState("");

  async function submit() {
    setErr("");
    if (!username.trim()) { setErr("Username is required"); return; }
    if (mode === "create" && !password.trim()) { setErr("Password is required for new users"); return; }

    setSaving(true);
    try {
      const url    = mode === "create"
        ? `${API}/api/v1/users/`
        : `${API}/api/v1/users/${initial!.id}`;
      const method = mode === "create" ? "POST" : "PATCH";
      const body: Record<string, unknown> = { username, email, full_name: fullName, roles: [role], is_active: isActive };
      if (password) body.password = password;

      const res = await fetch(url, {
        method,
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `API ${res.status}`);
      }
      onSaved();
      onClose();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-[#1f2937] bg-[#0c111d] p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-100">
            {mode === "create" ? "Create User" : "Edit User"}
          </h2>
          <button onClick={onClose} className="text-slate-600 hover:text-slate-300">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Username" icon={User}>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={mode === "edit"}
                className="w-full rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-amber-500/40 disabled:opacity-50"
                placeholder="john_doe"
              />
            </Field>
            <Field label="Full name" icon={User}>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
                placeholder="John Doe"
              />
            </Field>
          </div>

          <Field label="Email" icon={Mail}>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
              placeholder="john@company.com"
            />
          </Field>

          <Field label={mode === "create" ? "Password" : "New password (leave blank to keep)"} icon={Key}>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
              placeholder="••••••••"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Role" icon={Shield}>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
              >
                {["user","operator","admin"].map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </Field>

            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">Status</label>
              <button
                onClick={() => setIsActive((v) => !v)}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    : "border-[#1f2937] bg-[#111827] text-slate-500"
                }`}
              >
                <div className={`h-2 w-2 rounded-full ${isActive ? "bg-emerald-500" : "bg-slate-600"}`} />
                {isActive ? "Active" : "Inactive"}
              </button>
            </div>
          </div>

          {err && (
            <div className="flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
              <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
              {err}
            </div>
          )}
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-[#1f2937] px-4 py-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-lg bg-amber-500/20 border border-amber-500/30 px-4 py-1.5 text-xs font-medium text-amber-400 hover:bg-amber-500/30 transition-colors disabled:opacity-50"
          >
            {saving ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, icon: Icon, children }: { label: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="flex items-center gap-1 text-xs text-slate-400">
        <Icon className="h-3 w-3" />
        {label}
      </label>
      {children}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function UserManagementPage() {
  const router  = useRouter();
  const [users,   setUsers]   = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [search,  setSearch]  = useState("");
  const [modal,   setModal]   = useState<{ mode: "create" | "edit"; user?: UserRecord } | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const me = typeof window !== "undefined" ? getUser() : null;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const token = getToken();
      if (!token) { router.push("/login"); return; }
      const res = await fetch(`${API}/api/v1/users/`, { headers: authHeaders() });
      if (res.status === 403) { router.push("/"); return; }
      if (!res.ok) throw new Error(`API ${res.status}`);
      setUsers(await res.json());
    } catch { /* swallow */ }
    finally { setLoading(false); }
  }, [router]);

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    load();
  }, [load, router]);

  async function deleteUser(id: string, username: string) {
    if (!confirm(`Delete user "${username}"? This cannot be undone.`)) return;
    setDeleting(id);
    try {
      await fetch(`${API}/api/v1/users/${id}`, { method: "DELETE", headers: authHeaders() });
      setUsers((prev) => prev.filter((u) => u.id !== id));
    } catch { /* swallow */ }
    finally { setDeleting(null); }
  }

  const filtered = users.filter(
    (u) =>
      !search ||
      u.username.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      (u.full_name ?? "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#030712]">
      {modal && (
        <UserFormModal
          mode={modal.mode}
          initial={modal.user}
          onClose={() => setModal(null)}
          onSaved={load}
        />
      )}

      {/* Header */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#1f2937] px-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-amber-500/20 bg-amber-500/10">
            <UserCog className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100">User Management</h1>
            <p className="text-[11px] text-slate-500">{users.length} users · admin only</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search users…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-1.5 text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-amber-500/40 w-40"
          />
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 hover:border-[#374151] hover:text-slate-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => setModal({ mode: "create" })}
            className="flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-400 hover:bg-amber-500/20 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> New User
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="flex shrink-0 gap-px border-b border-[#1f2937]">
        {[
          { label: "Total",    value: users.length,                              color: "text-slate-300" },
          { label: "Active",   value: users.filter((u) => u.is_active).length,   color: "text-emerald-400" },
          { label: "Inactive", value: users.filter((u) => !u.is_active).length,  color: "text-red-400"     },
          { label: "Admins",   value: users.filter((u) => u.roles.includes("admin")).length, color: "text-amber-400" },
        ].map(({ label, value, color }) => (
          <div key={label} className="flex flex-1 flex-col items-center justify-center py-3">
            <span className={`text-lg font-bold ${color}`}>{value}</span>
            <span className="text-[10px] uppercase tracking-widest text-slate-600">{label}</span>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {loading && users.length === 0 ? (
          <div className="flex h-40 items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#1f2937] border-t-amber-500" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-slate-600">
            No users found.
          </div>
        ) : (
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-[#1f2937] text-[10px] uppercase tracking-widest text-slate-600">
                <th className="px-6 py-3 text-left">User</th>
                <th className="px-4 py-3 text-left">Email</th>
                <th className="px-4 py-3 text-left">Role</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => (
                <tr
                  key={u.id}
                  className="border-b border-[#0f1520] hover:bg-[#0a1020] transition-colors"
                >
                  <td className="px-6 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#111827] border border-[#1f2937]">
                        <User className="h-3.5 w-3.5 text-slate-500" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-200">{u.username}</p>
                        {u.full_name && <p className="text-[11px] text-slate-500">{u.full_name}</p>}
                      </div>
                    </div>
                  </td>
                  <td className="max-w-[260px] px-4 py-3">
                    <span className="flex min-w-0 items-center gap-1.5 text-slate-400" title={u.email ?? undefined}>
                      <Mail className="h-3 w-3 flex-shrink-0 text-slate-600" />
                      <span className="truncate">{u.email || <span className="text-slate-600">—</span>}</span>
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {(u.roles ?? ["user"]).map((r) => <RoleBadge key={r} role={r} />)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {u.is_active ? (
                      <span className="flex items-center gap-1.5 text-[11px] text-emerald-400">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 status-pulse" /> Active
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-[11px] text-slate-600">
                        <span className="h-1.5 w-1.5 rounded-full bg-slate-600" /> Inactive
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => setModal({ mode: "edit", user: u })}
                        title="Edit"
                        className="rounded-lg border border-[#1f2937] p-1.5 text-slate-500 hover:border-amber-500/30 hover:text-amber-400 transition-colors"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      {u.id !== me?.user_id && (
                        <button
                          onClick={() => deleteUser(u.id, u.username)}
                          disabled={deleting === u.id}
                          title="Delete"
                          className="rounded-lg border border-[#1f2937] p-1.5 text-slate-500 hover:border-red-500/30 hover:text-red-400 transition-colors disabled:opacity-40"
                        >
                          {deleting === u.id
                            ? <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                            : <Trash2 className="h-3.5 w-3.5" />
                          }
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
