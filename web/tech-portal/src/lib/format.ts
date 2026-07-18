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

export function formatRelative(iso: string): string {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const diff = Date.now() - ts;
  if (diff < 0) return new Date(iso).toLocaleString("zh-TW");
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "剛剛";
  if (min < 60) return `${min} 分鐘前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小時前`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day} 天前`;
  return new Date(iso).toLocaleDateString("zh-TW");
}
