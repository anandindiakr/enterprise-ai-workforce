"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  BookOpen, Upload, Trash2, Search, RefreshCw, FileText,
  Sparkles, ChevronRight, CheckCircle, AlertTriangle, Clock,
  Zap, RotateCcw, Info, Database, Star,
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

interface KBStats {
  total: number;
  indexed: number;
  complete: number;
  pending: number;
  failed: number;
  vector_count: number;
  chroma_available: boolean;
  agents_have_access: boolean;
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

// Status badge — "indexed" and "complete" are both green/working
function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { cls: string; icon: React.ElementType; label: string; tip: string }> = {
    complete: {
      cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
      icon: Star,
      label: "Vector + DB",
      tip: "Semantic + keyword search active. Best quality responses.",
    },
    indexed: {
      cls: "border-blue-500/30 bg-blue-500/10 text-blue-400",
      icon: CheckCircle,
      label: "Active",
      tip: "Content saved. Agents can use this document immediately via keyword search.",
    },
    pending: {
      cls: "border-amber-500/30 bg-amber-500/10 text-amber-400",
      icon: Clock,
      label: "Indexing…",
      tip: "Being processed. Agents can use it once indexing completes.",
    },
    processing: {
      cls: "border-blue-500/30 bg-blue-500/10 text-blue-400",
      icon: RefreshCw,
      label: "Processing",
      tip: "Embedding in progress.",
    },
    failed: {
      cls: "border-red-500/30 bg-red-500/10 text-red-400",
      icon: AlertTriangle,
      label: "Vector failed",
      tip: "Vector indexing failed but agents can still use keyword search. Click Reindex All to retry.",
    },
  };
  const c = cfg[status] ?? {
    cls: "border-slate-700 bg-slate-800 text-slate-400",
    icon: Info,
    label: status,
    tip: "",
  };
  const Icon = c.icon;
  return (
    <span title={c.tip} className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold cursor-help ${c.cls}`}>
      <Icon className="h-2.5 w-2.5" />
      {c.label}
    </span>
  );
}

// KB health banner
function HealthBanner({ stats, onReindex, reindexing }: {
  stats: KBStats;
  onReindex: () => void;
  reindexing: boolean;
}) {
  const hasFailed = stats.failed > 0;
  const allGood = stats.agents_have_access && !hasFailed;

  return (
    <div className={`rounded-2xl border p-4 mb-5 ${
      allGood
        ? "border-emerald-500/20 bg-emerald-500/5"
        : hasFailed
          ? "border-amber-500/20 bg-amber-500/5"
          : "border-slate-700 bg-[#0c111d]"
    }`}>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${
            allGood ? "bg-emerald-500/10" : "bg-amber-500/10"
          }`}>
            <Database className={`h-4 w-4 ${allGood ? "text-emerald-400" : "text-amber-400"}`} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-200">
              {stats.agents_have_access
                ? `${stats.indexed} document${stats.indexed !== 1 ? "s" : ""} active — agents can use your content`
                : "No documents yet — upload files to give agents knowledge"}
            </p>
            <div className="flex items-center gap-3 mt-0.5 text-[11px] text-slate-500">
              <span className="flex items-center gap-1">
                <Star className="h-2.5 w-2.5 text-emerald-400" />
                {stats.complete} vector indexed
              </span>
              <span className="flex items-center gap-1">
                <CheckCircle className="h-2.5 w-2.5 text-blue-400" />
                {stats.indexed - stats.complete} keyword only
              </span>
              {stats.failed > 0 && (
                <span className="flex items-center gap-1 text-amber-400">
                  <AlertTriangle className="h-2.5 w-2.5" />
                  {stats.failed} failed (click Reindex)
                </span>
              )}
              <span className="flex items-center gap-1">
                <Zap className="h-2.5 w-2.5 text-violet-400" />
                {stats.vector_count} vectors in store
              </span>
            </div>
          </div>
        </div>
        {stats.total > 0 && (
          <button
            onClick={onReindex}
            disabled={reindexing}
            className="flex items-center gap-1.5 rounded-xl border border-[#1f2937] px-3 py-2 text-xs text-slate-400 hover:text-amber-400 hover:border-amber-500/30 disabled:opacity-50 transition-all"
          >
            <RotateCcw className={`h-3.5 w-3.5 ${reindexing ? "animate-spin" : ""}`} />
            {reindexing ? "Reindexing…" : "Reindex All"}
          </button>
        )}
      </div>

