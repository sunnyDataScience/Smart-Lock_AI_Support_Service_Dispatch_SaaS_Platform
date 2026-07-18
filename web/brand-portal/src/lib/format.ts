import {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  isLocale,
  type Locale,
} from "@/i18n/config";

/**
 * 讀取當前語系（UAT W6-6）：formatRelative 呼叫點遍佈 30+ 檔，逐一改簽名
 * 傳 locale 侵入過大；改由 formatter 自行讀 LocaleProvider 持久化的
 * localStorage key。SSR 走預設值（與 LocaleProvider 首屏行為一致）。
 */
function currentLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  try {
    const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    return isLocale(raw) ? raw : DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE;
  }
}

export function formatRelative(iso: string, locale?: Locale): string {
  const loc = locale ?? currentLocale();
  const en = loc === "en";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const diff = Date.now() - ts;
  if (diff < 0) return new Date(iso).toLocaleString(en ? "en-US" : "zh-TW");
  const min = Math.floor(diff / 60_000);
  if (min < 1) return en ? "just now" : "剛剛";
  if (min < 60)
    return en ? `${min} minute${min === 1 ? "" : "s"} ago` : `${min} 分鐘前`;
  const hr = Math.floor(min / 60);
  if (hr < 24)
    return en ? `${hr} hour${hr === 1 ? "" : "s"} ago` : `${hr} 小時前`;
  const day = Math.floor(hr / 24);
  if (day < 7)
    return en ? `${day} day${day === 1 ? "" : "s"} ago` : `${day} 天前`;
  return new Date(iso).toLocaleDateString(en ? "en-US" : "zh-TW");
}

/**
 * 帳務域統一幣別格式（UAT W1-5）：一律「NT$ 3,825」——整數、千分位、
 * 無 TWD 前綴、無小數。全平台僅新台幣，currency 欄位不參與顯示。
 */
export function formatTwd(amount: string | number | null | undefined): string {
  if (amount == null || amount === "") return "—";
  const n = typeof amount === "string" ? Number(amount) : amount;
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}
