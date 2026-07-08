"use client";

import {
  Fragment,
  useMemo,
  useRef,
  type CSSProperties,
  type ReactNode,
} from "react";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useSidebar } from "@shared/components/layout/SidebarContext";
import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";
import { SkeletonTableRow } from "./Skeleton";

/**
 * DataTable — 通用列表/表格元件
 *
 * 設計目標：
 * - 統一 ARIA roles（role=table/row/cell/columnheader）
 * - 統一 loading / empty / error 狀態
 * - 內建 react-virtual 虛擬化（>= virtualizeThreshold 行才啟用）
 * - 內建 RWD card mode（mobile 自動轉卡片，欄位 priority 控制顯示）
 * - 對外保持「columns + items」最小 prop 介面
 *
 * 用法：
 *   <DataTable
 *     items={workOrders}
 *     rowKey={(o) => o.id}
 *     columns={columns}
 *     loading={loading}
 *     error={error}
 *     emptyText="目前無工單"
 *     rowHref={(o) => `/work-orders/${o.id}`}
 *     ariaLabel="工單列表"
 *     virtualizeThreshold={50}
 *   />
 */

export interface ColumnDef<T> {
  /** 唯一 key，用於 React key */
  key: string;
  /** 表頭文字 */
  label: string;
  /**
   * Tailwind width class (e.g. "w-[120px]", "flex-1")。桌機表格用，
   * card mode 不影響。
   */
  width?: string;
  /** Cell 對齊（影響 textAlign） */
  align?: "left" | "right" | "center";
  /**
   * Card mode 優先級：
   *   "primary"   → 卡片顯示為標題（首 2 個 primary 欄位排版略大）
   *   "secondary" → 卡片副標 / meta row
   *   "hidden"    → 行動模式不顯示（節省螢幕空間）
   *   undefined   → 預設 "secondary"
   */
  priority?: "primary" | "secondary" | "hidden";
  /** Card mode 副標前綴（e.g. "狀態：" prefix） */
  cardLabel?: string;
  /** 自訂 render；不傳時用 String(item[accessor 或 key]) */
  render?: (item: T, idx: number) => ReactNode;
  /** 取資料路徑；不傳時用 (item as any)[key] */
  accessor?: (item: T) => unknown;
}

export interface DataTableProps<T> {
  items: T[];
  /** 每行唯一 key */
  rowKey: (item: T) => string;
  columns: ColumnDef<T>[];
  loading?: boolean;
  error?: unknown;
  emptyText?: string;
  /** 整列點擊時跳轉 URL（傳此 prop 時整列變 Link） */
  rowHref?: (item: T) => string;
  /** ARIA label for table */
  ariaLabel?: string;
  /** 行高（虛擬化估算用，預設 48px） */
  rowHeight?: number;
  /** 列數 >= 此值才啟用虛擬化（預設 50） */
  virtualizeThreshold?: number;
  /** 虛擬化 viewport 高度（預設 600px） */
  virtualViewportHeight?: number;
  /** 強制 card mode（預設依 isMobile 自動切換） */
  forceCardMode?: boolean;
  className?: string;
}

const DEFAULT_ROW_HEIGHT = 48;
const DEFAULT_VIRTUALIZE_THRESHOLD = 50;
const DEFAULT_VIRTUAL_VIEWPORT_HEIGHT = 600;

function alignClass(align?: ColumnDef<unknown>["align"]) {
  switch (align) {
    case "right":
      return "text-right";
    case "center":
      return "text-center";
    default:
      return "text-left";
  }
}

function cellValue<T>(col: ColumnDef<T>, item: T, idx: number): ReactNode {
  if (col.render) return col.render(item, idx);
  if (col.accessor) {
    const v = col.accessor(item);
    return v === null || v === undefined ? "—" : String(v);
  }
  // No render / accessor: try direct key lookup
  const v = (item as Record<string, unknown>)[col.key];
  return v === null || v === undefined ? "—" : String(v);
}

