"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { BookOpen, Upload, Trash2, Search, RefreshCw, FileText } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { getToken } from "@/lib/auth";

interface KBDocument {
  id: string;
  title: string;
  category: string | null;
  file_name: string | null;
  file_size: number;
  embedding_status: string;
  created_at: string;
}

// Always use the env var — default to port 8080 (not 8000)
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    pending:    "bg-yellow-500/20 text-yellow-400",
    processing: "bg-blue-500/20 text-blue-400",
    indexed:    "bg-emerald-500/20 text-emerald-400",
    error:      "bg-red-500/20 text-red-400",
  };
  return `px-2 py-0.5 rounded text-xs font-medium ${map[status] ?? "bg-slate-700 text-slate-400"}`;
}

export default function KnowledgeBasePage() {
  const [docs, setDocs] = useState<KBDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadCategory, setUploadCategory] = useState("General");

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ limit: "50" });
    if (category) params.set("category", category);
    try {
      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), 10000); // 10 s timeout
      const res = await fetch(`${API}/api/v1/knowledge?${params}`, {
        headers: authHeaders(),
        signal: controller.signal,
      });
      clearTimeout(tid);
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const data = await res.json();
      setDocs(data.documents ?? []);
      setTotal(data.total ?? 0);
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") {
        setError("Request timed out — is the API running on port 8080?");
      } else {
        setError(e instanceof Error ? e.message : "Failed to load documents");
      }
      setDocs([]);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg("");
    const form = new FormData();
    form.append("file", file);
    form.append("title", uploadTitle || file.name);
    form.append("category", uploadCategory);
    try {
      const res = await fetch(`${API}/api/v1/knowledge/upload`, {
        method: "POST",
        headers: authHeaders(),
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      setUploadMsg(`Uploaded: ${data.title}`);
      setUploadTitle("");
      if (fileRef.current) fileRef.current.value = "";
      fetchDocs();
    } catch (e: unknown) {
      setUploadMsg(e instanceof Error ? `Error: ${e.message}` : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this document?")) return;
    await fetch(`${API}/api/v1/knowledge/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    fetchDocs();
  }

  const filtered = docs.filter(
    (d) =>
      !search ||
      d.title.toLowerCase().includes(search.toLowerCase()) ||
      (d.file_name ?? "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-6xl mx-auto text-slate-100">
        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <BookOpen className="h-7 w-7 text-violet-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Knowledge Base</h1>
            <p className="text-sm text-slate-400 mt-0.5">{total} document{total !== 1 ? "s" : ""} — agents use these during conversations</p>
          </div>
        </div>

        {/* Upload card */}
        <div className="mb-6 rounded-xl border border-violet-500/30 bg-violet-500/5 p-5">
          <h2 className="text-sm font-semibold text-violet-300 mb-3 flex items-center gap-2">
            <Upload className="h-4 w-4" /> Upload Document
          </h2>
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">Title (optional)</label>
              <input
                type="text"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                placeholder="e.g. Sales Playbook Q3"
                className="px-3 py-1.5 rounded-lg border border-slate-600 bg-slate-800 text-sm text-slate-200 w-48 focus:outline-none focus:ring-2 focus:ring-violet-500"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">Category</label>
              <select
                value={uploadCategory}
                onChange={(e) => setUploadCategory(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-slate-600 bg-slate-800 text-sm text-slate-200"
              >
                {["General", "HR", "Sales", "Finance", "IT", "Marketing", "Support"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">File (.txt .md .pdf .docx .csv .json)</label>
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.md,.pdf,.docx,.csv,.json"
                className="text-sm text-slate-300 file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-violet-600 file:text-white file:text-xs file:cursor-pointer"
              />
            </div>
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-50 transition-colors"
            >
              {uploading ? "Uploading…" : "Upload"}
            </button>
          </div>
          {uploadMsg && (
            <p className={`mt-2 text-sm ${uploadMsg.startsWith("Error") ? "text-red-400" : "text-emerald-400"}`}>
              {uploadMsg}
            </p>
          )}
        </div>

        {/* Filter bar */}
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search documents…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500 w-52"
            />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-sm text-slate-200"
          >
            <option value="">All categories</option>
            {["HR", "Sales", "Finance", "IT", "Marketing", "Support", "General"].map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <button
            onClick={fetchDocs}
            className="p-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-400 hover:bg-slate-700 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>
        )}

        {/* Document grid */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-slate-700 bg-slate-800 p-4 animate-pulse">
                <div className="h-5 bg-slate-700 rounded w-3/4 mb-2" />
                <div className="h-3 bg-slate-700 rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-500">
            <BookOpen className="h-12 w-12 mb-3 opacity-30" />
            <p className="font-medium text-slate-400">No documents yet</p>
            <p className="text-sm mt-1">Upload your first document above</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((doc) => (
              <div
                key={doc.id}
                className="rounded-xl border border-slate-700 bg-slate-800 p-4 hover:border-violet-500/50 transition-colors group"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-5 w-5 text-violet-400 flex-shrink-0" />
                    <h3 className="font-medium text-slate-100 text-sm truncate">{doc.title}</h3>
                  </div>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-all flex-shrink-0"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  {doc.category && (
                    <span className="px-2 py-0.5 rounded bg-slate-700 text-slate-300">{doc.category}</span>
                  )}
                  <span className={statusBadge(doc.embedding_status)}>{doc.embedding_status}</span>
                  {doc.file_size > 0 && <span>{formatBytes(doc.file_size)}</span>}
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  {new Date(doc.created_at).toLocaleDateString()}
                  {doc.file_name && ` · ${doc.file_name}`}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
