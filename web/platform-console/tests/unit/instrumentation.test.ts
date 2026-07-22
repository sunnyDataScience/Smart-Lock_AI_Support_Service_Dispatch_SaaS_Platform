/**
 * src/instrumentation.ts 單元測試（CR-0156 / ADR-007 可觀測性補課）。
 *
 * 驗證範式三鐵律（比照 api/core/observability.py）：
 *   1. opt-in：OTEL_EXPORTER_OTLP_ENDPOINT 未設＝完全 no-op（連套件都不 import）
 *   2. 設定時：registerOTel 以正確 serviceName 被呼叫
 *   3. 任何失敗（import 失敗 / registerOTel throw）＝降級 no-op + warning，絕不 throw
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 追蹤 mock 模組工廠是否被執行——用來證明「env 未設時連 import 都不發生」
let factoryCalls = 0;
const registerOTelMock = vi.fn();

/** 每個測試重置模組快取後再載入 SUT，確保動態 import 吃到當前 mock。 */
async function loadRegister(): Promise<() => Promise<void>> {
  const mod = await import("../../src/instrumentation");
  return mod.register;
}

describe("instrumentation register()（OTLP opt-in）", () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.resetModules();
    factoryCalls = 0;
    registerOTelMock.mockReset();
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    // 預設 mock：@vercel/otel 正常存在
    vi.doMock("@vercel/otel", () => {
      factoryCalls += 1;
      return { registerOTel: registerOTelMock };
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    warnSpy.mockRestore();
    vi.doUnmock("@vercel/otel");
  });

  it("env 未設 → 完全 no-op（不 import 套件、不呼叫 registerOTel、不 warn）", async () => {
    vi.stubEnv("OTEL_EXPORTER_OTLP_ENDPOINT", undefined);
    const register = await loadRegister();

    await expect(register()).resolves.toBeUndefined();

    expect(factoryCalls).toBe(0); // 連動態 import 都沒發生
    expect(registerOTelMock).not.toHaveBeenCalled();
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it("env 為空白字串 → 視同未設（trim 後 no-op）", async () => {
    vi.stubEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "   ");
    const register = await loadRegister();

    await register();

    expect(factoryCalls).toBe(0);
    expect(registerOTelMock).not.toHaveBeenCalled();
  });

  it("env 設定 → registerOTel 以預設 serviceName=platform-console 呼叫", async () => {
    vi.stubEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318");
    vi.stubEnv("OTEL_SERVICE_NAME", undefined);
    const register = await loadRegister();

    await register();

    expect(registerOTelMock).toHaveBeenCalledTimes(1);
    expect(registerOTelMock).toHaveBeenCalledWith({ serviceName: "platform-console" });
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it("OTEL_SERVICE_NAME 設定 → 覆寫 serviceName（與 api 同語意）", async () => {
    vi.stubEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318");
    vi.stubEnv("OTEL_SERVICE_NAME", "platform-console-uat");
    const register = await loadRegister();

    await register();

    expect(registerOTelMock).toHaveBeenCalledWith({
      serviceName: "platform-console-uat",
    });
  });

  it("registerOTel throw → 降級 no-op + warning，絕不向外 throw", async () => {
    vi.stubEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318");
    registerOTelMock.mockImplementation(() => {
      throw new Error("collector 連線設定錯誤");
    });
    const register = await loadRegister();

    await expect(register()).resolves.toBeUndefined();

    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(String(warnSpy.mock.calls[0][0])).toContain("降級停用");
  });

  it("@vercel/otel import 失敗（套件缺）→ 降級 no-op + warning，絕不向外 throw", async () => {
    vi.stubEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318");
    // 覆寫 mock：模組工廠 throw ＝ 動態 import reject（套件缺失情境）
    vi.doMock("@vercel/otel", () => {
      throw new Error("Cannot find module '@vercel/otel'");
    });
    const register = await loadRegister();

    await expect(register()).resolves.toBeUndefined();

    expect(registerOTelMock).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });
});
