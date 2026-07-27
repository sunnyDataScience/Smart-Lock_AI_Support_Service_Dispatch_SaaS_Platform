export type CapabilityId = `${string}.${"read" | "create" | "update" | "delete" | "execute"}`;

export interface CapabilityContext {
  role: string | null;
  tenantId: string | null;
}

export interface CapabilityRequirement<TCapability extends string = CapabilityId> {
  requiredCapability: TCapability;
  contextRequirement: "authenticated" | "tenant";
}

export function hasCapability<TCapability extends string>(
  grants: ReadonlySet<TCapability>,
  requirement: CapabilityRequirement<TCapability>,
  context: CapabilityContext,
): boolean {
  if (!context.role || !grants.has(requirement.requiredCapability)) return false;
  return requirement.contextRequirement !== "tenant" || Boolean(context.tenantId);
}
