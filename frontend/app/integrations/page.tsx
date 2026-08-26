"use client";

import { useEffect, useState } from "react";
import {
  Plug, CheckCircle, Clock, AlertCircle, ExternalLink,
  Users, DollarSign, BarChart2, Cpu, Mail, Calendar,
  ShoppingCart, Building2, Briefcase, ChevronRight,
} from "lucide-react";

interface Integration {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: React.ElementType;
  color: string;
  status: "connected" | "available" | "coming_soon";
  docsUrl?: string;
  fields?: { key: string; label: string; type: "text" | "password" | "url" }[];
}

const INTEGRATIONS: Integration[] = [
  {
    id: "hubspot",
    name: "HubSpot CRM",
    description: "Sync contacts, deals, and pipeline data with the Sales agent.",
    category: "CRM",
    icon: ShoppingCart,
    color: "text-orange-400",
    status: "available",
    docsUrl: "https://developers.hubspot.com/docs/api/overview",
    fields: [
      { key: "api_key", label: "API Key", type: "password" },
      { key: "portal_id", label: "Portal ID", type: "text" },
    ],
  },
  {
    id: "salesforce",
    name: "Salesforce",
    description: "Connect to Salesforce CRM for advanced sales workflows.",
    category: "CRM",
    icon: Building2,
    color: "text-blue-400",
    status: "available",
    docsUrl: "https://developer.salesforce.com/docs/apis",
    fields: [
      { key: "client_id", label: "Client ID", type: "text" },
      { key: "client_secret", label: "Client Secret", type: "password" },
      { key: "instance_url", label: "Instance URL", type: "url" },
    ],
  },
  {
    id: "bamboohr",
    name: "BambooHR",
    description: "Employee records, onboarding, and leave management for the HR agent.",
    category: "HRIS",
    icon: Users,
    color: "text-green-400",
    status: "available",
    docsUrl: "https://documentation.bamboohr.com/docs",
    fields: [
      { key: "api_key", label: "API Key", type: "password" },
      { key: "subdomain", label: "Company Subdomain", type: "text" },
    ],
  },
  {
    id: "workday",
    name: "Workday",
    description: "Full HR suite — payroll, recruiting, and workforce analytics.",
    category: "HRIS",
    icon: Briefcase,
    color: "text-violet-400",
    status: "coming_soon",
  },
  {
    id: "quickbooks",
    name: "QuickBooks",
    description: "Invoices, expenses, and financial reports for the Finance agent.",
    category: "Finance",
    icon: DollarSign,
    color: "text-emerald-400",
    status: "available",
    docsUrl: "https://developer.intuit.com/app/developer/qbo/docs/api",
    fields: [
      { key: "client_id", label: "Client ID", type: "text" },
      { key: "client_secret", label: "Client Secret", type: "password" },
      { key: "realm_id", label: "Realm ID", type: "text" },
    ],
  },
  {
    id: "xero",
    name: "Xero",
    description: "Cloud accounting for invoicing, payroll, and bank reconciliation.",
    category: "Finance",
    icon: BarChart2,
    color: "text-blue-300",
    status: "coming_soon",
  },
  {
    id: "jira",
    name: "Jira",
    description: "IT ticket management and sprint tracking for the Technology agent.",
    category: "IT",
    icon: Cpu,
    color: "text-sky-400",
    status: "available",
    docsUrl: "https://developer.atlassian.com/cloud/jira/platform/rest/v3/",
    fields: [
      { key: "domain", label: "Domain (e.g. mycompany.atlassian.net)", type: "url" },
      { key: "email", label: "Email", type: "text" },
      { key: "api_token", label: "API Token", type: "password" },
    ],
  },
  {
    id: "zendesk",
    name: "Zendesk",
    description: "Customer support tickets and satisfaction scoring.",
    category: "Support",
    icon: Mail,
    color: "text-yellow-400",
    status: "available",
    docsUrl: "https://developer.zendesk.com/api-reference",
    fields: [
      { key: "subdomain", label: "Subdomain", type: "text" },
      { key: "email", label: "Agent Email", type: "text" },
      { key: "api_token", label: "API Token", type: "password" },
    ],
  },
  {
    id: "google_calendar",
    name: "Google Calendar",
    description: "Schedule meetings and check availability during conversations.",
    category: "Productivity",
    icon: Calendar,
    color: "text-red-400",
    status: "available",
    docsUrl: "https://developers.google.com/calendar",
    fields: [
      { key: "client_id", label: "OAuth Client ID", type: "text" },
      { key: "client_secret", label: "OAuth Client Secret", type: "password" },
    ],
  },
  {
    id: "slack",
    name: "Slack",
    description: "Post notifications and escalation alerts to Slack channels.",
    category: "Productivity",
    icon: Mail,
    color: "text-purple-400",
    status: "coming_soon",
  },
];

