/**
 * API fetch client for Smart Lock Admin REST API.
 *
 * 用途：
 *   - 注入 Authorization / X-Tenant-ID / Idempotency-Key headers
 *   - 處理 401 自動 refresh token（once）
 *   - 統一錯誤格式（後端回 ApiErrorResponse）→ 前端 throw ApiError
 *   - GET 共享 in-flight promise + 30s staleTime cache（避免重複 fetch）
 *
 * 型別來源：web/types/api.generated.ts（由 docs/02-design/specs/openapi.yaml 透過 ./scripts/ci/generate-api-types.sh 產生）
 *
 * 用法：
 *   import { api } from "@/lib/api";
 *   const cfg = await api.get("/api/v1/config");
 *   await api.patch("/api/v1/config", { rag: { max_results: 5 } });
 *
 *   // mutate 後清相關 GET cache：
 *   import { cacheInvalidate } from "@/lib/cache";
 *   cacheInvalidate("GET:/api/v1/work-orders");
 */

import { cacheGet, cacheClear } from "./cache";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

const STORAGE_KEYS = {
  access: "smartlock.access_token",
  refresh: "smartlock.refresh_token",
  tenant: "smartlock.tenant_id",
  email: "smartlock.email",
} as const;

export interface ApiErrorResponse {
  error_code: string;
  message: string;
  details?: unknown;
  request_id?: string;
  timestamp?: string;
}

export class ApiError extends Error {
  status: number;
  errorCode: string;
  details?: unknown;
  requestId?: string;
  constructor(status: number, body: ApiErrorResponse) {
    super(body.message || `HTTP ${status}`);
    this.status = status;
    this.errorCode = body.error_code || "UNKNOWN";
    this.details = body.details;
    this.requestId = body.request_id;
  }
}

interface RequestOptions {
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  idempotencyKey?: string;
  signal?: AbortSignal;
  /** 跳過 401 → refresh → retry 流程（用於 login/refresh 自身）。 */
  skipAuth?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(path, BASE_URL);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

function readToken(key: string): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(key);
}

function writeToken(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  if (value === null) window.localStorage.removeItem(key);
  else window.localStorage.setItem(key, value);
}

export const auth = {
  getAccessToken: () => readToken(STORAGE_KEYS.access),
  getRefreshToken: () => readToken(STORAGE_KEYS.refresh),
  getTenantId: () =>
    readToken(STORAGE_KEYS.tenant) ?? "00000000-0000-0000-0000-000000000001",
  getEmail: () => readToken(STORAGE_KEYS.email),
  setTokens(access: string, refresh: string) {
    writeToken(STORAGE_KEYS.access, access);
    writeToken(STORAGE_KEYS.refresh, refresh);
  },
  setTenantId(tenantId: string) {
    writeToken(STORAGE_KEYS.tenant, tenantId);
  },
  setEmail(email: string) {
    writeToken(STORAGE_KEYS.email, email);
  },
  clear() {
    writeToken(STORAGE_KEYS.access, null);
    writeToken(STORAGE_KEYS.refresh, null);
    writeToken(STORAGE_KEYS.email, null);
  },
};

export interface CurrentSession {
  userId: string | null;
  role: string | null;
  tenantId: string | null;
  email: string | null;
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const padded = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padding = "=".repeat((4 - (padded.length % 4)) % 4);
    const json = atob(padded + padding);
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function getCurrentSession(): CurrentSession | null {
  const token = auth.getAccessToken();
  if (!token) return null;
  const payload = decodeJwtPayload(token);
  if (!payload) return null;
  const sub = typeof payload.sub === "string" ? payload.sub : null;
  const role = typeof payload.role === "string" ? payload.role : null;
  const tenantId =
    typeof payload.tenant_id === "string" ? payload.tenant_id : null;
  return { userId: sub, role, tenantId, email: auth.getEmail() };
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  const token = auth.getRefreshToken();
  if (!token) return false;

  refreshInFlight = (async () => {
    try {
      const res = await fetch(buildUrl("/api/v1/auth/refresh"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: token }),
      });
      if (!res.ok) return false;
      const data = (await res.json()) as { data?: { access_token: string; refresh_token: string } };
      if (!data.data) return false;
      auth.setTokens(data.data.access_token, data.data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function rawRequest<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  if (!options.skipAuth) {
    const token = auth.getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    headers["X-Tenant-ID"] = auth.getTenantId();
  }

  if (options.idempotencyKey && method !== "GET") {
    headers["Idempotency-Key"] = options.idempotencyKey;
  }

  const init: RequestInit = {
    method,
    headers,
    signal: options.signal,
  };
  if (options.body !== undefined) init.body = JSON.stringify(options.body);

  let res = await fetch(buildUrl(path, options.query), init);

  if (res.status === 401 && !options.skipAuth) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) (init.headers as Record<string, string>)["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(buildUrl(path, options.query), init);
    }
  }

  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await res.json() : await res.text();

  if (!res.ok) {
    const body = (typeof payload === "object" && payload) as ApiErrorResponse;
    throw new ApiError(res.status, body ?? { error_code: "UNKNOWN", message: String(payload) });
  }

  return payload as T;
}

/**
 * request — 對外 API。GET 走 cache（共享 in-flight + 30s staleTime），
 * 其他 method 直接打。signal / skipAuth 任一存在時 bypass cache。
 */
async function request<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const isCacheable =
    method === "GET" && !options.signal && !options.skipAuth;
  if (!isCacheable) {
    return rawRequest<T>(method, path, options);
  }

