"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Rocket, Building2, PackagePlus, MessageSquareText, CheckCircle2,
  ArrowRight, ArrowLeft, SkipForward, Trash2, Sparkles, PartyPopper,
} from "lucide-react";
import { getToken, apiFetch } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const STEPS = [
  { key: "company", label: "Company Info", icon: Building2 },
  { key: "products", label: "Products & Services", icon: PackagePlus },
  { key: "scripts", label: "Call Scripts", icon: MessageSquareText },
  { key: "review", label: "Review & Finish", icon: CheckCircle2 },
];

interface QuickProduct {
  name: string;
  description: string;
  price: string;
}

export default function OnboardingWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Step 1: Company info
  const [companyName, setCompanyName] = useState("");
  const [tagline, setTagline] = useState("");
  const [website, setWebsite] = useState("");

  // Step 2: Quick products
  const [products, setProducts] = useState<QuickProduct[]>([]);
  const [pName, setPName] = useState("");
  const [pDesc, setPDesc] = useState("");
  const [pPrice, setPPrice] = useState("");
  const [productsSaved, setProductsSaved] = useState(0);

  // Step 3: Reception call script (the department that answers first)
  const [greeting, setGreeting] = useState("");
  const [closing, setClosing] = useState("");
  const [transferMsg, setTransferMsg] = useState("");
  // Full agent_overrides object as last loaded from the server, so saving the
  // reception script doesn't wipe out any other department's scripts that
  // were configured separately (e.g. from Settings).
  const [existingOverrides, setExistingOverrides] = useState<Record<string, unknown>>({});

  const loadExisting = useCallback(async () => {
    try {
      const res = await apiFetch(`${API}/api/v1/settings/company`, { headers: authHeaders() });
      if (!res.ok) return;
      const d = await res.json();
      setCompanyName(d.company_name || "");
      setTagline(d.company_tagline || "");
      setWebsite(d.company_website || "");
      setExistingOverrides(d.agent_overrides || {});
      const rec = d.agent_overrides?.reception;
      if (rec) {
        setGreeting(rec.greeting || "");
        setClosing(rec.closing || "");
        setTransferMsg(rec.transfer_message || "");
      }
    } catch {}
  }, []);

  useEffect(() => { loadExisting(); }, [loadExisting]);

  const goNext = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const goBack = () => setStep((s) => Math.max(s - 1, 0));

  // Persists whatever is currently typed for the Company Info step.
  // Returns true on success so callers (Next / Skip) can decide what to do.
  async function persistCompanyInfo(): Promise<boolean> {
    if (!companyName.trim() && !tagline.trim() && !website.trim()) return true; // nothing to save
    const res = await apiFetch(`${API}/api/v1/settings/company`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ company_name: companyName, company_tagline: tagline, company_website: website }),
    });
    return res.ok;
  }

  async function saveCompanyInfo() {
    setSaving(true); setError("");
    try {
      const ok = await persistCompanyInfo();
      if (!ok) throw new Error("Failed to save");
      goNext();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save company info");
    } finally {
      setSaving(false);
    }
  }

  function addProductToList() {
    if (!pName.trim()) return;
    setProducts((prev) => [...prev, { name: pName.trim(), description: pDesc.trim(), price: pPrice.trim() }]);
    setPName(""); setPDesc(""); setPPrice("");
  }

  function removeProduct(i: number) {
    setProducts((prev) => prev.filter((_, idx) => idx !== i));
  }

  // Persists any products currently in the list (including one still typed
  // into the add-product fields but not yet clicked "Add" -- so Skip never
  // silently drops a product the user was in the middle of entering).
  async function persistProducts(): Promise<boolean> {
    const pending = [...products];
    if (pName.trim()) {
      pending.push({ name: pName.trim(), description: pDesc.trim(), price: pPrice.trim() });
    }
    if (pending.length === 0) return true; // nothing to save
    let saved = 0;
    let ok = true;
    for (const p of pending) {
      const res = await apiFetch(`${API}/api/v1/products`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ name: p.name, description: p.description, price: p.price || null, category: "General", is_active: true }),
      });
      if (res.ok) saved += 1; else ok = false;
    }
    setProductsSaved(saved);
    return ok;
  }

  async function saveProductsAndNext() {
    setSaving(true); setError("");
    try {
      const ok = await persistProducts();
      if (!ok) throw new Error("Some products failed to save");
      goNext();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save products");
    } finally {
      setSaving(false);
    }
  }

  // Persists the reception script fields, merged into whatever other
  // departments' overrides already existed -- never replaces the whole
  // agent_overrides object, so other departments' scripts survive.
  async function persistScripts(): Promise<boolean> {
    if (!greeting.trim() && !closing.trim() && !transferMsg.trim()) return true; // nothing to save
    const merged = {
      ...existingOverrides,
      reception: { display_name: "", greeting, closing, transfer_message: transferMsg, script: "" },
    };
    const res = await apiFetch(`${API}/api/v1/settings/company`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        company_name: companyName, company_tagline: tagline, company_website: website,
        agent_overrides: merged,
      }),
    });
    if (res.ok) setExistingOverrides(merged);
    return res.ok;
  }

  async function saveScriptsAndNext() {
    setSaving(true); setError("");
    try {
      const ok = await persistScripts();
      if (!ok) throw new Error("Failed to save");
      goNext();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save call scripts");
    } finally {
      setSaving(false);
    }
  }

  async function finishOnboarding() {
    setSaving(true); setError("");
    try {
      const res = await apiFetch(`${API}/api/v1/settings/onboarding/complete`, {
        method: "POST", headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      router.push("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to complete onboarding");
    } finally {
      setSaving(false);
    }
  }

  async function skipStep() {
    if (step === STEPS.length - 1) { finishOnboarding(); return; }
    setSaving(true); setError("");
    try {
      if (step === 0) await persistCompanyInfo();
      else if (step === 1) await persistProducts();
      else if (step === 2) await persistScripts();
      // Best-effort: even if a persist call fails, still let the user move on
      // rather than trapping them on this step -- but the current values
      // remain in local state so they can retry via "Next" later.
    } finally {
      setSaving(false);
      goNext();
    }
  }

  const inputCls = "w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:border-amber-500/50 focus:outline-none";
  const fill = (s: string) => s
    .replaceAll("{company_name}", companyName || "your company")
    .replaceAll("{agent_name}", "our assistant");

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 flex items-start justify-center p-6">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/20">
            <Rocket className="h-5 w-5 text-amber-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Welcome — let&apos;s set up your AI Workforce</h1>
            <p className="text-xs text-slate-500">Four quick steps. You can skip any step and finish it later from Settings.</p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mb-8 flex items-center gap-1">
          {STEPS.map((s, i) => (
            <div key={s.key} className="flex flex-1 items-center gap-1">
              <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                i < step ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                : i === step ? "border-amber-500/50 bg-amber-500/10 text-amber-400"
                : "border-[#1f2937] text-slate-600"
              }`}>
                {i < step ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div className={`h-0.5 flex-1 ${i < step ? "bg-emerald-500/40" : "bg-[#1f2937]"}`} />
              )}
            </div>
          ))}
        </div>
        <p className="mb-4 text-center text-xs font-semibold text-slate-400">{STEPS[step].label}</p>

        {error && (
          <div className="mb-4 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-400">{error}</div>
        )}

        <div className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-6">
          {/* STEP 1: Company Info */}
          {step === 0 && (
            <div className="space-y-4">
              <p className="text-xs text-slate-500">
                This appears in greetings, chat headers, and voice call intros — e.g.
                &quot;Thank you for calling {companyName || "[Your Company]"}, how can I help?&quot;
              </p>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">Company Name</label>
                <input value={companyName} onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="e.g. AI Algo" className={inputCls} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">Tagline (optional)</label>
                <input value={tagline} onChange={(e) => setTagline(e.target.value)}
                  placeholder="e.g. Your AI-Powered Enterprise Workforce" className={inputCls} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">Website (optional)</label>
                <input value={website} onChange={(e) => setWebsite(e.target.value)}
                  placeholder="https://example.com" className={inputCls} />
              </div>
            </div>
          )}

          {/* STEP 2: Products */}
          {step === 1 && (
            <div className="space-y-4">
              <p className="text-xs text-slate-500">
                Add a few of your key products or services so agents can answer questions about what you actually
                offer — no documents to write. You can add more anytime from <strong className="text-slate-400">Products &amp; Services</strong>.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 items-end rounded-xl border border-[#1f2937] bg-[#070d1a] p-3">
                <div className="sm:col-span-1">
                  <label className="mb-1 block text-[11px] text-slate-500">Name</label>
                  <input value={pName} onChange={(e) => setPName(e.target.value)} placeholder="e.g. Website Design"
                    className={inputCls} />
                </div>
                <div className="sm:col-span-1">
                  <label className="mb-1 block text-[11px] text-slate-500">Short description</label>
                  <input value={pDesc} onChange={(e) => setPDesc(e.target.value)} placeholder="What it includes"
                    className={inputCls} />
                </div>
                <div className="flex gap-2">
                  <input value={pPrice} onChange={(e) => setPPrice(e.target.value)} placeholder="Price (optional)"
                    className={inputCls} />
                  <button onClick={addProductToList} disabled={!pName.trim()}
                    className="flex-shrink-0 rounded-lg bg-amber-500 px-3 py-2 text-xs font-semibold text-black hover:bg-amber-400 disabled:opacity-40">
                    Add
                  </button>
                </div>
              </div>
              {products.length > 0 && (
                <div className="space-y-2">
                  {products.map((p, i) => (
                    <div key={i} className="flex items-center justify-between rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2">
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-slate-300 truncate">{p.name}{p.price ? ` — ${p.price}` : ""}</p>
                        {p.description && <p className="text-[11px] text-slate-500 truncate">{p.description}</p>}
                      </div>
                      <button onClick={() => removeProduct(i)} className="text-slate-600 hover:text-red-400 flex-shrink-0">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {products.length === 0 && (
                <p className="text-[11px] text-slate-600 italic">No products added yet — that&apos;s OK, you can skip this step.</p>
              )}
            </div>
          )}

          {/* STEP 3: Call scripts */}
          {step === 2 && (
            <div className="space-y-4">
              <p className="text-xs text-slate-500">
                Set how your Reception desk answers the phone. Use <code className="text-slate-400">{"{company_name}"}</code> as
                a placeholder — it&apos;s replaced automatically.
              </p>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">Greeting</label>
                <textarea value={greeting} onChange={(e) => setGreeting(e.target.value)}
                  placeholder="e.g. Thank you for calling {company_name}, how can I assist you today?"
                  className={`${inputCls} min-h-[70px] resize-y`} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">Closing line</label>
                <textarea value={closing} onChange={(e) => setClosing(e.target.value)}
                  placeholder="e.g. Thanks for calling {company_name}, have a great day!"
                  className={`${inputCls} min-h-[60px] resize-y`} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">Transfer message</label>
                <textarea value={transferMsg} onChange={(e) => setTransferMsg(e.target.value)}
                  placeholder="e.g. Sure, I'm transferring you now — please hold for a moment."
                  className={`${inputCls} min-h-[60px] resize-y`} />
              </div>
              {(greeting || closing || transferMsg) && (
                <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-[11px] text-slate-400 space-y-1">
                  <p className="font-semibold text-amber-400 flex items-center gap-1"><Sparkles className="h-3 w-3" /> Preview</p>
                  {greeting && <p>&quot;{fill(greeting)}&quot;</p>}
                  {transferMsg && <p className="italic">&quot;{fill(transferMsg)}&quot;</p>}
                  {closing && <p>&quot;{fill(closing)}&quot;</p>}
                </div>
              )}
            </div>
          )}

          {/* STEP 4: Review */}
          {step === 3 && (
            <div className="space-y-4 text-center py-4">
              <PartyPopper className="h-10 w-10 text-amber-400 mx-auto" />
              <h2 className="text-base font-semibold text-white">You&apos;re almost set up!</h2>
              <div className="text-left rounded-xl border border-[#1f2937] bg-[#070d1a] p-4 space-y-2 text-xs text-slate-400">
                <p><span className="text-slate-500">Company:</span> {companyName || "(not set)"}</p>
                <p><span className="text-slate-500">Products added this session:</span> {productsSaved}</p>
                <p><span className="text-slate-500">Reception greeting:</span> {greeting ? "configured" : "using default"}</p>
                <p><span className="text-slate-500">Transfer message:</span> {transferMsg ? "configured" : "using default"}</p>
              </div>
              <p className="text-[11px] text-slate-500">
                You can revisit and refine any of this anytime from Settings, Products &amp; Services, or Call Scripts.
              </p>
            </div>
          )}
        </div>

        {/* Nav buttons */}
        <div className="mt-5 flex items-center justify-between">
          <button onClick={goBack} disabled={step === 0}
            className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-4 py-2 text-xs text-slate-400 hover:text-slate-200 disabled:opacity-30">
            <ArrowLeft className="h-3.5 w-3.5" /> Back
          </button>
          <div className="flex items-center gap-2">
            <button onClick={skipStep} className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs text-slate-500 hover:text-slate-300">
              <SkipForward className="h-3.5 w-3.5" /> {step === STEPS.length - 1 ? "Skip & finish later" : "Skip for now"}
            </button>
            {step === 0 && (
              <button onClick={saveCompanyInfo} disabled={saving}
                className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-semibold text-black hover:bg-amber-400 disabled:opacity-50">
                {saving ? "Saving…" : "Next"} <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
            {step === 1 && (
              <button onClick={saveProductsAndNext} disabled={saving}
                className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-semibold text-black hover:bg-amber-400 disabled:opacity-50">
                {saving ? "Saving…" : "Next"} <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
            {step === 2 && (
              <button onClick={saveScriptsAndNext} disabled={saving}
                className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-semibold text-black hover:bg-amber-400 disabled:opacity-50">
                {saving ? "Saving…" : "Next"} <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
            {step === 3 && (
              <button onClick={finishOnboarding} disabled={saving}
                className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-5 py-2 text-xs font-semibold text-black hover:bg-emerald-400 disabled:opacity-50">
                <CheckCircle2 className="h-3.5 w-3.5" /> {saving ? "Finishing…" : "Finish Setup"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
