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
