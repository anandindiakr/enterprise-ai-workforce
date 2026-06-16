"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  User, Key, Bell, Shield, Database, Cpu,
  Save, Eye, EyeOff, CheckCircle, AlertCircle,
  ChevronRight, Zap, Trash2, RefreshCw, Globe,
  Building2, ChevronDown, ChevronUp, Bot,
} from "lucide-react";
import { getUser, setToken, clearAuth, type AuthUser, authHeaders } from "@/lib/auth";

/* ── Types ───────────────────────────────────────────────── */

interface SettingsSection {
  id: string;
  label: string;
  icon: React.ElementType;
  description: string;
}

const SECTIONS: SettingsSection[] = [
  { id: "company",        label: "Company & Agents", icon: Building2, description: "Brand identity and per-agent scripts" },
  { id: "profile",        label: "Profile",         icon: User,     description: "Your account details and preferences" },
  { id: "api_keys",       label: "API Keys",        icon: Key,      description: "Configure AI provider credentials" },
  { id: "notifications",  label: "Notifications",   icon: Bell,     description: "Alert and notification settings" },
  { id: "security",       label: "Security",        icon: Shield,   description: "Password and authentication settings" },
  { id: "integrations",   label: "Integrations",    icon: Database, description: "CRM, ERP, and third-party connections" },
  { id: "system",         label: "System",          icon: Cpu,      description: "Platform behaviour and advanced options" },
];

/* ── Sub-components ──────────────────────────────────────── */

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-4">
      <h3 className="text-[11px] font-mono uppercase tracking-widest text-slate-600">{label}</h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({
  label, description, children,
}: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border border-[#1f2937] bg-[#0c111d] px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-slate-200">{label}</p>
        {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${checked ? "bg-amber-500" : "bg-[#1f2937]"}`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${checked ? "translate-x-[18px]" : "translate-x-[2px]"}`}
      />
    </button>
  );
}

