"use client";

/**
 * ClientLayout: wraps children with AuthGuard and conditionally renders
 * the Sidebar (hidden on public/fullscreen pages like /welcome and /login).
 */

import { useEffect } from "react";
import { AuthGuard, useIsSidebarVisible } from "@/components/AuthGuard";
import { Sidebar } from "@/components/Sidebar";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { NotificationBell } from "@/components/NotificationBell";
import { installFetchInterceptor } from "@/lib/auth";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const showSidebar = useIsSidebarVisible();

  // Install once, app-wide: transparently refreshes an expired access token
  // and retries the request instead of every page failing silently after
  // the 1-hour token lifetime with a generic "Failed to save" error.
  useEffect(() => { installFetchInterceptor(); }, []);

  return (
    <AuthGuard>
      {showSidebar && <Sidebar />}
      <div className={showSidebar ? "flex flex-1 flex-col overflow-hidden" : "flex-1 overflow-y-auto"}>
        {showSidebar && (
          <header className="flex h-10 flex-shrink-0 items-center justify-end border-b border-[#1f2937] bg-[#070d1a]/90 px-4">
            <NotificationBell />
          </header>
        )}
        <main className="flex-1 overflow-y-auto bg-grid">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>
    </AuthGuard>
  );
}

