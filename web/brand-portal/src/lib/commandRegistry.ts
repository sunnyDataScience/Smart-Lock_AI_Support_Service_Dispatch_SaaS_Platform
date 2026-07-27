import { canAccessRoute } from "./rolePolicy";
import type { SavedView } from "./preferences";
import {
  hasCapability,
  type CapabilityId,
} from "@smartlock/shared-contract/capability";

export type Capability = CapabilityId &
  (
  | "work_orders.read"
  | "problem_cards.read"
  | "problem_cards.create"
  | "dispatch_queue.read"
  | "notifications.read"
  | "saved_views.read"
  );

export interface CommandContext {
  role: string | null;
  tenantId: string | null;
}

export interface CommandDefinition {
  command_id: string;
  label: string;
  keywords: readonly string[];
  route: string;
  required_capability: Capability;
  context_requirement: "authenticated" | "tenant";
  analytics_event: string;
}

const ROLE_CAPABILITIES: Record<string, readonly Capability[]> = {
  admin: [
    "work_orders.read",
    "problem_cards.read",
    "problem_cards.create",
    "dispatch_queue.read",
    "notifications.read",
    "saved_views.read",
  ],
  operations_manager: [
    "work_orders.read",
    "problem_cards.read",
    "problem_cards.create",
    "dispatch_queue.read",
    "notifications.read",
    "saved_views.read",
  ],
  dispatcher: [
    "work_orders.read",
    "problem_cards.read",
    "problem_cards.create",
    "dispatch_queue.read",
    "notifications.read",
    "saved_views.read",
  ],
  customer_service: [
    "work_orders.read",
    "problem_cards.read",
    "problem_cards.create",
    "notifications.read",
    "saved_views.read",
  ],
  reviewer: [
    "work_orders.read",
    "problem_cards.read",
    "notifications.read",
    "saved_views.read",
  ],
};

export const BASE_COMMANDS: readonly CommandDefinition[] = [
  {
    command_id: "work-orders.search",
    label: "搜尋工單",
    keywords: ["工單", "搜尋", "work order"],
    route: "/work-orders?palette=search",
    required_capability: "work_orders.read",
    context_requirement: "tenant",
    analytics_event: "command.work_orders.search",
  },
  {
    command_id: "problem-cards.search",
    label: "搜尋問題卡",
    keywords: ["問題卡", "搜尋", "problem card"],
    route: "/problem-cards?palette=search",
    required_capability: "problem_cards.read",
    context_requirement: "tenant",
    analytics_event: "command.problem_cards.search",
  },
  {
    command_id: "problem-cards.create-draft",
    label: "建立問題卡草稿",
    keywords: ["建立", "草稿", "問題卡"],
    route: "/problem-cards?palette=create",
    required_capability: "problem_cards.create",
    context_requirement: "tenant",
    analytics_event: "command.problem_cards.create_draft",
  },
  {
    command_id: "dispatch.queue",
    label: "切換到派工佇列",
    keywords: ["派工", "佇列", "queue"],
    route: "/admin/dispatch-queue",
    required_capability: "dispatch_queue.read",
    context_requirement: "tenant",
    analytics_event: "command.dispatch.queue",
  },
  {
    command_id: "notifications.open",
    label: "開啟通知中心",
    keywords: ["通知", "notification"],
    route: "/notifications",
    required_capability: "notifications.read",
    context_requirement: "authenticated",
    analytics_event: "command.notifications.open",
  },
];

export function commandsForContext(
  context: CommandContext,
  savedViews: readonly SavedView[] = [],
): CommandDefinition[] {
  const capabilities = new Set(
    context.role ? ROLE_CAPABILITIES[context.role] ?? [] : [],
  );
  const dynamic: CommandDefinition[] = capabilities.has("saved_views.read")
    ? savedViews.map((view) => ({
        command_id: `saved-view.${view.id}`,
        label: `已儲存檢視：${view.label}`,
        keywords: ["檢視", "saved view", view.label],
        route: view.route,
        required_capability: "saved_views.read",
        context_requirement: "tenant",
        analytics_event: "command.saved_view.open",
      }))
    : [];

  return [...BASE_COMMANDS, ...dynamic].filter((command) => {
    if (
      !hasCapability(
        capabilities,
        {
          requiredCapability: command.required_capability,
          contextRequirement: command.context_requirement,
        },
        context,
      )
    ) {
      return false;
    }
    return canAccessRoute(command.route.split("?")[0], context.role);
  });
}

export function filterCommands(
  commands: readonly CommandDefinition[],
  query: string,
): CommandDefinition[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return [...commands];
  return commands.filter((command) =>
    [command.label, ...command.keywords]
      .join(" ")
      .toLocaleLowerCase()
      .includes(normalized),
  );
}

export function nextCommandIndex(
  current: number,
  direction: 1 | -1,
  count: number,
): number {
  if (count <= 0) return 0;
  return (current + direction + count) % count;
}
