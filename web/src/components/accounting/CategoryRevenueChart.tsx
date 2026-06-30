"use client";

// 問題類別營收佔比（取代原 ServiceTypeChart 假資料）。資料源 getRevenueSummary.by_category
// （invoices→work_orders→problem_cards.category 聚合）。標題用「問題類別」而非「服務類型」：
// 後端唯一有資料的維度是 pc.category（卡片/密碼/電池…），真正的 service_category enum 未填。

export interface CategoryRevenuePoint {
  category: string;
  revenue: string; // decimal string，例 "29408.00"
  share: number; // 0..1
}

interface Props {
  items: CategoryRevenuePoint[];
  loading?: boolean;
}

const PALETTE = [
  "#2563EB",
  "#F59E0B",
  "#10B981",
  "#8B5CF6",
  "#EC4899",
  "#06B6D4",
  "#0EA5E9",
  "#F43F5E",
];
const TRACK = [
  "#EFF6FF",
  "#FFF7ED",
  "#ECFDF5",
  "#F5F3FF",
  "#FDF2F8",
  "#ECFEFF",
  "#F0F9FF",
  "#FFF1F2",
];

function formatTwd(amount: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export default function CategoryRevenueChart({ items, loading }: Props) {
  // 條寬以最大值正規化（最高類別 = 滿格），純視覺比例，與 share 無關。
  const maxRevenue = items.reduce(
    (m, p) => Math.max(m, Number(p.revenue) || 0),
    0,
  );

  return (
    <div className="flex flex-1 flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <span className="text-base font-semibold text-[var(--text-primary)]">
        問題類別營收佔比
      </span>

      <div className="flex flex-1 flex-col justify-center gap-[14px]">
        {loading && items.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[12px] text-[var(--text-secondary)]">
            載入中…
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[12px] text-[var(--text-secondary)]">
            尚無資料
          </div>
        ) : (
          items.map((row, i) => {
            const rev = Number(row.revenue) || 0;
            const width =
              maxRevenue > 0
                ? `${Math.max((rev / maxRevenue) * 100, 2)}%`
                : "0%";
            return (
              <div key={row.category} className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] text-[var(--text-primary)]">
                    {row.category}
                  </span>
                  <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                    {formatTwd(row.revenue)}
                  </span>
                </div>
                <div
                  className="h-5 w-full rounded"
                  style={{ backgroundColor: TRACK[i % TRACK.length] }}
                >
                  <div
                    className="h-5 rounded"
                    style={{ width, backgroundColor: PALETTE[i % PALETTE.length] }}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
