// OIDC 授權碼流薄回調(WBS 2.1.1-R2/CR-0146/ADR-024)。
//
// ADR-024:唯一的 server-side 認證 handler(非 BFF)——用 code 換 token、
// 寫 httpOnly cookie(JS 不可讀;api 端 R1 已支援 cookie 來源,CR-0141 D5),
// 資料 API 仍瀏覽器直連。過渡期雙寫:token 同時經 fragment(#)交給
// /auth/sso-complete 存 localStorage(既有 30+ 頁同步 getCurrentSession 依賴;
// localStorage 退場=ACT-01 R3)。fragment 不入 server log/Referer。
//
// server-side env(不烤入 bundle):CASDOOR_ENDPOINT / CASDOOR_CLIENT_ID /
// CASDOOR_CLIENT_SECRET。未配置 → 503(SSO 未啟用)。

import { NextRequest, NextResponse } from "next/server";

const COOKIE_NAME = "smartlock_access_token"; // 對齊 api core/deps._ACCESS_TOKEN_COOKIE

export async function GET(request: NextRequest) {
  const endpoint = process.env.CASDOOR_ENDPOINT?.replace(/\/$/, "");
  const clientId = process.env.CASDOOR_CLIENT_ID;
  const clientSecret = process.env.CASDOOR_CLIENT_SECRET;
  if (!endpoint || !clientId || !clientSecret) {
    return NextResponse.json(
      { error: "SSO 未啟用(CASDOOR_* env 未配置)" }, { status: 503 });
  }

  const code = request.nextUrl.searchParams.get("code");
  if (!code) {
    return NextResponse.redirect(new URL("/platform/login?sso_error=missing_code", request.url));
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: clientId,
    client_secret: clientSecret,
    code,
  });
  let tokenResp: Response;
  try {
    tokenResp = await fetch(`${endpoint}/api/login/oauth/access_token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.redirect(new URL("/platform/login?sso_error=idp_unreachable", request.url));
  }
  const data = await tokenResp.json().catch(() => ({}));
  const accessToken: string | undefined = data.access_token;
  const refreshToken: string | undefined = data.refresh_token;
  if (!tokenResp.ok || !accessToken) {
    return NextResponse.redirect(new URL("/platform/login?sso_error=exchange_failed", request.url));
  }

  // 雙寫:httpOnly cookie(ACT-01 目標態)+ fragment 交 client 存 localStorage(過渡)
  const fragment = new URLSearchParams({
    access_token: accessToken,
    ...(refreshToken ? { refresh_token: refreshToken } : {}),
  });
  const res = NextResponse.redirect(
    new URL(`/auth/sso-complete#${fragment.toString()}`, request.url));
  res.cookies.set(COOKIE_NAME, accessToken, {
    httpOnly: true,
    sameSite: "lax",       // CSRF 緩解(CR-0141 D5;另有 X-Tenant-ID 自訂 header 防線)
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 3600,          // 對齊 Casdoor application expireInHours=1
  });
  return res;
}
