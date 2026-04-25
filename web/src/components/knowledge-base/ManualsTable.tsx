"use client";

import { Download, Trash2, Loader } from "lucide-react";

interface ManualItem {
  id: string;
  fileName: string;
  brand: string;
  pages: number;
  chunks: number | null;
  uploadedAt: string;
  status: "completed" | "processing";
}

const manuals: ManualItem[] = [
  {
    id: "m-001",
    fileName: "Yale_YDM-4109_安裝手冊.pdf",
    brand: "Yale",
    pages: 48,
    chunks: 156,
    uploadedAt: "2天前",
    status: "completed",
  },
  {
    id: "m-002",
    fileName: "Samsung_SHP-DP609_維修指南.pdf",
    brand: "Samsung",
    pages: 72,
    chunks: 234,
    uploadedAt: "3天前",
    status: "completed",
  },
  {
    id: "m-003",
    fileName: "Gateman_F300_用戶手冊.pdf",
    brand: "Gateman",
    pages: 32,
    chunks: 98,
    uploadedAt: "1週前",
    status: "completed",
  },
  {
    id: "m-004",
    fileName: "美樂_ENTR_技術規格.pdf",
    brand: "美樂",
    pages: 24,
    chunks: null,
    uploadedAt: "1小時前",
    status: "processing",
  },
  {
    id: "m-005",
    fileName: "Philips_9300_安裝指南.pdf",
    brand: "Philips",
    pages: 56,
    chunks: 178,
    uploadedAt: "2週前",
    status: "completed",
  },
  {
    id: "m-006",
    fileName: "Yale_YDR-323_電子鎖快速指南.pdf",
    brand: "Yale",
    pages: 16,
    chunks: 45,
    uploadedAt: "1個月前",
    status: "completed",
  },
];

const columns = [
  { label: "檔案名稱", width: "flex-1", align: "text-left" },
  { label: "品牌", width: "w-[80px]", align: "text-left" },
  { label: "頁數", width: "w-[60px]", align: "text-right" },
  { label: "切片數", width: "w-[70px]", align: "text-right" },
  { label: "上傳日期", width: "w-[80px]", align: "text-left" },
  { label: "處理狀態", width: "w-[90px]", align: "text-center" },
  { label: "操作", width: "w-[60px]", align: "text-center" },
];

function StatusBadge({ status }: { status: ManualItem["status"] }) {
  if (status === "processing") {
    return (
      <span className="inline-flex items-center justify-center gap-[6px] rounded-full bg-[#DBEAFE] px-3 py-0 text-xs font-medium text-[var(--primary)]">
        <Loader className="h-3 w-3 animate-spin" />
        處理中
      </span>
    );
  }
  return (
    <span className="inline-flex items-center justify-center rounded-full bg-[#ECFDF5] px-3 py-0 text-xs font-medium text-[var(--status-success)]">
      已完成
    </span>
  );
}

export default function ManualsTable() {
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

      {/* Rows */}
      {manuals.map((item) => (
        <div
          key={item.id}
          className="flex h-12 items-center border-t border-[var(--border)] px-4"
        >
          <span className="flex-1 truncate text-[13px] text-[var(--text-primary)]">
            {item.fileName}
          </span>
          <span className="w-[80px] text-[13px] text-[var(--text-primary)]">
            {item.brand}
          </span>
          <span className="w-[60px] text-right text-[13px] text-[var(--text-secondary)]">
            {item.pages}頁
          </span>
          <span className="w-[70px] text-right text-[13px] text-[var(--text-secondary)]">
            {item.chunks !== null ? `${item.chunks}切片` : "-"}
          </span>
          <span className="w-[80px] text-[13px] text-[var(--text-secondary)]">
            {item.uploadedAt}
          </span>
          <span className="flex w-[90px] justify-center">
            <StatusBadge status={item.status} />
          </span>
          <span className="flex w-[60px] items-center justify-center gap-3">
            <button>
              <Download
                className={`h-4 w-4 ${
                  item.status === "processing"
                    ? "text-[var(--text-disabled)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              />
            </button>
            <button>
              <Trash2 className="h-4 w-4 text-[var(--text-secondary)] hover:text-[var(--status-danger)]" />
            </button>
          </span>
        </div>
      ))}
    </div>
  );
}
