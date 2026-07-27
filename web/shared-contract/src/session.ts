export type Portal = "brand" | "tech" | "platform" | "landing";

export interface SessionClaims {
  userId: string;
  role: string;
  tenantId: string | null;
  email?: string | null;
  portal: Portal;
  expiresAt?: number;
}

export function isSessionClaims(value: unknown): value is SessionClaims {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.userId === "string" &&
    typeof record.role === "string" &&
    (typeof record.tenantId === "string" || record.tenantId === null) &&
    ["brand", "tech", "platform", "landing"].includes(String(record.portal))
  );
}
