"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  Calculator,
  FileDown,
  Mail,
  Plus,
  RefreshCw,
  ScrollText,
  Trash2,
  X,
} from "lucide-react";
import { authHeaders } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

interface Entry {
  id: string;
  entry_date: string;
  entry_type: "invoice" | "expense" | "payment";
  vendor: string;
  description: string;
  amount: number;
  currency: string;
  category: string | null;
  status: string;
  source_doc: string | null;
}

interface Summary {
  total_invoiced: number;
  total_expenses: number;
  net: number;
  count: number;
  by_category: { category: string; total: number }[];
}

const TYPE_STYLES: Record<string, string> = {
  invoice: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  expense: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  payment: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
};

export default function FinancePage() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [showBill, setShowBill] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  /* Add-entry form */
  const [form, setForm] = useState({
    entry_type: "expense", vendor: "", amount: "", currency: "INR",
    category: "", description: "", entry_date: "",
  });
  const [saving, setSaving] = useState(false);

  /* Bill ingestion */
  const [billText, setBillText] = useState("");
  const [ingesting, setIngesting] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [lr, sr] = await Promise.all([
        fetch(`${API}/api/v1/finance/ledger?limit=300`, { headers: authHeaders() }),
        fetch(`${API}/api/v1/finance/ledger/summary`, { headers: authHeaders() }),
      ]);
      if (lr.ok) setEntries((await lr.json()).entries ?? []);
      if (sr.ok) setSummary(await sr.json());
    } catch { /* network */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const addEntry = async () => {
    const amount = parseFloat(form.amount);
    if (!amount || amount <= 0) { setNotice("Enter a valid amount."); return; }
    setSaving(true);
    try {
      const r = await fetch(`${API}/api/v1/finance/ledger`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_type: form.entry_type,
          vendor: form.vendor,
          amount,
          currency: form.currency || "INR",
          category: form.category || null,
          description: form.description,
          entry_date: form.entry_date || null,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setNotice(d.detail ?? "Save failed");
      } else {
        setShowAdd(false);
        setForm({ entry_type: "expense", vendor: "", amount: "", currency: "INR", category: "", description: "", entry_date: "" });
        setNotice("Entry recorded.");
        fetchAll();
      }
    } catch { setNotice("Network error"); }
    setSaving(false);
  };

  const ingestBill = async () => {
    if (billText.trim().length < 20) { setNotice("Paste at least a couple of lines from the bill."); return; }
    setIngesting(true);
    try {
      const r = await fetch(`${API}/api/v1/finance/ledger/ingest`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ text: billText, source_doc: "pasted" }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setNotice(d.detail ?? "Ingestion failed");
      } else {
        const d = await r.json();
        setNotice(
          d.extraction === "llm"
            ? `Bill processed — ${d.count} ledger ${d.count === 1 ? "entry" : "entries"} created.`
            : "Saved for manual review (AI extraction unavailable on this server)."
        );
        setShowBill(false);
        setBillText("");
        fetchAll();
      }
    } catch { setNotice("Network error"); }
    setIngesting(false);
  };

  const removeEntry = async (id: string) => {
    if (!confirm("Delete this ledger entry?")) return;
    await fetch(`${API}/api/v1/finance/ledger/${id}`, { method: "DELETE", headers: authHeaders() });
    fetchAll();
  };

  const emailReport = async () => {
    const to = prompt("Email the ledger summary to:");
    if (!to) return;
    const r = await fetch(`${API}/api/v1/finance/ledger/email`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ to }),
    });
    if (r.ok) setNotice(`Report emailed to ${to}.`);
    else {
      const d = await r.json().catch(() => ({}));
      setNotice(d.detail ?? "Email failed");
    }
  };

  const exportCsv = async () => {
    const r = await fetch(`${API}/api/v1/finance/ledger/export.csv`, { headers: authHeaders() });
    if (!r.ok) return;
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "ledger.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const money = (n: number, cur = "INR") =>
    `${cur === "INR" ? "₹" : cur === "USD" ? "$" : cur + " "}${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

  return (
    <div className="min-h-screen bg-[#030712] text-slate-300">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1f2937] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-amber-500/20 bg-amber-500/10">
            <Calculator className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-200">Finance Ledger</h1>
            <p className="text-[11px] text-slate-500">
              {summary?.count ?? 0} entries · bills in, books in order
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={fetchAll} className="rounded-xl border border-[#1f2937] p-2 text-slate-500 transition-all hover:text-slate-300">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button onClick={exportCsv} title="Export CSV"
            className="flex items-center gap-1.5 rounded-xl border border-[#1f2937] px-3 py-2 text-xs text-slate-400 transition-all hover:border-[#374151] hover:text-slate-200">
            <FileDown className="h-3.5 w-3.5" /> CSV
          </button>
          <button onClick={emailReport}
            className="flex items-center gap-1.5 rounded-xl border border-[#1f2937] px-3 py-2 text-xs text-slate-400 transition-all hover:border-cyan-500/30 hover:text-cyan-400">
            <Mail className="h-3.5 w-3.5" /> Email report
          </button>
          <button onClick={() => setShowBill(true)}
            className="flex items-center gap-1.5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-400 transition-all hover:bg-emerald-500/20">
            <ScrollText className="h-3.5 w-3.5" /> Paste Bill
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/20 px-3 py-2 text-xs font-medium text-amber-400 transition-all hover:bg-amber-500/30">
            <Plus className="h-3.5 w-3.5" /> Add Entry
          </button>
        </div>
      </div>

      {notice && (
        <div className="mx-6 mt-4 flex items-center justify-between rounded-xl border border-[#1f2937] bg-[#0c111d] px-4 py-2 text-xs text-slate-300">
          <span>{notice}</span>
          <button onClick={() => setNotice(null)}><X className="h-3.5 w-3.5 text-slate-500" /></button>
        </div>
      )}

      <div className="space-y-5 p-6">
        {/* Summary cards */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[
            { label: "Total Invoiced", value: money(summary?.total_invoiced ?? 0), color: "text-emerald-400", icon: ArrowUpRight },
            { label: "Total Expenses", value: money(summary?.total_expenses ?? 0), color: "text-rose-400", icon: ArrowDownRight },
            { label: "Net", value: money(summary?.net ?? 0), color: (summary?.net ?? 0) >= 0 ? "text-cyan-400" : "text-rose-400", icon: Calculator },
            { label: "Entries", value: String(summary?.count ?? 0), color: "text-slate-200", icon: ScrollText },
          ].map(({ label, value, color, icon: Icon }) => (
            <div key={label} className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-4">
              <div className="mb-1 flex items-center gap-2">
                <Icon className="h-3.5 w-3.5 text-slate-600" />
                <p className="text-[11px] uppercase tracking-wider text-slate-600">{label}</p>
              </div>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Ledger table */}
        <div className="overflow-hidden rounded-2xl border border-[#1f2937] bg-[#0c111d]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead className="border-b border-[#1f2937] text-[10px] uppercase tracking-wider text-slate-600">
                <tr>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Vendor</th>
                  <th className="px-4 py-3">Description</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-600">Loading…</td></tr>
                ) : entries.length === 0 ? (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-600">
                    No entries yet — paste a bill or add one manually.
                  </td></tr>
                ) : entries.map((e) => (
                  <tr key={e.id} className="border-b border-[#141c2e] last:border-0 hover:bg-[#0f1626]">
                    <td className="whitespace-nowrap px-4 py-2.5 text-slate-400">
                      {new Date(e.entry_date).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded-md border px-1.5 py-0.5 text-[10px] capitalize ${TYPE_STYLES[e.entry_type] ?? ""}`}>
                        {e.entry_type}
                      </span>
                    </td>
                    <td className="max-w-[160px] truncate px-4 py-2.5 text-slate-200" title={e.vendor}>{e.vendor || "—"}</td>
                    <td className="max-w-[240px] truncate px-4 py-2.5 text-slate-400" title={e.description}>{e.description || "—"}</td>
                    <td className={`whitespace-nowrap px-4 py-2.5 text-right font-medium ${e.entry_type === "expense" ? "text-rose-400" : "text-emerald-400"}`}>
                      {e.entry_type === "expense" ? "−" : "+"}{money(e.amount, e.currency)}
                    </td>
                    <td className="px-4 py-2.5 capitalize text-slate-500">{e.category || "—"}</td>
                    <td className="px-4 py-2.5 text-slate-500">{e.status === "pending_review" ? "⏳ review" : e.status}</td>
                    <td className="px-4 py-2.5">
                      <button onClick={() => removeEntry(e.id)} className="text-slate-600 transition-colors hover:text-red-400">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Add-entry modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-[#1f2937] bg-[#0c111d] p-6 shadow-2xl">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200">New Ledger Entry</h2>
              <button onClick={() => setShowAdd(false)}><X className="h-4 w-4 text-slate-500" /></button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <label className="col-span-1">
                <span className="mb-1 block text-slate-500">Type</span>
                <select value={form.entry_type} onChange={(e) => setForm({ ...form, entry_type: e.target.value })}
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200">
                  <option value="expense">Expense (money out)</option>
                  <option value="invoice">Invoice (money in)</option>
                  <option value="payment">Payment received</option>
                </select>
              </label>
              <label className="col-span-1">
                <span className="mb-1 block text-slate-500">Amount *</span>
                <input value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  type="number" min="0" placeholder="15000"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-1">
                <span className="mb-1 block text-slate-500">Vendor</span>
                <input value={form.vendor} onChange={(e) => setForm({ ...form, vendor: e.target.value })}
                  placeholder="AWS / Acme Corp"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-1">
                <span className="mb-1 block text-slate-500">Category</span>
                <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
                  placeholder="software / rent / travel"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-1">
                <span className="mb-1 block text-slate-500">Currency</span>
                <input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                  placeholder="INR"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-1">
                <span className="mb-1 block text-slate-500">Date</span>
                <input value={form.entry_date} onChange={(e) => setForm({ ...form, entry_date: e.target.value })}
                  type="date"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-2">
                <span className="mb-1 block text-slate-500">Description</span>
                <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  rows={2} placeholder="What was this for?"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
            </div>
            <button onClick={addEntry} disabled={saving}
              className="mt-5 w-full rounded-xl bg-amber-500 py-2.5 text-xs font-semibold text-black transition-colors hover:bg-amber-400 disabled:opacity-50">
              {saving ? "Saving…" : "Record Entry"}
            </button>
          </div>
        </div>
      )}

      {/* Paste-bill modal */}
      {showBill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-2xl border border-[#1f2937] bg-[#0c111d] p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200">Paste Bill / Invoice Text</h2>
              <button onClick={() => setShowBill(false)}><X className="h-4 w-4 text-slate-500" /></button>
            </div>
            <p className="mb-3 text-[11px] leading-relaxed text-slate-500">
              Copy the text from a bill or invoice (or type the details) and the AI
              extracts vendor, amount, date and category into ledger entries
              automatically. Without an OpenAI key on the server it saves the bill
              for manual review instead.
            </p>
            <textarea value={billText} onChange={(e) => setBillText(e.target.value)}
              rows={9} placeholder={"ACME ELECTRICITY BILL\nInvoice No: AP/2026/0042\nDate: 05/08/2026\nAmount: ₹4,230.00\nDue for August electricity."}
              className="w-full rounded-xl border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-xs text-slate-200" />
            <button onClick={ingestBill} disabled={ingesting}
              className="mt-4 w-full rounded-xl bg-emerald-500 py-2.5 text-xs font-semibold text-black transition-colors hover:bg-emerald-400 disabled:opacity-50">
              {ingesting ? "Processing…" : "Process Bill"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
