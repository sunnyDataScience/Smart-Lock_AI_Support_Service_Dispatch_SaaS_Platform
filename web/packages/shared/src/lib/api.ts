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
 *   import { api } from "@shared/lib/api";
 *   const cfg = await api.get("/api/v1/config");
 *   await api.patch("/api/v1/config", { rag: { max_results: 5 } });
 *
 *   // mutate 後清 GET cache。注意：cache key 是 `GET:${完整URL}:${tenant}`
 *   // （含 BASE_URL host），path-prefix（如 GET:/tenants/…）對不上 startsWith，
 *   // 故用廣域 "GET:" 清全部 GET 快取（與各頁慣例一致）：
 *   import { cacheInvalidate } from "@shared/lib/cache";
 *   cacheInvalidate("GET:");
 */

import { cacheGet, cacheClear } from "./cache";

// 用 || 而非 ??：Docker build-arg 未傳時 ENV 會是空字串 ""（非 undefined），
// 需讓空字串也 fallback 到本機預設（?? 只攔 null/undefined，會放過 ""）。
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001";

const STORAGE_KEYS = {
  access: "smartlock.access_token",
  refresh: "smartlock.refresh_token",
  tenant: "smartlock.tenant_id",
  email: "smartlock.email",
} as const;

/**
 * ApiErrorResponse — superset interface compatible with:
 *   - RFC7807 problem+json fields (type/title/status/detail/instance) — new
 *   - Legacy fields (error_code/message/request_id/timestamp/details) — kept as extension members
 *
 * All fields are optional so both old and new response shapes parse without throwing.
 * Callers MUST NOT fetch the `type` URI — it is an identifier string only (D5 decision).
 */
export interface ApiErrorResponse {
  // RFC7807 fields (new — application/problem+json)
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;

  // Legacy extension members (backward-compat)
  error_code?: string;
  message?: string;
  details?: unknown;
  request_id?: string;
  timestamp?: string;
}

/** Derive error_code from RFC7807 type URI (urn:smartlock:error:{code} → upper CODE). */
function deriveCodeFromType(type: string | undefined): string | undefined {
  if (!type) return undefined;
  // Format: urn:smartlock:error:validation_error → VALIDATION_ERROR
  const match = /^urn:smartlock:error:(.+)$/.exec(type);
  if (!match) return undefined;
  return match[1].toUpperCase();
}

export class ApiError extends Error {
  status: number;
  errorCode: string;
  details?: unknown;
  requestId?: string;
  constructor(status: number, body: ApiErrorResponse) {
    // Prefer detail (RFC7807) → message (legacy) → title (RFC7807) → fallback
    const msg = body.detail ?? body.message ?? body.title ?? `HTTP ${status}`;
    super(msg);
    this.status = status;
    // Prefer error_code (legacy extension member) → derive from type URI → "UNKNOWN"
    this.errorCode = body.error_code ?? deriveCodeFromType(body.type) ?? "UNKNOWN";
    this.details = body.details;
    // Prefer request_id (legacy) → instance (RFC7807 — may be path, not ID)
    this.requestId = body.request_id ?? body.instance;
  }
}

