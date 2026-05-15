"use client";

/**
 * AuthGuard: on every page (except /login) verify a JWT token exists
 * in localStorage. If missing → redirect to /login.
 * Runs client-side only (no SSR flicker thanks to a loading state).
 */

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

const PUBLIC_PATHS = ["/login"];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const path   = usePathname();
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (PUBLIC_PATHS.includes(path)) {
      setChecking(false);
      return;
    }
    const token = localStorage.getItem("workforce_token");
    if (!token) {
      router.replace("/login");
    } else {
      setChecking(false);
    }
  }, [path, router]);

  /* Show a spinner while we check localStorage (avoids flash of protected content) */
  if (checking && !PUBLIC_PATHS.includes(path)) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#030712]">
        <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
      </div>
    );
  }

  return <>{children}</>;
}
