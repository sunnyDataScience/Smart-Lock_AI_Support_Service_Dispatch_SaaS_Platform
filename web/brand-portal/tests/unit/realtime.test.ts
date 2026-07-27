/**
 * lib/realtime 單元測試（UAT R3-4 / R3-5 realtime 收斂回歸）。
 *
 * 驗證三個 UAT 場景：
 *   1. access token 不進 WebSocket URL，認證只走 HttpOnly cookie
 *   2. 握手失敗（未 open 即斷）→ 先走 refresh 換新 token 再重連
 *   3. 同 channel 單一活躍連線 + handler 註冊表（StrictMode 雙掛載 / 斷線恢復
 *      後 handler 依然觸發）
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const authMock = {
  getAccessToken: vi.fn<() => string | null>(() => "token-1"),
  getTenantId: vi.fn<() => string | null>(() => "tenant-1"),
};
const tryRefreshMock = vi.fn(async () => true);

vi.mock("@/lib/api", () => ({
  auth: authMock,
  tryRefreshAccessToken: tryRefreshMock,
}));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  closedByClient = false;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
  close() {
    this.closedByClient = true;
    this.onclose?.();
  }
  // 測試輔助：模擬 server 端事件
  serverOpen() {
    this.onopen?.();
  }
  serverMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
  serverDrop() {
    this.onclose?.();
  }
}

async function importRealtime() {
  vi.resetModules();
  return await import("@/lib/realtime");
}

describe("subscribeRealtime（UAT R3 realtime 收斂）", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubEnv("NEXT_PUBLIC_REALTIME_BASE_URL", "ws://rt.test");
    vi.stubGlobal("WebSocket", FakeWebSocket);
    FakeWebSocket.instances = [];
    authMock.getAccessToken.mockReturnValue("token-1");
    authMock.getTenantId.mockReturnValue("tenant-1");
    tryRefreshMock.mockClear();
    tryRefreshMock.mockResolvedValue(true);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("R3-5：重連 URL 不洩漏 access token", async () => {
    const rt = await importRealtime();
    rt.subscribeRealtime({ channelPath: "/realtime/x", onMessage: () => {} });

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).not.toContain("access_token");
    expect(FakeWebSocket.instances[0].url).toContain("tenant_id=tenant-1");

    // REST refresh 後 server 斷線 → cookie 由瀏覽器自動帶入重連。
    FakeWebSocket.instances[0].serverOpen();
    authMock.getAccessToken.mockReturnValue("token-2");
    FakeWebSocket.instances[0].serverDrop();
    await vi.advanceTimersByTimeAsync(1000); // backoff 第一階 1s

    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[1].url).not.toContain("access_token");
  });

  it("R3-5：握手失敗（未 open 即關）→ 先 refresh 再重連", async () => {
    const rt = await importRealtime();
    rt.subscribeRealtime({ channelPath: "/realtime/x", onMessage: () => {} });

    // 未 serverOpen 直接斷 = 握手 403 情境
    FakeWebSocket.instances[0].serverDrop();
    expect(tryRefreshMock).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1000);

    expect(tryRefreshMock).toHaveBeenCalledTimes(1);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("R3-4：同 channel 共用單一連線，多 handler 都觸發", async () => {
    const rt = await importRealtime();
    const seenA: unknown[] = [];
    const seenB: unknown[] = [];
    rt.subscribeRealtime({
      channelPath: "/realtime/x",
      onMessage: (m) => seenA.push(m),
    });
    rt.subscribeRealtime({
      channelPath: "/realtime/x",
      onMessage: (m) => seenB.push(m),
    });

    expect(FakeWebSocket.instances).toHaveLength(1);
    FakeWebSocket.instances[0].serverOpen();
    FakeWebSocket.instances[0].serverMessage({ type: "ping" });

    expect(seenA).toHaveLength(1);
    expect(seenB).toHaveLength(1);
  });

  it("R3-4：StrictMode 快速退訂重掛 → 重用同一連線不產生殭屍 socket", async () => {
    const rt = await importRealtime();
    const seen: unknown[] = [];
    const unsub = rt.subscribeRealtime({
      channelPath: "/realtime/x",
      onMessage: () => {},
    });
    FakeWebSocket.instances[0].serverOpen();

    unsub(); // StrictMode cleanup
    rt.subscribeRealtime({
      channelPath: "/realtime/x",
      onMessage: (m) => seen.push(m),
    }); // 立即重掛（linger 250ms 內）

    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].closedByClient).toBe(false);

    // 斷線恢復後 handler 依然觸發
    FakeWebSocket.instances[0].serverDrop();
    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);
    FakeWebSocket.instances[1].serverOpen();
    FakeWebSocket.instances[1].serverMessage({ type: "after-reconnect" });
    expect(seen).toHaveLength(1);
  });

  it("最後一個訂閱者退訂 → linger 後才拆線", async () => {
    const rt = await importRealtime();
    const unsub = rt.subscribeRealtime({
      channelPath: "/realtime/x",
      onMessage: () => {},
    });
    FakeWebSocket.instances[0].serverOpen();

    unsub();
    expect(FakeWebSocket.instances[0].closedByClient).toBe(false);
    await vi.advanceTimersByTimeAsync(250);
    expect(FakeWebSocket.instances[0].closedByClient).toBe(true);
    // 拆線後不再重連
    await vi.advanceTimersByTimeAsync(30000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("斷線時 status listener 收到 closed（指示燈真實回報）", async () => {
    const rt = await importRealtime();
    const statuses: string[] = [];
    rt.subscribeRealtime({
      channelPath: "/realtime/x",
      onMessage: () => {},
      onStatusChange: (s) => statuses.push(s),
    });
    FakeWebSocket.instances[0].serverOpen();
    FakeWebSocket.instances[0].serverDrop();
    expect(statuses).toEqual(["connecting", "open", "closed"]);
  });
});
