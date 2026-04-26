"use client";

interface StockBadge {
  label: string;
  textColor: string;
  bgColor: string;
}

interface InventoryRow {
  name: string;
  sku: string;
  stock: number;
  stockBadge: StockBadge | null;
  safetyThreshold: number;
  lastRestockDate: string;
}

const rows: InventoryRow[] = [
  {
    name: "智慧門鎖主機板",
    sku: "SKU-SL-001",
    stock: 245,
    stockBadge: null,
    safetyThreshold: 50,
    lastRestockDate: "2026/04/10",
  },
  {
    name: "鋰電池模組",
    sku: "SKU-BT-032",
    stock: 18,
    stockBadge: { label: "低庫存", textColor: "#B45309", bgColor: "#FFFBEB" },
    safetyThreshold: 30,
    lastRestockDate: "2026/03/22",
  },
  {
    name: "指紋辨識模組",
    sku: "SKU-FP-015",
    stock: 0,
    stockBadge: { label: "缺貨", textColor: "#DC2626", bgColor: "#FEF2F2" },
    safetyThreshold: 20,
    lastRestockDate: "2026/02/15",
  },
  {
    name: "WiFi 通訊模組",
    sku: "SKU-WF-008",
    stock: 89,
    stockBadge: null,
    safetyThreshold: 25,
    lastRestockDate: "2026/04/18",
  },
  {
    name: "不鏽鋼鎖體",
    sku: "SKU-LB-021",
    stock: 8,
    stockBadge: { label: "低庫存", textColor: "#B45309", bgColor: "#FFFBEB" },
    safetyThreshold: 15,
    lastRestockDate: "2026/03/05",
  },
  {
    name: "IC 卡讀取器",
    sku: "SKU-IC-044",
    stock: 0,
    stockBadge: { label: "缺貨", textColor: "#DC2626", bgColor: "#FEF2F2" },
    safetyThreshold: 10,
    lastRestockDate: "2026/01/28",
  },
  {
    name: "觸控面板",
    sku: "SKU-TP-027",
    stock: 156,
    stockBadge: null,
    safetyThreshold: 40,
    lastRestockDate: "2026/04/20",
  },
];

const columns = [
  { label: "物料名稱", width: "w-[180px]" },
  { label: "SKU", width: "w-[120px]" },
  { label: "當前庫存", width: "w-[150px]" },
  { label: "安全庫存閾值", width: "w-[110px]" },
  { label: "最後補貨日期", width: "w-[120px]" },
  { label: "操作", width: "flex-1" },
];

export default function InventoryTable() {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center border-b border-[var(--border)] bg-[#F8FAFC]">
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
          key={row.sku}
          className={`flex h-[52px] items-center bg-[var(--bg-surface)] ${
            idx < rows.length - 1 ? "border-b border-[var(--border)]" : ""
          }`}
        >
          <div className="flex w-[180px] items-center px-3">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              {row.name}
            </span>
          </div>

          <div className="flex w-[120px] items-center px-3">
            <span className="font-mono text-xs text-[var(--text-secondary)]">
              {row.sku}
            </span>
          </div>

          <div className="flex w-[150px] items-center gap-2 px-3">
            <span
              className={`text-[13px] font-semibold ${
                row.stock === 0
                  ? "text-[#DC2626]"
                  : row.stockBadge
                    ? "text-[#B45309]"
                    : "text-[var(--text-primary)]"
              }`}
            >
              {row.stock}
            </span>
            {row.stockBadge && (
              <span
                className="rounded-[10px] px-2 py-[2px] text-[11px] font-semibold"
                style={{
                  color: row.stockBadge.textColor,
                  backgroundColor: row.stockBadge.bgColor,
                }}
              >
                {row.stockBadge.label}
              </span>
            )}
          </div>

          <div className="flex w-[110px] items-center px-3">
            <span className="text-[13px] text-[var(--text-secondary)]">
              {row.safetyThreshold}
            </span>
          </div>

          <div className="flex w-[120px] items-center px-3">
            <span className="text-[13px] text-[var(--text-secondary)]">
              {row.lastRestockDate}
            </span>
          </div>

          <div className="flex flex-1 items-center justify-end gap-[6px] px-3">
            <button className="rounded-md bg-[var(--primary)] px-3 py-[5px] text-xs font-medium text-white">
              補貨
            </button>
            <button className="rounded-md border border-[var(--border)] px-3 py-[5px] text-xs font-medium text-[var(--text-secondary)]">
              編輯
            </button>
            <button className="rounded-md border border-[var(--border)] px-3 py-[5px] text-xs font-medium text-[var(--text-secondary)]">
              紀錄
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
