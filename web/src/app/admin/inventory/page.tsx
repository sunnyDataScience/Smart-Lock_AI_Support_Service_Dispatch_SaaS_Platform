"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Search, ChevronDown, RefreshCw } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import InventoryTable from "@/components/admin/InventoryTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type InventoryItem = components["schemas"]["InventoryItem"];
type StockStatus = components["schemas"]["InventoryStockStatus"];

interface InventoryItemPage {
  items?: InventoryItem[];
  next_cursor?: string | null;
  has_more?: boolean;
}

const PAGE_LIMIT = 50;

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [keyword, setKeyword] = useState("");

  async function fetchItems() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: String(PAGE_LIMIT) });
      const res = await api.get<InventoryItemPage>(
        `/api/v1/inventory/items?${params.toString()}`,
      );
      setItems(res.items ?? []);
      setHasMore(!!res.has_more);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    if (!keyword.trim()) return items;
    const q = keyword.trim().toLowerCase();
    return items.filter(
      (i) =>
        i.name.toLowerCase().includes(q) ||
        i.part_number.toLowerCase().includes(q),
    );
  }, [items, keyword]);

  const summary = useMemo(() => {
    const total = items.length;
    const low = items.filter((i) => i.stock_status === "low_stock").length;
    const out = items.filter((i) => i.stock_status === "out_of_stock").length;
    return { total, low, out };
  }, [items]);

  const summaryCards = [
    {
      label: hasMore ? `本頁品項 (+)` : "本頁品項",
      value: summary.total,
      textColor: "var(--text-primary)",
      bgColor: "var(--bg-surface)",
      borderColor: "var(--border)",
    },
    {
      label: "低庫存",
      value: summary.low,
      textColor: "#92400E",
      bgColor: "#FFFBEB",
      borderColor: "#FDE68A",
    },
    {
      label: "缺貨",
      value: summary.out,
      textColor: "#991B1B",
      bgColor: "#FEF2F2",
      borderColor: "#FECACA",
    },
  ];

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              物料庫存管理
            </h1>
            <div className="flex items-center gap-2">
              <button
                onClick={fetchItems}
                disabled={loading}
                title="重新整理"
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${
                    loading ? "animate-spin" : ""
                  }`}
                />
              </button>
              <button
                disabled
                title="即將推出（需 createInventoryItem 端點）"
                className="flex cursor-not-allowed items-center gap-[6px] rounded-lg bg-[var(--primary)] px-4 py-[10px] text-sm font-medium text-white opacity-50"
              >
                <Plus className="h-4 w-4" />
                新增物料
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] leading-relaxed text-amber-800">
            目前僅展示 read-only 庫存清單（最近 {PAGE_LIMIT} 筆）；
            inventory_items 為全公司共用倉庫表（無 tenant_id），所有租戶共享庫存視角。
            補貨 / 編輯 / 異動紀錄等寫入流程需 inventory_transactions 端點接入後再上線。
          </div>

          <div className="flex gap-4">
            {summaryCards.map((card) => (
              <div
                key={card.label}
                className="flex flex-1 flex-col gap-1 rounded-lg border px-4 py-3"
                style={{
                  backgroundColor: card.bgColor,
                  borderColor: card.borderColor,
                }}
              >
                <span
                  className="text-[13px] font-medium"
                  style={{ color: card.textColor }}
                >
                  {card.label}
                </span>
                <span
                  className="text-[28px] font-bold"
                  style={{ color: card.textColor }}
                >
                  {card.value}
                </span>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
              <Search className="h-4 w-4 text-[var(--text-secondary)]" />
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="搜尋物料名稱或料號（本頁過濾）..."
                className="flex-1 bg-transparent text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
              />
            </div>
            <button
              disabled
              title="即將推出（需 server-side category filter）"
              className="flex w-[160px] cursor-not-allowed items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 opacity-50"
            >
              <span className="text-[13px] text-[var(--text-secondary)]">
                物料類別
              </span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>
            <button
              disabled
              title="即將推出（需 server-side status filter）"
              className="flex w-[160px] cursor-not-allowed items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 opacity-50"
            >
              <span className="text-[13px] text-[var(--text-secondary)]">
                庫存狀態
              </span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>
          </div>

          <InventoryTable items={filtered} loading={loading} />
        </div>
      </div>
    </div>
  );
}