  const tenant = auth.getTenantId();
  const fullUrl = buildUrl(path, options.query);
  const key = `GET:${fullUrl}:${tenant}`;
  return cacheGet<T>(key, () => rawRequest<T>(method, path, options));
}

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function uploadMultipart<T>(
  path: string,
  formData: FormData,
  opts?: { idempotencyKey?: string },
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = auth.getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  headers["X-Tenant-ID"] = auth.getTenantId();
  headers["Idempotency-Key"] = opts?.idempotencyKey ?? newIdempotencyKey();
  // 不設 Content-Type — 讓瀏覽器自動帶 boundary

  let res = await fetch(buildUrl(path), { method: "POST", headers, body: formData });

  if (res.status === 401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(buildUrl(path), { method: "POST", headers, body: formData });
    }
  }

  const contentType = res.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await res.json() : await res.text();

  if (!res.ok) {
    const body = (typeof payload === "object" && payload) as ApiErrorResponse;
    throw new ApiError(res.status, body ?? { error_code: "UNKNOWN", message: String(payload) });
  }

  return payload as T;
}

async function downloadBlob(
  path: string,
  opts?: { query?: RequestOptions["query"]; filename?: string },
): Promise<void> {
  const headers: Record<string, string> = {};
  const token = auth.getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  headers["X-Tenant-ID"] = auth.getTenantId();

  let res = await fetch(buildUrl(path, opts?.query), { method: "GET", headers });

  if (res.status === 401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(buildUrl(path, opts?.query), { method: "GET", headers });
    }
  }

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json")
      ? ((await res.json()) as ApiErrorResponse)
      : { error_code: "UNKNOWN", message: await res.text() };
    throw new ApiError(res.status, payload);
  }

  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(cd);
  const filename = opts?.filename ?? match?.[1] ?? "download";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * downloadBlobPost — POST + JSON body that returns a streaming download.
 *
 * For endpoints like /audit-logs/export where the filter payload is too large
 * for a query string and the response is a text/csv | application/json stream.
 *
 * Returns the blob and the resolved filename so callers can either auto-download
 * (default) or pipe the data elsewhere (e.g. a preview pane).
 */
async function downloadBlobPost(
  path: string,
  body: unknown,
  opts?: { filename?: string; idempotencyKey?: string },
): Promise<{ blob: Blob; filename: string }> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = auth.getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  headers["X-Tenant-ID"] = auth.getTenantId();
  headers["Idempotency-Key"] = opts?.idempotencyKey ?? newIdempotencyKey();

  const init: RequestInit = {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  };

  let res = await fetch(buildUrl(path), init);

  if (res.status === 401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) (init.headers as Record<string, string>)["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(buildUrl(path), init);
    }
  }

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json")
      ? ((await res.json()) as ApiErrorResponse)
      : { error_code: "UNKNOWN", message: await res.text() };
    throw new ApiError(res.status, payload);
  }

  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(cd);
  const filename = opts?.filename ?? match?.[1] ?? "download";
  return { blob, filename };
}

/** Helper — trigger browser download from an already-resolved blob + filename. */
function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  get: <T = unknown>(path: string, opts?: Omit<RequestOptions, "body" | "idempotencyKey">) =>
    request<T>("GET", path, opts),
  post: <T = unknown>(path: string, body?: unknown, opts?: Omit<RequestOptions, "body">) =>
    request<T>("POST", path, { ...opts, body, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() }),
  put: <T = unknown>(path: string, body?: unknown, opts?: Omit<RequestOptions, "body">) =>
    request<T>("PUT", path, { ...opts, body, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() }),
  patch: <T = unknown>(path: string, body?: unknown, opts?: Omit<RequestOptions, "body">) =>
    request<T>("PATCH", path, { ...opts, body, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() }),
  delete: <T = unknown>(path: string, opts?: Omit<RequestOptions, "body">) =>
    request<T>("DELETE", path, { ...opts, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() }),
  upload: uploadMultipart,
  download: downloadBlob,
  downloadPost: downloadBlobPost,
  triggerDownload: triggerBlobDownload,
  raw: request,
};

export interface LoginResponse {
  data: {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
  };
  message?: string;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await request<LoginResponse>("POST", "/api/v1/auth/login", {
    body: { email, password },
    skipAuth: true,
  });
  auth.setTokens(res.data.access_token, res.data.refresh_token);
  auth.setEmail(email);
  return res;
}

// Tech-login PWA stub (`tech-login/page.tsx` is v0.1 WIP).  No dedicated tech
// auth endpoint exists yet; for now treat `identifier` (phone or email) as the
// admin login key so the build passes.  Replace with a real
// `/api/v1/auth/tech-login` endpoint when the technician auth track lands.
export async function loginTechnician(
  identifier: string,
  password: string,
): Promise<LoginResponse> {
  return login(identifier, password);
}

export async function logout(): Promise<void> {
  const refresh = auth.getRefreshToken();
  try {
    await request("POST", "/api/v1/auth/logout", {
      body: refresh ? { refresh_token: refresh } : undefined,
    });
  } catch {
    // ignore — clear local state regardless
  } finally {
    auth.clear();
    // 清掉所有 GET cache，避免下次登入讀到上一個帳號的資料
    cacheClear();
  }
}
