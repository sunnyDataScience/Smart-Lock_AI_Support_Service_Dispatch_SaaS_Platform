/** Runtime-only SSO capability; never exposes endpoint, client ID, or secret. */
export const dynamic = "force-dynamic";

export async function GET() {
  const enabled = Boolean(
    process.env.CASDOOR_ENDPOINT?.trim() &&
      process.env.CASDOOR_CLIENT_ID?.trim() &&
      process.env.CASDOOR_CLIENT_SECRET?.trim(),
  );
  return Response.json(
    { enabled },
    { headers: { "Cache-Control": "no-store, private" } },
  );
}
