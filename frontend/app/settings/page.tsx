"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  User, Key, Bell, Shield, Database, Cpu,
  Save, Eye, EyeOff, CheckCircle, AlertCircle,
  ChevronRight, Zap, Trash2, RefreshCw, Globe,
  Building2, ChevronDown, ChevronUp, Bot,
  Users, UserPlus, UserX, ToggleLeft, ToggleRight,
  Lock, Sparkles, Wand2, ClipboardCopy,
} from "lucide-react";
import { getUser, setToken, clearAuth, type AuthUser, authHeaders } from "@/lib/auth";

/* ── Types ───────────────────────────────────────────────── */

interface SettingsSection {
  id: string;
  label: string;
  icon: React.ElementType;
  description: string;
  adminOnly?: boolean;
}

const SECTIONS: SettingsSection[] = [
  { id: "company",        label: "Company & Agents",  icon: Building2, description: "Brand identity and per-agent scripts",       adminOnly: true  },
  { id: "users",          label: "User Management",   icon: Users,     description: "Add and manage platform users",              adminOnly: true  },
  { id: "profile",        label: "Profile",           icon: User,      description: "Your account details and preferences"                         },
  { id: "api_keys",       label: "API Keys",          icon: Key,       description: "Configure AI provider credentials",          adminOnly: true  },
  { id: "notifications",  label: "Notifications",     icon: Bell,      description: "Alert and notification settings"                              },
  { id: "security",       label: "Security",          icon: Shield,    description: "Password and authentication settings"                         },
  { id: "integrations",   label: "Integrations",      icon: Database,  description: "CRM, ERP, and third-party connections",      adminOnly: true  },
  { id: "system",         label: "System",            icon: Cpu,       description: "Platform behaviour and advanced options",    adminOnly: true  },
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

interface AgentOverride {
  display_name: string;
  greeting: string;
  closing: string;
  transfer_message: string;
  script: string; // legacy free-text fallback
}
const EMPTY_OVERRIDE: AgentOverride = { display_name: "", greeting: "", closing: "", transfer_message: "", script: "" };

/* ── Script Wizard ───────────────────────────────────────────
   Always-available helper that suggests greeting / closing /
   transfer wording, tailored to the company name, department,
   and (if available) the products/services on file — so a
   beginner never has to stare at a blank textbox. Runs fully
   client-side (no API key or extra network round-trip needed). */

interface WizardProduct { name: string; category: string | null }

type ScriptTone = "warm" | "professional" | "upbeat";

const TONE_META: Record<ScriptTone, { label: string; emoji: string }> = {
  warm:         { label: "Warm & Friendly",        emoji: "😊" },
  professional: { label: "Professional & Concise", emoji: "🤝" },
  upbeat:       { label: "Upbeat & Energetic",      emoji: "✨" },
};

function buildScriptIdeas(opts: {
  companyName: string;
  deptLabel: string;
  agentName: string;
  tone: ScriptTone;
  products: WizardProduct[];
}): { greeting: string; closing: string; transfer: string } {
  const { deptLabel, tone, products } = opts;
  const company = opts.companyName || "{company_name}";
  const agent = opts.agentName || "{agent_name}";
  const dept = deptLabel;
  const topProducts = products.slice(0, 3).map((p) => p.name).filter(Boolean);
  const productLine = topProducts.length
    ? topProducts.length === 1
      ? ` We help with ${topProducts[0]}.`
      : ` We help with things like ${topProducts.slice(0, -1).join(", ")} and ${topProducts[topProducts.length - 1]}.`
    : "";

  const GREETINGS: Record<ScriptTone, string> = {
    warm: `Thank you so much for calling ${company}! This is ${agent} from ${dept}.${productLine} How can I help you today?`,
    professional: `Good day, thank you for calling ${company}, ${dept} department. This is ${agent} speaking. How may I assist you?`,
    upbeat: `Hey there! Thanks for calling ${company} — you've reached ${agent} in ${dept}.${productLine} What can I do for you today?`,
  };
  const CLOSINGS: Record<ScriptTone, string> = {
    warm: `Thanks so much for calling ${company} — it was a pleasure helping you. Have a wonderful day!`,
    professional: `Thank you for contacting ${company}. Have a good day.`,
    upbeat: `Thanks a ton for calling ${company}! Take care and have an awesome day!`,
  };
  const TRANSFERS: Record<ScriptTone, string> = {
    warm: `Of course — let me connect you with our ${dept} team right away so they can take great care of you. One moment please!`,
    professional: `Understood. I'll transfer you to our ${dept} department now — please hold for a moment.`,
    upbeat: `No problem at all! Connecting you to ${dept} now — hang tight, just a sec!`,
  };

  return { greeting: GREETINGS[tone], closing: CLOSINGS[tone], transfer: TRANSFERS[tone] };
}

function ScriptWizard({
  deptLabel, agentName, companyName, products, onUse,
}: {
  deptLabel: string;
  agentName: string;
  companyName: string;
  products: WizardProduct[];
  onUse: (field: "greeting" | "closing" | "transfer_message", value: string) => void;
}) {
  const [tone, setTone] = useState<ScriptTone>("warm");
  const [open, setOpen] = useState(false);
  const ideas = buildScriptIdeas({ companyName, deptLabel, agentName, tone, products });

  return (
    <div className="rounded-lg border border-violet-500/25 bg-violet-500/5 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2.5 text-left hover:bg-violet-500/10 transition-colors"
      >
        <span className="flex items-center gap-2 text-xs font-medium text-violet-300">
          <Wand2 className="h-3.5 w-3.5" />
          Script Wizard — need help writing this?
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5 text-violet-400" /> : <ChevronDown className="h-3.5 w-3.5 text-violet-400" />}
      </button>
      {open && (
        <div className="border-t border-violet-500/20 p-3 space-y-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] text-violet-300/70 mr-1">Tone:</span>
            {(Object.keys(TONE_META) as ScriptTone[]).map((t) => (
              <button
                key={t}
                onClick={() => setTone(t)}
                className={`rounded-full border px-2.5 py-1 text-[10px] transition-all ${
                  tone === t
                    ? "border-violet-400/50 bg-violet-500/20 text-violet-200"
                    : "border-[#1f2937] text-slate-500 hover:text-slate-300"
                }`}
              >
                {TONE_META[t].emoji} {TONE_META[t].label}
              </button>
            ))}
          </div>
          {products.length === 0 && (
            <p className="text-[10px] text-slate-600">
              Tip: add items in <span className="text-violet-300/80">Products &amp; Services</span> and these
              suggestions will automatically mention them.
            </p>
          )}
          {([
            { field: "greeting" as const, label: "Greeting idea", text: ideas.greeting },
            { field: "closing" as const, label: "Closing idea", text: ideas.closing },
            { field: "transfer_message" as const, label: "Transfer idea", text: ideas.transfer },
          ]).map(({ field, label, text }) => (
            <div key={field} className="rounded-lg border border-[#1f2937] bg-[#070d1a] p-2.5">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-[10px] font-medium text-slate-500">{label}</span>
                <button
                  onClick={() => onUse(field, text)}
                  className="flex items-center gap-1 rounded-md bg-violet-500/15 border border-violet-500/30 px-2 py-0.5 text-[10px] text-violet-300 hover:bg-violet-500/25 transition-all"
                >
                  <ClipboardCopy className="h-2.5 w-2.5" /> Use this
                </button>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GlobalGreetingWizard({
  companyName, products, onUse,
}: { companyName: string; products: WizardProduct[]; onUse: (value: string) => void }) {
  const [tone, setTone] = useState<ScriptTone>("warm");
  const [open, setOpen] = useState(false);
  const ideas = buildScriptIdeas({ companyName, deptLabel: "our team", agentName: "", tone, products });

  return (
    <div className="rounded-lg border border-violet-500/25 bg-violet-500/5 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2.5 text-left hover:bg-violet-500/10 transition-colors"
      >
        <span className="flex items-center gap-2 text-xs font-medium text-violet-300">
          <Wand2 className="h-3.5 w-3.5" />
          Script Wizard — get a greeting idea
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5 text-violet-400" /> : <ChevronDown className="h-3.5 w-3.5 text-violet-400" />}
      </button>
      {open && (
        <div className="border-t border-violet-500/20 p-3 space-y-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] text-violet-300/70 mr-1">Tone:</span>
            {(Object.keys(TONE_META) as ScriptTone[]).map((t) => (
              <button
                key={t}
                onClick={() => setTone(t)}
                className={`rounded-full border px-2.5 py-1 text-[10px] transition-all ${
                  tone === t
                    ? "border-violet-400/50 bg-violet-500/20 text-violet-200"
                    : "border-[#1f2937] text-slate-500 hover:text-slate-300"
                }`}
              >
                {TONE_META[t].emoji} {TONE_META[t].label}
              </button>
            ))}
          </div>
          <div className="rounded-lg border border-[#1f2937] bg-[#070d1a] p-2.5">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-[10px] font-medium text-slate-500">Greeting idea</span>
              <button
                onClick={() => onUse(ideas.greeting)}
                className="flex items-center gap-1 rounded-md bg-violet-500/15 border border-violet-500/30 px-2 py-0.5 text-[10px] text-violet-300 hover:bg-violet-500/25 transition-all"
              >
                <ClipboardCopy className="h-2.5 w-2.5" /> Use this
              </button>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">{ideas.greeting}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function CompanyPanel({ apiBase }: { apiBase: string }) {
  const [companyName, setCompanyName]       = useState("");
  const [tagline, setTagline]               = useState("");
  const [website, setWebsite]               = useState("");
  const [greetingScript, setGreetingScript] = useState("");
  const [overrides, setOverrides]           = useState<Record<string, AgentOverride>>({});
  const [expanded, setExpanded]             = useState<string | null>(null);
  const [saving, setSaving]                 = useState(false);
  const [msg, setMsg]                       = useState<{ ok: boolean; text: string } | null>(null);
  const [products, setProducts]             = useState<WizardProduct[]>([]);

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
    // Fetch products/services so the Script Wizard can mention them by name.
    fetch(`${apiBase}/api/v1/products`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : []))
      .then((list) => {
        if (Array.isArray(list)) {
          setProducts(
            list
              .filter((p: { is_active?: boolean }) => p.is_active !== false)
              .map((p: { name: string; category: string | null }) => ({ name: p.name, category: p.category ?? null }))
          );
        }
      })
      .catch(() => {});
  }, [apiBase]);

  const setOverride = (dept: string, field: keyof AgentOverride, val: string) => {
    setOverrides((prev) => ({
      ...prev,
      [dept]: { ...EMPTY_OVERRIDE, ...(prev[dept] ?? {}), [field]: val },
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
        <GlobalGreetingWizard companyName={companyName} products={products} onUse={setGreetingScript} />
      </div>

      {/* Per-department agent customisation */}
      <div className="rounded-xl border border-[#1f2937] bg-[#0c111d] p-5 space-y-2">
        <h3 className="text-[11px] font-mono uppercase tracking-widest text-slate-600 mb-3">Per-Department Agent Scripts</h3>
        {DEPARTMENTS.map(({ key, label, emoji }) => {
          const open = expanded === key;
          const ov   = { ...EMPTY_OVERRIDE, ...(overrides[key] ?? {}) };
          const previewName = companyName || "the company";
          const previewAgent = ov.display_name || "the assistant";
          const fill = (s: string) => s
            .replaceAll("{agent_name}", previewAgent)
            .replaceAll("{company_name}", previewName)
            .replaceAll("{department}", label);
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

                  <ScriptWizard
                    deptLabel={label}
                    agentName={ov.display_name}
                    companyName={companyName}
                    products={products}
                    onUse={(field, value) => setOverride(key, field, value)}
                  />

                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-slate-500">Greeting (start of call)</label>
                    <textarea value={ov.greeting} onChange={(e) => setOverride(key, "greeting", e.target.value)}
                      placeholder={`e.g. "Thank you for calling {company_name}, this is {agent_name} from ${label}. How can I help you today?"`}
                      className={textareaCls} />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-slate-500">Closing line (end of call)</label>
                    <textarea value={ov.closing} onChange={(e) => setOverride(key, "closing", e.target.value)}
                      placeholder={`e.g. "Thanks for calling {company_name}, have a great day!"`}
                      className={textareaCls} />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-slate-500">Transfer / escalation message</label>
                    <textarea value={ov.transfer_message} onChange={(e) => setOverride(key, "transfer_message", e.target.value)}
                      placeholder={`e.g. "Sure, let me connect you to our ${label} team now — one moment please."`}
                      className={textareaCls} />
                    <p className="mt-1 text-[10px] text-slate-600">
                      Said to the caller right before transferring to this department, so there's no awkward silence.
                    </p>
                  </div>
                  <p className="text-[10px] text-slate-600">
                    Placeholders: <code className="text-amber-500/80">{"{agent_name}"}</code>,{" "}
                    <code className="text-amber-500/80">{"{company_name}"}</code>,{" "}
                    <code className="text-amber-500/80">{"{department}"}</code>. Leave any field blank to fall back to the global greeting script above.
                  </p>

                  {/* Legacy field - kept for backward compatibility with existing data */}
                  {ov.script && (
                    <div className="rounded-lg border border-dashed border-[#1f2937] p-3">
                      <label className="mb-1 block text-[11px] font-medium text-slate-500">Legacy single-field script (still in use if the fields above are blank)</label>
                      <textarea value={ov.script} onChange={(e) => setOverride(key, "script", e.target.value)}
                        className={textareaCls} />
                    </div>
                  )}

                  {/* Test / preview */}
                  <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 space-y-2">
                    <p className="text-[11px] font-medium text-amber-400/90">Preview (with current company name substituted)</p>
                    <p className="text-xs text-slate-300"><span className="text-slate-500">Greeting:</span> {ov.greeting ? fill(ov.greeting) : <span className="text-slate-600 italic">using global default</span>}</p>
                    <p className="text-xs text-slate-300"><span className="text-slate-500">Closing:</span> {ov.closing ? fill(ov.closing) : <span className="text-slate-600 italic">using global default</span>}</p>
                    <p className="text-xs text-slate-300"><span className="text-slate-500">Transfer:</span> {ov.transfer_message ? fill(ov.transfer_message) : <span className="text-slate-600 italic">using default transfer phrase</span>}</p>
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

/* ── UsersPanel ──────────────────────────────────────────── */

interface UserRecord {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  roles: string[];
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  last_login: string | null;
}

function UsersPanel({ apiBase }: { apiBase: string }) {
  const [userList, setUserList]   = useState<UserRecord[]>([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [username, setUsername]   = useState("");
  const [email, setEmail]         = useState("");
  const [password, setPassword]   = useState("");
  const [fullName, setFullName]   = useState("");
  const [creating, setCreating]   = useState(false);
  const [showPw, setShowPw]       = useState(false);
  const [msg, setMsg]             = useState<{ ok: boolean; text: string } | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${apiBase}/api/v1/users/`, { headers: authHeaders() });
      if (r.ok) setUserList(await r.json());
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, [apiBase]);

  const createUser = async () => {
    if (!username.trim() || !email.trim() || !password.trim()) {
      setMsg({ ok: false, text: "Username, email and password are required" });
      return;
    }
    setCreating(true);
    setMsg(null);
    try {
      const r = await fetch(`${apiBase}/api/v1/users/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ username: username.trim(), email: email.trim(), password, full_name: fullName.trim() || undefined }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail ?? "Failed to create user");
      setMsg({ ok: true, text: `User "${username}" created — they can now login immediately.` });
      setUsername(""); setEmail(""); setPassword(""); setFullName("");
      setShowForm(false);
      await load();
    } catch (e: unknown) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Error" });
    } finally {
      setCreating(false);
    }
  };

  const toggleActive = async (u: UserRecord) => {
    try {
      await fetch(`${apiBase}/api/v1/users/${u.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ is_active: !u.is_active }),
      });
      await load();
    } catch {}
  };

  const deleteUser = async (u: UserRecord) => {
    if (!confirm(`Permanently delete user "${u.username}"? This cannot be undone.`)) return;
    try {
      await fetch(`${apiBase}/api/v1/users/${u.id}`, { method: "DELETE", headers: authHeaders() });
      await load();
    } catch {}
  };

  const inputCls = "w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-xs text-slate-300 placeholder-slate-600 focus:border-amber-500/50 focus:outline-none";

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-mono uppercase tracking-widest text-slate-600">Platform Users</p>
        <button
          onClick={() => { setShowForm((v) => !v); setMsg(null); }}
          className="flex items-center gap-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 text-xs font-medium text-amber-400 transition-all hover:bg-amber-500/20"
        >
          <UserPlus className="h-3.5 w-3.5" />
          Add User
        </button>
      </div>

      {msg && (
        <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
          msg.ok ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" : "border-red-500/25 bg-red-500/10 text-red-400"
        }`}>
          {msg.ok ? <CheckCircle className="h-3.5 w-3.5 flex-shrink-0" /> : <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />}
          {msg.text}
        </div>
      )}

      {showForm && (
        <div className="rounded-xl border border-amber-500/20 bg-[#0c111d] p-5 space-y-3">
          <h3 className="text-[11px] font-mono uppercase tracking-widest text-amber-500/70 mb-1">New User</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-[11px] font-medium text-slate-400">Username *</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="john_doe" className={inputCls} />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-slate-400">Full Name</label>
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Doe" className={inputCls} />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-400">Email Address *</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="john@company.com" className={inputCls} />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-400">Password * (min 6 chars)</label>
            <div className="relative">
              <input
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Set a strong password"
                className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 pr-9 text-xs text-slate-300 placeholder-slate-600 focus:border-amber-500/50 focus:outline-none"
              />
              <button type="button" onClick={() => setShowPw((s) => !s)} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                {showPw ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
            <p className="mt-1 text-[10px] text-slate-600">The user can login with this username and password immediately.</p>
          </div>
          <div className="flex items-center justify-end gap-2 pt-1">
            <button onClick={() => setShowForm(false)} className="rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-500 hover:text-slate-300">
              Cancel
            </button>
            <button
              onClick={createUser}
              disabled={creating}
              className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-1.5 text-xs font-semibold text-black hover:bg-amber-400 disabled:opacity-60"
            >
              {creating ? <RefreshCw className="h-3 w-3 animate-spin" /> : <UserPlus className="h-3 w-3" />}
              Create User
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8 text-slate-600 text-xs">
          <RefreshCw className="h-4 w-4 animate-spin mr-2" /> Loading users…
        </div>
      ) : userList.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#1f2937] py-8 text-center text-xs text-slate-600">
          No users found. Add your first user above.
        </div>
      ) : (
        <div className="space-y-2">
          {userList.map((u) => (
            <div key={u.id} className="flex items-center justify-between gap-3 rounded-xl border border-[#1f2937] bg-[#0c111d] px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-sm text-slate-200">{u.username}</span>
                  {u.roles.map((r) => (
                    <span key={r} className={`rounded-full px-2 py-0.5 text-[10px] border ${
                      r === "admin" ? "bg-red-500/10 border-red-500/20 text-red-400" : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                    }`}>{r}</span>
                  ))}
                  {!u.is_active && (
                    <span className="rounded-full bg-slate-500/10 border border-slate-500/20 px-2 py-0.5 text-[10px] text-slate-500">Inactive</span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">{u.email}{u.full_name ? ` · ${u.full_name}` : ""}</p>
                {u.last_login && <p className="text-[10px] text-slate-700 mt-0.5">Last login: {new Date(u.last_login).toLocaleString()}</p>}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => toggleActive(u)}
                  title={u.is_active ? "Deactivate" : "Activate"}
                  className={`flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[11px] transition-all ${
                    u.is_active
                      ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/25"
                      : "border-slate-600/25 bg-slate-600/10 text-slate-500 hover:bg-emerald-500/10 hover:text-emerald-400 hover:border-emerald-500/25"
                  }`}
                >
                  {u.is_active ? <ToggleRight className="h-3.5 w-3.5" /> : <ToggleLeft className="h-3.5 w-3.5" />}
                  {u.is_active ? "Active" : "Inactive"}
                </button>
                <button
                  onClick={() => deleteUser(u)}
                  className="rounded-lg border border-[#1f2937] p-1.5 text-slate-600 hover:border-red-500/25 hover:bg-red-500/10 hover:text-red-400 transition-all"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-3">
        <p className="text-[11px] text-slate-600">
          New users are assigned the <strong className="text-amber-500/70">agent</strong> role by default and can login immediately.
          Share the login URL with them after creation.
        </p>
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

    users: <UsersPanel apiBase={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080"} />,

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
          {SECTIONS.filter((s) => !s.adminOnly || user?.roles?.includes("admin")).map(({ id, label, icon: Icon, adminOnly }) => (
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
              <span className="flex-1">{label}</span>
              {adminOnly && <span title="Admin only"><Lock className="h-2.5 w-2.5 flex-shrink-0 text-amber-600/60" /></span>}
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
            {/* Only show Save for non-admin-only sections, or when admin */}
            {(!SECTIONS.find((s) => s.id === activeSection)?.adminOnly || user?.roles?.includes("admin")) && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-1.5 text-xs font-semibold text-black transition-all hover:bg-amber-400 disabled:opacity-60"
              >
                {saving ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                Save Changes
              </button>
            )}
          </div>
        </div>

        {/* Section content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-2xl">
            {(() => {
              const section = SECTIONS.find((s) => s.id === activeSection);
              const isAdmin = user?.roles?.includes("admin");
              if (section?.adminOnly && !isAdmin) {
                return (
                  <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-[#1f2937] bg-[#0c111d] py-20 text-center">
                    <div className="flex h-14 w-14 items-center justify-center rounded-full border border-amber-500/20 bg-amber-500/10">
                      <Lock className="h-6 w-6 text-amber-500/60" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-slate-300">Admin Access Required</h3>
                      <p className="mt-1 text-xs text-slate-500">This section is restricted to administrators only.</p>
                      <p className="mt-0.5 text-xs text-slate-600">Contact your admin if you need access.</p>
                    </div>
                  </div>
                );
              }
              return sectionContent[activeSection] ?? null;
            })()}
          </div>
        </div>
      </div>
    </div>
  );
}