interface RequestOptions {
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  idempotencyKey?: string;
  signal?: AbortSignal;
  /** 跳過 401 → refresh → retry 流程（用於 login/refresh 自身）。 */
  skipAuth?: boolean;
  /** 額外 headers（如 SoD X-Initiator / X-Approver / X-Executor）。 */
  headers?: Record<string, string>;
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

/**
 * 預設租戶 ID — session/JWT 無 tenant 時的退回值（local dev / 未登入情境）。
 *
 * 收斂前散落在 11+ 個 page / component 內以 inline 字面量重抄此 UUID
 * （`session?.tenantId ?? "00000000-…-0001"`），改為唯一常數 + helper。
 *
 * TODO(安全, 跨頁行為決策)：正式環境理應在無有效 tenant 時擋下並導回登入，
 *   而非靜默退回 1 號租戶（多租戶資料外洩風險）。此為跨 12 頁面的行為變更，
 *   屬業主裁決範圍，本次只做「集中字面量」不改 runtime 行為。
 */
export const FALLBACK_TENANT_ID = "00000000-0000-0000-0000-000000000001";

export const auth = {
  getAccessToken: () => readToken(STORAGE_KEYS.access),
  getRefreshToken: () => readToken(STORAGE_KEYS.refresh),
  getTenantId: () => readToken(STORAGE_KEYS.tenant) ?? FALLBACK_TENANT_ID,
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

/**
 * tenantPath — 組出 tenant-scoped v2 路徑 `/tenants/{tenantId}/{suffix}`。
 *
 * tenantId 來源與 X-Tenant-ID header 一致（auth.getTenantId()：localStorage →
 * 退回預設租戶）。P3 caller 遷移用：把 legacy `/api/v1/foo` 改成
 * `tenantPath("/foo")` 即可，header / Idempotency-Key 仍由 client 自動注入。
 *
 * 僅用於 tenant-scoped 端點；平台級 flat 端點（/auth, /consumer, /kb/documents,
 * /sops, /vouchers/{id}/void 等）直接寫新 literal 路徑，不經此 helper。
 *
 *   api.get(tenantPath("/work-orders"))            // → /tenants/{tid}/work-orders
 *   cacheInvalidate("GET:")  // cache key 含完整 URL，用廣域 prefix 清，勿用 path-prefix
 *
 * 注意 tenant 來源差異：本 helper 走 `auth.getTenantId()`（localStorage，與
 * X-Tenant-ID header 一致）；頁面層的 `resolveTenantId()` 走 JWT claim。多數情境兩者
 * 相同，但若刻意需要與 header 對齊請用 tenantPath，需與 session 角色一致請用 resolveTenantId。
 */
export function tenantPath(suffix: string): string {
  const s = suffix.startsWith("/") ? suffix : `/${suffix}`;
  return `/tenants/${auth.getTenantId()}${s}`;
}

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

/**
 * resolveTenantId — 頁面用：取目前 JWT session 的 tenant_id，缺則退回 FALLBACK_TENANT_ID。
 *
 * 收斂 11+ 個 page / component 內 inline 重抄的
 * `getCurrentSession()?.tenantId ?? "00000000-…-0001"`。
 * 來源語意刻意對齊原 caller（JWT claim，而非 auth.getTenantId() 的 localStorage）。
 */
export function resolveTenantId(): string {
  return getCurrentSession()?.tenantId ?? FALLBACK_TENANT_ID;
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  const token = auth.getRefreshToken();
  if (!token) return false;

  refreshInFlight = (async () => {
    try {
      // CR-0114:平台 console 的 refresh 走平台端點（撤銷/狀態查平台庫）;
      // 依目前 session 的 role 判斷（platform token 只會出現在 console session）。
      const isPlatform = getCurrentSession()?.role === "platform_admin";
      const res = await fetch(
        buildUrl(isPlatform ? "/api/v1/platform/auth/refresh" : "/api/v1/auth/refresh"),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: token }),
        },
      );
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

// Session 失效（access + refresh 皆過期/無效）→ 清 token 並導去對應入口的登入頁。
// 為何需要：AuthGuard 只驗「token 存在」不驗「是否過期」，隔夜後過期 token 仍會放行頁面，
// 頁面拿過期 token 一路 401（refresh 也失敗）就白屏。在 API 層統一兜底，任何 portal 皆適用。
function loginPathForCurrentLocation(): string {
  if (typeof window === "undefined") return "/login";
  const p = window.location.pathname;
  // CR-0114 平台 console 有自己的登入頁
  if (p.startsWith("/platform")) return "/platform/login";
  // 20260702 決議 2:廠商登入已併入品牌/經銷/鎖店入口(/login)
  if (p.startsWith("/vendor")) return "/login";
  // 技師入口路由（與 TechBottomNav 一致）
  if (/^\/(home|pool|my-orders|account|tech-login)(\/|$)/.test(p)) return "/tech-login";
  return "/login";
}

let sessionExpiredHandled = false;
function handleSessionExpired(): void {
  if (typeof window === "undefined" || sessionExpiredHandled) return;
  sessionExpiredHandled = true; // 並發 401 只導一次（full nav 後模組重載自動歸零）
  auth.clear();
  const target = loginPathForCurrentLocation();
  if (window.location.pathname !== target) {
    window.location.replace(target); // replace：不在歷史留下已失效的死頁
  }
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

  // 非 GET 一律帶 Idempotency-Key：caller 給就用其值，否則自動生成（與 upload/
  // download 一致）。後端部分端點以 idempotency_guard 強制要求此 header（如
  // monthly-settlements:generate），缺則 400 MISSING_IDEMPOTENCY_KEY；未掛 guard 的
  // 端點忽略此 header（無害）。修正前 api.post 不帶 key → 這類按鈕按了即 400。
  if (method !== "GET") {
    headers["Idempotency-Key"] = options.idempotencyKey ?? newIdempotencyKey();
  }

  // 額外 headers（SoD 等）— 最後合併，可覆寫上方預設
  if (options.headers) {
    for (const [k, v] of Object.entries(options.headers)) headers[k] = v;
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
    if (res.status === 401) handleSessionExpired(); // 刷新失敗/仍 401 → session 失效，導登入頁
  }

  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get("content-type") ?? "";
  // Accept both application/json and application/problem+json (RFC7807)
  const isJson = contentType.includes("application/json") || contentType.includes("application/problem+json");
  const payload = isJson ? await res.json() : await res.text();

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
    if (res.status === 401) handleSessionExpired();
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
    if (res.status === 401) handleSessionExpired();
  }

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json") || contentType.includes("application/problem+json");
    const payload = isJson
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
 * fetchBlobGet — GET 一個受保護的二進位資源，回傳 Blob（供 inline 預覽等）。
 *
 * 與 downloadBlob 不同：不自動觸發下載，把 Blob 交給呼叫端（如平台 KYC 文件
 * 預覽面板）。共用同一套 401 → refresh → retry 鏈，不繞過 token 續期。
 */
async function fetchBlobGet(path: string): Promise<{ blob: Blob; contentType: string }> {
  const headers: Record<string, string> = {};
  const token = auth.getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  headers["X-Tenant-ID"] = auth.getTenantId();

  let res = await fetch(buildUrl(path), { method: "GET", headers });

  if (res.status === 401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(buildUrl(path), { method: "GET", headers });
    }
    if (res.status === 401) handleSessionExpired();
  }

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json") || contentType.includes("application/problem+json");
    const payload = isJson
      ? ((await res.json()) as ApiErrorResponse)
      : { error_code: "UNKNOWN", message: await res.text() };
    throw new ApiError(res.status, payload);
  }

  return { blob: await res.blob(), contentType: res.headers.get("content-type") ?? "" };
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
    if (res.status === 401) handleSessionExpired();
  }

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json") || contentType.includes("application/problem+json");
    const payload = isJson
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
  fetchBlob: fetchBlobGet,
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

// 技師登入走專用端點 POST /api/v1/technicians/login（auth.py:58,回傳與 admin
// login 相同的 {data:{access_token,refresh_token,...}} 信封,token 內 role=technician）。
// 之前暫接 admin login() 是 WIP stub,demo-tech 密碼存技師庫 → admin 端點必 401。
// CR-0099：identifier 可為手機（09xxxxxxxx）或 email，後端以 identifier 欄位解析。
export async function loginTechnician(
  identifier: string,
  password: string,
): Promise<LoginResponse> {
  const res = await request<LoginResponse>("POST", "/api/v1/technicians/login", {
    body: { identifier: identifier.trim(), password },
    skipAuth: true,
  });
  auth.setTokens(res.data.access_token, res.data.refresh_token);
  auth.setEmail(identifier);
  return res;
}

// 廠商/品牌商登入走專用端點 POST /api/v1/vendors/login（CR-0029；role=vendor，
// 與後台角色隔離）。回傳同 admin/technician 信封。
export async function loginVendor(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const res = await request<LoginResponse>("POST", "/api/v1/vendors/login", {
    body: { email, password },
    skipAuth: true,
  });
  auth.setTokens(res.data.access_token, res.data.refresh_token);
  auth.setEmail(email);
  return res;
}

// 平台管理員登入（CR-0114;role=platform_admin,與品牌/技師完全隔離,
// console 專用端點 + 平台庫帳號池）。回傳同 admin/technician 信封。
export async function loginPlatformAdmin(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const res = await request<LoginResponse>("POST", "/api/v1/platform/auth/login", {
    body: { email, password },
    skipAuth: true,
  });
  auth.setTokens(res.data.access_token, res.data.refresh_token);
  auth.setEmail(email);
  return res;
}

// 平台管理員登出（撤銷寫平台庫 revoked_jti）
export async function logoutPlatformAdmin(): Promise<void> {
  const refresh = auth.getRefreshToken();
  try {
    await request("POST", "/api/v1/platform/auth/logout", {
      body: refresh ? { refresh_token: refresh } : undefined,
    });
  } catch {
    // ignore — clear local state regardless
  } finally {
    auth.clear();
    cacheClear();
  }
}

// 自助忘記密碼（CR-0025 / ADR-0114）。兩端皆 skipAuth（登入前）。
// request 一律 200（不洩漏帳號是否存在）；confirm 成功 204、token 無效/過期/已用拋 ApiError。
export async function requestPasswordReset(email: string): Promise<{ message: string }> {
  return request<{ message: string }>("POST", "/api/v1/auth/request-password-reset", {
    body: { email },
    skipAuth: true,
  });
}

export async function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  await request<void>("POST", "/api/v1/auth/confirm-password-reset", {
    body: { token, new_password: newPassword },
    skipAuth: true,
  });
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
