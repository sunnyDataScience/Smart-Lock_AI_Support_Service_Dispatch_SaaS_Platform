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
 *   // mutate 後清 GET cache。注意：cache key 是 `GET:${完整URL}:${tenant}`
 *   // （含 BASE_URL host），path-prefix（如 GET:/tenants/…）對不上 startsWith，
 *   // 故用廣域 "GET:" 清全部 GET 快取（與各頁慣例一致）：
 *   import { cacheInvalidate } from "@/lib/cache";
 *   cacheInvalidate("GET:");
 */

import { cacheGet, cacheClear, cacheInvalidate } from "./cache";
import {
  ApiError,
  type ApiErrorResponse,
} from "@smartlock/shared-contract/errors";
import { apiBaseUrl } from "./runtimeConfig";
export { ApiError };
export type { ApiErrorResponse } from "@smartlock/shared-contract/errors";

// 用 || 而非 ??：Docker build-arg 未傳時 ENV 會是空字串 ""（非 undefined），
// 需讓空字串也 fallback 到本機預設（?? 只攔 null/undefined，會放過 ""）。
const LEGACY_SESSION_KEYS = [
  "smartlock.access_token",
  "smartlock.refresh_token",
  "smartlock.tenant_id",
  "smartlock.email",
] as const;
let accessTokenMemory: string | null = null;

/**
 * ApiErrorResponse — superset interface compatible with:
 *   - RFC7807 problem+json fields (type/title/status/detail/instance) — new
 *   - Legacy fields (error_code/message/request_id/timestamp/details) — kept as extension members
 *
 * All fields are optional so both old and new response shapes parse without throwing.
 * Callers MUST NOT fetch the `type` URI — it is an identifier string only (D5 decision).
 */
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

// ── CR-0177 S3a：統一帶 credentials，讓後端寫的 httpOnly access cookie 隨請求送出 ──
// Browser 走同站 /api-proxy 時 cookie 由 Web origin 保存並由 server proxy 轉送；
// 直連 API／WebSocket 才需要同父網域的 AUTH_COOKIE_DOMAIN。
function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, { ...init, credentials: "include" });
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(path.replace(/^\/+/, ""), `${apiBaseUrl()}/`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

function removeLegacySessionStorage() {
  if (typeof window === "undefined") return;
  for (const key of LEGACY_SESSION_KEYS) window.localStorage.removeItem(key);
}

const CLAIMS_COOKIE = `smartlock_claims_${process.env.NEXT_PUBLIC_APP_MODE || "app"}`;

interface ClaimsCookie {
  userId: string | null;
  role: string | null;
  tenantId: string | null;
  email: string | null;
}

function writeClaimsCookie(claims: ClaimsCookie | null) {
  if (typeof document === "undefined") return;
  if (claims === null) {
    document.cookie = `${CLAIMS_COOKIE}=; path=/; max-age=0; samesite=lax`;
    return;
  }
  const value = encodeURIComponent(JSON.stringify(claims));
  const secure = window.location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${CLAIMS_COOKIE}=${value}; path=/; max-age=2592000; samesite=lax${secure}`;
}

function readClaimsCookie(): ClaimsCookie | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${CLAIMS_COOKIE}=([^;]*)`),
  );
  if (!match) return null;
  try {
    return JSON.parse(decodeURIComponent(match[1])) as ClaimsCookie;
  } catch {
    return null;
  }
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
  getAccessToken: () => accessTokenMemory,
  getRefreshToken: () => null,
  getTenantId: () => readClaimsCookie()?.tenantId ?? FALLBACK_TENANT_ID,
  getEmail: () => readClaimsCookie()?.email ?? null,
  setTokens(access: string, _refresh?: string) {
    accessTokenMemory = access || null;
    removeLegacySessionStorage();
    const payload = decodeJwtPayload(access);
    if (payload) {
      writeClaimsCookie({
        userId: typeof payload.sub === "string" ? payload.sub : null,
        role: typeof payload.role === "string" ? payload.role : null,
        tenantId:
          typeof payload.tenant_id === "string" ? payload.tenant_id : null,
        email:
          typeof payload.email === "string"
            ? payload.email
            : readClaimsCookie()?.email ?? null,
      });
    }
  },
  setTenantId(tenantId: string) {
    const claims = readClaimsCookie();
    if (claims) writeClaimsCookie({ ...claims, tenantId });
  },
  setEmail(email: string) {
    const claims = readClaimsCookie();
    if (claims) writeClaimsCookie({ ...claims, email });
  },
  setSessionClaims(session: CurrentSession) {
    writeClaimsCookie(session);
  },
  clear() {
    accessTokenMemory = null;
    removeLegacySessionStorage();
    writeClaimsCookie(null);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("smartlock.session_event", `logout:${Date.now()}`);
    }
  },
};

