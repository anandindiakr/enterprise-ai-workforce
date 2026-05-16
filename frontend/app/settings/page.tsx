"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  User, Key, Bell, Shield, Database, Cpu,
  Save, Eye, EyeOff, CheckCircle, AlertCircle,
  ChevronRight, Zap, Trash2, RefreshCw, Globe,
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

/* ── Main page ───────────────────────────────────────────── */

export default function SettingsPage() {
  const router = useRouter();
  const [activeSection, setActiveSection] = useState("profile");
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

      // Persist profile to API if changed
      if (user && (fullName !== (user.full_name ?? "") || email !== (user.email ?? ""))) {
        const res = await fetch(`${apiBase}/api/v1/users/${user.user_id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({
            ...(fullName ? { full_name: fullName } : {}),
            ...(email    ? { email }               : {}),
          }),
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          throw new Error(detail?.detail ?? `API ${res.status}`);
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
        {[
          { name: "CRM",         desc: "Connect Salesforce, HubSpot, or Pipedrive",     status: "not_configured" },
          { name: "HRIS",        desc: "Connect BambooHR, Workday, or Gusto",            status: "not_configured" },
          { name: "ERP",         desc: "Connect SAP, Oracle, or NetSuite",               status: "not_configured" },
          { name: "Ticketing",   desc: "Connect Jira, Zendesk, or ServiceNow",           status: "not_configured" },
          { name: "Analytics",   desc: "Connect Google Analytics, Mixpanel, or Amplitude", status: "not_configured" },
          { name: "Calendar",    desc: "Connect Google Calendar or Outlook",             status: "not_configured" },
        ].map(({ name, desc, status }) => (
          <div key={name} className="flex items-center justify-between rounded-xl border border-[#1f2937] bg-[#0c111d] px-4 py-3">
            <div>
              <p className="text-sm font-medium text-slate-200">{name}</p>
              <p className="text-xs text-slate-500">{desc}</p>
            </div>
            <button className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 transition-all hover:border-[#374151] hover:text-slate-200">
              Configure <ChevronRight className="h-3 w-3" />
            </button>
          </div>
        ))}
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
