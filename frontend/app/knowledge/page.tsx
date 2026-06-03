"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  BookOpen, Upload, Trash2, Search, RefreshCw, FileText,
  Sparkles, ChevronRight,
} from "lucide-react";
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

interface SearchResult {
  id?: string;
  content?: string;
  text?: string;
  metadata?: Record<string, string>;
  score?: number;
  distance?: number;
}

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
    complete:   "bg-emerald-500/20 text-emerald-400",
    indexed:    "bg-emerald-500/20 text-emerald-400",
    error:      "bg-red-500/20 text-red-400",
  };
  return `px-2 py-0.5 rounded text-xs font-medium ${map[status] ?? "bg-slate-700 text-slate-400"}`;
}

export default function KnowledgeBasePage() {
  const [tab, setTab] = useState<"docs" | "search">("docs");

  // --- Documents tab ---
  const [docs, setDocs] = useState<KBDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterText, setFilterText] = useState("");
  const [category, setCategory] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [pollingId, setPollingId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadCategory, setUploadCategory] = useState("General");

  // --- Search tab ---
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [searchDone, setSearchDone] = useState(false);

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ limit: "50" });
    if (category) params.set("category", category);
    try {
      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), 10000);
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
      setError(e instanceof Error ? e.message : "Failed to load documents");
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
      setUploadMsg(`Uploaded: "${data.title}" — embedding in progress…`);
      setUploadTitle("");
      if (fileRef.current) fileRef.current.value = "";
      fetchDocs();
      // Start polling embedding status
      if (data.id) pollEmbedding(data.id);
    } catch (e: unknown) {
      setUploadMsg(e instanceof Error ? `Error: ${e.message}` : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function pollEmbedding(docId: string) {
    setPollingId(docId);
    const startMs = Date.now();
    const maxMs   = 120_000; // 2 min timeout

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/v1/knowledge/${docId}`, { headers: authHeaders() });
        if (!res.ok) { clearInterval(interval); setPollingId(null); return; }
        const doc: KBDocument = await res.json();

        // Refresh the list so the badge updates live
        fetchDocs();

        if (doc.embedding_status === "complete" || doc.embedding_status === "indexed") {
          setUploadMsg(`Embedding complete for "${doc.title}" — ready for search.`);
          clearInterval(interval);
          setPollingId(null);
        } else if (doc.embedding_status === "error") {
          setUploadMsg(`Embedding failed for "${doc.title}". Please re-upload.`);
          clearInterval(interval);
          setPollingId(null);
        } else if (Date.now() - startMs > maxMs) {
          setUploadMsg("Embedding is taking longer than expected — check back later.");
          clearInterval(interval);
          setPollingId(null);
        }
      } catch {
        clearInterval(interval);
        setPollingId(null);
      }
    }, 3_000);
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this document?")) return;
    await fetch(`${API}/api/v1/knowledge/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    fetchDocs();
  }

  async function handleSearch(e?: React.FormEvent) {
    e?.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchError("");
    setSearchResults([]);
    setSearchDone(false);
    try {
      const params = new URLSearchParams({ q: searchQuery.trim(), top_k: "8" });
      const res = await fetch(`${API}/api/v1/knowledge/search?${params}`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const data = await res.json();
      setSearchResults(data.results ?? []);
      setSearchDone(true);
    } catch (e: unknown) {
      setSearchError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  const filtered = docs.filter(
    (d) =>
      !filterText ||
      d.title.toLowerCase().includes(filterText.toLowerCase()) ||
      (d.file_name ?? "").toLowerCase().includes(filterText.toLowerCase())
  );

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-6xl mx-auto text-slate-100">

        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <BookOpen className="h-7 w-7 text-violet-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Knowledge Base</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              {total} document{total !== 1 ? "s" : ""} — agents use these during conversations
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-slate-700">
          {(["docs", "search"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
                tab === t
                  ? "border-violet-500 text-violet-300"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              {t === "docs" ? (
                <span className="flex items-center gap-1.5"><FileText className="h-3.5 w-3.5" /> Documents</span>
              ) : (
                <span className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" /> Semantic Search</span>
              )}
            </button>
          ))}
        </div>

        {/* ── DOCUMENTS TAB ─────────────────────────────────────────── */}
        {tab === "docs" && (
          <>
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
                    {["General","HR","Sales","Finance","IT","Marketing","Support"].map((c) => (
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
                  disabled={uploading || !!pollingId}
                  className="px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-50 transition-colors"
                >
                  {uploading ? "Uploading…" : pollingId ? "Embedding…" : "Upload"}
                </button>
              </div>
              {uploadMsg && (
                <p className={`mt-2 text-sm flex items-center gap-2 ${uploadMsg.startsWith("Error") || uploadMsg.startsWith("Embedding failed") ? "text-red-400" : uploadMsg.includes("complete") ? "text-emerald-400" : "text-violet-300"}`}>
                  {pollingId && <RefreshCw className="h-3.5 w-3.5 animate-spin flex-shrink-0" />}
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
                  placeholder="Filter by name…"
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  className="pl-9 pr-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500 w-52"
                />
              </div>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-sm text-slate-200"
              >
                <option value="">All categories</option>
                {["HR","Sales","Finance","IT","Marketing","Support","General"].map((c) => (
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
          </>
        )}

        {/* ── SEMANTIC SEARCH TAB ───────────────────────────────────── */}
        {tab === "search" && (
          <div>
            <div className="mb-5 rounded-xl border border-blue-500/30 bg-blue-500/5 p-5">
              <p className="text-sm text-blue-300 mb-3">
                Ask a question or enter a topic — the AI will find the most relevant passages from your documents.
              </p>
              <form onSubmit={handleSearch} className="flex gap-3">
                <div className="relative flex-1">
                  <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-blue-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="e.g. What is our refund policy?"
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-600 bg-slate-800 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <button
                  type="submit"
                  disabled={searching || !searchQuery.trim()}
                  className="px-5 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2"
                >
                  {searching ? (
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  {searching ? "Searching…" : "Search"}
                </button>
              </form>
            </div>

            {searchError && (
              <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{searchError}</div>
            )}

            {searchDone && searchResults.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-slate-500">
                <Search className="h-12 w-12 mb-3 opacity-30" />
                <p className="font-medium text-slate-400">No matching results</p>
                <p className="text-sm mt-1">Try uploading more documents or rephrasing your query</p>
              </div>
            )}

            {searchResults.length > 0 && (
              <div className="space-y-4">
                <p className="text-xs text-slate-500">{searchResults.length} result{searchResults.length !== 1 ? "s" : ""} for &quot;{searchQuery}&quot;</p>
                {searchResults.map((r, i) => {
                  const text = r.content ?? r.text ?? "";
                  const title = r.metadata?.title ?? r.metadata?.file_name ?? `Result ${i + 1}`;
                  const score = r.score ?? (r.distance != null ? (1 - r.distance) : null);
                  return (
                    <div key={i} className="rounded-xl border border-slate-700 bg-slate-800 p-4 hover:border-blue-500/40 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <ChevronRight className="h-4 w-4 text-blue-400" />
                          <span className="text-sm font-medium text-slate-200">{title}</span>
                          {r.metadata?.category && (
                            <span className="px-2 py-0.5 rounded bg-slate-700 text-slate-400 text-xs">{r.metadata.category}</span>
                          )}
                        </div>
                        {score != null && (
                          <span className="text-xs text-slate-500">
                            {(score * 100).toFixed(0)}% match
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-400 leading-relaxed line-clamp-5">{text}</p>
                    </div>
                  );
                })}
              </div>
            )}

            {!searchDone && !searching && (
              <div className="flex flex-col items-center justify-center py-16 text-slate-500">
                <Sparkles className="h-12 w-12 mb-3 opacity-30" />
                <p className="text-sm">Enter a question above to search your documents</p>
              </div>
            )}
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
