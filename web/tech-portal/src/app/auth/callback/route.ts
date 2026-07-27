// OIDC 授權碼流薄回調(WBS 2.1.1-R2/CR-0146/ADR-024)。
//
// ADR-024:server-side code exchange；token 只寫 HttpOnly cookie。
//
// server-side env(不烤入 bundle):CASDOOR_ENDPOINT / CASDOOR_CLIENT_ID /
// CASDOOR_CLIENT_SECRET。未配置 → 503(SSO 未啟用)。

import { NextRequest, NextResponse } from "next/server";

const ACCESS_COOKIE = "smartlock_access_token";
const REFRESH_COOKIE = "smartlock_refresh_token";
const OAUTH_STATE_COOKIE = "smartlock_oauth_state_tech";

function errorRedirect(request: NextRequest, code: string) {
  const response = NextResponse.redirect(
    new URL(`/tech-login?sso_error=${encodeURIComponent(code)}`, request.url),
  );
  response.cookies.set(OAUTH_STATE_COOKIE, "", { path: "/auth", maxAge: 0 });
  return response;
}

export async function GET(request: NextRequest) {
  const endpoint = process.env.CASDOOR_ENDPOINT?.replace(/\/$/, "");
  const clientId = process.env.CASDOOR_CLIENT_ID;
  const clientSecret = process.env.CASDOOR_CLIENT_SECRET;
  if (!endpoint || !clientId || !clientSecret) {
    return NextResponse.json(
      { error: "SSO 未啟用(CASDOOR_* env 未配置)" }, { status: 503 });
  }

  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const expectedState = request.cookies.get(OAUTH_STATE_COOKIE)?.value;
  if (!state || !expectedState || state !== expectedState) {
    return errorRedirect(request, "invalid_state");
  }
  if (!code) {
    return errorRedirect(request, "missing_code");
  }

  const redirectUri = new URL("/auth/callback", request.url).toString();
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: clientId,
    client_secret: clientSecret,
    code,
    redirect_uri: redirectUri,
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
    return errorRedirect(request, "idp_unreachable");
  }
  const data = await tokenResp.json().catch(() => ({}));
  const accessToken: string | undefined = data.access_token;
  const refreshToken: string | undefined = data.refresh_token;
  if (!tokenResp.ok || !accessToken) {
    return errorRedirect(request, "exchange_failed");
  }

  const res = NextResponse.redirect(
    new URL("/auth/sso-complete", request.url));
  res.cookies.set(OAUTH_STATE_COOKIE, "", { path: "/auth", maxAge: 0 });
  res.cookies.set(ACCESS_COOKIE, accessToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 3600,
    domain: process.env.AUTH_COOKIE_DOMAIN || undefined,
  });
  if (refreshToken) {
    res.cookies.set(REFRESH_COOKIE, refreshToken, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 30 * 86400,
      domain: process.env.AUTH_COOKIE_DOMAIN || undefined,
    });
  }
  return res;
}
