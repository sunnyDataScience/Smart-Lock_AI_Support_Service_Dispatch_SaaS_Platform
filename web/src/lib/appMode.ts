// 部署模式(CR-0112 師傅端/派工方雙 stack 拆分):
//   all(預設)— 單一部署同時服務兩端(既有行為,未設 env 時零影響)
//   dispatch — 派工方 stack:師傅工作台路由不在此部署,導向對方 portal
//   tech     — 師傅 stack:只留師傅端路由與必要公開頁,其餘導向對方 portal
// NEXT_PUBLIC_* 於 next build 時烤入 bundle(web/Dockerfile ARG),runtime 不可改。
export type AppMode = "all" | "dispatch" | "tech";

const raw = process.env.NEXT_PUBLIC_APP_MODE || "all";
export const APP_MODE: AppMode =
  raw === "tech" || raw === "dispatch" ? raw : "all";

// 對方 portal 絕對 URL(如 http://localhost:3001);空字串 = 未配置,退回站內路由。
export const PEER_PORTAL_URL = (
  process.env.NEXT_PUBLIC_PEER_PORTAL_URL || ""
).replace(/\/+$/, "");

// 師傅工作台路由(需要 technician 登入態的頁面;/tech-login 為入口頁另計)
const TECH_APP_PREFIXES = ["/home", "/pool", "/my-orders", "/account"];

// tech build 保留的路徑(師傅端 + 必要公開頁;token 公開頁屬派工方 web 服務)
const TECH_BUILD_ALLOWED = [
  "/",
  "/tech-login",
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
 * 注意:dispatch build 保留 /tech-login 當優雅入口(誤入者仍可登入,
 * landing/登入頁的師傅連結會優先指向 PEER_PORTAL_URL)。
 */
export function crossModeRedirect(pathname: string): string | null {
  if (APP_MODE === "all") return null;
  if (APP_MODE === "dispatch") {
    if (TECH_APP_PREFIXES.some((p) => matchPrefix(pathname, p))) {
      return PEER_PORTAL_URL ? `${PEER_PORTAL_URL}${pathname}` : "/";
    }
    return null;
  }
  // tech build
  if (TECH_BUILD_ALLOWED.some((p) => matchPrefix(pathname, p))) return null;
  return PEER_PORTAL_URL ? `${PEER_PORTAL_URL}${pathname}` : "/tech-login";
}