const CATEGORIES = [...new Set(INTEGRATIONS.map((i) => i.category))];

// Vendor catalog → generic connector key stored by the backend
// (GET/POST /api/v1/settings/integrations). The backend stores connector
// base URLs, not vendor OAuth credentials.
const VENDOR_TO_KEY: Record<string, string> = {
  hubspot:         "crm_base_url",
  salesforce:      "crm_base_url",
  bamboohr:        "hris_base_url",
  quickbooks:      "finance_base_url",
  jira:            "devops_base_url",
  zendesk:         "devops_base_url",
  google_calendar: "calendar_base_url",
};

// Resolve the connector base URL from this vendor's form fields, or null when
// the fields can't produce one (API-key/OAuth-only vendors).
function resolveConnectorValue(id: string, values: Record<string, string>): string | null {
  const urlField = id === "salesforce" ? "instance_url" : id === "jira" ? "domain" : null;
  if (urlField && values[urlField]?.trim()) return values[urlField].trim();
  if (id === "bamboohr" && values.subdomain?.trim())
    return `https://${values.subdomain.trim()}.bamboohr.com`;
  if (id === "zendesk" && values.subdomain?.trim())
    return `https://${values.subdomain.trim()}.zendesk.com`;
  return null;
}

function statusIcon(status: Integration["status"]) {
  if (status === "connected")
    return <CheckCircle className="h-4 w-4 text-emerald-400" />;
  if (status === "available")
    return <Clock className="h-4 w-4 text-slate-500" />;
  return <AlertCircle className="h-4 w-4 text-slate-600" />;
}

function statusLabel(status: Integration["status"]) {
  if (status === "connected") return "Connected";
  if (status === "available") return "Not connected";
  return "Coming soon";
}

