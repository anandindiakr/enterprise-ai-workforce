"use client";

/**
 * AuthGuard: on every page (except /login and /welcome) verify a JWT token
 * exists in localStorage.  If missing → redirect to /welcome.
 * Runs client-side only (no SSR flicker thanks to a loading state).
 */

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

// Pages that don't require authentication
export const PUBLIC_PATHS = ["/login", "/welcome"];

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
    } else {
      setChecking(false);
    }
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
