"use client";

import { Download, Trash2, Loader, AlertCircle } from "lucide-react";
import type { components } from "@/types/api.generated";
import { formatRelative } from "@/lib/format";

type Manual = components["schemas"]["Manual"];

interface Props {
  items: Manual[];
  loading?: boolean;
  onDelete?: (manual: Manual) => void;
  pendingDeleteId?: string | null;
}

const columns = [
  { label: "檔案名稱", width: "flex-1", align: "text-left" },
  { label: "品牌 / 型號", width: "w-[140px]", align: "text-left" },
  { label: "檔案大小", width: "w-[90px]", align: "text-right" },
  { label: "切片數", width: "w-[80px]", align: "text-right" },
  { label: "上傳日期", width: "w-[100px]", align: "text-left" },
  { label: "處理狀態", width: "w-[100px]", align: "text-center" },
  { label: "操作", width: "w-[60px]", align: "text-center" },
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: Manual["status"] }) {
  if (status === "processing") {
    return (
      <span className="inline-flex items-center justify-center gap-[6px] rounded-full bg-[#DBEAFE] px-3 py-0 text-xs font-medium text-[var(--primary)]">
        <Loader className="h-3 w-3 animate-spin" />
        處理中
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center justify-center gap-[6px] rounded-full bg-[#FEE2E2] px-3 py-0 text-xs font-medium text-[var(--status-danger)]">
        <AlertCircle className="h-3 w-3" />
        失敗
      </span>
    );
  }
  return (
    <span className="inline-flex items-center justify-center rounded-full bg-[#ECFDF5] px-3 py-0 text-xs font-medium text-[var(--status-success)]">
      已完成
    </span>
  );
}

export default function ManualsTable({ items, loading, onDelete, pendingDeleteId }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)]">
      {/* Header */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-4">
        {columns.map((col) => (
          <span
            key={col.label}
            className={`${col.width} text-[13px] font-semibold text-[var(--text-secondary)] ${col.align}`}
          >
            {col.label}
          </span>
        ))}
      </div>

      {/* Empty state */}
      {!loading && items.length === 0 && (
        <div className="flex h-24 items-center justify-center border-t border-[var(--border)] text-sm text-[var(--text-secondary)]">
          目前沒有手冊
        </div>
      )}

      {/* Loading skeleton */}
      {loading && items.length === 0 && (
        <div className="flex h-24 items-center justify-center border-t border-[var(--border)] text-sm text-[var(--text-secondary)]">
          載入中…
        </div>
      )}

      {/* Rows */}
      {items.map((item) => {
        const isReady = item.status === "ready";
        const brandModel = item.model ? `${item.brand} / ${item.model}` : item.brand;
        return (
          <div
            key={item.id}
            className="flex h-12 items-center border-t border-[var(--border)] px-4"
          >
            <span
              className="flex-1 truncate text-[13px] text-[var(--text-primary)]"
              title={item.title}
            >
              {item.title}
            </span>
            <span className="w-[140px] truncate text-[13px] text-[var(--text-primary)]">
              {brandModel}
            </span>
            <span className="w-[90px] text-right text-[13px] text-[var(--text-secondary)]">
              {formatBytes(item.file_size_bytes)}
            </span>
            <span className="w-[80px] text-right text-[13px] text-[var(--text-secondary)]">
              {item.chunk_count != null ? `${item.chunk_count} 段` : "—"}
            </span>
            <span className="w-[100px] text-[13px] text-[var(--text-secondary)]">
              {formatRelative(item.created_at)}
            </span>
            <span className="flex w-[100px] justify-center">
              <StatusBadge status={item.status} />
            </span>
            <span className="flex w-[60px] items-center justify-center gap-3">
              <button
                disabled
                title="即將推出"
                className="cursor-not-allowed"
              >
                <Download
                  className={`h-4 w-4 ${
                    isReady ? "text-[var(--text-secondary)]" : "text-[var(--text-disabled)]"
                  }`}
                />
              </button>
              {onDelete ? (
                <button
                  onClick={() => onDelete(item)}
                  disabled={pendingDeleteId === item.id}
                  title="刪除手冊"
                  className="rounded p-[2px] text-[var(--text-secondary)] transition hover:bg-red-50 hover:text-[var(--status-danger)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              ) : (
                <button disabled title="即將推出" className="cursor-not-allowed">
                  <Trash2 className="h-4 w-4 text-[var(--text-disabled)]" />
                </button>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}
