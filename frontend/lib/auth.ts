/**
 * Auth helpers — JWT token stored in localStorage.
 * All API calls read from here; the login page writes here.
 */

const TOKEN_KEY   = "workforce_token";
const REFRESH_KEY = "workforce_refresh_token";
const USER_KEY    = "workforce_user";

export interface AuthUser {
  user_id?:   string;
  username:   string;
  email?:     string;
  full_name?: string;
  roles:      string[];
  scopes?:    string[];
  tenant_id?: string;
}

export function saveToken(token: string, user: AuthUser, refreshToken?: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
}

/** Alias kept for callers that use setToken */
export const setToken = saveToken;

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw) as AuthUser; } catch { return null; }
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

/** Returns headers with Authorization if a token exists. */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Redirects to /login if no token is stored. Call inside useEffect. */
export function requireAuth(): void {
  if (typeof window !== "undefined" && !isAuthenticated()) {
    window.location.href = "/login";
  }
}

/**
 * Attempt to refresh the access token using the stored refresh token.
 * Returns the new access token on success, null on failure.
 */
export async function tryRefreshToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
  try {
    const res = await fetch(`${API}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) { clearAuth(); return null; }
    const data = await res.json();
    const user = getUser();
    if (user) saveToken(data.access_token, user, data.refresh_token ?? refresh);
    return data.access_token;
  } catch {
    return null;
  }
}

// Avoid firing multiple concurrent refresh requests when several API calls
// hit a 401 at the same time (e.g. a page that fires several fetches on load).
let _refreshInFlight: Promise<string | null> | null = null;
function refreshOnce(): Promise<string | null> {
  if (!_refreshInFlight) {
    _refreshInFlight = tryRefreshToken().finally(() => { _refreshInFlight = null; });
  }
  return _refreshInFlight;
}

/**
 * Authenticated fetch wrapper. Attaches the bearer token automatically and,
 * if the server responds 401 (access token expired), transparently swaps in
 * a fresh token via the refresh token and retries the request ONCE. If the
 * refresh also fails, the stored session is cleared and the user is sent to
 * /login instead of leaving pages stuck showing a generic "Failed to save".
 */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const doFetch = (token: string | null) => {
    const headers: Record<string, string> = {
      ...(init.headers as Record<string, string> | undefined),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
    return fetch(input, { ...init, headers });
  };

  let res = await doFetch(getToken());

  if (res.status === 401 && getRefreshToken()) {
    const newToken = await refreshOnce();
    if (newToken) {
      res = await doFetch(newToken);
    } else if (typeof window !== "undefined") {
      clearAuth();
      window.location.href = "/login";
    }
  }

  return res;
}

let _fetchPatched = false;

/**
 * Installs a global window.fetch interceptor so EVERY call site in the app
 * (most pages call `fetch()` directly with `authHeaders()`, not `apiFetch`)
 * benefits from automatic token-refresh-and-retry on 401, without having to
 * touch every page. This is the fix for the whole class of "intermittent"
 * errors (onboarding "Failed to save", portal/monitoring/admin errors, etc.)
 * that only appear after the 1-hour access token has quietly expired.
 *
 * Safe to call multiple times; only patches once. Only intercepts requests
 * carrying an `Authorization: Bearer` header, so public endpoints (login,
 * forgot-password, health checks) are never touched or looped.
 */
export function installFetchInterceptor(): void {
  if (typeof window === "undefined" || _fetchPatched) return;
  _fetchPatched = true;

  const originalFetch = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    const hadAuthHeader = headers.has("Authorization");

    let res = await originalFetch(input, init);

    if (res.status === 401 && hadAuthHeader && getRefreshToken()) {
      const newToken = await refreshOnce();
      if (newToken) {
        headers.set("Authorization", `Bearer ${newToken}`);
        const retryInit: RequestInit = { ...init, headers };
        res = await originalFetch(input, retryInit);
      } else {
        clearAuth();
        if (!window.location.pathname.startsWith("/login")) {
          window.location.href = "/login";
        }
      }
    }

    return res;
  };
}
