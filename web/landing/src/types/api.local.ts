/**
 * api.local.ts — runtime 契約未宣告型別的本地補丁（CR-0126）
 *
 * 型別 SoT 改認 runtime export（api.main:app）後，以下端點因 FastAPI 端
 * 未掛 response_model（回傳裸 dict envelope），不會出現在 api.generated.ts
 * 的 components.schemas。此處依實際回傳形狀本地宣告：
 *   - Notification 系列：api/services/notification_service.py（SELECT 欄位一一對應）
 *   - *Envelope：ApiResponseGeneric + data 縮窄（後端信封慣例）
 *
 * 若後端日後補宣告 response_model，對應型別應改回 api.generated 並自本檔刪除。
 */
import type { components } from "./api.generated";

export type NotificationType =
  | "work_order"
  | "refund"
  | "dispute"
  | "rbac"
  | "inventory"
  | "sla"
  | "system"
  | "mention"
  // work_order_service._auto_notify 實際寫入的三個工單事件 type
  | "work_order_assigned"
  | "work_order_completed"
  | "work_order_rejected"
  // notification_template_service._VALID_TYPES（migration 071 CHECK 值域）
  | "quote"
  | "payment"
  | "dispatch"
  | "delay"
  | "completion"
  | "rma";

export type NotificationSeverity = "info" | "warning" | "critical";

export interface Notification {
  /** Format: uuid */
  id: string;
  type: NotificationType;
  severity: NotificationSeverity;
  title: string;
  body: string;
  source: "websocket" | "line_push" | "system" | "email_fallback";
  /** Format: date-time */
  created_at: string;
  /** Format: date-time */
  read_at?: string | null;
  /** Format: date-time */
  archived_at?: string | null;
  related_entity?: {
    type?: string;
    /** Format: uuid */
    id?: string;
    /** Format: uri */
    url?: string;
  } | null;
  actions?: {
    label?: string;
    endpoint?: string;
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  }[];
  /** Format: uuid — 對應 domain event，除錯用 */
  raw_event_id?: string | null;
}

export type ManualEnvelope = components["schemas"]["ApiResponseGeneric"] & {
  data?: components["schemas"]["Manual"];
};

export type PricingRuleEnvelope = components["schemas"]["ApiResponseGeneric"] & {
  data?: components["schemas"]["PricingRule"];
};
