"use client";

interface WarrantyRow {
  id: string;
  brand: string;
  model: string;
  customer: string;
  startDate: string;
  endDate: string;
  remaining: string;
  remainingColor: string;
  remainingBold: boolean;
  status: { label: string; textColor: string; bgColor: string };
  hasApproveButton: boolean;
}

const rows: WarrantyRow[] = [
  {
    id: "WC-20250301",
    brand: "Yale",
    model: "YDM-7116A",
    customer: "王大明",
    startDate: "2025-03-01",
    endDate: "2026-03-01",
    remaining: "186 天",
    remainingColor: "var(--status-success)",
    remainingBold: false,
    status: { label: "有效", textColor: "#15803D", bgColor: "#DCFCE7" },
    hasApproveButton: true,
  },
  {
    id: "WC-20250115",
    brand: "Samsung",
    model: "SHP-DP609",
    customer: "李美玲",
    startDate: "2024-05-15",
    endDate: "2025-05-15",
    remaining: "45 天",
    remainingColor: "var(--status-warning)",
    remainingBold: false,
    status: { label: "寬限期", textColor: "#92400E", bgColor: "#FEF3C7" },
    hasApproveButton: true,
  },
  {
    id: "WC-20250220",
    brand: "Gateman",
    model: "SHINE",
    customer: "張志豪",
    startDate: "2025-06-20",
    endDate: "2026-06-20",
    remaining: "312 天",
    remainingColor: "var(--status-success)",
    remainingBold: false,
    status: { label: "有效", textColor: "#15803D", bgColor: "#DCFCE7" },
    hasApproveButton: true,
  },
  {
    id: "WC-20240210",
    brand: "Schlage",
    model: "BE469ZP",
    customer: "陳小華",
    startDate: "2024-04-10",
    endDate: "2025-04-10",
    remaining: "-15 天",
    remainingColor: "var(--status-danger)",
    remainingBold: true,
    status: { label: "已過期", textColor: "#B91C1C", bgColor: "#FEE2E2" },
    hasApproveButton: false,
  },
  {
    id: "WC-20240422",
    brand: "Kwikset",
    model: "Halo Touch",
    customer: "林雅婷",
    startDate: "2025-04-22",
    endDate: "2026-04-22",
    remaining: "今日到期",
    remainingColor: "var(--status-danger)",
    remainingBold: true,
    status: { label: "有效", textColor: "#15803D", bgColor: "#DCFCE7" },
    hasApproveButton: true,
  },
  {
    id: "WC-20240801",
    brand: "August",
    model: "Wi-Fi Smart Lock",
    customer: "吳建宏",
    startDate: "2024-05-01",
    endDate: "2025-05-01",
    remaining: "18 天",
    remainingColor: "var(--status-danger)",
    remainingBold: true,
    status: { label: "寬限期", textColor: "#92400E", bgColor: "#FEF3C7" },
    hasApproveButton: true,
  },
];

const columns = [
  { label: "案件編號", width: "w-[100px]" },
  { label: "設備", width: "w-[120px]" },
  { label: "客戶", width: "w-[70px]" },
  { label: "保固起始日", width: "w-[95px]" },
  { label: "保固到期日", width: "w-[95px]" },
  { label: "剩餘天數", width: "w-[72px]" },
  { label: "狀態", width: "w-[64px]" },
  { label: "證據", width: "w-[130px]" },
  { label: "操作", width: "flex-1" },
];

function EvidenceThumbnails() {
  return (
    <div className="flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-6 w-6 rounded bg-[#E2E8F0]"
        />
      ))}
      <span className="text-[11px] text-[var(--text-secondary)]">+2</span>
    </div>
  );
}

export default function WarrantyClaimsTable() {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center bg-[#F8FAFC] border-b border-[var(--border)]">
        {columns.map((col) => (
          <div
            key={col.label}
            className={`flex items-center px-3 ${col.width}`}
          >
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {rows.map((row, idx) => (
        <div
          key={row.id}
          className={`flex h-[52px] items-center bg-[var(--bg-surface)] ${
            idx < rows.length - 1
              ? "border-b border-[var(--border)]"
              : ""
          }`}
        >
          <div className="flex w-[100px] items-center px-3">
            <span className="font-mono text-xs font-medium text-[var(--text-primary)]">
              {row.id}
            </span>
          </div>

          <div className="flex w-[120px] flex-col justify-center px-3">
            <span className="text-xs font-semibold text-[var(--text-primary)]">
              {row.brand}
            </span>
            <span className="text-[11px] text-[var(--text-secondary)]">
              {row.model}
            </span>
          </div>

          <div className="flex w-[70px] items-center px-3">
            <span className="text-xs text-[var(--text-primary)]">
              {row.customer}
            </span>
          </div>

          <div className="flex w-[95px] items-center px-3">
            <span className="text-xs text-[var(--text-primary)]">
              {row.startDate}
            </span>
          </div>

          <div className="flex w-[95px] items-center px-3">
            <span className="text-xs text-[var(--text-primary)]">
              {row.endDate}
            </span>
          </div>

          <div className="flex w-[72px] items-center px-3">
            <span
              className="text-xs"
              style={{
                color: row.remainingColor,
                fontWeight: row.remainingBold ? "700" : "600",
              }}
            >
              {row.remaining}
            </span>
          </div>

          <div className="flex w-[64px] items-center px-3">
            <span
              className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
              style={{
                color: row.status.textColor,
                backgroundColor: row.status.bgColor,
              }}
            >
              {row.status.label}
            </span>
          </div>

          <div className="flex w-[130px] items-center px-3">
            <EvidenceThumbnails />
          </div>

          <div className="flex flex-1 items-center justify-end gap-[6px] px-3">
            <button className="rounded-md border border-[var(--border)] px-2 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
              檢視詳情
            </button>
            {row.hasApproveButton && (
              <button className="rounded-md bg-[var(--primary)] px-2 py-1 text-[11px] font-medium text-white">
                核准保固
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
