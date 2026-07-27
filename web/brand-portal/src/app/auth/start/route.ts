import { randomUUID } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const OAUTH_STATE_COOKIE = "smartlock_oauth_state_dispatch";

export async function GET(request: NextRequest) {
  const endpoint = process.env.CASDOOR_ENDPOINT?.trim().replace(/\/+$/, "");
  const clientId = process.env.CASDOOR_CLIENT_ID?.trim();
  const clientSecret = process.env.CASDOOR_CLIENT_SECRET?.trim();
  if (!endpoint || !clientId || !clientSecret) {
    return NextResponse.json({ error: "SSO_NOT_CONFIGURED" }, { status: 503 });
  }

  const state = randomUUID();
  const redirectUri = new URL("/auth/callback", request.url);
  const authorize = new URL("/login/oauth/authorize", `${endpoint}/`);
  authorize.searchParams.set("client_id", clientId);
  authorize.searchParams.set("response_type", "code");
  authorize.searchParams.set("redirect_uri", redirectUri.toString());
  authorize.searchParams.set("scope", "read");
  authorize.searchParams.set("state", state);

  const response = NextResponse.redirect(authorize);
  response.cookies.set(OAUTH_STATE_COOKIE, state, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/auth",
    maxAge: 600,
  });
  return response;
}
