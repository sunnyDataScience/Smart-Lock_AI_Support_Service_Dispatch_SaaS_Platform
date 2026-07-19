/**
 * 工單狀態群組正反向映射測試（UAT R3-7 回歸）。
 *
 * 篩選器把群組值展開成多個原始 status（後端 status query param 可重複）；
 * 反向映射必須與 statusGroupOf 正向一致（含 v2 DB 防禦值 created / confirmed），
 * 否則選了狀態必空清單（R3-7 根因同型）。
 */
import { describe, expect, it } from "vitest";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_VALUES,
  rawStatusesOfGroup,
  statusGroupOf,
} from "../../src/components/work-orders/statusGroup";

describe("rawStatusesOfGroup（UAT R3-7 群組 → 原始 status 展開）", () => {
  it("每個群組展開的原始值正向映射回同一群組", () => {
    for (const group of STATUS_GROUP_VALUES) {
      const raws = rawStatusesOfGroup(group);
      expect(raws.length).toBeGreaterThan(0);
      for (const raw of raws) {
        expect(statusGroupOf(raw)).toBe(group);
      }
    }
  });

  it("全部 enum status 都被某個群組涵蓋（無漏網）", () => {
    const covered = new Set(
      STATUS_GROUP_VALUES.flatMap((g) => rawStatusesOfGroup(g)),
    );
    for (const raw of Object.keys(STATUS_GROUP_MAP)) {
      expect(covered.has(raw)).toBe(true);
    }
  });

  it("v2 DB 防禦值 created / confirmed 比照 statusGroupOf 涵蓋", () => {
    expect(rawStatusesOfGroup("pending")).toContain("created");
    expect(rawStatusesOfGroup("done")).toContain("confirmed");
  });

  it("dispatched 群組含派工鏈全部中間態（R3-7 原「已派工」單值必空的根因）", () => {
    const dispatched = rawStatusesOfGroup("dispatched");
    for (const s of ["accepted", "scheduled", "dispatching", "assigned", "en_route", "arrived"]) {
      expect(dispatched).toContain(s);
    }
  });
});
