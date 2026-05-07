"use client";

/**
 * DateRangePicker — Dashboard / 報表頁共用日期範圍選擇器
 *
 * 結構：Radix Popover trigger 按鈕 + popover 內容（左 preset 列、右雙月日曆）
 * 依賴：@radix-ui/react-popover（已安裝）+ lucide-react icon
 *
 * 為什麼自寫日曆：F-021 只需要月份切換 + 區間選取，套 react-day-picker / date-fns
 * 會多帶 ~30KB；既有 Modal.tsx 也是直接走 Radix primitive 風格。
 *
 * 鍵盤：方向鍵移動 focus、Enter 選日、Esc 關 popover（Radix 自帶）。
 * 響應式：< 640px 縮成單月，靠 grid 自動 flow。
 *
 * 用法：
 *   const [range, setRange] = useState<DateRange>(getPresetRange('last7'));
 *   <DateRangePicker value={range} onChange={setRange} />
 */

import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from "lucide-react";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import {
  PRESETS,
  addDays,
  addMonths,
  detectPreset,
  endOfMonth,
  formatDateRange,
  getPresetRange,
  isSameDay,
  isSameMonth,
  startOfDay,
  startOfMonth,
  type DateRange,
  type PresetDef,
  type PresetKey,
} from "@/lib/dateRange";

const WEEKDAY_LABELS = ["日", "一", "二", "三", "四", "五", "六"];

const MONTH_FORMATTER = new Intl.DateTimeFormat("zh-TW", {
  year: "numeric",
  month: "long",
});

export interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
  /** 自訂 presets；不傳用內建 7 個 */
  presets?: ReadonlyArray<PresetDef>;
  /** trigger 按鈕額外 className */
  className?: string;
  /** 觸發按鈕的 aria-label，預設「選擇日期區間」 */
  ariaLabel?: string;
  /** 停用整顆元件（loading 狀態用） */
  disabled?: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// 主元件
// ─────────────────────────────────────────────────────────────────────────────