/**
 * tenantPath — 組出 tenant-scoped v2 路徑 `/tenants/{tenantId}/{suffix}`。
 *
 * tenantId 來源與 X-Tenant-ID header 一致（auth.getTenantId()：claims cookie →
 * 退回預設租戶）。P3 caller 遷移用：把 legacy `/api/v1/foo` 改成
 * `tenantPath("/foo")` 即可，header / Idempotency-Key 仍由 client 自動注入。
 *
 * 僅用於 tenant-scoped 端點；平台級 flat 端點（/auth, /consumer, /kb/documents,
 * /sops, /vouchers/{id}/void 等）直接寫新 literal 路徑，不經此 helper。
 *
 *   api.get(tenantPath("/work-orders"))            // → /tenants/{tid}/work-orders
 *   cacheInvalidate("GET:")  // cache key 含完整 URL，用廣域 prefix 清，勿用 path-prefix
 *
 * 注意 tenant 來源差異：本 helper 走 `auth.getTenantId()`（claims cookie，與
 * X-Tenant-ID header 一致）；頁面層的 `resolveTenantId()` 走 session claim。多數情境兩者
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
  const claims = readClaimsCookie();
  if (claims && (claims.userId || claims.role)) return claims;
  if (typeof window !== "undefined") {
    const legacy = window.localStorage.getItem("smartlock.access_token");
    if (legacy) {
      auth.setTokens(legacy);
      return readClaimsCookie();
    }
  }
  return null;
}

export async function bootstrapSession(): Promise<CurrentSession | null> {
  const existing = getCurrentSession();
  if (existing) return existing;
  const platform = process.env.NEXT_PUBLIC_APP_MODE === "platform";
  const sessionPath = platform
    ? "/api/v2/platform/auth/session"
    : "/api/v2/auth/session";
  let response = await apiFetch(buildUrl(sessionPath));
  if (response.status === 401) {
    const refreshed = await apiFetch(
      buildUrl(
        platform
          ? "/api/v1/platform/auth/refresh"
          : "/api/v1/auth/refresh",
      ),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Auth-Response-Mode": "cookie",
        },
        body: JSON.stringify({}),
      },
    );
    if (!refreshed.ok) return null;
    response = await apiFetch(buildUrl(sessionPath));
  }
  if (!response.ok) return null;
  const payload = (await response.json()) as {
    data?: { user_id?: string; role?: string; tenant_id?: string };
  };
  if (!payload.data?.user_id || !payload.data.role) return null;
  const session: CurrentSession = {
    userId: payload.data.user_id,
    role: payload.data.role,
    tenantId: payload.data.tenant_id ?? null,
    email: null,
  };
  auth.setSessionClaims(session);
  return session;
}

/**
 * resolveTenantId — 頁面用：取目前 JWT session 的 tenant_id，缺則退回 FALLBACK_TENANT_ID。
 *
 * 收斂 11+ 個 page / component 內 inline 重抄的
 * `getCurrentSession()?.tenantId ?? "00000000-…-0001"`。
 * 來源語意刻意對齊原 caller（session claim，而非任意 request tenant）。
 */
export function resolveTenantId(): string {
  return getCurrentSession()?.tenantId ?? FALLBACK_TENANT_ID;
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      // CR-0114:平台 console 的 refresh 走平台端點（撤銷/狀態查平台庫）;
      // 依目前 session 的 role 判斷（platform token 只會出現在 console session）。
      const isPlatform = getCurrentSession()?.role === "platform_admin";
      const res = await apiFetch(
        buildUrl(isPlatform ? "/api/v1/platform/auth/refresh" : "/api/v1/auth/refresh"),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Auth-Response-Mode": "cookie",
          },
          body: JSON.stringify({}),
        },
      );
      if (!res.ok) return false;
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

