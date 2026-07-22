/**
 * piiScrub 單元測試（四站一致）：scrubText regex 行為 + SpanProcessor 遮蔽/防禦。
 */
import { describe, expect, it } from "vitest";
import { PIIScrubSpanProcessor, scrubText } from "../../src/observability/piiScrub";

describe("scrubText", () => {
  it("台灣手機/市話 → [PHONE]", () => {
    expect(scrubText("請回撥 0912-345-678 或 0912345678")).toBe(
      "請回撥 [PHONE] 或 [PHONE]",
    );
    expect(scrubText("市話 02-27001234")).toBe("市話 [PHONE]");
  });

  it("email → [EMAIL]", () => {
    expect(scrubText("聯絡 sunny@funngo.ai 謝謝")).toBe("聯絡 [EMAIL] 謝謝");
  });

  it("LINE uid → 雜湊（U#12hex）或環境退化遮罩，不留原值", () => {
    const uid = "U" + "0123456789abcdef".repeat(2);
    const out = scrubText(`uid=${uid} 完畢`);
    expect(out).not.toContain(uid);
    expect(out).toMatch(/uid=(U#[0-9a-f]{12}|\[LINE_UID\]) 完畢/);
  });

  it("地址 → [ADDR]", () => {
    expect(scrubText("到府：台北市大安區和平東路二段106號")).toContain("[ADDR]");
  });

  it("token 參數 → [TOKEN]（保留參數名）", () => {
    expect(scrubText("GET /cb?access_token=abc123&x=1")).toBe(
      "GET /cb?access_token=[TOKEN]&x=1",
    );
  });

  it("乾淨字串原樣", () => {
    expect(scrubText("工單 WO-20260722-0001 已派工")).toBe(
      "工單 WO-20260722-0001 已派工",
    );
  });
});

describe("PIIScrubSpanProcessor", () => {
  it("onEnd 就地遮蔽 string 與 string[] 屬性，數值/bool 原樣", () => {
    const attrs: Record<string, unknown> = {
      "http.url": "/cb?access_token=zzz",
      note: "電話 0912-345-678",
      tags: ["a@b.tw", 42],
      "http.status_code": 200,
      ok: true,
    };
    const p = new PIIScrubSpanProcessor();
    p.onEnd({ attributes: attrs } as never);
    expect(attrs["http.url"]).toBe("/cb?access_token=[TOKEN]");
    expect(attrs["note"]).toBe("電話 [PHONE]");
    expect(attrs["tags"]).toEqual(["[EMAIL]", 42]);
    expect(attrs["http.status_code"]).toBe(200);
    expect(attrs["ok"]).toBe(true);
  });

  it("怪 span 絕不 throw（attributes getter 炸/缺）", () => {
    const p = new PIIScrubSpanProcessor();
    const evil = Object.defineProperty({}, "attributes", {
      get() {
        throw new Error("boom");
      },
    });
    expect(() => p.onEnd(evil as never)).not.toThrow();
    expect(() => p.onEnd({} as never)).not.toThrow();
  });

  it("lifecycle 介面齊備（onStart no-op / flush / shutdown resolve）", async () => {
    const p = new PIIScrubSpanProcessor();
    expect(() => p.onStart({} as never)).not.toThrow();
    await expect(p.forceFlush()).resolves.toBeUndefined();
    await expect(p.shutdown()).resolves.toBeUndefined();
  });
});