export default function IntegrationsPage() {
  const [filter, setFilter] = useState("All");
  const [active, setActive] = useState<Integration | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [connected, setConnected] = useState<Set<string>>(new Set());

  const shown = INTEGRATIONS.filter(
    (i) => filter === "All" || i.category === filter
  );

  /* Load the real connected state from the backend on mount. */
  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("workforce_token") : null;
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    fetch(`${apiBase}/api/v1/settings/integrations`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        const configured = new Set(
          (d.integrations ?? []).map((i: { key: string }) => i.key)
        );
        const connectedVendors = new Set<string>();
        Object.entries(VENDOR_TO_KEY).forEach(([vendor, key]) => {
          if (configured.has(key)) connectedVendors.add(vendor);
        });
        setConnected(connectedVendors);
      })
      .catch(() => {});
  }, []);

  function openConfig(integration: Integration) {
    if (integration.status === "coming_soon") return;
    setActive(integration);
    setFormValues({});
    setSaveMsg("");
  }

  async function handleSave() {
    if (!active) return;
    setSaving(true);
    setSaveMsg("");
    const key = VENDOR_TO_KEY[active.id];
    const value = resolveConnectorValue(active.id, formValues);

    if (!key) {
      // Vendor not mapped to a backend connector — don't fake success.
      setSaveMsg("This integration isn't wired to a connector yet.");
      setSaving(false);
      return;
    }
    if (value === null) {
      setSaveMsg(
        "This vendor needs a connector URL, which its fields can't provide. " +
        "Add the base URL under Settings → Integrations."
      );
      setSaving(false);
      return;
    }

    const token = typeof window !== "undefined" ? localStorage.getItem("workforce_token") : null;
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    try {
      const r = await fetch(`${apiBase}/api/v1/settings/integrations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ integrations: { [key]: value } }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setConnected((prev) => new Set([...prev, active.id]));
      setSaveMsg("Configuration saved. Agents can now use this integration.");
    } catch {
      setSaveMsg("Save failed — check your connection and try again.");
    }
    setSaving(false);
  }

  return (
    <div className="p-6 max-w-6xl mx-auto text-slate-100">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <Plug className="h-7 w-7 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Integrations</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Connect your existing tools so AI agents can read and act on real data
          </p>
        </div>
      </div>

      {/* Notice */}
      <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-300">
        <strong>Note:</strong> Integrations are currently in mock mode — agents respond with simulated data.
        Connector endpoints configured here are stored and shown as Connected; live
        vendor sync is enabled once real connectors are activated.
      </div>

      {/* Category filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        {["All", ...CATEGORIES].map((c) => (
          <button
            key={c}
            onClick={() => setFilter(c)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              filter === c
                ? "bg-blue-600 text-white"
                : "border border-slate-600 text-slate-400 hover:text-slate-200 hover:border-slate-500"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {shown.map((integration) => {
          const Icon = integration.icon;
          const isConnected = connected.has(integration.id);
          return (
            <div
              key={integration.id}
              onClick={() => openConfig(integration)}
              className={`rounded-xl border p-5 transition-all ${
                integration.status === "coming_soon"
                  ? "border-slate-700 bg-slate-800/50 cursor-not-allowed opacity-60"
                  : "border-slate-700 bg-slate-800 cursor-pointer hover:border-blue-500/50 hover:bg-slate-700/50"
              }`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg border border-slate-600 bg-slate-900 p-2">
                    <Icon className={`h-5 w-5 ${integration.color}`} />
                  </div>
                  <div>
                    <p className="font-semibold text-sm text-slate-100">{integration.name}</p>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">{integration.category}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {isConnected ? <CheckCircle className="h-4 w-4 text-emerald-400" /> : statusIcon(integration.status)}
                </div>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed mb-3">{integration.description}</p>
              <div className="flex items-center justify-between">
                <span className={`text-xs ${isConnected ? "text-emerald-400" : "text-slate-500"}`}>
                  {isConnected ? "Connected" : statusLabel(integration.status)}
                </span>
                {integration.status !== "coming_soon" && (
                  <ChevronRight className="h-4 w-4 text-slate-500" />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Config modal */}
      {active && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={(e) => { if (e.target === e.currentTarget) setActive(null); }}
        >
          <div className="w-full max-w-lg rounded-2xl border border-slate-600 bg-[#0c1220] p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-5">
              <div className="rounded-lg border border-slate-600 bg-slate-800 p-2">
                <active.icon className={`h-5 w-5 ${active.color}`} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">{active.name}</h2>
                <p className="text-xs text-slate-400">{active.category}</p>
              </div>
              {active.docsUrl && (
                <a
                  href={active.docsUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="ml-auto flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                >
                  Docs <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>

            <p className="text-sm text-slate-300 mb-4">{active.description}</p>

            {active.fields?.map((f) => (
              <div key={f.key} className="mb-3">
                <label className="block text-xs text-slate-400 mb-1">{f.label}</label>
                <input
                  type={f.type === "password" ? "password" : "text"}
                  value={formValues[f.key] ?? ""}
                  onChange={(e) => setFormValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                  placeholder={f.type === "password" ? "••••••••" : `Enter ${f.label.toLowerCase()}`}
                  className="w-full px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            ))}

            {saveMsg && (
              <p className="mb-3 text-sm text-emerald-400">{saveMsg}</p>
            )}

            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => setActive(null)}
                className="px-4 py-2 rounded-lg border border-slate-600 text-sm text-slate-400 hover:text-slate-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? "Saving…" : "Save & Connect"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
