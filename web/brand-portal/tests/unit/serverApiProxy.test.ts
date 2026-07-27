import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { proxyApiRequest } from "@/lib/serverApiProxy";

describe("runtime API proxy", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("forwards cookies and preserves both HttpOnly Set-Cookie headers", async () => {
    vi.stubEnv("API_BASE_URL", "https://api.staging.example");
    let upstreamUrl = "";
    let upstreamCookie: string | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const upstreamRequest = new Request(input, init);
        upstreamUrl = upstreamRequest.url;
        upstreamCookie = upstreamRequest.headers.get("cookie");
        const headers = new Headers();
        headers.append(
          "set-cookie",
          "smartlock_access_token=access; Path=/; HttpOnly; SameSite=Lax",
        );
        headers.append(
          "set-cookie",
          "smartlock_refresh_token=refresh; Path=/; HttpOnly; SameSite=Lax",
        );
        return new Response('{"data":{}}', {
          status: 200,
          headers,
        });
      }),
    );

    const response = await proxyApiRequest(
      new NextRequest("https://web.example/api-proxy/api/v1/auth/refresh", {
        method: "POST",
        headers: {
          cookie: "smartlock_refresh_token=old",
          "content-type": "application/json",
        },
        body: "{}",
      }),
      ["api", "v1", "auth", "refresh"],
      "API_BASE_URL",
    );

    expect(upstreamUrl).toBe(
      "https://api.staging.example/api/v1/auth/refresh",
    );
    expect(upstreamCookie).toBe("smartlock_refresh_token=old");
    const cookies = (
      response.headers as Headers & { getSetCookie: () => string[] }
    ).getSetCookie();
    expect(cookies).toHaveLength(2);
    expect(cookies[0]).toContain("smartlock_access_token=");
    expect(cookies[1]).toContain("smartlock_refresh_token=");
  });
});
