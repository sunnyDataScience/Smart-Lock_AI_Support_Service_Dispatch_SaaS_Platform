import { describe, expect, it, vi } from "vitest";

import {
  MutationConflictError,
  createMutationAction,
  type MutationStateAdapter,
} from "../../src/lib/mutation";

function stateAdapter<T>(initial: T): MutationStateAdapter<T> & { value: T } {
  return {
    value: initial,
    read() {
      return this.value;
    },
    write(next) {
      this.value = next;
    },
  };
}

describe("createMutationAction", () => {
  it("低風險 optimistic mutation 會先更新，成功後 reconcile 並精準失效", async () => {
    const state = stateAdapter([{ id: "n1", read: false }]);
    let resolve!: (value: { readAt: string }) => void;
    const execute = vi.fn(
      () =>
        new Promise<{ readAt: string }>((done) => {
          resolve = done;
        }),
    );
    const invalidate = vi.fn();
    const action = createMutationAction({
      id: "notification.mark-read",
      mode: "optimistic",
      risk: "notification",
      state,
      optimisticPatch: (items) =>
        items.map((item) => (item.id === "n1" ? { ...item, read: true } : item)),
      execute,
      reconcile: (items, result) =>
        items.map((item) =>
          item.id === "n1" ? { ...item, readAt: result.readAt } : item,
        ),
      invalidateKeys: ["notifications:list", "notifications:unread-count"],
      invalidate,
      actionIdFactory: () => "action-1",
    });

    const pending = action.run();
    expect(state.value).toEqual([{ id: "n1", read: true }]);
    expect(execute).toHaveBeenCalledWith({
      actionId: "action-1",
      attempt: 1,
    });

    resolve({ readAt: "2026-07-27T12:00:00Z" });
    await expect(pending).resolves.toEqual({
      actionId: "action-1",
      result: { readAt: "2026-07-27T12:00:00Z" },
    });
    expect(state.value).toEqual([
      { id: "n1", read: true, readAt: "2026-07-27T12:00:00Z" },
    ]);
    expect(invalidate).toHaveBeenCalledWith([
      "notifications:list",
      "notifications:unread-count",
    ]);
  });

  it.each([
    new TypeError("Failed to fetch"),
    Object.assign(new Error("HTTP 503"), { status: 503 }),
  ])("offline/5xx 失敗會還原 optimistic snapshot", async (error) => {
    const state = stateAdapter({ read: false, unrelated: 7 });
    const action = createMutationAction({
      id: "notification.mark-read",
      mode: "optimistic",
      risk: "notification",
      state,
      optimisticPatch: (current) => ({ ...current, read: true }),
      execute: vi.fn().mockRejectedValue(error),
      actionIdFactory: () => "action-rollback",
    });

    await expect(action.run()).rejects.toBe(error);
    expect(state.value).toEqual({ read: false, unrelated: 7 });
  });

  it("409 會轉成帶 currentVersion 的 MutationConflictError 並 rollback", async () => {
    const state = stateAdapter({ version: 3, value: "old" });
    const apiError = Object.assign(new Error("version mismatch"), {
      status: 409,
      errorCode: "CONCURRENT_MODIFICATION",
      details: { current_version: 4, current: { version: 4, value: "server" } },
    });
    const action = createMutationAction({
      id: "preference.update",
      mode: "optimistic",
      risk: "preference",
      state,
      optimisticPatch: (current) => ({ ...current, value: "local" }),
      execute: vi.fn().mockRejectedValue(apiError),
      actionIdFactory: () => "action-conflict",
    });

    await expect(action.run()).rejects.toMatchObject({
      name: "MutationConflictError",
      actionId: "action-conflict",
      currentVersion: 4,
      current: { version: 4, value: "server" },
    });
    expect(state.value).toEqual({ version: 3, value: "old" });
    expect(MutationConflictError.is(apiError)).toBe(false);
  });

  it("retry 沿用同一 actionId，attempt 遞增", async () => {
    const state = stateAdapter({ enabled: false });
    const execute = vi
      .fn()
      .mockRejectedValueOnce(Object.assign(new Error("HTTP 503"), { status: 503 }))
      .mockResolvedValueOnce({ enabled: true });
    const action = createMutationAction({
      id: "preference.update",
      mode: "optimistic",
      risk: "preference",
      state,
      optimisticPatch: () => ({ enabled: true }),
      execute,
      actionIdFactory: () => "stable-action-id",
    });

    await expect(action.run()).rejects.toThrow("HTTP 503");
    await expect(action.retry()).resolves.toEqual({
      actionId: "stable-action-id",
      result: { enabled: true },
    });
    expect(execute.mock.calls).toEqual([
      [{ actionId: "stable-action-id", attempt: 1 }],
      [{ actionId: "stable-action-id", attempt: 2 }],
    ]);
  });

  it("server-confirmed 在伺服器成功前不修改 state", async () => {
    const state = stateAdapter({ approved: false });
    let resolve!: (value: { approved: boolean }) => void;
    const action = createMutationAction({
      id: "quote.approve",
      mode: "server-confirmed",
      risk: "quote",
      state,
      execute: () =>
        new Promise<{ approved: boolean }>((done) => {
          resolve = done;
        }),
      reconcile: (_current, result) => result,
      actionIdFactory: () => "quote-action",
    });

    const pending = action.run();
    expect(state.value).toEqual({ approved: false });
    resolve({ approved: true });
    await pending;
    expect(state.value).toEqual({ approved: true });
  });

  it("runtime 也會拒絕把敏感操作偽裝成 optimistic", () => {
    const state = stateAdapter({ approved: false });
    expect(() =>
      createMutationAction({
        id: "quote.approve",
        mode: "optimistic",
        risk: "quote",
        state,
        optimisticPatch: () => ({ approved: true }),
        execute: async () => ({ approved: true }),
      } as never),
    ).toThrow(/server-confirmed/);
  });
});
