/** Build-once promotion：瀏覽器走本站 proxy；server 端讀 runtime env。 */
export function apiBaseUrl(): string {
  const baked = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (baked) return baked.replace(/\/+$/, "");
  if (typeof window !== "undefined") {
    return `${window.location.origin}/api-proxy`;
  }
  return (process.env["API_BASE_URL"] || "http://localhost:8001").replace(
    /\/+$/,
    "",
  );
}

export function platformApiBaseUrl(): string {
  const baked = process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL?.trim();
  if (baked) return baked.replace(/\/+$/, "");
  if (typeof window !== "undefined") {
    return `${window.location.origin}/platform-api-proxy`;
  }
  return (
    process.env["PLATFORM_API_BASE_URL"] ||
    process.env["API_BASE_URL"] ||
    "http://localhost:8003"
  ).replace(/\/+$/, "");
}
