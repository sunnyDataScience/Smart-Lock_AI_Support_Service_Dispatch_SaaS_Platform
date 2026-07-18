/**
 * lib/format 單元測試（UAT round2 W1-5 / W6-6 回歸）。
 *
 * - formatTwd：帳務域統一「NT$ 3,825」整數格式（無 TWD 前綴、無小數）
 * - formatRelative：相對時間依 locale 輸出（en 用 "1 hour ago" 類）
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { formatRelative, formatTwd } from "../../src/lib/format";

describe("formatTwd（UAT W1-5 幣別統一）", () => {
  it("字串金額 → NT$ 千分位整數", () => {
    expect(formatTwd("3825")).toBe("NT$ 3,825");
    expect(formatTwd("3825.00")).toBe("NT$ 3,825");
  });

  it("數字金額同樣格式化", () => {
    expect(formatTwd(1234567)).toBe("NT$ 1,234,567");
  });

  it("null / undefined / 空字串 → —", () => {
    expect(formatTwd(null)).toBe("—");
    expect(formatTwd(undefined)).toBe("—");
    expect(formatTwd("")).toBe("—");
  });

  it("非數字字串 fail-soft 原樣帶出", () => {
    expect(formatTwd("abc")).toBe("NT$ abc");
  });
});

describe("formatRelative（UAT W6-6 locale 化）", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("zh-TW 輸出中文相對時間", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-18T12:00:00Z"));
    expect(formatRelative("2026-07-18T11:58:00Z", "zh-TW")).toBe("2 分鐘前");
    expect(formatRelative("2026-07-18T10:00:00Z", "zh-TW")).toBe("2 小時前");
    expect(formatRelative("2026-07-16T12:00:00Z", "zh-TW")).toBe("2 天前");
    expect(formatRelative("2026-07-18T11:59:50Z", "zh-TW")).toBe("剛剛");
  });

  it("en 輸出英文相對時間（含單複數）", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-18T12:00:00Z"));
    expect(formatRelative("2026-07-18T11:59:00Z", "en")).toBe("1 minute ago");
    expect(formatRelative("2026-07-18T11:58:00Z", "en")).toBe("2 minutes ago");
    expect(formatRelative("2026-07-18T11:00:00Z", "en")).toBe("1 hour ago");
    expect(formatRelative("2026-07-17T12:00:00Z", "en")).toBe("1 day ago");
    expect(formatRelative("2026-07-18T11:59:50Z", "en")).toBe("just now");
  });

  it("未傳 locale 時（無 window）fallback 預設 zh-TW", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-18T12:00:00Z"));
    expect(formatRelative("2026-07-18T11:58:00Z")).toBe("2 分鐘前");
  });

  it("無效 ISO 原樣回傳", () => {
    expect(formatRelative("not-a-date", "en")).toBe("not-a-date");
  });
});
