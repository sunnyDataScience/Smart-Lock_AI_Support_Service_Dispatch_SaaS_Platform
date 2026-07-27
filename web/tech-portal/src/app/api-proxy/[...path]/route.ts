import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/lib/serverApiProxy";

/** Same-origin runtime API proxy. */
export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };
async function handler(request: NextRequest, context: Context) {
  return proxyApiRequest(request, (await context.params).path, "API_BASE_URL");
}
export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE, handler as HEAD };
