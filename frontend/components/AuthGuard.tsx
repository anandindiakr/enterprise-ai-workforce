"use client";

/**
 * AuthGuard: on every page (except /login and /welcome) verify a JWT token
 * exists in localStorage.  If missing → redirect to /welcome.
 * Runs client-side only (no SSR flicker thanks to a loading state).
 */

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { getUser } from "@/lib/auth";

// Pages that don't require authentication
export const PUBLIC_PATHS = ["/login", "/welcome"];

const ONBOARDING_REDIRECT_FLAG = "workforce_onboarding_redirected";

// Pages that should NOT show the sidebar (full-screen layouts)
const NO_SIDEBAR_PATHS = ["/login", "/welcome"];

export function useIsSidebarVisible() {
  const path = usePathname();
  return !NO_SIDEBAR_PATHS.some((p) => path === p || path.startsWith(p + "/"));
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const path   = usePathname();
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  const isPublic = PUBLIC_PATHS.some((p) => path === p || path.startsWith(p + "/"));

  useEffect(() => {
    if (isPublic) {
      setChecking(false);
      return;
    }
    const token = localStorage.getItem("workforce_token");
    if (!token) {
      router.replace("/welcome");
      return;
    }
    setChecking(false);

    // One-time onboarding nudge: if an admin hasn't finished the setup
    // wizard yet, send them there once per browser session. They can
    // always "Skip for now" — this never hard-blocks daily use.
    if (path === "/onboarding") return;
    const user = getUser();
    if (!user?.roles?.includes("admin")) return;
    if (sessionStorage.getItem(ONBOARDING_REDIRECT_FLAG)) return;

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    fetch(`${apiBase}/api/v1/settings/company`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && !d.onboarding_complete) {
          sessionStorage.setItem(ONBOARDING_REDIRECT_FLAG, "1");
          router.replace("/onboarding");
        }
      })
      .catch(() => {});
  }, [path, router, isPublic]);

  /* Show a spinner while we check localStorage (avoids flash of protected content) */
  if (checking && !isPublic) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#030712]">
        <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
      </div>
    );
  }

  return <>{children}</>;
}