function SecretField({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "sk-…"}
        className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 pr-9 font-mono text-xs text-slate-300 placeholder-slate-600 focus:border-[#374151] focus:outline-none"
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400"
      >
        {show ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

/* ── CompanyPanel ────────────────────────────────────────── */

const DEPARTMENTS = [
  { key: "reception",     label: "Reception",     emoji: "👋" },
  { key: "customer_care", label: "Customer Care", emoji: "💬" },
  { key: "sales",         label: "Sales",         emoji: "💰" },
  { key: "hr",            label: "HR",            emoji: "👥" },
  { key: "finance",       label: "Finance",       emoji: "💵" },
  { key: "technology",    label: "Technology",    emoji: "⚙️" },
  { key: "marketing",     label: "Marketing",     emoji: "📢" },
];

interface AgentOverride { display_name: string; script: string; }

function CompanyPanel({ apiBase }: { apiBase: string }) {
  const [companyName, setCompanyName]       = useState("");
  const [tagline, setTagline]               = useState("");
  const [website, setWebsite]               = useState("");
  const [greetingScript, setGreetingScript] = useState("");
  const [overrides, setOverrides]           = useState<Record<string, AgentOverride>>({});
  const [expanded, setExpanded]             = useState<string | null>(null);
  const [saving, setSaving]                 = useState(false);
  const [msg, setMsg]                       = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    fetch(`${apiBase}/settings/company`, { headers: authHeaders() })
      .then((r) => r.json())
      .then((d) => {
        setCompanyName(d.company_name   ?? "");
        setTagline(d.company_tagline    ?? "");
        setWebsite(d.company_website    ?? "");
        setGreetingScript(d.greeting_script ?? "");
        setOverrides(d.agent_overrides  ?? {});
      })
      .catch(() => {});
  }, [apiBase]);

  const setOverride = (dept: string, field: keyof AgentOverride, val: string) => {
    setOverrides((prev) => ({
      ...prev,
      [dept]: { ...(prev[dept] ?? { display_name: "", script: "" }), [field]: val },
    }));
  };

  const handleSave = async () => {
    setSaving(true); setMsg(null);
    try {
      const res = await fetch(`${apiBase}/settings/company`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          company_name:    companyName,
          company_tagline: tagline,
          company_website: website,
          greeting_script: greetingScript,
          agent_overrides: overrides,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Save failed");
      setMsg({ ok: true, text: `Saved — ${data.company_name}` });
    } catch (e: unknown) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Error" });
    } finally {
      setSaving(false);
    }
  };

  const inputCls = "w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-xs text-slate-300 placeholder-slate-600 focus:border-amber-500/50 focus:outline-none";
  const textareaCls = `${inputCls} min-h-[80px] resize-y font-mono`;

  return (
    <div className="space-y-6">
      {/* Company identity */}
      <div className="rounded-xl border border-[#1f2937] bg-[#0c111d] p-5 space-y-4">
        <h3 className="text-[11px] font-mono uppercase tracking-widest text-slate-600">Company Identity</h3>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Company Name</label>
            <input value={companyName} onChange={(e) => setCompanyName(e.target.value)}
              placeholder="AlgoWorkforce" className={inputCls} />
            <p className="mt-1 text-[10px] text-slate-600">Agents will say this name when introducing themselves.</p>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Tagline</label>
            <input value={tagline} onChange={(e) => setTagline(e.target.value)}
              placeholder="Your AI-Powered Enterprise Workforce" className={inputCls} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Website</label>
            <input value={website} onChange={(e) => setWebsite(e.target.value)}
              placeholder="https://www.algoworkforce.com" className={inputCls} />
          </div>
        </div>
      </div>

      {/* Global greeting script */}
      <div className="rounded-xl border border-[#1f2937] bg-[#0c111d] p-5 space-y-3">
        <h3 className="text-[11px] font-mono uppercase tracking-widest text-slate-600">Global Greeting Script</h3>
        <textarea value={greetingScript} onChange={(e) => setGreetingScript(e.target.value)}
          placeholder={"Hello! This is {agent_name} from {company_name}. How may I help you today?"}
          className={textareaCls} />
        <p className="text-[10px] text-slate-600">
          Placeholders: <code className="text-amber-500/80">{"{agent_name}"}</code>,{" "}
          <code className="text-amber-500/80">{"{company_name}"}</code>,{" "}
          <code className="text-amber-500/80">{"{department}"}</code>.
          Leave blank to use the default per-agent greeting. Per-department scripts below override this.
        </p>
      </div>

      {/* Per-department agent customisation */}
      <div className="rounded-xl border border-[#1f2937] bg-[#0c111d] p-5 space-y-2">
        <h3 className="text-[11px] font-mono uppercase tracking-widest text-slate-600 mb-3">Per-Department Agent Scripts</h3>
        {DEPARTMENTS.map(({ key, label, emoji }) => {
          const open = expanded === key;
          const ov   = overrides[key] ?? { display_name: "", script: "" };
          return (
            <div key={key} className="rounded-lg border border-[#1f2937] overflow-hidden">
              <button
                onClick={() => setExpanded(open ? null : key)}
                className="flex w-full items-center justify-between px-4 py-3 text-left text-xs text-slate-300 hover:bg-[#111827] transition-colors"
              >
                <span className="flex items-center gap-2">
                  <span>{emoji}</span>
                  <span className="font-medium">{label}</span>
                  {ov.display_name && (
                    <span className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 text-[10px] text-amber-400">
                      {ov.display_name}
                    </span>
                  )}
                </span>
                {open ? <ChevronUp className="h-3.5 w-3.5 text-slate-500" /> : <ChevronDown className="h-3.5 w-3.5 text-slate-500" />}
              </button>
              {open && (
                <div className="border-t border-[#1f2937] px-4 pb-4 pt-3 space-y-3 bg-[#070d1a]">
                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-slate-500">Agent Display Name</label>
                    <input value={ov.display_name} onChange={(e) => setOverride(key, "display_name", e.target.value)}
                      placeholder={`e.g. "Alex" or "Sam"`} className={inputCls} />
                    <p className="mt-1 text-[10px] text-slate-600">Overrides the default name for this department only.</p>
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-slate-500">Custom Greeting / Script</label>
                    <textarea value={ov.script} onChange={(e) => setOverride(key, "script", e.target.value)}
                      placeholder={`Hi, I'm {agent_name} from ${label}. How can I help?`}
                      className={textareaCls} />
                    <p className="mt-1 text-[10px] text-slate-600">
                      This overrides the global greeting for the <strong className="text-slate-400">{label}</strong> department.
                      Use <code className="text-amber-500/80">{"{agent_name}"}</code> and{" "}
                      <code className="text-amber-500/80">{"{company_name}"}</code> as placeholders.
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Save button */}
      <div className="flex items-center justify-between pt-2">
        {msg && (
          <span className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs ${
            msg.ok ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" : "border-red-500/25 bg-red-500/10 text-red-400"
          }`}>
            {msg.ok ? <CheckCircle className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
            {msg.text}
          </span>
        )}
        <button onClick={handleSave} disabled={saving}
          className="ml-auto flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-1.5 text-xs font-semibold text-black transition-all hover:bg-amber-400 disabled:opacity-60"
        >
          {saving ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
          Save Company Settings
        </button>
      </div>
    </div>
  );
}

/* ── IntegrationsPanel ───────────────────────────────────── */

const INTEGRATION_META: Record<string, { label: string; desc: string; placeholder: string }> = {
  crm_base_url:       { label: "CRM",       desc: "Salesforce, HubSpot, Pipedrive",          placeholder: "https://crm.yourcompany.com" },
  hris_base_url:      { label: "HRIS",      desc: "BambooHR, Workday, Gusto",                placeholder: "https://hris.yourcompany.com" },
  finance_base_url:   { label: "Finance / ERP", desc: "SAP, Oracle, NetSuite",               placeholder: "https://erp.yourcompany.com" },
  devops_base_url:    { label: "Ticketing / DevOps", desc: "Jira, Zendesk, ServiceNow",      placeholder: "https://jira.yourcompany.com" },
  analytics_base_url: { label: "Analytics", desc: "Google Analytics, Mixpanel, Amplitude",   placeholder: "https://analytics.yourcompany.com" },
  calendar_base_url:  { label: "Calendar",  desc: "Google Calendar, Microsoft Outlook",      placeholder: "https://calendar.yourcompany.com" },
  email_base_url:     { label: "Email",     desc: "SMTP gateway or SendGrid/Resend endpoint", placeholder: "https://email.yourcompany.com" },
};

function IntegrationsPanel({ apiBase }: { apiBase: string }) {
  const [data, setData] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ key: string; ok: boolean; text: string } | null>(null);

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("workforce_token") : null;
    fetch(`${apiBase}/api/v1/settings/integrations`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (!d) return;
        const vals: Record<string, string> = {};
        (d.integrations ?? []).forEach((i: { key: string; value: string }) => { vals[i.key] = i.value; });
        setData(vals);
      })
      .catch(() => {});
  }, [apiBase]);

  async function save(key: string) {
    setSaving(true);
    const token = typeof window !== "undefined" ? localStorage.getItem("workforce_token") : null;
    try {
      const r = await fetch(`${apiBase}/api/v1/settings/integrations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ integrations: { [key]: editVal } }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData((prev) => ({ ...prev, [key]: editVal }));
      setEditing(null);
      setMsg({ key, ok: true, text: "Saved" });
      setTimeout(() => setMsg(null), 2500);
    } catch {
      setMsg({ key, ok: false, text: "Save failed — admin role required" });
      setTimeout(() => setMsg(null), 3000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-[11px] font-mono uppercase tracking-widest text-slate-600 mb-2">MCP Connector Base URLs</p>
      {Object.entries(INTEGRATION_META).map(([key, meta]) => {
        const current = data[key] || "";
        const isEditing = editing === key;
        return (
          <div key={key} className="rounded-xl border border-[#1f2937] bg-[#0c111d] px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-slate-200">{meta.label}</p>
                  {current && (
                    <span className="inline-block rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400">Connected</span>
                  )}
                </div>
                <p className="text-xs text-slate-500">{meta.desc}</p>
                {current && !isEditing && (
                  <p className="mt-1 font-mono text-[11px] text-slate-400 truncate">{current}</p>
                )}
                {msg?.key === key && (
                  <p className={`mt-1 text-xs ${msg.ok ? "text-emerald-400" : "text-red-400"}`}>{msg.text}</p>
                )}
              </div>
              {!isEditing ? (
                <button
                  onClick={() => { setEditing(key); setEditVal(current); }}
                  className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 hover:border-[#374151] hover:text-slate-200 transition-all whitespace-nowrap"
                >
                  {current ? "Edit" : "Configure"} <ChevronRight className="h-3 w-3" />
                </button>
              ) : (
                <div className="flex gap-2 items-center min-w-0">
                  <input
                    autoFocus
                    type="url"
                    value={editVal}
                    onChange={(e) => setEditVal(e.target.value)}
                    placeholder={meta.placeholder}
                    className="w-64 rounded-lg border border-[#374151] bg-[#070d1a] px-3 py-1.5 font-mono text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-500"
                    onKeyDown={(e) => { if (e.key === "Enter") save(key); if (e.key === "Escape") setEditing(null); }}
                  />
                  <button
                    onClick={() => save(key)}
                    disabled={saving}
                    className="rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-medium text-black hover:bg-amber-400 disabled:opacity-50 whitespace-nowrap"
                  >
                    {saving ? "…" : "Save"}
                  </button>
                  <button onClick={() => setEditing(null)} className="text-slate-500 hover:text-slate-300 text-xs">Cancel</button>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Main page ───────────────────────────────────────────── */

export default function SettingsPage() {
  const router = useRouter();
  const [activeSection, setActiveSection] = useState("company");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [serverKeyStatus, setServerKeyStatus] = useState<Record<string, boolean>>({});

  /* Profile state */
  const [fullName, setFullName] = useState("");
  const [email, setEmail]       = useState("");

  /* API Keys */
  const [openaiKey,     setOpenaiKey]     = useState("");
  const [elevenLabsKey, setElevenLabsKey] = useState("");
  const [deepgramKey,   setDeepgramKey]   = useState("");
  const [twilioSid,     setTwilioSid]     = useState("");
  const [twilioToken,   setTwilioToken]   = useState("");

  /* Notifications */
  const [emailNotif,   setEmailNotif]   = useState(true);
  const [browserNotif, setBrowserNotif] = useState(false);
  const [soundNotif,   setSoundNotif]   = useState(true);

  /* Security */
  const [currentPw, setCurrentPw] = useState("");
  const [newPw,     setNewPw]     = useState("");
  const [confirmPw, setConfirmPw] = useState("");

  /* System */
  const [streamingChat, setStreamingChat] = useState(true);
  const [autoScroll,    setAutoScroll]    = useState(true);
  const [debugMode,     setDebugMode]     = useState(false);
  const [language,      setLanguage]      = useState("en");

  useEffect(() => {
    const u = getUser();
    setUser(u);
    if (u) {
      setFullName(u.full_name ?? "");
      setEmail(u.email ?? "");
    }
    // Load saved settings from localStorage
    try {
      const saved = JSON.parse(localStorage.getItem("ai_workforce_settings") ?? "{}");
      if (saved.openaiKey)     setOpenaiKey(saved.openaiKey);
      if (saved.elevenLabsKey) setElevenLabsKey(saved.elevenLabsKey);
      if (saved.deepgramKey)   setDeepgramKey(saved.deepgramKey);
      if (saved.twilioSid)     setTwilioSid(saved.twilioSid);
      if (typeof saved.streamingChat === "boolean") setStreamingChat(saved.streamingChat);
      if (typeof saved.autoScroll    === "boolean") setAutoScroll(saved.autoScroll);
      if (typeof saved.debugMode     === "boolean") setDebugMode(saved.debugMode);
      if (typeof saved.emailNotif    === "boolean") setEmailNotif(saved.emailNotif);
      if (typeof saved.soundNotif    === "boolean") setSoundNotif(saved.soundNotif);
      if (saved.language) setLanguage(saved.language);
    } catch {}
    // Fetch server-side key status
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    fetch(`${apiBase}/api/v1/settings/keys`, { headers: authHeaders() })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (!data) return;
        const status: Record<string, boolean> = {};
        (data.keys ?? []).forEach((k: { key: string; is_set: boolean }) => { status[k.key] = k.is_set; });
        setServerKeyStatus(status);
      })
      .catch(() => {});
  }, []);

  async function handleSave() {
    setSaving(true);
    setError(null);
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    try {
      // Save non-secret settings to localStorage
      const localSettings = {
        openaiKey, elevenLabsKey, deepgramKey, twilioSid,
        streamingChat, autoScroll, debugMode,
        emailNotif, browserNotif, soundNotif, language,
      };
      localStorage.setItem("ai_workforce_settings", JSON.stringify(localSettings));

      // POST API keys to backend (they get applied to os.environ immediately)
      const keysPayload: Record<string, string> = {};
      if (openaiKey)     keysPayload["openai_api_key"]     = openaiKey;
      if (elevenLabsKey) keysPayload["elevenlabs_api_key"] = elevenLabsKey;
      if (deepgramKey)   keysPayload["deepgram_api_key"]   = deepgramKey;
      if (twilioSid)     keysPayload["twilio_account_sid"] = twilioSid;
      if (twilioToken)   keysPayload["twilio_auth_token"]  = twilioToken;
      if (Object.keys(keysPayload).length > 0) {
        const kr = await fetch(`${apiBase}/api/v1/settings/keys`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ keys: keysPayload }),
        });
        if (kr.ok) {
          // Refresh server key status
          const statusData = await fetch(`${apiBase}/api/v1/settings/keys`, { headers: authHeaders() }).then((r) => r.json()).catch(() => null);
          if (statusData) {
            const status: Record<string, boolean> = {};
            (statusData.keys ?? []).forEach((k: { key: string; is_set: boolean }) => { status[k.key] = k.is_set; });
            setServerKeyStatus(status);
          }
        }
      }

      // Persist profile to API if changed (any authenticated user can update own profile)
      if (user && (fullName !== (user.full_name ?? "") || email !== (user.email ?? ""))) {
        const res = await fetch(`${apiBase}/api/v1/auth/profile`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({
            ...(fullName ? { full_name: fullName } : {}),
            ...(email    ? { email }               : {}),
          }),
        });
        if (!res.ok) {
          // Non-fatal — keys were already saved; just log profile update failure
          console.warn("Profile update failed:", res.status);
        }
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: any) {
      setError(e.message ?? "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handlePasswordChange() {
    if (newPw !== confirmPw) { setError("Passwords do not match"); return; }
    if (newPw.length < 6)    { setError("Password must be at least 6 characters"); return; }
    setError(null);
    setSaving(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
      const res = await fetch(`${apiBase}/api/v1/auth/change-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `${res.status}`);
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: any) {
      setError(e.message ?? "Password change failed");
    } finally {
      setSaving(false);
    }
  }

  const sectionContent: Record<string, React.ReactNode> = {
    company: <CompanyPanel apiBase={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080"} />,

    profile: (
      <div className="space-y-6">
        <FieldGroup label="Account Information">
          <Field label="Username" description="Your unique login identifier">
            <span className="rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 font-mono text-xs text-slate-400">
              {user?.username ?? "—"}
            </span>
          </Field>
          <Field label="Full Name" description="Displayed in the platform">
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Your full name"
              className="rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-xs text-slate-300 placeholder-slate-600 focus:border-[#374151] focus:outline-none"
            />
          </Field>
          <Field label="Email Address" description="Used for notifications and recovery">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-xs text-slate-300 placeholder-slate-600 focus:border-[#374151] focus:outline-none"
            />
          </Field>
          <Field label="Role" description="Your assigned platform role">
            <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 font-mono text-[10px] text-amber-400">
              {user?.roles?.[0] ?? "user"}
            </span>
          </Field>
        </FieldGroup>
      </div>
    ),

    api_keys: (
      <div className="space-y-6">
        <FieldGroup label="AI Providers">
          <div className="rounded-xl border border-[#1f2937] bg-[#0c111d] p-4 space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-300">
                OpenAI API Key
                {serverKeyStatus["openai_api_key"] && (
                  <span className="ml-2 inline-block rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400">Active on server</span>
                )}
              </label>
              <SecretField value={openaiKey} onChange={setOpenaiKey} placeholder="sk-..." />
              <p className="mt-1 text-[10px] text-slate-600">Powers all chat and agent intelligence</p>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-300">
                ElevenLabs API Key
                {serverKeyStatus["elevenlabs_api_key"] && (
                  <span className="ml-2 inline-block rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400">Active on server</span>
                )}
              </label>
              <SecretField value={elevenLabsKey} onChange={setElevenLabsKey} placeholder="xi-..." />
              <p className="mt-1 text-[10px] text-slate-600">Text-to-Speech for voice agents</p>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-300">
                Deepgram API Key
                {serverKeyStatus["deepgram_api_key"] && (
                  <span className="ml-2 inline-block rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400">Active on server</span>
                )}
              </label>
              <SecretField value={deepgramKey} onChange={setDeepgramKey} placeholder="Token..." />
              <p className="mt-1 text-[10px] text-slate-600">Speech-to-Text transcription</p>
            </div>
          </div>
        </FieldGroup>
        <FieldGroup label="Communication Providers">
          <div className="rounded-xl border border-[#1f2937] bg-[#0c111d] p-4 space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-300">
                Twilio Account SID
                {serverKeyStatus["twilio_account_sid"] && (
                  <span className="ml-2 inline-block rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400">Active on server</span>
                )}
              </label>
              <SecretField value={twilioSid} onChange={setTwilioSid} placeholder="AC..." />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-300">
                Twilio Auth Token
                {serverKeyStatus["twilio_auth_token"] && (
                  <span className="ml-2 inline-block rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400">Active on server</span>
                )}
              </label>
              <SecretField value={twilioToken} onChange={setTwilioToken} placeholder="Auth token..." />
              <p className="mt-1 text-[10px] text-slate-600">Required for phone call inbound/outbound</p>
            </div>
          </div>
        </FieldGroup>
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
          <p className="text-[11px] text-emerald-400/80">
            API keys are encrypted and saved to the server. They take effect immediately — no restart needed.
            Keys already active on the server are marked <strong>Active on server</strong>.
          </p>
        </div>
      </div>
    ),

    notifications: (
      <div className="space-y-6">
        <FieldGroup label="Notification Channels">
          <Field label="Email Notifications" description="Receive updates and alerts via email">
            <Toggle checked={emailNotif} onChange={setEmailNotif} />
          </Field>
          <Field label="Browser Notifications" description="Push notifications in the browser">
            <Toggle checked={browserNotif} onChange={setBrowserNotif} />
          </Field>
          <Field label="Sound Alerts" description="Play sounds for new messages and events">
            <Toggle checked={soundNotif} onChange={setSoundNotif} />
          </Field>
        </FieldGroup>
      </div>
    ),

    security: (
      <div className="space-y-6">
        <FieldGroup label="Change Password">
          <div className="rounded-xl border border-[#1f2937] bg-[#0c111d] p-4 space-y-3">
            {[
              { label: "Current Password", value: currentPw, onChange: setCurrentPw },
              { label: "New Password",     value: newPw,     onChange: setNewPw     },
              { label: "Confirm Password", value: confirmPw, onChange: setConfirmPw },
            ].map(({ label, value, onChange }) => (
              <div key={label}>
                <label className="mb-1.5 block text-xs font-medium text-slate-400">{label}</label>
                <SecretField value={value} onChange={onChange} placeholder="••••••" />
              </div>
            ))}
            <button
              onClick={handlePasswordChange}
              disabled={saving || !currentPw || !newPw}
              className="mt-1 w-full rounded-lg bg-amber-500/10 border border-amber-500/20 py-2 text-xs font-medium text-amber-400 transition-all hover:bg-amber-500/20 disabled:opacity-40"
            >
              Update Password
            </button>
          </div>
        </FieldGroup>
        <FieldGroup label="Session">
          <Field label="Sign Out Everywhere" description="Invalidate all active sessions">
            <button
              onClick={() => { clearAuth(); router.push("/login"); }}
              className="flex items-center gap-1.5 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-1.5 text-xs text-red-400 transition-all hover:bg-red-500/15"
            >
              <Trash2 className="h-3 w-3" /> Sign Out
            </button>
          </Field>
        </FieldGroup>
      </div>
    ),

    integrations: (
      <div className="space-y-4">
        <IntegrationsPanel apiBase={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080"} />
      </div>
    ),

    system: (
      <div className="space-y-6">
        <FieldGroup label="Chat Behaviour">
          <Field label="Streaming Responses" description="Receive agent replies as they are generated">
            <Toggle checked={streamingChat} onChange={setStreamingChat} />
          </Field>
          <Field label="Auto-Scroll" description="Automatically scroll to the latest message">
            <Toggle checked={autoScroll} onChange={setAutoScroll} />
          </Field>
        </FieldGroup>
        <FieldGroup label="Advanced">
          <Field label="Debug Mode" description="Show raw API payloads and timing information">
            <Toggle checked={debugMode} onChange={setDebugMode} />
          </Field>
          <Field label="Interface Language" description="Language for the UI (agents respond in user language)">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-1.5 text-xs text-slate-300 focus:border-[#374151] focus:outline-none"
            >
              {[["en","English"],["es","Español"],["fr","Français"],["de","Deutsch"],["ar","العربية"],["zh","中文"],["ja","日本語"]].map(([v,l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </Field>
        </FieldGroup>
        <FieldGroup label="Data">
          <Field label="Clear Local Cache" description="Remove stored sessions, settings, and tokens">
            <button
              onClick={() => { localStorage.clear(); sessionStorage.clear(); window.location.reload(); }}
              className="flex items-center gap-1.5 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-1.5 text-xs text-red-400 transition-all hover:bg-red-500/15"
            >
              <Trash2 className="h-3 w-3" /> Clear Cache
            </button>
          </Field>
        </FieldGroup>
      </div>
    ),
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Sidebar ──────────────────────────────────────────── */}
      <aside className="flex w-[220px] flex-shrink-0 flex-col border-r border-[#1f2937] bg-[#070d1a]">
        <div className="flex h-14 items-center border-b border-[#1f2937] px-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20">
              <Zap className="h-3.5 w-3.5 text-amber-400" />
            </div>
            <span className="text-sm font-semibold text-slate-100">Settings</span>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 p-2 pt-3">
          {SECTIONS.map(({ id, label, icon: Icon, description }) => (
            <button
              key={id}
              onClick={() => setActiveSection(id)}
              className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs transition-all ${
                activeSection === id
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                  : "text-slate-500 hover:bg-[#111827] hover:text-slate-300"
              }`}
            >
              <Icon className="h-3.5 w-3.5 flex-shrink-0" />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      {/* ── Content ──────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex h-14 flex-shrink-0 items-center justify-between border-b border-[#1f2937] bg-[#0a0f1a] px-6">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">
              {SECTIONS.find((s) => s.id === activeSection)?.label}
            </h2>
            <p className="text-[11px] text-slate-500">
              {SECTIONS.find((s) => s.id === activeSection)?.description}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {saved && (
              <span className="flex items-center gap-1.5 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400">
                <CheckCircle className="h-3 w-3" /> Saved
              </span>
            )}
            {error && (
              <span className="flex items-center gap-1.5 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-1.5 text-xs text-red-400">
                <AlertCircle className="h-3 w-3" /> {error}
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-1.5 text-xs font-semibold text-black transition-all hover:bg-amber-400 disabled:opacity-60"
            >
              {saving ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
              Save Changes
            </button>
          </div>
        </div>

        {/* Section content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-2xl">
            {sectionContent[activeSection] ?? null}
          </div>
        </div>
      </div>
    </div>
  );
}
