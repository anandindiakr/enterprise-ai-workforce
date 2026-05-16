"use client";

/**
 * ClientLayout: wraps children with AuthGuard and conditionally renders
 * the Sidebar (hidden on public/fullscreen pages like /welcome and /login).
 */

import { AuthGuard, useIsSidebarVisible } from "@/components/AuthGuard";
import { Sidebar } from "@/components/Sidebar";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const showSidebar = useIsSidebarVisible();

  return (
    <AuthGuard>
      {showSidebar && <Sidebar />}
      <main
        className={
          showSidebar
            ? "flex-1 overflow-y-auto bg-grid"
            : "flex-1 overflow-y-auto"
        }
      >
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
    </AuthGuard>
  );
}