/* ────────────────────────────────────────────────────────────────────────
 * 桌機表格模式
 * ──────────────────────────────────────────────────────────────────────── */

function TableHeader<T>({ columns }: { columns: ColumnDef<T>[] }) {
  return (
    <div role="row" className="flex h-[44px] items-center bg-[var(--bg-page)] px-4">
      {columns.map((col) => (
        <div
          key={col.key}
          role="columnheader"
          aria-sort="none"
          className={`${col.width ?? "flex-1"} px-0`}
        >
          <span
            className={`block text-[12px] font-semibold text-[var(--text-secondary)] ${alignClass(col.align)}`}
          >
            {col.label}
          </span>
        </div>
      ))}
    </div>
  );
}

interface RowProps<T> {
  item: T;
  idx: number;
  columns: ColumnDef<T>[];
  rowHref?: (item: T) => string;
  style?: CSSProperties;
}

function TableRow<T>({ item, idx, columns, rowHref, style }: RowProps<T>) {
  const rowClasses = `flex h-12 items-center border-b border-[var(--border)] px-4 hover:bg-[var(--primary-light)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 focus-visible:ring-inset ${
    idx % 2 === 0 ? "bg-[var(--bg-surface)]" : "bg-[var(--bg-page)]"
  }`;
  const rowAttrs = {
    role: "row" as const,
    "aria-rowindex": idx + 2,
    style,
  };
  const cells = columns.map((col) => (
    <div
      key={col.key}
      role="cell"
      className={`${col.width ?? "flex-1"} truncate pr-3 text-[13px] text-[var(--text-primary)] ${alignClass(col.align)}`}
    >
      {cellValue(col, item, idx)}
    </div>
  ));

  if (rowHref) {
    return (
      <Link href={rowHref(item)} className={rowClasses} {...rowAttrs}>
        {cells}
      </Link>
    );
  }
  return (
    <div className={rowClasses} {...rowAttrs}>
      {cells}
    </div>
  );
}

