import { NextRequest } from "next/server";

const REQUEST_HOP_HEADERS = ["host", "content-length", "connection"];
const RESPONSE_HOP_HEADERS = ["content-length", "content-encoding", "transfer-encoding", "connection"];

export async function proxyApiRequest(
  request: NextRequest,
  path: readonly string[],
  targetEnv: "API_BASE_URL" | "PLATFORM_API_BASE_URL",
): Promise<Response> {
  const base = process.env[targetEnv]?.trim();
  if (!base || !/^https?:\/\//.test(base)) {
    return Response.json(
      { error_code: "API_PROXY_NOT_CONFIGURED", message: `${targetEnv} is required` },
      { status: 503 },
    );
  }
  const target = new URL(path.map(encodeURIComponent).join("/"), `${base.replace(/\/+$/, "")}/`);
  target.search = request.nextUrl.search;
  const headers = new Headers(request.headers);
  REQUEST_HOP_HEADERS.forEach((name) => headers.delete(name));
  headers.set("x-forwarded-host", request.nextUrl.host);
  headers.set("x-forwarded-proto", request.nextUrl.protocol.replace(":", ""));
  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body,
    redirect: "manual",
    cache: "no-store",
  });
  const responseHeaders = new Headers(upstream.headers);
  RESPONSE_HOP_HEADERS.forEach((name) => responseHeaders.delete(name));
  const setCookies = (
    upstream.headers as Headers & { getSetCookie?: () => string[] }
  ).getSetCookie?.();
  if (setCookies?.length) {
    responseHeaders.delete("set-cookie");
    for (const value of setCookies) responseHeaders.append("set-cookie", value);
  }
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
