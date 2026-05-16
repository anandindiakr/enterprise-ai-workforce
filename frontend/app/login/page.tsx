"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { saveToken } from "@/lib/auth";
import { Zap, Eye, EyeOff, Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  /* Already logged in → skip */
  useEffect(() => {
    const token = typeof window !== "undefined" && localStorage.getItem("workforce_token");
    if (token) router.replace("/");
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    try {
      const res = await fetch(`${apiBase}/api/v1/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(body.detail ?? "Invalid credentials");
      }
      const data = await res.json() as { access_token: string };
      saveToken(data.access_token, { username, roles: ["agent"] });
      router.replace("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full w-full items-center justify-center bg-[#030712]">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500 shadow-lg shadow-amber-500/25">
            <Zap className="h-6 w-6 text-black" />
          </div>
          <div className="text-center">
            <h1
              className="text-2xl font-bold tracking-widest text-slate-100"
              style={{ fontFamily: "var(--font-syne)" }}
            >
              WORKFORCE
            </h1>
            <p className="mt-1 text-xs text-slate-500">Enterprise AI Platform</p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-8 shadow-2xl">
          <h2 className="mb-6 text-sm font-semibold text-slate-200">Sign in to your workspace</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div>
              <label className="mb-1.5 block text-[11px] font-mono uppercase tracking-widest text-slate-500">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3.5 py-2.5 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/25 transition-colors"
                placeholder="admin"
              />
            </div>

            {/* Password */}
            <div>
              <label className="mb-1.5 block text-[11px] font-mono uppercase tracking-widest text-slate-500">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="w-full rounded-lg border border-[#1f2937] bg-[#070d1a] px-3.5 py-2.5 pr-10 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/25 transition-colors"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  tabIndex={-1}
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                {error}
              </p>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-amber-400 disabled:opacity-60 disabled:cursor-not-allowed mt-2"
            >
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Signing in…</>
              ) : (
                "Sign in"
              )}
            </button>
          </form>

          {/* Demo hint */}
          <div className="mt-5 rounded-lg border border-[#1f2937] bg-[#070d1a] px-3 py-2.5">
            <p className="font-mono text-[10px] uppercase tracking-wider text-slate-600 mb-1.5">Demo accounts</p>
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400"><span className="text-amber-400 font-mono">admin</span> / admin</span>
                <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-400 font-mono">Full access</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400"><span className="text-cyan-400 font-mono">agent</span> / agent</span>
                <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] text-cyan-400 font-mono">Agent access</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
