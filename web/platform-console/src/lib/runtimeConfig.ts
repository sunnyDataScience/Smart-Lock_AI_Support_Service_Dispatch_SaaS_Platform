/** Build-once promotion：瀏覽器走本站 proxy；server 端讀 runtime env。 */
export function apiBaseUrl(): string {
  const baked = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (baked) return baked.replace(/\/+$/, "");
  if (typeof window !== "undefined") return `${window.location.origin}/api-proxy`;
  return (process.env["API_BASE_URL"] || "http://localhost:8003").replace(/\/+$/, "");
}

export const platformApiBaseUrl = apiBaseUrl;
