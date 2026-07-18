/**
 * 金額統一格式（UAT P3）：NT$ + 千分位、無小數。
 * 後端 Decimal 序列化為字串（如 "1500.00"）；null / 空值 / 非數字 → "—"。
 * 範例：formatNTD("1500.00") → "NT$ 1,500"
 */
export function formatNTD(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num)) return "—";
  return `NT$ ${Math.round(num).toLocaleString("zh-TW")}`;
}

// 「剛剛」不走 Intl.RelativeTimeFormat：numeric:"auto" 的 0 分鐘會輸出
// "this minute" / 「這一分鐘」，對使用者不自然，改用固定字串。
const JUST_NOW: Record<string, string> = {
  "zh-TW": "剛剛",
  en: "just now",
};

/**
 * 相對時間（UAT W6-6）：依 locale 輸出 —— zh-TW「5 分鐘前」/ en "5 minutes ago"。
 * locale 省略時維持原行為（zh-TW），既有 callsite 不強迫改動。
 */
export function formatRelative(iso: string, locale: string = "zh-TW"): string {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const diff = Date.now() - ts;
  if (diff < 0) return new Date(iso).toLocaleString(locale);
  const min = Math.floor(diff / 60_000);
  if (min < 1) return JUST_NOW[locale] ?? JUST_NOW["zh-TW"];
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "always" });
  if (min < 60) return rtf.format(-min, "minute");
  const hr = Math.floor(min / 60);
  if (hr < 24) return rtf.format(-hr, "hour");
  const day = Math.floor(hr / 24);
  if (day < 7) return rtf.format(-day, "day");
  return new Date(iso).toLocaleDateString(locale);
}
