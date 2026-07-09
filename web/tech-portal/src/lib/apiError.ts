/**
 * 使用者導向的錯誤訊息工具。
 *
 * 收斂前各頁直接把 `${e.errorCode} (${e.status})：${e.message}` 丟給使用者看
 * （露出開發者導向的英文錯誤碼與後端英文 message，例如「NOT_FOUND (404)：
 * Exception not found or already closed」）。本工具把任意錯誤轉成繁中、
 * 使用者看得懂的單行訊息：
 *   1. 後端 message 已是中文（業務刻意寫給使用者）→ 直接採用，最精準。
 *   2. 否則用錯誤碼 → 繁中映射（CODE_MESSAGES）。
 *   3. 再否則退回狀態碼族群（fallbackByStatus）。
 *
 * 錯誤碼與 request id 仍保留在 ApiError 物件上（開發者可由 Network 面板查），
 * 只是不再出現在使用者面前。
 */

import { ApiError } from "@/lib/api";

/**
 * 後端錯誤碼 → 使用者看得懂的繁中訊息。
 * 只收錄使用者實際會碰到的碼；查無對應時退回 fallbackByStatus。
 * 碼清單對齊 api/ 內 `ApiError("CODE", ...)` 的實際使用。
 */
const CODE_MESSAGES: Record<string, string> = {
  // 通用
  VALIDATION_ERROR: "輸入的資料有誤，請檢查後再試一次。",
  INVALID: "輸入的資料有誤，請檢查後再試一次。",
  NOT_FOUND: "找不到資料，可能已被刪除或狀態已變更，請重新整理後再試。",
  STATE_CONFLICT: "目前狀態無法執行此操作，請重新整理後再試。",
  INVALID_STATE: "目前狀態無法執行此操作，請重新整理後再試。",
  CONFLICT: "資料已被其他人更新，請重新整理後再試。",
  GONE: "此項目已不存在或已關閉。",
  DB_UNAVAILABLE: "系統忙線中，請稍後再試。",
  DB_ERROR: "系統發生問題，請稍後再試。",
  INTERNAL_ERROR: "系統發生問題，請稍後再試。",
  INTERNAL: "系統發生問題，請稍後再試。",

  // 認證 / 權限
  UNAUTHENTICATED: "登入已逾時，請重新登入。",
  TOKEN_STALE: "登入已逾時，請重新登入。",
  TOKEN_REVOKED: "登入已失效，請重新登入。",
  FORBIDDEN: "您沒有執行此操作的權限。",
  CROSS_TENANT_WRITE: "您沒有存取此資料的權限。",
  CROSS_TENANT_READ: "您沒有存取此資料的權限。",
  CROSS_PARTNER_READ: "您沒有存取此資料的權限。",
  RBAC_HIERARCHY_VIOLATION: "您的角色權限不足，無法執行此操作。",
  OVERRIDE_NOT_ALLOWED: "您沒有覆寫此設定的權限。",
  SOD_VIOLATION: "因職責分離限制，您無法同時擔任此操作的多個角色。",
  SOD_VIOLATION_RBAC: "因職責分離限制，您無法同時擔任此操作的多個角色。",
  ACCOUNT_DISABLED: "此帳號已停用，請聯絡管理員。",
  LOGIN_LOCKED: "登入嘗試次數過多，帳號已暫時鎖定，請稍後再試。",
  INVALID_CURRENT_PASSWORD: "目前密碼不正確。",
  RESET_TOKEN_INVALID: "重設連結無效，請重新申請。",
  RESET_TOKEN_EXPIRED: "重設連結已過期，請重新申請。",

  // 設定 / 主檔
  CONFIG_NOT_FOUND: "找不到對應的設定。",
  ITEM_INACTIVE: "此項目已停用，無法選用。",
  TEMPLATE_NOT_APPROVED: "範本尚未核准，無法使用。",
  PARTNER_NOT_BOUND: "尚未綁定合作廠商。",
  INVALID_PERIOD: "期間設定有誤，請重新選擇。",

  // 工單 / 派工 / 簽名 / 結案
  WORK_ORDER_NOT_FOUND: "找不到對應的工單。",
  CASE_NOT_FOUND: "找不到對應的案件。",
  TECHNICIAN_NOT_FOUND: "找不到對應的技師。",
  MEDIA_NOT_FOUND: "找不到對應的檔案。",
  HIGH_RISK_HOLD: "此工單因高風險異常已被暫停，請先處理對應異常。",
  PAYMENT_REQUIRED_FOR_DISPATCH: "需先完成付款才能派工。",
  PAYMENT_PROOF_REQUIRED: "請先上傳付款憑證。",
  MATERIALS_REQUIRED: "請先填寫所需料件。",
  SIGNATURE_REQUIRED: "請先完成簽名。",
  SIGNATURE_INVALID: "簽名驗證失敗，請重新簽署。",
  ADDRESS_REQUIRED_FOR_CLOSE: "請先填寫地址才能結案。",

  // 請求層
  MISSING_IDEMPOTENCY_KEY: "請求逾時或重複，請重新整理後再試一次。",
};

/** 查無對應錯誤碼時，依 HTTP 狀態碼族群回退繁中訊息。 */
function fallbackByStatus(status: number): string {
  if (status === 401) return "登入已逾時，請重新登入。";
  if (status === 403) return "您沒有執行此操作的權限。";
  if (status === 404) return "找不到資料，可能已被刪除或狀態已變更，請重新整理後再試。";
  if (status === 409) return "目前狀態無法執行此操作，請重新整理後再試。";
  if (status === 422) return "輸入的資料有誤，請檢查後再試一次。";
  if (status === 429) return "操作過於頻繁，請稍後再試。";
  if (status >= 500) return "系統發生問題，請稍後再試。";
  if (status >= 400) return "操作失敗，請檢查輸入後再試一次。";
  return "操作失敗，請稍後再試。";
}

/** message 是否已含中文（後端刻意寫給使用者的訊息）→ 可直接顯示。 */
function looksUserFriendly(msg: string | undefined | null): boolean {
  return !!msg && /[一-鿿]/.test(msg);
}

/**
 * 把任意錯誤轉成使用者看得懂的繁中單行訊息。
 *
 * 取代散落各頁的 `${e.errorCode} (${e.status})：${e.message}`，不再對使用者
 * 露出英文錯誤碼／HTTP 狀態碼／後端英文 message。
 */
export function friendlyError(e: unknown): string {
  if (e instanceof ApiError) {
    if (looksUserFriendly(e.message)) return e.message;
    const mapped = CODE_MESSAGES[e.errorCode];
    if (mapped) return mapped;
    return fallbackByStatus(e.status);
  }
  if (e instanceof Error) {
    if (e.name === "AbortError") return "請求已取消。";
    // fetch 連線失敗（後端未啟動／網路中斷）
    if (e.name === "TypeError" && /fetch/i.test(e.message)) return "連線失敗，請檢查網路後再試。";
    if (looksUserFriendly(e.message)) return e.message;
  }
  return "操作失敗，請稍後再試。";
}
