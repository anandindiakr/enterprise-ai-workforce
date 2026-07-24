"use client";

import { useState, useEffect, useCallback } from "react";
import {
  PackagePlus, Trash2, Search, RefreshCw, Pencil, X,
  CheckCircle, AlertTriangle, ToggleLeft, ToggleRight, Sparkles,
} from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { getToken } from "@/lib/auth";

interface Product {
  id: string;
  name: string;
  description: string;
  category: string | null;
  price: string | null;
  sku: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
const CATEGORIES = ["General", "Products", "Services", "Support Plans", "Add-ons"];

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

interface FormState {
  name: string;
  description: string;
  category: string;
  price: string;
  sku: string;
  is_active: boolean;
}

const EMPTY_FORM: FormState = {
  name: "", description: "", category: "General", price: "", sku: "", is_active: true,
};

function ProductModal({
  initial, onClose, onSave, saving,
}: {
  initial: FormState;
  onClose: () => void;
  onSave: (f: FormState) => void;
  saving: boolean;
}) {
  const [form, setForm] = useState<FormState>(initial);
  const inputCls = "w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:border-emerald-500/50 focus:outline-none";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-[#1f2937] bg-[#0c111d] p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">{initial.name ? "Edit Product / Service" : "Add Product / Service"}</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300"><X className="h-4 w-4" /></button>
        </div>
        <p className="text-[11px] text-slate-500">
          No need to write documents — fill this simple form and your AI agents will immediately be able to answer
          questions about it on chat and phone calls.
        </p>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Name *</label>
            <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Website Design Package" className={inputCls} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Description</label>
            <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="What is it, what's included, who it's for…"
              className={`${inputCls} min-h-[90px] resize-y`} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">Category</label>
              <select value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                className={inputCls}>
                {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">Price (optional)</label>
              <input value={form.price} onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
                placeholder="e.g. $499 or Contact us" className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 items-end">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">SKU (optional)</label>
              <input value={form.sku} onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))}
                placeholder="e.g. WEB-001" className={inputCls} />
            </div>
            <label className="flex items-center gap-2 pb-2 text-xs text-slate-400 cursor-pointer">
              <button type="button" onClick={() => setForm((f) => ({ ...f, is_active: !f.is_active }))}>
                {form.is_active ? <ToggleRight className="h-6 w-6 text-emerald-400" /> : <ToggleLeft className="h-6 w-6 text-slate-600" />}
              </button>
              Active (visible to agents)
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="rounded-lg border border-[#1f2937] px-4 py-2 text-xs text-slate-400 hover:text-slate-200">Cancel</button>
          <button
            onClick={() => onSave(form)}
            disabled={saving || !form.name.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-black hover:bg-emerald-400 disabled:opacity-50"
          >
            {saving ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5" />}
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterText, setFilterText] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/v1/products`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setProducts(data.products ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load products");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setEditing(null); setModalOpen(true); };
  const openEdit = (p: Product) => { setEditing(p); setModalOpen(true); };

  const handleSave = async (form: FormState) => {
    setSaving(true);
    setMsg(null);
    try {
      const url = editing ? `${API}/api/v1/products/${editing.id}` : `${API}/api/v1/products`;
      const method = editing ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Save failed");
      setMsg({ ok: true, text: `"${data.name}" saved — agents can answer questions about it now.` });
      setModalOpen(false);
      await load();
    } catch (e: unknown) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Error saving product" });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (p: Product) => {
    if (!confirm(`Delete "${p.name}"? This also removes it from the AI knowledge base.`)) return;
    try {
      await fetch(`${API}/api/v1/products/${p.id}`, { method: "DELETE", headers: authHeaders() });
      await load();
    } catch {}
  };

  const filtered = products.filter(
    (p) => !filterText || p.name.toLowerCase().includes(filterText.toLowerCase()) ||
      (p.category ?? "").toLowerCase().includes(filterText.toLowerCase())
  );

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-6xl mx-auto text-slate-100">
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <PackagePlus className="h-4.5 w-4.5 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Products &amp; Services</h1>
              <p className="text-xs text-slate-500 mt-0.5">
                {products.length} item{products.length !== 1 ? "s" : ""} — automatically feeds your AI agents' knowledge
              </p>
            </div>
          </div>
          <button onClick={openCreate}
            className="flex items-center gap-1.5 rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-black hover:bg-emerald-400 transition-all">
            <PackagePlus className="h-3.5 w-3.5" /> Add Product / Service
          </button>
        </div>

        <div className="mb-5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 flex items-start gap-2 text-[11px] text-slate-400">
          <Sparkles className="h-4 w-4 text-emerald-400 flex-shrink-0 mt-0.5" />
          <p>
            This is the easiest way to teach your AI Workforce what your business actually sells. No document
            writing needed — just fill in the fields and your Sales, Reception and Customer Care agents can
            immediately answer caller/chat questions about it, on the phone and in chat.
          </p>
        </div>

        {msg && (
          <div className={`mb-4 flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
            msg.ok ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" : "border-red-500/25 bg-red-500/10 text-red-400"
          }`}>
            {msg.ok ? <CheckCircle className="h-3.5 w-3.5 flex-shrink-0" /> : <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />}
            {msg.text}
          </div>
        )}

        <div className="relative mb-4 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-600" />
          <input type="text" placeholder="Filter by name or category…"
            value={filterText} onChange={(e) => setFilterText(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-[#1f2937] bg-[#0c111d] text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500" />
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl border border-red-500/20 bg-red-500/5 text-red-400 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-[#1f2937] bg-[#0c111d] p-4 animate-pulse">
                <div className="h-4 bg-[#1f2937] rounded w-3/4 mb-2" />
                <div className="h-3 bg-[#1f2937] rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-600 rounded-2xl border border-dashed border-[#1f2937]">
            <PackagePlus className="h-12 w-12 mb-3 opacity-30" />
            <p className="font-medium text-slate-500">No products or services yet</p>
            <p className="text-xs mt-1 mb-4">Add your first one so agents know what your business offers</p>
            <button onClick={openCreate}
              className="flex items-center gap-1.5 rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-black hover:bg-emerald-400">
              <PackagePlus className="h-3.5 w-3.5" /> Add your first product
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((p) => (
              <div key={p.id}
                className="group rounded-2xl border border-[#1f2937] bg-[#0c111d] p-4 hover:border-emerald-500/30 transition-all">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h3 className="font-medium text-slate-200 text-sm truncate">{p.name}</h3>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0">
                    <button onClick={() => openEdit(p)} className="text-slate-600 hover:text-emerald-400" title="Edit">
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button onClick={() => handleDelete(p)} className="text-slate-600 hover:text-red-400" title="Delete">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
                {p.description && (
                  <p className="text-xs text-slate-500 line-clamp-2 mb-2">{p.description}</p>
                )}
                <div className="flex flex-wrap items-center gap-1.5">
                  {p.category && (
                    <span className="rounded-full border border-[#1f2937] px-2 py-0.5 text-[10px] text-slate-500 bg-[#060c16]">{p.category}</span>
                  )}
                  {p.price && (
                    <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-400">{p.price}</span>
                  )}
                  {!p.is_active && (
                    <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] text-slate-500">Inactive</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {modalOpen && (
          <ProductModal
            initial={editing ? {
              name: editing.name, description: editing.description ?? "", category: editing.category ?? "General",
              price: editing.price ?? "", sku: editing.sku ?? "", is_active: editing.is_active,
            } : EMPTY_FORM}
            onClose={() => setModalOpen(false)}
            onSave={handleSave}
            saving={saving}
          />
        )}
      </div>
    </ErrorBoundary>
  );
}
