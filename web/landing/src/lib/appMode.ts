// 部署模式(CR-0112 師傅端/派工方雙 stack 拆分 + landing 獨立容器 + CR-0114 platform):
//   all(預設)— 單一部署同時服務兩端(既有行為,未設 env 時零影響)
//   dispatch — 派工方 stack:師傅工作台路由不在此部署,導向對方 portal
//   tech     — 師傅 stack:只留師傅端路由與必要公開頁,其餘導向對方 portal
//   landing  — 公開行銷一頁式:只渲染 `/`,其餘導向派工 portal;
//              CTA 以絕對 URL 指向師傅/派工 portal(NEXT_PUBLIC_TECH/DISPATCH_PORTAL_URL)
//   platform — 平台方 console:只渲染 /platform 頁群(平台管理員自用)
// NEXT_PUBLIC_* 於 next build 時烤入 bundle(web/Dockerfile ARG),runtime 不可改。
import { platformApiBaseUrl } from "./runtimeConfig";
export type AppMode = "all" | "dispatch" | "tech" | "landing" | "platform";

const raw = process.env.NEXT_PUBLIC_APP_MODE || "all";
export const APP_MODE: AppMode =
  raw === "tech" || raw === "dispatch" || raw === "landing" || raw === "platform"
    ? raw
    : "all";

// 對方 portal 絕對 URL(dispatch↔tech 配對用;如 http://localhost:3001);
// 空字串 = 未配置,退回站內路由。
export const PEER_PORTAL_URL = (
  process.env.NEXT_PUBLIC_PEER_PORTAL_URL || ""
).replace(/\/+$/, "");

// landing 容器專用:師傅 / 派工方 portal 絕對 URL(landing 無登入態,CTA 一律外導)。
export const TECH_PORTAL_URL = (
  process.env.NEXT_PUBLIC_TECH_PORTAL_URL || ""
).replace(/\/+$/, "");
export const DISPATCH_PORTAL_URL = (
  process.env.NEXT_PUBLIC_DISPATCH_PORTAL_URL || ""
).replace(/\/+$/, "");

// landing 品牌申請表單直打 platform API(CR-0114 R2;瀏覽器端,
// 與 NEXT_PUBLIC_API_BASE_URL(品牌 api)分開 —— 申請歸平台方管)。
export const PLATFORM_API_BASE_URL = platformApiBaseUrl();

// landing 容器專用:平台 console 絕對 URL(品牌申請導入頁移到 platform 站
// /platform/apply,landing 品牌 CTA 以絕對 URL 外導;如 http://localhost:3003)。
export const PLATFORM_PORTAL_URL = (
  process.env.NEXT_PUBLIC_PLATFORM_PORTAL_URL || "http://localhost:3003"
).replace(/\/+$/, "");

// 師傅工作台路由(需要 technician 登入態的頁面;/tech-login 為入口頁另計)
const TECH_APP_PREFIXES = ["/home", "/pool", "/my-orders", "/account"];

// tech build 保留的路徑(師傅端 + 必要公開頁;token 公開頁屬派工方 web 服務)
const TECH_BUILD_ALLOWED = [
  "/",
  "/tech-login",
  "/tech-register", // CR-0115 師傅 KYC 註冊獨立頁
  "/forgot-password",
  "/reset-password",
  ...TECH_APP_PREFIXES,
];

function matchPrefix(pathname: string, prefix: string): boolean {
  if (prefix === "/") return pathname === "/";
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/**
 * 目前 build 是否允許此路徑。
 * 不允許 → 回傳應導向的目標(站內路由,或對方 portal 的絕對 URL);允許 → null。
 */
export function crossModeRedirect(pathname: string): string | null {
  if (APP_MODE === "all") return null;
  if (APP_MODE === "platform") {
    // 平台 console 只服務 /platform 頁群;其餘一律導 console 登入頁。
    if (matchPrefix(pathname, "/platform")) return null;
    return "/platform/login";
  }
  if (APP_MODE === "landing") {
    // 行銷容器只服務 `/`;其餘一律導派工 portal(未配置則回站內首頁)。
    if (pathname === "/") return null;
    return DISPATCH_PORTAL_URL ? `${DISPATCH_PORTAL_URL}${pathname}` : "/";
  }
  if (APP_MODE === "dispatch") {
    // 品牌 stack 首頁不渲染對外導流 landing(導流站 = landing 容器 3002):
    // 一律進品牌登入;已登入者由 AuthGuard `token && isPublic` 分支依角色送 /dashboard
    // (2026-07-05 業主裁決:消除 3000 與 3002 landing 重複 + 品牌後台入口誤放師父 CTA)。
    if (pathname === "/") return "/login";
    // /platform 屬平台 console 部署,品牌 build 不服務(deny-by-default 回登入)。
    if (matchPrefix(pathname, "/platform")) return "/login";
    // CR-0114 收斂:師傅 KYC 註冊頁屬 tech 站(師傅身分歸平台方)。品牌 build
    // 不服務 —— 否則表單會 POST 品牌 API,在品牌庫產生平台 console 看不到的
    // 「幽靈師傅」。導對方 tech portal 同路徑。
    if (matchPrefix(pathname, "/tech-register")) {
      return PEER_PORTAL_URL ? `${PEER_PORTAL_URL}${pathname}` : "/login";
    }
    if (TECH_APP_PREFIXES.some((p) => matchPrefix(pathname, p))) {
      return PEER_PORTAL_URL ? `${PEER_PORTAL_URL}${pathname}` : "/login";
    }
    return null;
  }
  // tech build(/platform 不在 TECH_BUILD_ALLOWED → 自然導出)
  if (TECH_BUILD_ALLOWED.some((p) => matchPrefix(pathname, p))) return null;
  return PEER_PORTAL_URL ? `${PEER_PORTAL_URL}${pathname}` : "/tech-login";
}

// ── landing / 跨端 CTA href 解析(集中處,各頁共用)──────────────────────
// 師傅註冊入口:landing → TECH_PORTAL_URL;dispatch(配 PEER)→ 對方 portal;
// 其餘 → 站內。
export function techRegisterHref(): string {
  const base =
    APP_MODE === "landing"
      ? TECH_PORTAL_URL
      : APP_MODE === "dispatch"
        ? PEER_PORTAL_URL
        : "";
  // CR-0115：師傅註冊改獨立多步驟頁 /tech-register（原 /tech-login?tab=register 退場）
  return `${base}/tech-register`;
}

// 派工方登入入口:landing → DISPATCH_PORTAL_URL;其餘 → 站內 /login。
export function dispatchLoginHref(): string {
  const base = APP_MODE === "landing" ? DISPATCH_PORTAL_URL : "";
  return `${base}/login`;
}

// 品牌/經銷/鎖店「申請導入平台」入口:landing → PLATFORM_PORTAL_URL 的
// /platform/apply(公開頁,平台方管);平台站內本身用相對路徑;其餘部署退回站內。
export function brandApplyHref(): string {
  const base = APP_MODE === "landing" ? PLATFORM_PORTAL_URL : "";
  return `${base}/platform/apply`;
}
