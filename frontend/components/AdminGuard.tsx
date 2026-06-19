"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getUser } from "@/lib/auth";
import { ShieldAlert, ArrowLeft, Loader2 } from "lucide-react";

interface AdminGuardProps {
  children: React.ReactNode;
}

/**
 * Wrap any admin-only page with this component.
 * - Redirects to /login if not authenticated.
 * - Shows a full-screen "Access Denied" if user lacks the "admin" role.
 * - Renders children when admin is confirmed.
 */
export default function AdminGuard({ children }: AdminGuardProps) {
  const router = useRouter();
  const [status, setStatus] = useState<"loading" | "allowed" | "denied">("loading");

  useEffect(() => {
    const user = getUser();
    if (!user) {
      router.push("/login");
      return;
    }
    setStatus(user.roles?.includes("admin") ? "allowed" : "denied");
  }, [router]);

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center h-screen bg-[#030712]">
        <Loader2 className="h-8 w-8 animate-spin text-amber-500/60" />
      </div>
    );
  }

  if (status === "denied") {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-[#030712] gap-5 px-4 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full border border-amber-500/20 bg-amber-500/10">
          <ShieldAlert className="h-9 w-9 text-amber-500/60" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-slate-200">Admin Access Required</h1>
          <p className="mt-1.5 text-sm text-slate-500">
            This page is restricted to platform administrators.
          </p>
          <p className="mt-0.5 text-xs text-slate-600">
            Contact your administrator if you need access.
          </p>
        </div>
        <button
          onClick={() => router.push("/")}
          className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-5 py-2.5 text-sm font-medium text-amber-400 transition-all hover:bg-amber-500/20"
        >
          <ArrowLeft className="h-4 w-4" />
          Return to Dashboard
        </button>
      </div>
    );
  }

  return <>{children}</>;
}