function VirtualizedRows<T>({
  items,
  rowKey,
  columns,
  rowHref,
  rowHeight,
  viewportHeight,
}: {
  items: T[];
  rowKey: (item: T) => string;
  columns: ColumnDef<T>[];
  rowHref?: (item: T) => string;
  rowHeight: number;
  viewportHeight: number;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 5,
  });

  return (
    <div
      ref={parentRef}
      className="overflow-auto"
      style={{ height: `${viewportHeight}px` }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {virtualizer.getVirtualItems().map((vi) => {
          const item = items[vi.index];
          return (
            <TableRow
              key={rowKey(item)}
              item={item}
              idx={vi.index}
              columns={columns}
              rowHref={rowHref}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${vi.start}px)`,
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Card mode（行動版）
 * ──────────────────────────────────────────────────────────────────────── */

function Card<T>({
  item,
  idx,
  columns,
  rowHref,
}: {
  item: T;
  idx: number;
  columns: ColumnDef<T>[];
  rowHref?: (item: T) => string;
}) {
  const primary = columns.filter((c) => c.priority === "primary");
  const secondary = columns.filter(
    (c) => c.priority === "secondary" || c.priority === undefined,
  );
  // priority="hidden" 完全跳過

  const content = (
    <>
      {primary.length > 0 && (
        <div className="flex flex-col gap-0.5">
          {primary.map((col) => (
            <div
              key={col.key}
              className="text-[14px] font-semibold text-[var(--text-primary)]"
            >
              {cellValue(col, item, idx)}
            </div>
          ))}
        </div>
      )}
      {secondary.length > 0 && (
        <dl className="mt-2 flex flex-col gap-1 text-[12px]">
          {secondary.map((col) => (
            <Fragment key={col.key}>
              <div className="flex items-baseline gap-2">
                <dt className="shrink-0 text-[var(--text-tertiary)]">
                  {col.cardLabel ?? col.label}：
                </dt>
                <dd className="min-w-0 truncate text-[var(--text-primary)]">
                  {cellValue(col, item, idx)}
                </dd>
              </div>
            </Fragment>
          ))}
        </dl>
      )}
    </>
  );

  const cardClasses =
    "block rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4 hover:bg-[var(--primary-light)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1";

  if (rowHref) {
    return (
      <Link
        href={rowHref(item)}
        role="row"
        aria-rowindex={idx + 2}
        className={cardClasses}
      >
        {content}
      </Link>
    );
  }
  return (
    <div role="row" aria-rowindex={idx + 2} className={cardClasses}>
      {content}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Main DataTable
 * ──────────────────────────────────────────────────────────────────────── */

export default function DataTable<T>({
  items,
  rowKey,
  columns,
  loading,
  error,
  emptyText = "目前無資料",
  rowHref,
  ariaLabel = "資料表格",
  rowHeight = DEFAULT_ROW_HEIGHT,
  virtualizeThreshold = DEFAULT_VIRTUALIZE_THRESHOLD,
  virtualViewportHeight = DEFAULT_VIRTUAL_VIEWPORT_HEIGHT,
  forceCardMode,
  className = "",
}: DataTableProps<T>) {
  const { isMobile } = useSidebar();
  const useCardMode = forceCardMode ?? isMobile;

  const visibleColumns = useMemo(
    () => (useCardMode ? columns.filter((c) => c.priority !== "hidden") : columns),
    [columns, useCardMode],
  );

  // ── Loading state ──
  if (loading && items.length === 0) {
    if (useCardMode) {
      return (
        <div className={`flex flex-col gap-2 ${className}`}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-lg bg-[var(--border)]"
            />
          ))}
        </div>
      );
    }
    return (
      <div
        role="table"
        aria-label={ariaLabel}
        aria-busy="true"
        className={`overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] ${className}`}
      >
        <TableHeader columns={visibleColumns} />
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonTableRow key={i} cols={visibleColumns.length} />
        ))}
      </div>
    );
  }

  // ── Error state ──
  if (error) {
    return <ErrorState error={error} variant="block" className={className} />;
  }

  // ── Empty state ──
  if (items.length === 0) {
    return (
      <div
        role="table"
        aria-label={ariaLabel}
        className={`overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] ${className}`}
      >
        {!useCardMode && <TableHeader columns={visibleColumns} />}
        <EmptyState title={emptyText} height="h-[180px]" />
      </div>
    );
  }

  // ── Card mode（行動版）──
  if (useCardMode) {
    return (
      <div
        role="table"
        aria-label={ariaLabel}
        aria-rowcount={items.length + 1}
        className={`flex flex-col gap-2 ${className}`}
      >
        {items.map((item, idx) => (
          <Card
            key={rowKey(item)}
            item={item}
            idx={idx}
            columns={columns}
            rowHref={rowHref}
          />
        ))}
      </div>
    );
  }

  // ── Table mode（桌機）──
  const useVirtual = items.length >= virtualizeThreshold;
  return (
    <div
      role="table"
      aria-label={ariaLabel}
      aria-rowcount={items.length + 1}
      aria-colcount={visibleColumns.length}
      className={`overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] ${className}`}
    >
      <TableHeader columns={visibleColumns} />
      {useVirtual ? (
        <VirtualizedRows
          items={items}
          rowKey={rowKey}
          columns={visibleColumns}
          rowHref={rowHref}
          rowHeight={rowHeight}
          viewportHeight={virtualViewportHeight}
        />
      ) : (
        items.map((item, idx) => (
          <TableRow
            key={rowKey(item)}
            item={item}
            idx={idx}
            columns={visibleColumns}
            rowHref={rowHref}
          />
        ))
      )}
    </div>
  );
}
