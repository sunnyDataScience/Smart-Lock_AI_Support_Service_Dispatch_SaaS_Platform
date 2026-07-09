/**
 * dateRange — DateRangePicker 與 dashboard / 報表頁共用的純函式工具。
 *
 * 設計原則：
 *   - 不依賴任何套件（不裝 date-fns / dayjs / react-day-picker）
 *   - 所有日期計算用原生 Date + Intl
 *   - 「日」是 calendar day（local timezone），不處理時分秒
 *   - from <= to；單日選擇 from === to
 *
 * 後端目前僅支援 DashboardPeriod enum（today / 7d / 30d / 90d）— 詳見
 * `docs/02-design/specs/openapi.yaml`。lib 層提供 `mapRangeToDashboardPeriod`
 * 把 range 折回最接近的 enum，自訂 / 本月 / 上月 / 昨天等沒有對應 enum 的
 * preset 由各頁面自行決定 fallback 行為。
 */

export interface DateRange {
  from: Date | null;
  to: Date | null;
}

export type PresetKey =
  | "today"
  | "yesterday"
  | "last7"
  | "last30"
  | "thisMonth"
  | "lastMonth"
  | "custom";

export interface PresetDef {
  key: PresetKey;
  label: string;
}

export const PRESETS: ReadonlyArray<PresetDef> = [
  { key: "today", label: "今天" },
  { key: "yesterday", label: "昨天" },
  { key: "last7", label: "過去 7 日" },
  { key: "last30", label: "過去 30 日" },
  { key: "thisMonth", label: "本月" },
  { key: "lastMonth", label: "上月" },
  { key: "custom", label: "自訂" },
];

// ─────────────────────────────────────────────────────────────────────────────
// 內部小工具 — 全部 immutable，回新 Date instance
// ─────────────────────────────────────────────────────────────────────────────

/** 取得「今天」的 00:00:00 local — 用 new Date(y, m, d) 避免 UTC 漂移 */
export function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

/** 加 n 天（可負）— 不改原物件 */
export function addDays(d: Date, days: number): Date {
  const next = new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);
  return next;
}

/** 加 n 月（可負）— Intl-safe，月底自動 clamp（Date 建構子原生行為） */
export function addMonths(d: Date, months: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + months, d.getDate());
}

/** 取月首（1 號 00:00） */
export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

/** 取月底（next month - 1 day） */
export function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

/** 兩個 Date 是否同一個 calendar day */
export function isSameDay(a: Date | null, b: Date | null): boolean {
  if (!a || !b) return a === b;
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/** 兩個 Date 是否同一個 calendar month */
export function isSameMonth(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()
  );
}

/** YYYY-MM-DD（local）— API 慣用格式 */
export function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Preset → DateRange
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 依 presetKey 算出今天起算的 DateRange。
 * `custom` 回傳目前選中的 range；若呼叫時沒有現存 range，預設過去 7 日。
 */
export function getPresetRange(
  key: PresetKey,
  current?: DateRange,
  now: Date = new Date(),
): DateRange {
  const today = startOfDay(now);

  switch (key) {
    case "today":
      return { from: today, to: today };
    case "yesterday": {
      const y = addDays(today, -1);
      return { from: y, to: y };
    }
    case "last7":
      // 含今天往前 7 天 → from = today - 6
      return { from: addDays(today, -6), to: today };
    case "last30":
      return { from: addDays(today, -29), to: today };
    case "thisMonth":
      return { from: startOfMonth(today), to: today };
    case "lastMonth": {
      const last = addMonths(today, -1);
      return { from: startOfMonth(last), to: endOfMonth(last) };
    }
    case "custom":
      return current ?? { from: addDays(today, -6), to: today };
  }
}

/**
 * 反向偵測 — 給定 range，看看符不符合某個 preset。
 * 用來在初始化 picker 時把寫死的「過去 7 日」高亮對應 preset。
 * 不符合任何 preset → 回 'custom'。
 */
export function detectPreset(
  range: DateRange,
  now: Date = new Date(),
): PresetKey {
  if (!range.from || !range.to) return "custom";
  for (const p of PRESETS) {
    if (p.key === "custom") continue;
    const std = getPresetRange(p.key, undefined, now);
    if (
      std.from &&
      std.to &&
      isSameDay(std.from, range.from) &&
      isSameDay(std.to, range.to)
    ) {
      return p.key;
    }
  }
  return "custom";
}

// ─────────────────────────────────────────────────────────────────────────────
// Format
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 顯示用字串。已選 preset 名 → 顯示 label；自訂 → "YYYY-MM-DD ~ YYYY-MM-DD"。
 * range 不完整 → "選擇日期"
 */
export function formatDateRange(
  range: DateRange,
  options: { locale?: string; presetLabel?: string } = {},
): string {
  const { presetLabel } = options;
  if (presetLabel) return presetLabel;
  if (!range.from || !range.to) return "選擇日期";
  if (isSameDay(range.from, range.to)) return toIsoDate(range.from);
  return `${toIsoDate(range.from)} ~ ${toIsoDate(range.to)}`;
}

/**
 * 給 API query string 用。null → undefined（讓 api.ts 的 buildUrl 略過此 key）。
 */
export function toQueryString(range: DateRange): {
  from: string | undefined;
  to: string | undefined;
} {
  return {
    from: range.from ? toIsoDate(range.from) : undefined,
    to: range.to ? toIsoDate(range.to) : undefined,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 後端 enum 對接
// ─────────────────────────────────────────────────────────────────────────────

export type DashboardPeriodEnum = "today" | "7d" | "30d" | "90d";

/**
 * 把 DateRange 折回後端能吃的 DashboardPeriod。
 *
 * 對應規則（與 PRESETS 對齊）：
 *   today      → "today"
 *   last7      → "7d"
 *   last30     → "30d"
 *   ~ 90 天    → "90d"  （>= 60 天的 custom range 折成 90d，方便看大致趨勢）
 *   其他       → fallback "30d"
 *
 * 備註：本月 / 上月 / 昨天 / 自訂目前後端沒對應 enum，
 * 統一 fallback 30d，UI 上的 range 仍會顯示給使用者，僅資料是近 30 天。
 * 完整 from/to filter 待 [[E7x]] §4.3「後端 API 缺口」補。
 */
export function mapRangeToDashboardPeriod(
  range: DateRange,
  now: Date = new Date(),
): DashboardPeriodEnum {
  if (!range.from || !range.to) return "30d";
  const today = startOfDay(now);

  // 單日 = today
  if (isSameDay(range.from, today) && isSameDay(range.to, today)) {
    return "today";
  }

  // 量「天數」（含頭尾）— 用 ms 差除以 86400000 + 1
  const days =
    Math.round(
      (startOfDay(range.to).getTime() - startOfDay(range.from).getTime()) /
        86400000,
    ) + 1;

  // 結束日不是今天 → 這個 range 沒辦法 1:1 對到 enum，但仍依長度挑最接近的
  if (days <= 1) return "today";
  if (days <= 7) return "7d";
  if (days <= 30) return "30d";
  return "90d";
}