// Session 失效（access + refresh cookie 皆過期/無效）→ 清 claims 並導登入。
// AuthGuard 會 bootstrap；API 層仍統一承接並發 401，避免頁面白屏。
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

  let res = await apiFetch(buildUrl(path, options.query), init);

  if (res.status === 401 && !options.skipAuth) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) (init.headers as Record<string, string>)["Authorization"] = `Bearer ${newToken}`;
      res = await apiFetch(buildUrl(path, options.query), init);
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
    const result = await rawRequest<T>(method, path, options);
    // 寫入成功後清 GET 快取：mutate→refetch 是常見模式，不清則 30s staleTime 內的
    // refetch 會讀到 mutate 前的舊資料（如 admin/staff 核准後畫面不更新）。此處自動化
    // 既有慣例（原各頁須手動 cacheInvalidate("GET:")），杜絕漏清 footgun。
    if (method !== "GET") cacheInvalidate("GET:");
    return result;
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

  let res = await apiFetch(buildUrl(path), { method: "POST", headers, body: formData });

  if (res.status === 401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
      res = await apiFetch(buildUrl(path), { method: "POST", headers, body: formData });
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

  let res = await apiFetch(buildUrl(path, opts?.query), { method: "GET", headers });

  if (res.status === 401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
      res = await apiFetch(buildUrl(path, opts?.query), { method: "GET", headers });
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

  let res = await apiFetch(buildUrl(path), { method: "GET", headers });

  if (res.status === 401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
      res = await apiFetch(buildUrl(path), { method: "GET", headers });
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

  let res = await apiFetch(buildUrl(path), init);

  if (res.status === 401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) (init.headers as Record<string, string>)["Authorization"] = `Bearer ${newToken}`;
      res = await apiFetch(buildUrl(path), init);
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
    authenticated?: boolean;
    access_token?: string;
    refresh_token?: string;
    token_type: string;
    expires_in: number;
  };
  message?: string;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  auth.clear();
  const res = await request<LoginResponse>("POST", "/api/v1/auth/login", {
    body: { email, password },
    skipAuth: true,
    headers: { "X-Auth-Response-Mode": "cookie" },
  });
  if (!(await bootstrapSession())) throw new Error("Cookie session bootstrap failed");
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
  auth.clear();
  const res = await request<LoginResponse>("POST", "/api/v1/technicians/login", {
    body: { identifier: identifier.trim(), password },
    skipAuth: true,
    headers: { "X-Auth-Response-Mode": "cookie" },
  });
  if (!(await bootstrapSession())) throw new Error("Cookie session bootstrap failed");
  auth.setEmail(identifier);
  return res;
}

// 廠商/品牌商登入走專用端點 POST /api/v1/vendors/login（CR-0029；role=vendor，
// 與後台角色隔離）。回傳同 admin/technician 信封。
export async function loginVendor(
  email: string,
  password: string,
): Promise<LoginResponse> {
  auth.clear();
  const res = await request<LoginResponse>("POST", "/api/v1/vendors/login", {
    body: { email, password },
    skipAuth: true,
    headers: { "X-Auth-Response-Mode": "cookie" },
  });
  if (!(await bootstrapSession())) throw new Error("Cookie session bootstrap failed");
  auth.setEmail(email);
  return res;
}

// 平台管理員登入（CR-0114;role=platform_admin,與品牌/技師完全隔離,
// console 專用端點 + 平台庫帳號池）。回傳同 admin/technician 信封。
export async function loginPlatformAdmin(
  email: string,
  password: string,
): Promise<LoginResponse> {
  auth.clear();
  const res = await request<LoginResponse>("POST", "/api/v1/platform/auth/login", {
    body: { email, password },
    skipAuth: true,
    headers: { "X-Auth-Response-Mode": "cookie" },
  });
  if (!(await bootstrapSession())) throw new Error("Cookie session bootstrap failed");
  auth.setEmail(email);
  return res;
}

// 平台管理員登出（撤銷寫平台庫 revoked_jti）
export async function logoutPlatformAdmin(): Promise<void> {
  try {
    await request("POST", "/api/v1/platform/auth/logout", {
      body: {},
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
  try {
    await request("POST", "/api/v1/auth/logout", {
      body: {},
    });
  } catch {
    // ignore — clear local state regardless
  } finally {
    auth.clear();
    // 清掉所有 GET cache，避免下次登入讀到上一個帳號的資料
    cacheClear();
  }
}
