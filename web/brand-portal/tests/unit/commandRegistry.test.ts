import { describe, expect, it } from "vitest";

import {
  commandsForContext,
  filterCommands,
  nextCommandIndex,
} from "../../src/lib/commandRegistry";

describe("capability-driven command registry", () => {
  it("dispatcher 可見派工佇列，customer service 不可見", () => {
    const dispatcher = commandsForContext({
      role: "dispatcher",
      tenantId: "tenant-1",
    });
    const customerService = commandsForContext({
      role: "customer_service",
      tenantId: "tenant-1",
    });

    expect(dispatcher.some((item) => item.command_id === "dispatch.queue")).toBe(
      true,
    );
    expect(
      customerService.some((item) => item.command_id === "dispatch.queue"),
    ).toBe(false);
  });

  it("tenant context 缺失時不顯示 tenant-scoped command", () => {
    const commands = commandsForContext({
      role: "admin",
      tenantId: null,
    });
    expect(commands.map((item) => item.command_id)).toEqual([
      "notifications.open",
    ]);
  });

  it("saved view 仍受 capability 與 route policy 約束", () => {
    const views = [
      { id: "mine", label: "我的工單", route: "/work-orders?owner=me" },
      { id: "roles", label: "角色治理", route: "/admin/roles" },
    ];
    const customerService = commandsForContext(
      { role: "customer_service", tenantId: "tenant-1" },
      views,
    );
    expect(
      customerService.some((item) => item.command_id === "saved-view.mine"),
    ).toBe(true);
    expect(
      customerService.some((item) => item.command_id === "saved-view.roles"),
    ).toBe(false);
  });

  it("搜尋與環狀鍵盤選擇為 deterministic", () => {
    const commands = commandsForContext({
      role: "admin",
      tenantId: "tenant-1",
    });
    expect(filterCommands(commands, "問題卡").length).toBeGreaterThan(0);
    expect(nextCommandIndex(0, -1, 3)).toBe(2);
    expect(nextCommandIndex(2, 1, 3)).toBe(0);
  });
});
