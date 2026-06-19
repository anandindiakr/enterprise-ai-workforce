"use client";

import { useEffect, useState, useCallback } from "react";
import { authHeaders } from "@/lib/auth";
import {
  CreditCard, CheckCircle, XCircle, Clock, AlertTriangle,
  RefreshCw, X, Zap, Crown, Sparkles, ArrowUpRight, Receipt,
  TrendingUp, ChevronDown, ChevronUp, Check, Building2,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ─── Types ──────────────────────────────────────────────────────────────────

interface Plan {
  key: string; name: string;
  amount_cents_monthly: number; amount_display_monthly: string;
  amount_cents_annual: number; amount_display_annual: string;
  annual_discount_pct: number;
  max_users: number; max_chat_sessions: number; max_voice_minutes: number;
  features: string[];
}

interface Subscription {
  id: string; tenant_id: string; plan: string; status: string;
  billing_cycle: string; currency: string;
  amount_cents: number; amount_display: string;
  current_period_start?: string; current_period_end?: string;
  trial_end?: string; cancel_at_period_end: boolean; canceled_at?: string;
  stripe_connected: boolean; stripe_customer_id?: string;
  created_at: string;
}

interface Invoice {
  id: string; invoice_number: string; tenant_id: string; status: string;
  amount_due_cents: number; amount_due_display: string;
  amount_paid_cents: number; currency: string;
  description?: string;
  period_start?: string; period_end?: string;
  due_date?: string; paid_at?: string;
  line_items: Array<{ description: string; amount_cents: number; quantity: number }>;
  pdf_url?: string; hosted_invoice_url?: string;
  notes?: string; created_at: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const PLAN_ICONS: Record<string, React.ElementType> = {
  free: Clock, starter: Zap, pro: Crown, enterprise: Sparkles,
};
const PLAN_COLORS: Record<string, string> = {
  free:       "text-slate-400 bg-slate-500/10 border-slate-500/20",
  starter:    "text-blue-400 bg-blue-500/10 border-blue-500/20",
  pro:        "text-amber-400 bg-amber-500/10 border-amber-500/20",
  enterprise: "text-violet-400 bg-violet-500/10 border-violet-500/20",
};
const STATUS_COLORS: Record<string, string> = {
  active:        "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  trialing:      "text-blue-400 bg-blue-500/10 border-blue-500/20",
  past_due:      "text-red-400 bg-red-500/10 border-red-500/20",
  canceled:      "text-slate-400 bg-slate-500/10 border-slate-500/20",
  unpaid:        "text-red-400 bg-red-500/10 border-red-500/20",
  paused:        "text-amber-400 bg-amber-500/10 border-amber-500/20",
  paid:          "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  open:          "text-amber-400 bg-amber-500/10 border-amber-500/20",
  draft:         "text-slate-400 bg-slate-500/10 border-slate-500/20",
  void:          "text-slate-400 bg-slate-500/10 border-slate-500/20",
  uncollectible: "text-red-400 bg-red-500/10 border-red-500/20",
};

function fmt(isoDate?: string) {
  if (!isoDate) return "—";
  return new Date(isoDate).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

// ─── Plan Card ───────────────────────────────────────────────────────────────

function PlanCard({
  plan, currentPlan, billingCycle, onSelect, loading,
}: {
  plan: Plan; currentPlan: string; billingCycle: "monthly" | "annual";
  onSelect: (key: string) => void; loading: boolean;
}) {
  const isCurrent = plan.key === currentPlan;
  const PlanIcon = PLAN_ICONS[plan.key] ?? Zap;
  const price = billingCycle === "annual" ? plan.amount_display_annual : plan.amount_display_monthly;

  return (
    <div className={`relative flex flex-col rounded-2xl border p-4 transition-all
      ${isCurrent ? "border-amber-500/40 bg-amber-500/5" : "border-[#1f2937] bg-[#0c111d] hover:border-[#2d3748]"}`}>
      {isCurrent && (
        <span className="absolute -top-2.5 left-3 rounded-full border border-amber-500/30 bg-[#0c111d] px-2 py-0.5 text-[10px] font-semibold text-amber-400">
          Current plan
        </span>
      )}
      <div className="flex items-center gap-2 mb-2">
        <div className={`flex h-7 w-7 items-center justify-center rounded-lg border ${PLAN_COLORS[plan.key]}`}>
          <PlanIcon className="h-3.5 w-3.5" />
        </div>
        <p className="text-sm font-semibold text-slate-200">{plan.name}</p>
      </div>
      <p className="text-2xl font-bold text-slate-100 mb-0.5">{price}</p>
      <p className="text-[10px] text-slate-600 mb-3">
        {plan.max_users} users · {plan.max_chat_sessions.toLocaleString()} sessions · {plan.max_voice_minutes} voice min
      </p>
      <ul className="flex-1 space-y-1 mb-4">
        {plan.features.map(f => (
          <li key={f} className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Check className="h-2.5 w-2.5 text-emerald-400 flex-shrink-0" /> {f}
          </li>
        ))}
      </ul>
      <button
        onClick={() => onSelect(plan.key)}
        disabled={isCurrent || loading}
        className={`w-full rounded-xl py-2 text-xs font-medium transition-all disabled:opacity-40
          ${isCurrent
            ? "border border-amber-500/20 text-amber-400 cursor-default"
            : "border border-[#1f2937] text-slate-300 hover:border-amber-500/30 hover:text-amber-400 hover:bg-amber-500/5"}`}
      >
        {isCurrent ? "Active" : `Switch to ${plan.name}`}
      </button>
    </div>
  );
}

// ─── Invoice Row ─────────────────────────────────────────────────────────────

function InvoiceRow({ inv, onPay }: { inv: Invoice; onPay: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const statusCls = STATUS_COLORS[inv.status] ?? STATUS_COLORS.draft;

  return (
    <div className="rounded-xl border border-[#1f2937] bg-[#060c16]">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-3 p-3 text-left"
      >
        <Receipt className="h-3.5 w-3.5 text-slate-600 flex-shrink-0" />
        <span className="flex-1 text-xs font-medium text-slate-300">{inv.invoice_number}</span>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusCls}`}>
          {inv.status}
        </span>
        <span className="text-xs font-bold text-slate-200 w-16 text-right">{inv.amount_due_display}</span>
        <span className="text-[11px] text-slate-600 w-24 text-right">{fmt(inv.created_at)}</span>
        {open ? <ChevronUp className="h-3 w-3 text-slate-600" /> : <ChevronDown className="h-3 w-3 text-slate-600" />}
      </button>
      {open && (
        <div className="border-t border-[#1f2937] px-4 pb-3 pt-3 text-[11px] text-slate-500 space-y-2">
          {inv.description && <p>{inv.description}</p>}
          <div className="grid grid-cols-3 gap-2">
            <div><p className="text-slate-600">Period</p><p>{fmt(inv.period_start)} – {fmt(inv.period_end)}</p></div>
            <div><p className="text-slate-600">Due</p><p>{fmt(inv.due_date)}</p></div>
            <div><p className="text-slate-600">Paid at</p><p>{fmt(inv.paid_at)}</p></div>
          </div>
          {inv.line_items.length > 0 && (
            <div className="rounded-lg border border-[#1f2937] p-2 space-y-1">
              {inv.line_items.map((li, i) => (
                <div key={i} className="flex justify-between">
                  <span>{li.description} × {li.quantity}</span>
                  <span className="text-slate-300">${(li.amount_cents / 100).toFixed(2)}</span>
                </div>
              ))}
              <div className="flex justify-between border-t border-[#1f2937] pt-1 font-semibold text-slate-300">
                <span>Total</span><span>{inv.amount_due_display}</span>
              </div>
            </div>
          )}
          <div className="flex items-center gap-2 mt-1">
            {inv.hosted_invoice_url && (
              <a href={inv.hosted_invoice_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 rounded-lg border border-[#1f2937] px-2.5 py-1.5 text-slate-400 hover:text-blue-400 transition-all">
                <ArrowUpRight className="h-3 w-3" /> View Online
              </a>
            )}
            {inv.pdf_url && (
              <a href={inv.pdf_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 rounded-lg border border-[#1f2937] px-2.5 py-1.5 text-slate-400 hover:text-blue-400 transition-all">
                <Receipt className="h-3 w-3" /> Download PDF
              </a>
            )}
            {inv.status === "open" && (
              <button onClick={() => onPay(inv.id)}
                className="flex items-center gap-1 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1.5 text-emerald-400 hover:bg-emerald-500/20 transition-all">
                <CheckCircle className="h-3 w-3" /> Mark Paid
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Billing Drawer ──────────────────────────────────────────────────────

export default function BillingDrawer({ slug, tenantName, onClose }: {
  slug: string;
  tenantName: string;
  onClose: () => void;
}) {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [stripeAvailable, setStripeAvailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "plans" | "invoices">("overview");
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const showMsg = (text: string, ok = true) => {
    setMsg({ text, ok });
    setTimeout(() => setMsg(null), 4000);
  };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [billingRes, plansRes] = await Promise.allSettled([
        fetch(`${API}/api/v1/billing/tenants/${slug}/billing`, { headers: authHeaders() }),
        fetch(`${API}/api/v1/billing/plans`),
      ]);
      if (billingRes.status === "fulfilled" && billingRes.value.ok) {
        const d = await billingRes.value.json();
        setSub(d.subscription);
        setInvoices(d.recent_invoices ?? []);
      }
      if (plansRes.status === "fulfilled" && plansRes.value.ok) {
        const d = await plansRes.value.json();
        setPlans(d.plans ?? []);
        setStripeAvailable(d.stripe_available ?? false);
      }
    } catch {}
    setLoading(false);
  }, [slug]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleChangePlan = async (planKey: string) => {
    setActionLoading(true);
    try {
      const r = await fetch(`${API}/api/v1/billing/tenants/${slug}/billing/subscribe`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ plan: planKey, billing_cycle: billingCycle }),
      });
      const d = await r.json();
      if (r.ok) {
        setSub(d.subscription);
        showMsg(`Plan changed to ${planKey}`, true);
        setActiveTab("overview");
      } else {
        showMsg(d.detail ?? "Plan change failed", false);
      }
    } catch {
      showMsg("Network error", false);
    }
    setActionLoading(false);
  };

  const handleCancel = async () => {
    if (!confirm("Cancel subscription? It will remain active until the end of the current period.")) return;
    setActionLoading(true);
    try {
      const r = await fetch(`${API}/api/v1/billing/tenants/${slug}/billing/cancel`, {
        method: "DELETE",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ at_period_end: true }),
      });
      const d = await r.json();
      if (r.ok) { setSub(d.subscription); showMsg(d.message); }
      else showMsg(d.detail ?? "Cancel failed", false);
    } catch { showMsg("Network error", false); }
    setActionLoading(false);
  };

  const handleCreateInvoice = async () => {
    if (!sub) return;
    setActionLoading(true);
    try {
      const r = await fetch(`${API}/api/v1/billing/tenants/${slug}/billing/invoices`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ plan: sub.plan, billing_cycle: sub.billing_cycle }),
      });
      const d = await r.json();
      if (r.ok) {
        setInvoices(prev => [d.invoice, ...prev]);
        showMsg(`Invoice ${d.invoice.invoice_number} created`);
        setActiveTab("invoices");
      } else showMsg(d.detail ?? "Failed to create invoice", false);
    } catch { showMsg("Network error", false); }
    setActionLoading(false);
  };

  const handlePayInvoice = async (invoiceId: string) => {
    setActionLoading(true);
    try {
      const r = await fetch(`${API}/api/v1/billing/tenants/${slug}/billing/invoices/${invoiceId}/pay`, {
        method: "PATCH",
        headers: authHeaders(),
      });
      const d = await r.json();
      if (r.ok) {
        setInvoices(prev => prev.map(i => i.id === invoiceId ? d.invoice : i));
        showMsg("Invoice marked as paid");
      } else showMsg(d.detail ?? "Failed", false);
    } catch { showMsg("Network error", false); }
    setActionLoading(false);
  };

  const PlanIcon = sub ? (PLAN_ICONS[sub.plan] ?? Zap) : Zap;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="w-full max-w-lg bg-[#0c111d] border-l border-[#1f2937] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1f2937] px-5 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20">
              <CreditCard className="h-4 w-4 text-amber-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-200">Billing</p>
              <p className="text-[11px] text-slate-500 flex items-center gap-1">
                <Building2 className="h-3 w-3" />{tenantName}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-all">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[#1f2937]">
          {(["overview", "plans", "invoices"] as const).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2.5 text-xs font-medium capitalize transition-all
                ${activeTab === tab
                  ? "border-b-2 border-amber-500 text-amber-400"
                  : "text-slate-500 hover:text-slate-300"}`}>
              {tab}
            </button>
          ))}
        </div>

        {/* Toast */}
        {msg && (
          <div className={`mx-5 mt-3 flex items-center gap-2 rounded-xl border px-3 py-2 text-xs
            ${msg.ok ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400" : "border-red-500/20 bg-red-500/10 text-red-400"}`}>
            {msg.ok ? <CheckCircle className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
            {msg.text}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-20 text-slate-600">
              <RefreshCw className="h-5 w-5 animate-spin mr-2" /> Loading...
            </div>
          ) : (
            <>
              {/* ── OVERVIEW ─────────────────────────────────────────── */}
              {activeTab === "overview" && sub && (
                <div className="space-y-4">
                  {/* Subscription card */}
                  <div className={`rounded-2xl border p-4 ${PLAN_COLORS[sub.plan] ?? PLAN_COLORS.starter}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <PlanIcon className="h-4 w-4" />
                        <p className="text-sm font-semibold capitalize">{sub.plan} Plan</p>
                      </div>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${STATUS_COLORS[sub.status] ?? ""}`}>
                        {sub.status}
                      </span>
                    </div>
                    <p className="text-3xl font-bold text-slate-100">{sub.amount_display}</p>
                    <p className="text-[11px] mt-0.5 opacity-70 capitalize">{sub.billing_cycle} billing</p>
                    {sub.current_period_end && (
                      <p className="text-[11px] mt-2 opacity-60">
                        {sub.cancel_at_period_end ? "Cancels" : "Renews"} {fmt(sub.current_period_end)}
                      </p>
                    )}
                    {sub.cancel_at_period_end && (
                      <div className="mt-2 flex items-center gap-1 text-[11px] text-amber-300">
                        <AlertTriangle className="h-3 w-3" /> Scheduled to cancel at period end
                      </div>
                    )}
                  </div>

                  {/* Stripe notice */}
                  {!stripeAvailable && (
                    <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-3 text-[11px] text-blue-400">
                      <p className="font-semibold mb-0.5">Stripe not connected</p>
                      <p>Add <code className="text-blue-300">STRIPE_SECRET_KEY</code> to your <code>.env</code> to enable
                        automatic payment collection, hosted invoice pages, and webhook sync.</p>
                    </div>
                  )}

                  {/* Quick stats */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl border border-[#1f2937] bg-[#060c16] p-3">
                      <p className="text-[10px] text-slate-600 mb-1">Current Period</p>
                      <p className="text-xs text-slate-300">{fmt(sub.current_period_start)}</p>
                      <p className="text-xs text-slate-300">– {fmt(sub.current_period_end)}</p>
                    </div>
                    <div className="rounded-xl border border-[#1f2937] bg-[#060c16] p-3">
                      <p className="text-[10px] text-slate-600 mb-1">Invoices</p>
                      <p className="text-lg font-bold text-slate-200">{invoices.length}</p>
                      <p className="text-[10px] text-slate-600">recent records</p>
                    </div>
                  </div>

                  {/* Recent invoices preview */}
                  {invoices.length > 0 && (
                    <div>
                      <p className="text-[11px] font-mono uppercase tracking-wider text-slate-600 mb-2">Recent Invoices</p>
                      <div className="space-y-2">
                        {invoices.slice(0, 3).map(inv => (
                          <div key={inv.id}
                            className="flex items-center justify-between rounded-lg border border-[#1f2937] px-3 py-2 text-xs">
                            <span className="text-slate-400">{inv.invoice_number}</span>
                            <span className={`rounded-full border px-1.5 py-0.5 text-[10px] ${STATUS_COLORS[inv.status] ?? ""}`}>
                              {inv.status}
                            </span>
                            <span className="font-semibold text-slate-200">{inv.amount_due_display}</span>
                            <span className="text-slate-600">{fmt(inv.created_at)}</span>
                          </div>
                        ))}
                      </div>
                      <button onClick={() => setActiveTab("invoices")}
                        className="mt-2 text-[11px] text-slate-500 hover:text-amber-400 flex items-center gap-1 transition-all">
                        View all invoices <ArrowUpRight className="h-3 w-3" />
                      </button>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-2">
                    <button onClick={() => setActiveTab("plans")}
                      className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-amber-500/20 bg-amber-500/10 py-2.5 text-xs font-medium text-amber-400 hover:bg-amber-500/20 transition-all">
                      <TrendingUp className="h-3.5 w-3.5" /> Change Plan
                    </button>
                    <button onClick={handleCreateInvoice} disabled={actionLoading}
                      className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-[#1f2937] py-2.5 text-xs text-slate-400 hover:text-slate-200 disabled:opacity-50 transition-all">
                      <Receipt className="h-3.5 w-3.5" /> Generate Invoice
                    </button>
                    {!sub.cancel_at_period_end && sub.status !== "canceled" && (
                      <button onClick={handleCancel} disabled={actionLoading}
                        className="rounded-xl border border-red-500/20 bg-red-500/5 px-3 py-2.5 text-xs text-red-400 hover:bg-red-500/10 disabled:opacity-50 transition-all">
                        Cancel
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* ── PLANS ───────────────────────────────────────────── */}
              {activeTab === "plans" && (
                <div className="space-y-4">
                  {/* Billing cycle toggle */}
                  <div className="flex items-center justify-between rounded-xl border border-[#1f2937] bg-[#060c16] p-3">
                    <p className="text-xs text-slate-400">Billing cycle</p>
                    <div className="flex rounded-lg border border-[#1f2937] overflow-hidden">
                      {(["monthly", "annual"] as const).map(cycle => (
                        <button key={cycle} onClick={() => setBillingCycle(cycle)}
                          className={`px-3 py-1.5 text-xs capitalize transition-all
                            ${billingCycle === cycle
                              ? "bg-amber-500/20 text-amber-400"
                              : "text-slate-500 hover:text-slate-300"}`}>
                          {cycle}
                          {cycle === "annual" && (
                            <span className="ml-1 text-[10px] text-emerald-400">−20%</span>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3">
                    {plans.map(plan => (
                      <PlanCard
                        key={plan.key} plan={plan}
                        currentPlan={sub?.plan ?? "free"}
                        billingCycle={billingCycle}
                        onSelect={handleChangePlan}
                        loading={actionLoading}
                      />
                    ))}
                  </div>

                  {!stripeAvailable && (
                    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-[11px] text-amber-400">
                      <p className="font-semibold mb-0.5">Plan changes are recorded locally</p>
                      <p>Connect Stripe to automatically charge customers on plan changes and send hosted payment links.</p>
                    </div>
                  )}
                </div>
              )}

              {/* ── INVOICES ────────────────────────────────────────── */}
              {activeTab === "invoices" && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-[11px] font-mono uppercase tracking-wider text-slate-600">{invoices.length} invoices</p>
                    <button onClick={handleCreateInvoice} disabled={actionLoading}
                      className="flex items-center gap-1.5 rounded-xl border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 hover:text-amber-400 hover:border-amber-500/30 disabled:opacity-50 transition-all">
                      <Receipt className="h-3 w-3" /> New Invoice
                    </button>
                  </div>

                  {invoices.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 text-slate-600">
                      <Receipt className="h-10 w-10 mb-3 opacity-30" />
                      <p className="text-sm">No invoices yet</p>
                      <p className="text-[11px] mt-1">Invoices appear here once generated or synced from Stripe</p>
                    </div>
                  ) : (
                    invoices.map(inv => (
                      <InvoiceRow key={inv.id} inv={inv} onPay={handlePayInvoice} />
                    ))
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
