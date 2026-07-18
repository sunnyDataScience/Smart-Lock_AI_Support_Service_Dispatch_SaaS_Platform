/**
 * 使用者導向的錯誤訊息工具。
 *
 * 收斂前各頁直接把 `${e.errorCode} (${e.status})：${e.message}` 丟給使用者看
 * （露出開發者導向的英文錯誤碼與後端英文 message，例如「NOT_FOUND (404)：
 * Exception not found or already closed」）。本工具把任意錯誤轉成使用者
 * 看得懂的單行訊息：
 *   1. 繁中模式：後端 message 已是中文（業務刻意寫給使用者）→ 直接採用，最精準。
 *   2. 否則用錯誤碼 → i18n 映射（`apiError.codes.*`，依當前語系取 zh-TW / en）。
 *   3. 再否則退回狀態碼族群（`apiError.status.*`）。
 *
 * UAT W6-2：原繁中硬編碼訊息表改接 i18n（`apiError.*` namespace，zh/en 對照）。
 * friendlyError 不是 React hook（toast / catch 區塊都要用），語系直接讀
 * localStorage —— 與 LocaleProvider 同一把 key，切換語系後的下一次錯誤即生效。
 * en 模式下後端中文 message 不再優先：先取錯誤碼的英文映射，映射不到才顯示
 * 後端中文（比英文錯誤碼友善），最後退狀態碼族群。
 *
 * 錯誤碼與 request id 仍保留在 ApiError 物件上（開發者可由 Network 面板查），
 * 只是不再出現在使用者面前。
 */

import { ApiError } from "@/lib/api";
import {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  isLocale,
  type Locale,
} from "@/i18n/config";
import { translate } from "@/lib/translate";

/** 當前語系（SSR / localStorage 例外時退回預設語系）。 */
function currentLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  try {
    const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    return isLocale(raw) ? raw : DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE;
  }
}

/** apiError namespace 快捷取字。 */
function tr(locale: Locale, key: string): string {
  return translate(locale, `apiError.${key}`);
}

/**
 * 後端錯誤碼 → 使用者看得懂的訊息（`apiError.codes.*`）。
 * 只收錄使用者實際會碰到的碼（碼清單對齊 api/ 內 `ApiError("CODE", ...)`
 * 的實際使用）；查無對應時回 null，由呼叫端退 fallbackByStatus。
 * translate 缺 key 時回傳完整 path，據此判斷「無此映射」。
 */
function codeMessage(locale: Locale, code: string): string | null {
  if (!code) return null;
  const path = `apiError.codes.${code}`;
  const msg = translate(locale, path);
  return msg === path ? null : msg;
}

/** 查無對應錯誤碼時，依 HTTP 狀態碼族群回退訊息。 */
function fallbackByStatus(locale: Locale, status: number): string {
  if (status === 401) return tr(locale, "status.s401");
  if (status === 403) return tr(locale, "status.s403");
  if (status === 404) return tr(locale, "status.s404");
  if (status === 409) return tr(locale, "status.s409");
  if (status === 422) return tr(locale, "status.s422");
  if (status === 429) return tr(locale, "status.s429");
  if (status >= 500) return tr(locale, "status.s5xx");
  if (status >= 400) return tr(locale, "status.s4xx");
  return tr(locale, "generic");
}

/** message 是否已含中文（後端刻意寫給使用者的訊息）→ 繁中模式可直接顯示。 */
function looksUserFriendly(msg: string | undefined | null): boolean {
  return !!msg && /[一-鿿]/.test(msg);
}

/**
 * 把任意錯誤轉成使用者看得懂的單行訊息（依當前語系取繁中／英文）。
 *
 * 取代散落各頁的 `${e.errorCode} (${e.status})：${e.message}`，不再對使用者
 * 露出英文錯誤碼／HTTP 狀態碼／後端英文 message。
 */
export function friendlyError(e: unknown): string {
  const locale = currentLocale();
  if (e instanceof ApiError) {
    // 繁中模式：後端中文 message 最精準，優先。
    if (locale === DEFAULT_LOCALE && looksUserFriendly(e.message)) {
      return e.message;
    }
    const mapped = codeMessage(locale, e.errorCode);
    if (mapped) return mapped;
    // en 模式且無映射：後端中文仍比英文錯誤碼／狀態碼友善，保底顯示。
    if (looksUserFriendly(e.message)) return e.message;
    return fallbackByStatus(locale, e.status);
  }
  if (e instanceof Error) {
    if (e.name === "AbortError") return tr(locale, "aborted");
    // fetch 連線失敗（後端未啟動／網路中斷）
    if (e.name === "TypeError" && /fetch/i.test(e.message)) {
      return tr(locale, "network");
    }
    if (looksUserFriendly(e.message)) return e.message;
  }
  return tr(locale, "generic");
}

/**
 * 登入頁專用：登入端點的 401 是「帳號或密碼錯誤」，不是 session 逾時——
 * 通用 friendlyError 把 401/UNAUTHENTICATED 一律翻成「登入已逾時」，
 * 用在登入表單會誤導使用者（尚未登入何來逾時，UAT 實測回報）。
 * 帳號鎖定／停用等具體錯誤碼仍走原映射。
 */
export function friendlyLoginError(e: unknown): string {
  if (e instanceof ApiError && e.status === 401) {
    const locale = currentLocale();
    if (e.errorCode !== "UNAUTHENTICATED" && e.errorCode !== "TOKEN_STALE") {
      const mapped = codeMessage(locale, e.errorCode);
      if (mapped) return mapped;
    }
    return tr(locale, "loginInvalid");
  }
  return friendlyError(e);
}
