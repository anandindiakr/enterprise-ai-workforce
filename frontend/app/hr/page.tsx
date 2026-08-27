"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Briefcase,
  RefreshCw,
  ScrollText,
  Trash2,
  UserPlus,
  X,
} from "lucide-react";
import { authHeaders } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

interface Applicant {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  position: string;
  status: string;
  score: number | null;
  skills: string[];
  notes: string;
  created_at: string;
}

const STAGES = ["applied", "screening", "interview", "offer", "hired", "rejected"] as const;

const STAGE_STYLES: Record<string, string> = {
  applied: "text-slate-400 bg-slate-500/10 border-slate-500/20",
  screening: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  interview: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  offer: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  hired: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  rejected: "text-rose-400 bg-rose-500/10 border-rose-500/20",
};

export default function HrPage() {
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [pipeline, setPipeline] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [showResume, setShowResume] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "", email: "", phone: "", position: "", notes: "",
  });
  const [resumeText, setResumeText] = useState("");
  const [resumePosition, setResumePosition] = useState("");
  const [resumeJd, setResumeJd] = useState("");
  const [busy, setBusy] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/v1/hr/applicants?limit=300`, { headers: authHeaders() });
      if (r.ok) {
        const d = await r.json();
        setApplicants(d.applicants ?? []);
        setPipeline(d.pipeline ?? {});
      }
    } catch { /* network */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const addApplicant = async () => {
    if (!form.name.trim()) { setNotice("Name is required."); return; }
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/v1/hr/applicants`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...form }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setNotice(d.detail ?? "Save failed");
      } else {
        setShowAdd(false);
        setForm({ name: "", email: "", phone: "", position: "", notes: "" });
        setNotice("Applicant added.");
        fetchAll();
      }
    } catch { setNotice("Network error"); }
    setBusy(false);
  };

  const ingestResume = async () => {
    if (resumeText.trim().length < 40) { setNotice("Paste the resume text (at least a few lines)."); return; }
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/v1/hr/applicants/ingest`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_text: resumeText,
          position: resumePosition,
          job_description: resumeJd || null,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setNotice(d.detail ?? "Ingestion failed");
      } else {
        const d = await r.json();
        const a = d.applicant as Applicant;
        setNotice(
          d.extraction === "llm"
            ? `Resume processed: ${a.name}${a.score != null ? ` — fit score ${a.score}/100` : ""}.`
            : "Resume saved for manual review (AI extraction unavailable on this server)."
        );
        setShowResume(false);
        setResumeText(""); setResumePosition(""); setResumeJd("");
        fetchAll();
      }
    } catch { setNotice("Network error"); }
    setBusy(false);
  };

  const setStatus = async (id: string, status: string) => {
    await fetch(`${API}/api/v1/hr/applicants/${id}`, {
      method: "PATCH",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    fetchAll();
  };

  const removeApplicant = async (id: string) => {
    if (!confirm("Remove this applicant?")) return;
    await fetch(`${API}/api/v1/hr/applicants/${id}`, { method: "DELETE", headers: authHeaders() });
    fetchAll();
  };

  return (
    <div className="min-h-screen bg-[#030712] text-slate-300">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1f2937] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-violet-500/20 bg-violet-500/10">
            <UserPlus className="h-4 w-4 text-violet-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-200">HR — Applicant Tracker</h1>
            <p className="text-[11px] text-slate-500">{applicants.length} candidates · recruitment pipeline</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={fetchAll} className="rounded-xl border border-[#1f2937] p-2 text-slate-500 transition-all hover:text-slate-300">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button onClick={() => setShowResume(true)}
            className="flex items-center gap-1.5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-400 transition-all hover:bg-emerald-500/20">
            <ScrollText className="h-3.5 w-3.5" /> Paste Resume
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 rounded-xl border border-violet-500/30 bg-violet-500/20 px-3 py-2 text-xs font-medium text-violet-400 transition-all hover:bg-violet-500/30">
            <UserPlus className="h-3.5 w-3.5" /> Add Applicant
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
        {/* Pipeline chips */}
        <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
          {STAGES.map((s) => (
            <div key={s} className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-3 text-center">
              <p className="text-[10px] uppercase tracking-wider text-slate-600">{s}</p>
              <p className={`mt-1 text-xl font-bold ${STAGE_STYLES[s].split(" ")[0]}`}>{pipeline[s] ?? 0}</p>
            </div>
          ))}
        </div>

        {/* Applicants table */}
        <div className="overflow-hidden rounded-2xl border border-[#1f2937] bg-[#0c111d]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-xs">
              <thead className="border-b border-[#1f2937] text-[10px] uppercase tracking-wider text-slate-600">
                <tr>
                  <th className="px-4 py-3">Candidate</th>
                  <th className="px-4 py-3">Position</th>
                  <th className="px-4 py-3">Contact</th>
                  <th className="px-4 py-3">Skills</th>
                  <th className="px-4 py-3 text-center">Fit</th>
                  <th className="px-4 py-3">Stage</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-600">Loading…</td></tr>
                ) : applicants.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-600">
                    No applicants yet — paste a resume or add a candidate manually.
                  </td></tr>
                ) : applicants.map((a) => (
                  <tr key={a.id} className="border-b border-[#141c2e] last:border-0 hover:bg-[#0f1626]">
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-slate-200">{a.name}</p>
                      {a.notes && <p className="mt-0.5 max-w-[220px] truncate text-[10px] text-slate-600" title={a.notes}>{a.notes}</p>}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400">
                      <span className="flex items-center gap-1"><Briefcase className="h-3 w-3 text-slate-600" />{a.position || "—"}</span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">
                      {a.email && <p className="max-w-[180px] truncate" title={a.email}>{a.email}</p>}
                      {a.phone && <p>{a.phone}</p>}
                      {!a.email && !a.phone && "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex max-w-[220px] flex-wrap gap-1">
                        {a.skills.slice(0, 4).map((s) => (
                          <span key={s} className="rounded-md border border-[#1f2937] bg-[#070d1a] px-1.5 py-0.5 text-[10px] text-slate-400">{s}</span>
                        ))}
                        {a.skills.length > 4 && <span className="text-[10px] text-slate-600">+{a.skills.length - 4}</span>}
                        {a.skills.length === 0 && <span className="text-slate-600">—</span>}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {a.score != null ? (
                        <span className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                          a.score >= 70 ? "bg-emerald-500/10 text-emerald-400"
                          : a.score >= 40 ? "bg-amber-500/10 text-amber-400"
                          : "bg-rose-500/10 text-rose-400"}`}>
                          {a.score}
                        </span>
                      ) : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      <select value={a.status} onChange={(e) => setStatus(a.id, e.target.value)}
                        className={`rounded-md border bg-[#070d1a] px-1.5 py-1 text-[10px] capitalize ${STAGE_STYLES[a.status] ?? ""}`}>
                        {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                    <td className="px-4 py-2.5">
                      <button onClick={() => removeApplicant(a.id)} className="text-slate-600 transition-colors hover:text-red-400">
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

      {/* Add-applicant modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-[#1f2937] bg-[#0c111d] p-6 shadow-2xl">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200">New Applicant</h2>
              <button onClick={() => setShowAdd(false)}><X className="h-4 w-4 text-slate-500" /></button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <label className="col-span-2">
                <span className="mb-1 block text-slate-500">Full name *</span>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-1">
                <span className="mb-1 block text-slate-500">Position</span>
                <input value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })}
                  placeholder="Sales Executive"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-1">
                <span className="mb-1 block text-slate-500">Email</span>
                <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-1">
                <span className="mb-1 block text-slate-500">Phone</span>
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-2">
                <span className="mb-1 block text-slate-500">Notes</span>
                <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  rows={2}
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
            </div>
            <button onClick={addApplicant} disabled={busy}
              className="mt-5 w-full rounded-xl bg-violet-500 py-2.5 text-xs font-semibold text-black transition-colors hover:bg-violet-400 disabled:opacity-50">
              {busy ? "Saving…" : "Add Applicant"}
            </button>
          </div>
        </div>
      )}

      {/* Paste-resume modal */}
      {showResume && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-2xl border border-[#1f2937] bg-[#0c111d] p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200">Paste Resume Text</h2>
              <button onClick={() => setShowResume(false)}><X className="h-4 w-4 text-slate-500" /></button>
            </div>
            <p className="mb-3 text-[11px] leading-relaxed text-slate-500">
              The AI extracts the candidate&apos;s name, contact and skills — and with a
              job description pasted below, it also scores the fit (0-100) and moves
              strong candidates straight to screening.
            </p>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <label className="col-span-2">
                <span className="mb-1 block text-slate-500">Applying for position</span>
                <input value={resumePosition} onChange={(e) => setResumePosition(e.target.value)}
                  placeholder="Sales Executive"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-2">
                <span className="mb-1 block text-slate-500">Resume text *</span>
                <textarea value={resumeText} onChange={(e) => setResumeText(e.target.value)}
                  rows={7} placeholder="Paste the resume content here…"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
              <label className="col-span-2">
                <span className="mb-1 block text-slate-500">Job description (optional — enables fit score)</span>
                <textarea value={resumeJd} onChange={(e) => setResumeJd(e.target.value)}
                  rows={3} placeholder="Responsibilities, must-have skills, experience…"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2 text-slate-200" />
              </label>
            </div>
            <button onClick={ingestResume} disabled={busy}
              className="mt-4 w-full rounded-xl bg-emerald-500 py-2.5 text-xs font-semibold text-black transition-colors hover:bg-emerald-400 disabled:opacity-50">
              {busy ? "Processing…" : "Process Resume"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