export default function DateRangePicker({
  value,
  onChange,
  presets = PRESETS,
  className = "",
  ariaLabel = "選擇日期區間",
  disabled = false,
}: DateRangePickerProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DateRange>(value);
  // 使用者點第一下後等第二下；null = 還沒開始選
  const [pickFromOnly, setPickFromOnly] = useState<Date | null>(null);

  // 開啟時把當前 value 載入草稿；關閉時不動草稿（避免閃）
  useEffect(() => {
    if (open) {
      setDraft(value);
      setPickFromOnly(null);
    }
  }, [open, value]);

  const detected = useMemo(() => detectPreset(draft), [draft]);
  const triggerLabel = useMemo(() => {
    const presetDef = presets.find((p) => p.key === detected);
    if (presetDef && presetDef.key !== "custom") {
      return formatDateRange(value, { presetLabel: presetDef.label });
    }
    return formatDateRange(value);
  }, [value, detected, presets]);

  const handlePresetClick = (key: PresetKey) => {
    if (key === "custom") {
      // 切到 custom，保留現值供雙擊調整
      setDraft(value);
      setPickFromOnly(null);
      return;
    }
    const next = getPresetRange(key, draft);
    setDraft(next);
    onChange(next);
    setOpen(false);
  };

  const handleDayClick = (day: Date) => {
    if (!pickFromOnly) {
      // 第一次點 → from = day, to = day
      setDraft({ from: day, to: day });
      setPickFromOnly(day);
      return;
    }
    // 第二次點 → 完成 range（自動排序 from <= to）
    const first = pickFromOnly;
    const second = day;
    const next: DateRange =
      second.getTime() < first.getTime()
        ? { from: second, to: first }
        : { from: first, to: second };
    setDraft(next);
    onChange(next);
    setPickFromOnly(null);
    setOpen(false);
  };

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-label={ariaLabel}
          className={[
            "inline-flex items-center gap-2 rounded-lg border border-[var(--border)]",
            "bg-[var(--bg-surface)] px-3 py-[7px]",
            "text-[13px] text-[var(--text-primary)]",
            "hover:bg-[var(--surface-strong)]",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]",
            "disabled:cursor-not-allowed disabled:opacity-50",
            className,
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <CalendarIcon className="h-4 w-4 text-[var(--text-secondary)]" aria-hidden="true" />
          <span>{triggerLabel}</span>
        </button>
      </PopoverPrimitive.Trigger>

      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={6}
          className={[
            "z-50 ui-modal-content",
            "rounded-lg border border-[var(--border)]",
            "bg-[var(--bg-surface)] text-[var(--text-primary)]",
            "shadow-[var(--shadow-popover)]",
            "p-0",
          ].join(" ")}
        >
          <DateRangePickerBody
            draft={draft}
            detectedPresetKey={detected}
            presets={presets}
            pickFromOnly={pickFromOnly}
            onPresetClick={handlePresetClick}
            onDayClick={handleDayClick}
          />
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Popover body — preset 列 + 雙月日曆
// ─────────────────────────────────────────────────────────────────────────────

interface BodyProps {
  draft: DateRange;
  detectedPresetKey: PresetKey;
  presets: ReadonlyArray<PresetDef>;
  pickFromOnly: Date | null;
  onPresetClick: (key: PresetKey) => void;
  onDayClick: (day: Date) => void;
}

function DateRangePickerBody({
  draft,
  detectedPresetKey,
  presets,
  pickFromOnly,
  onPresetClick,
  onDayClick,
}: BodyProps) {
  // 當前左月份（右月份 = 左 + 1）
  const initialMonth = useMemo(() => {
    if (draft.from) return startOfMonth(draft.from);
    return startOfMonth(new Date());
  }, [draft.from]);
  const [leftMonth, setLeftMonth] = useState<Date>(initialMonth);

  const rightMonth = useMemo(() => addMonths(leftMonth, 1), [leftMonth]);

  return (
    <div className="flex flex-col gap-0 sm:flex-row" data-testid="daterange-body">
      {/* Preset 列 */}
      <div
        className="flex shrink-0 flex-row gap-1 overflow-x-auto border-b border-[var(--border)] p-3 sm:flex-col sm:gap-[2px] sm:overflow-visible sm:border-b-0 sm:border-r sm:p-2"
        role="listbox"
        aria-label="預設日期範圍"
      >
        {presets.map((p) => {
          const active = p.key === detectedPresetKey;
          return (
            <button
              key={p.key}
              type="button"
              role="option"
              aria-selected={active}
              onClick={() => onPresetClick(p.key)}
              className={[
                "shrink-0 whitespace-nowrap rounded-md px-3 py-[6px] text-left text-[13px]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]",
                active
                  ? "bg-[var(--primary-light)] font-semibold text-[var(--primary)]"
                  : "text-[var(--text-primary)] hover:bg-[var(--surface-strong)]",
                "sm:min-w-[110px]",
              ].join(" ")}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      {/* 雙月日曆（< 640px 改單月） */}
      <div className="flex flex-col gap-3 p-3 sm:flex-row">
        <CalendarMonth
          month={leftMonth}
          range={draft}
          pickFromOnly={pickFromOnly}
          showLeftNav
          onPrev={() => setLeftMonth((m) => addMonths(m, -1))}
          onNext={() => setLeftMonth((m) => addMonths(m, 1))}
          onDayClick={onDayClick}
        />
        <div className="hidden sm:block">
          <CalendarMonth
            month={rightMonth}
            range={draft}
            pickFromOnly={pickFromOnly}
            showRightNav
            onPrev={() => setLeftMonth((m) => addMonths(m, -1))}
            onNext={() => setLeftMonth((m) => addMonths(m, 1))}
            onDayClick={onDayClick}
          />
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 單月日曆
// ─────────────────────────────────────────────────────────────────────────────

interface CalendarMonthProps {
  month: Date;
  range: DateRange;
  pickFromOnly: Date | null;
  showLeftNav?: boolean;
  showRightNav?: boolean;
  onPrev: () => void;
  onNext: () => void;
  onDayClick: (day: Date) => void;
}

function CalendarMonth({
  month,
  range,
  pickFromOnly,
  showLeftNav,
  showRightNav,
  onPrev,
  onNext,
  onDayClick,
}: CalendarMonthProps) {
  const titleId = useId();
  const days = useMemo(() => buildMonthGrid(month), [month]);
  const today = useMemo(() => startOfDay(new Date()), []);

  // 鍵盤導覽 — 方向鍵搬 focus，Enter / Space 選日。focus 走 grid cell tabindex。
  const gridRef = useRef<HTMLDivElement | null>(null);

  function handleKeyDown(e: KeyboardEvent<HTMLButtonElement>, day: Date) {
    let next: Date | null = null;
    switch (e.key) {
      case "ArrowLeft":
        next = addDays(day, -1);
        break;
      case "ArrowRight":
        next = addDays(day, 1);
        break;
      case "ArrowUp":
        next = addDays(day, -7);
        break;
      case "ArrowDown":
        next = addDays(day, 7);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        onDayClick(day);
        return;
      default:
        return;
    }
    if (next) {
      e.preventDefault();
      // 如果 next 跨月，讓父層切月份 — focus 在 effect 重 mount 後處理
      if (!isSameMonth(next, month)) {
        if (next.getTime() < startOfMonth(month).getTime()) onPrev();
        else onNext();
      }
      // focus 下一個按鈕（簡化：找 data-iso 屬性）
      const iso = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-${String(next.getDate()).padStart(2, "0")}`;
      // 等 React 重渲染後再 focus
      requestAnimationFrame(() => {
        const root = gridRef.current;
        if (!root) return;
        const target = root.querySelector<HTMLButtonElement>(
          `button[data-iso="${iso}"]`,
        );
        target?.focus();
      });
    }
  }

  return (
    <div className="flex flex-col gap-2" role="group" aria-labelledby={titleId}>
      <div className="flex items-center justify-between px-1">
        <button
          type="button"
          aria-label="上個月"
          onClick={onPrev}
          className={[
            "h-7 w-7 rounded-md text-[var(--text-secondary)] hover:bg-[var(--surface-strong)]",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]",
            showLeftNav ? "" : "invisible",
          ].join(" ")}
        >
          <ChevronLeft className="mx-auto h-4 w-4" aria-hidden="true" />
        </button>
        <span id={titleId} className="text-[13px] font-semibold">
          {MONTH_FORMATTER.format(month)}
        </span>
        <button
          type="button"
          aria-label="下個月"
          onClick={onNext}
          className={[
            "h-7 w-7 rounded-md text-[var(--text-secondary)] hover:bg-[var(--surface-strong)]",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]",
            showRightNav ? "" : "invisible",
          ].join(" ")}
        >
          <ChevronRight className="mx-auto h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div
        ref={gridRef}
        role="grid"
        className="grid w-[252px] grid-cols-7 gap-[2px] text-center"
      >
        {WEEKDAY_LABELS.map((w) => (
          <div
            key={w}
            role="columnheader"
            className="py-1 text-[11px] font-medium text-[var(--text-secondary)]"
          >
            {w}
          </div>
        ))}
        {days.map((d) => {
          const inMonth = isSameMonth(d, month);
          const inRange =
            range.from && range.to
              ? d.getTime() >= startOfDay(range.from).getTime() &&
                d.getTime() <= startOfDay(range.to).getTime()
              : false;
          const isStart = range.from && isSameDay(d, range.from);
          const isEnd = range.to && isSameDay(d, range.to);
          const isToday = isSameDay(d, today);
          const isPickAnchor = pickFromOnly && isSameDay(d, pickFromOnly);
          const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
          return (
            <button
              key={iso}
              type="button"
              role="gridcell"
              data-iso={iso}
              tabIndex={inMonth ? 0 : -1}
              onClick={() => onDayClick(d)}
              onKeyDown={(e) => handleKeyDown(e, d)}
              aria-label={iso}
              aria-pressed={!!(isStart || isEnd)}
              className={[
                "h-8 w-8 rounded-md text-[12px]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]",
                !inMonth ? "text-[var(--text-disabled)]" : "text-[var(--text-primary)]",
                inMonth && !inRange ? "hover:bg-[var(--surface-strong)]" : "",
                inRange && !isStart && !isEnd
                  ? "bg-[var(--primary-light)] text-[var(--primary)]"
                  : "",
                isStart || isEnd
                  ? "bg-[var(--primary)] font-semibold text-white hover:bg-[var(--primary-hover)]"
                  : "",
                isPickAnchor && !isEnd
                  ? "ring-2 ring-[var(--border-focus)] ring-offset-1"
                  : "",
                isToday && !isStart && !isEnd
                  ? "ring-1 ring-[var(--border-focus)]"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {d.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 月曆 grid 計算 — 6 週固定（含上下月補日）
// ─────────────────────────────────────────────────────────────────────────────

function buildMonthGrid(month: Date): Date[] {
  const first = startOfMonth(month);
  const startWeekday = first.getDay(); // 0 = Sunday
  const gridStart = addDays(first, -startWeekday);
  // 6 weeks × 7 days = 42 cells，固定大小避免月份切換時跳動
  const cells: Date[] = [];
  for (let i = 0; i < 42; i++) {
    cells.push(addDays(gridStart, i));
  }
  // 確保 endOfMonth 涵蓋到 — 若最後一格還沒到月底，多補一週（極少見）
  const last = endOfMonth(month);
  while (cells[cells.length - 1].getTime() < last.getTime()) {
    cells.push(addDays(cells[cells.length - 1], 1));
  }
  return cells;
}
