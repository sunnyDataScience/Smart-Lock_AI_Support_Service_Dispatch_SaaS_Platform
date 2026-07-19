/**
 * 工單狀態群組正反向映射 — 純函式模組（自 WorkOrdersTable.tsx 抽出）。
 *
 * 為什麼獨立成 .ts：R3-7 修復需要單元測試反向映射，但 vitest（vite/oxc）
 * 不吃 Next 的 jsx: "preserve"，.tsx 內的純函式無法被測試 import。
 * WorkOrdersTable.tsx re-export 本模組全部符號，既有 caller import 路徑不變。
 */

import type { components } from "@/types/api.generated";

type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];

export type StatusGroup = "pending" | "dispatched" | "in_progress" | "done" | "cancelled";

export const STATUS_GROUP_MAP: Record<WorkOrderStatus, StatusGroup> = {
  inquiring: "pending",
  qualified: "pending",
  quoted: "pending",
  negotiating: "pending",
  accepted: "dispatched",
  scheduled: "dispatched",
  dispatching: "dispatched",
  assigned: "dispatched",
  en_route: "dispatched",
  arrived: "dispatched",
  in_progress: "in_progress",
  completed: "done",
  billed: "done",
  paid: "done",
  closed: "done",
  cancelled: "cancelled",
};

/**
 * UAT P2-10：任意工單狀態字串 → 狀態群組。
 * 派工管理各頁（列表/看板/地圖/儀表板）皆以 STATUS_GROUP_MAP + status.workOrderGroup
 * 字典顯示；其他頁（如客戶詳情）的工單狀態 label 一律共用本 helper，不得另建字典。
 * v2 DB 另有 created / confirmed 兩值不在 WorkOrderStatus enum，此處防禦對應。
 */
export function statusGroupOf(status: string): StatusGroup {
  if (status in STATUS_GROUP_MAP) {
    return STATUS_GROUP_MAP[status as WorkOrderStatus];
  }
  if (status === "created") return "pending"; // 已建立＝待處理
  if (status === "confirmed") return "done"; // 客戶已確認＝已完成
  return "pending";
}

/** 篩選下拉的群組值順序（列表/看板/地圖三視圖共用，UAT R3-7） */
export const STATUS_GROUP_VALUES: readonly StatusGroup[] = [
  "pending",
  "dispatched",
  "in_progress",
  "done",
  "cancelled",
];

/**
 * UAT R3-7：statusGroupOf 的反向映射——群組值 → 該群組的全部原始 status。
 * 篩選器把群組值展開成多個 status query param（後端 status 已改可重複）；
 * v2 DB 防禦值 created / confirmed 比照 statusGroupOf 正向對應一併涵蓋。
 */
export function rawStatusesOfGroup(group: StatusGroup): string[] {
  const raws = (Object.keys(STATUS_GROUP_MAP) as WorkOrderStatus[]).filter(
    (s) => STATUS_GROUP_MAP[s] === group,
  ) as string[];
  if (group === "pending") raws.push("created");
  if (group === "done") raws.push("confirmed");
  return raws;
}