      {/* How agents use KB */}
      <div className="mt-3 rounded-xl border border-[#1f2937] bg-[#060c16] p-3 text-[11px] text-slate-500">
        <p className="font-semibold text-slate-400 mb-1">How agents use this:</p>
        <p>
          When a user asks a question (chat or voice), the agent automatically searches your knowledge base
          and injects relevant excerpts into its reasoning context before responding. This means your Sales
          agent will quote your product catalogue, your HR agent will reference your policies, etc.
        </p>
        <p className="mt-1">
          <span className="text-blue-400 font-semibold">Active (keyword)</span> = works immediately after upload.{" "}
          <span className="text-emerald-400 font-semibold">Vector + DB</span> = most accurate semantic matching.
        </p>
      </div>
    </div>
  );
}

export default function KnowledgeBasePage() {
  const [tab, setTab] = useState<"docs" | "search">("docs");

  // --- Documents tab ---
  const [docs, setDocs] = useState<KBDocument[]>([]);
  const [stats, setStats] = useState<KBStats | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterText, setFilterText] = useState("");
  const [category, setCategory] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [pollingId, setPollingId] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
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
      const [docsRes, statsRes] = await Promise.allSettled([
        fetch(`${API}/api/v1/knowledge?${params}`, { headers: authHeaders() }),
        fetch(`${API}/api/v1/knowledge/stats`, { headers: authHeaders() }),
      ]);
      if (docsRes.status === "fulfilled" && docsRes.value.ok) {
        const data = await docsRes.value.json();
        setDocs(data.documents ?? []);
        setTotal(data.total ?? 0);
      } else {
        throw new Error("Failed to load documents");
      }
      if (statsRes.status === "fulfilled" && statsRes.value.ok) {
        setStats(await statsRes.value.json());
      }
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
    setUploadMsg(null);
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
      setUploadMsg({ text: `"${data.title}" uploaded — agents can use it immediately. Vector indexing in background…`, ok: true });
      setUploadTitle("");
      if (fileRef.current) fileRef.current.value = "";
      fetchDocs();
      if (data.id) pollEmbedding(data.id);
    } catch (e: unknown) {
      setUploadMsg({ text: e instanceof Error ? e.message : "Upload failed", ok: false });
    } finally {
      setUploading(false);
    }
  }

  function pollEmbedding(docId: string) {
    setPollingId(docId);
    const startMs = Date.now();
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/v1/knowledge/${docId}`, { headers: authHeaders() });
        if (!res.ok) { clearInterval(interval); setPollingId(null); return; }
        const doc: KBDocument = await res.json();
        fetchDocs();
        if (doc.embedding_status === "complete") {
          setUploadMsg({ text: `Vector indexing complete for "${doc.title}" — full semantic search now active!`, ok: true });
          clearInterval(interval); setPollingId(null);
        } else if (doc.embedding_status === "failed") {
          setUploadMsg({ text: `Vector indexing failed (keyword search still works). Click "Reindex All" to retry.`, ok: false });
          clearInterval(interval); setPollingId(null);
        } else if (doc.embedding_status === "indexed") {
          setUploadMsg({ text: `"${doc.title}" is active — agents are using it. Vector indexing still in progress…`, ok: true });
        } else if (Date.now() - startMs > 120_000) {
          clearInterval(interval); setPollingId(null);
        }
      } catch { clearInterval(interval); setPollingId(null); }
    }, 3_000);
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this document? Agents will no longer be able to use it.")) return;
    await fetch(`${API}/api/v1/knowledge/${id}`, { method: "DELETE", headers: authHeaders() });
    fetchDocs();
  }

  async function handleReindex() {
    setReindexing(true);
    try {
      const res = await fetch(`${API}/api/v1/knowledge/reindex`, {
        method: "POST", headers: authHeaders(),
      });
      const data = await res.json();
      setUploadMsg({ text: data.message ?? `Reindexing ${data.queued} documents…`, ok: true });
      // Poll for completion
      setTimeout(fetchDocs, 5000);
      setTimeout(fetchDocs, 15000);
      setTimeout(fetchDocs, 30000);
    } catch {
      setUploadMsg({ text: "Reindex failed — check server logs", ok: false });
    } finally {
      setTimeout(() => setReindexing(false), 3000);
    }
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
      const res = await fetch(`${API}/api/v1/knowledge/search?${params}`, { headers: authHeaders() });
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
    (d) => !filterText ||
      d.title.toLowerCase().includes(filterText.toLowerCase()) ||
      (d.file_name ?? "").toLowerCase().includes(filterText.toLowerCase())
  );

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-6xl mx-auto text-slate-100">

        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-500/10 border border-violet-500/20">
              <BookOpen className="h-4.5 w-4.5 text-violet-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Knowledge Base</h1>
              <p className="text-xs text-slate-500 mt-0.5">
                {total} document{total !== 1 ? "s" : ""} — agents reference these during conversations
              </p>
            </div>
          </div>
          <button onClick={fetchDocs}
            className="rounded-xl border border-[#1f2937] p-2 text-slate-500 hover:text-slate-300 transition-all">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-5 border-b border-[#1f2937]">
          {(["docs", "search"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors -mb-px capitalize ${
                tab === t
                  ? "border-violet-500 text-violet-400"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}>
              {t === "docs"
                ? <span className="flex items-center gap-1.5"><FileText className="h-3.5 w-3.5" /> Documents</span>
                : <span className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" /> Semantic Search</span>
              }
            </button>
          ))}
        </div>

        {/* ── DOCUMENTS TAB ─────────────────────────────────────────── */}
        {tab === "docs" && (
          <>
            {/* Health banner */}
            {stats && (
              <HealthBanner stats={stats} onReindex={handleReindex} reindexing={reindexing} />
            )}

            {/* Upload card */}
            <div className="mb-5 rounded-2xl border border-violet-500/20 bg-violet-500/5 p-5">
              <h2 className="text-xs font-semibold text-violet-400 mb-3 flex items-center gap-1.5 font-mono uppercase tracking-wider">
                <Upload className="h-3.5 w-3.5" /> Upload Document
              </h2>
              <p className="text-[11px] text-slate-500 mb-3">
                Supported: .txt .md .pdf .docx .csv .json (max {20}MB).
                Documents are available to agents <strong className="text-slate-400">immediately</strong> after upload via keyword search.
                Vector embedding runs in the background for better semantic matching.
              </p>
              <div className="flex flex-wrap gap-3 items-end">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-slate-500">Title (optional)</label>
                  <input type="text" value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                    placeholder="e.g. Product Catalogue"
                    className="px-3 py-1.5 rounded-lg border border-[#1f2937] bg-[#060c16] text-sm text-slate-300 w-48 focus:outline-none focus:ring-1 focus:ring-violet-500 placeholder-slate-600" />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-slate-500">Category</label>
                  <select value={uploadCategory} onChange={(e) => setUploadCategory(e.target.value)}
                    className="px-3 py-1.5 rounded-lg border border-[#1f2937] bg-[#060c16] text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-violet-500">
                    {["General","HR","Sales","Finance","IT","Marketing","Support"].map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-slate-500">File</label>
                  <input ref={fileRef} type="file" accept=".txt,.md,.pdf,.docx,.csv,.json"
                    className="text-xs text-slate-400 file:mr-2 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-violet-600/80 file:text-white file:text-xs file:cursor-pointer" />
                </div>
                <button onClick={handleUpload}
                  disabled={uploading || !!pollingId}
                  className="px-4 py-2 rounded-xl bg-violet-600/80 border border-violet-500/30 text-white text-xs font-medium hover:bg-violet-600 disabled:opacity-50 transition-all">
                  {uploading ? "Uploading…" : pollingId ? "Indexing…" : "Upload"}
                </button>
              </div>
              {uploadMsg && (
                <div className={`mt-3 flex items-start gap-2 rounded-xl border p-3 text-xs
                  ${uploadMsg.ok
                    ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-400"
                    : "border-red-500/20 bg-red-500/5 text-red-400"}`}>
                  {uploadMsg.ok
                    ? <CheckCircle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                    : <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />}
                  {uploadMsg.text}
                </div>
              )}
            </div>

            {/* Filter bar */}
            <div className="flex flex-wrap gap-3 mb-4">
              <div className="relative flex-1 min-w-[180px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-600" />
                <input type="text" placeholder="Filter documents…"
                  value={filterText} onChange={(e) => setFilterText(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl border border-[#1f2937] bg-[#0c111d] text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500" />
              </div>
              <select value={category} onChange={(e) => setCategory(e.target.value)}
                className="px-3 py-2 rounded-xl border border-[#1f2937] bg-[#0c111d] text-sm text-slate-400 focus:outline-none">
                <option value="">All categories</option>
                {["HR","Sales","Finance","IT","Marketing","Support","General"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
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
              <div className="flex flex-col items-center justify-center py-20 text-slate-600">
                <BookOpen className="h-12 w-12 mb-3 opacity-30" />
                <p className="font-medium text-slate-500">No documents yet</p>
                <p className="text-xs mt-1">Upload your first document above to get started</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filtered.map((doc) => (
                  <div key={doc.id}
                    className="group rounded-2xl border border-[#1f2937] bg-[#0c111d] p-4 hover:border-violet-500/30 transition-all">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText className="h-4 w-4 text-violet-400 flex-shrink-0" />
                        <h3 className="font-medium text-slate-200 text-sm truncate">{doc.title}</h3>
                      </div>
                      <button onClick={() => handleDelete(doc.id)}
                        className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all flex-shrink-0"
                        title="Delete document">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 mb-2">
                      {doc.category && (
                        <span className="rounded-full border border-[#1f2937] px-2 py-0.5 text-[10px] text-slate-500 bg-[#060c16]">{doc.category}</span>
                      )}
                      <StatusBadge status={doc.embedding_status} />
                    </div>
                    <p className="text-[11px] text-slate-600">
                      {new Date(doc.created_at).toLocaleDateString()}
                      {doc.file_size > 0 && ` · ${formatBytes(doc.file_size)}`}
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
            <div className="mb-5 rounded-2xl border border-blue-500/20 bg-blue-500/5 p-5">
              <p className="text-xs text-slate-400 mb-3">
                Search for information across your uploaded documents using AI semantic matching.
                This is the same search agents use internally when answering questions.
              </p>
              <form onSubmit={handleSearch} className="flex gap-3">
                <div className="relative flex-1">
                  <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-blue-400" />
                  <input type="text" value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="e.g. What is our return policy? / Product pricing"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-[#1f2937] bg-[#060c16] text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500" />
                </div>
                <button type="submit" disabled={searching || !searchQuery.trim()}
                  className="px-5 py-2.5 rounded-xl bg-blue-600/80 border border-blue-500/30 text-white text-xs font-medium hover:bg-blue-600 disabled:opacity-50 transition-all flex items-center gap-2">
                  {searching ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                  {searching ? "Searching…" : "Search"}
                </button>
              </form>
            </div>

            {searchError && (
              <div className="mb-4 p-3 rounded-xl border border-red-500/20 bg-red-500/5 text-red-400 text-xs">{searchError}</div>
            )}

            {searchDone && searchResults.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-slate-600">
                <Search className="h-10 w-10 mb-3 opacity-30" />
                <p className="text-sm text-slate-500">No matching results</p>
                <p className="text-xs mt-1">Try rephrasing or uploading more documents</p>
              </div>
            )}

            {searchResults.length > 0 && (
              <div className="space-y-3">
                <p className="text-[11px] text-slate-600">{searchResults.length} result{searchResults.length !== 1 ? "s" : ""} for &ldquo;{searchQuery}&rdquo;</p>
                {searchResults.map((r, i) => {
                  const text = r.content ?? r.text ?? "";
                  const title = r.metadata?.title ?? r.metadata?.file_name ?? `Result ${i + 1}`;
                  const score = r.score ?? (r.distance != null ? 1 - r.distance : null);
                  return (
                    <div key={i} className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-4 hover:border-blue-500/30 transition-all">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <ChevronRight className="h-3.5 w-3.5 text-blue-400" />
                          <span className="text-sm font-medium text-slate-200">{title}</span>
                          {r.metadata?.category && (
                            <span className="rounded-full border border-[#1f2937] px-1.5 py-0.5 text-[10px] text-slate-500">{r.metadata.category}</span>
                          )}
                        </div>
                        {score != null && (
                          <span className="text-[11px] text-slate-600">{(score * 100).toFixed(0)}% match</span>
                        )}
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed line-clamp-5">{text}</p>
                    </div>
                  );
                })}
              </div>
            )}

            {!searchDone && !searching && (
              <div className="flex flex-col items-center justify-center py-16 text-slate-600">
                <Sparkles className="h-10 w-10 mb-3 opacity-30" />
                <p className="text-sm text-slate-500">Enter a question or topic to search</p>
              </div>
            )}
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
