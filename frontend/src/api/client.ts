// Thin fetch wrapper around the FastAPI backend. TODO: swap for a generated
// client once the OpenAPI schema stabilizes (FastAPI exposes /openapi.json for free).
//
// BASE_URL defaults to "" -- same-origin, which in dev means Vite's /api proxy and
// in Docker means nginx's. Both keep the browser on one origin, so CORS and the
// "which host is the API on" build arg stop mattering. Set VITE_API_BASE_URL only
// when the API genuinely lives somewhere else.

export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

const TOKEN_KEY = "access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Fired when the API rejects our token, so AuthContext can bounce to /login. */
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** Machine-readable discriminator for `{code, message}` detail shapes (e.g. login's
     * account_locked/invalid_credentials) -- undefined for plain-string/validation errors. */
    readonly code?: string,
    readonly extra?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * FastAPI errors are `{detail: ...}` where detail is a string, a list of
 * `{loc, msg}` objects (422s), or -- for a few endpoints that need callers to
 * branch on the failure kind, like login -- `{code, message, ...extra}`.
 */
async function toApiError(res: Response): Promise<ApiError> {
  const text = await res.text();
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    const detail = body.detail;
    if (typeof detail === "string") return new ApiError(res.status, detail);
    if (Array.isArray(detail)) {
      const parts = detail.map((d) => {
        const item = d as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
        return field ? `${field}: ${item.msg}` : (item.msg ?? "invalid");
      });
      return new ApiError(res.status, parts.join("; "));
    }
    if (detail && typeof detail === "object" && "code" in detail && "message" in detail) {
      const { code, message, ...extra } = detail as Record<string, unknown>;
      return new ApiError(res.status, String(message), String(code), extra);
    }
  } catch {
    // Not JSON (nginx/proxy error pages, mostly) -- fall through to the raw body.
  }
  return new ApiError(res.status, text || res.statusText || `request failed (${res.status})`);
}

async function request<T>(path: string, init?: RequestInit, jsonBody = true): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      // Multipart bodies must NOT set Content-Type by hand — the browser has to
      // append the boundary itself.
      ...(jsonBody ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });

  if (res.status === 401) {
    clearToken();
    onUnauthorized?.();
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface TotpRequiredResponse {
  totp_required: true;
  login_token: string;
}

export type LoginResponse = TokenResponse | TotpRequiredResponse;

export const api = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),

  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),

  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),

  upload: <T>(path: string, file: File, field = "file") => {
    const form = new FormData();
    form.append(field, file);
    return request<T>(path, { method: "POST", body: form }, false);
  },

  /**
   * `POST /api/auth/login` is an OAuth2 password flow, so it takes form-encoded
   * `username`/`password` rather than JSON -- and no bearer header, obviously.
   */
  login: async (email: string, password: string): Promise<LoginResponse> => {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) throw await toApiError(res);
    return res.json() as Promise<LoginResponse>;
  },

  verifyTotp: (loginToken: string, code: string): Promise<TokenResponse> =>
    request<TokenResponse>("/api/auth/login/totp", {
      method: "POST",
      body: JSON.stringify({ login_token: loginToken, code }),
    }),

  /**
   * Authenticated file download. `<a download>` can't carry an Authorization
   * header, so the bytes come through fetch and go out via an object URL.
   */
  download: async (path: string, filename: string): Promise<void> => {
    const token = getToken();
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw await toApiError(res);

    const url = URL.createObjectURL(await res.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
};
