"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Search, ChevronDown, RefreshCw } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import InventoryTable from "@/components/admin/InventoryTable";
import CreateInventoryItemModal from "@/components/admin/CreateInventoryItemModal";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import type { components } from "@shared/types/api.generated";

type InventoryItem = components["schemas"]["InventoryItem"];
type StockStatus = components["schemas"]["InventoryStockStatus"];

interface InventoryItemPage {
  items?: InventoryItem[];
  next_cursor?: string | null;
  has_more?: boolean;
}

const PAGE_LIMIT = 50;

export default function InventoryPage() {
  const t = useTranslations("admin.inventory");
  const tc = useTranslations("admin.common");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [stockStatusFilter, setStockStatusFilter] = useState<string>("");

  async function fetchItems() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: String(PAGE_LIMIT) });
      if (categoryFilter) params.set("category", categoryFilter);
      if (stockStatusFilter) params.set("stock_status", stockStatusFilter);
      if (keyword.trim()) params.set("keyword", keyword.trim());
      const res = await api.get<InventoryItemPage>(
        tenantPath(`/inventory/items?${params.toString()}`),
      );
      setItems(res.items ?? []);
      setHasMore(!!res.has_more);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryFilter, stockStatusFilter]);

  // 從目前 items 抽 distinct categories（MVP — 完整版需 backend listCategories endpoint）
  const categoryOptions = useMemo(() => {
    const set = new Set<string>();
    items.forEach((i) => {
      if (i.category) set.add(i.category);
    });
    return Array.from(set).sort();
  }, [items]);

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
      label: hasMore ? t("summary.currentMore") : t("summary.current"),
      value: summary.total,
      textColor: "var(--text-primary)",
      bgColor: "var(--bg-surface)",
      borderColor: "var(--border)",
    },
    {
      label: t("summary.low"),
      value: summary.low,
      textColor: "#92400E",
      bgColor: "#FFFBEB",
      borderColor: "#FDE68A",
    },
    {
      label: t("summary.out"),
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
        <div className="flex flex-1 flex-col gap-5 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {t("title")}
            </h1>
            <div className="flex items-center gap-2">
              <button
                onClick={fetchItems}
                disabled={loading}
                title={tc("refresh")}
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${
                    loading ? "animate-spin" : ""
                  }`}
                />
              </button>
              <button
                onClick={() => setCreateOpen(true)}
                title={t("addItem")}
                className="flex items-center gap-[6px] rounded-lg bg-[var(--primary)] px-4 py-[10px] text-sm font-medium text-white hover:opacity-90"
              >
                <Plus className="h-4 w-4" />
                {t("addItem")}
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

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
                placeholder={t("searchPlaceholder")}
                className="flex-1 bg-transparent text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
              />
            </div>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="w-[160px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] outline-none"
            >
              <option value="">{t("categoryLabel")}</option>
              {categoryOptions.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
            <select
              value={stockStatusFilter}
              onChange={(e) => setStockStatusFilter(e.target.value)}
              className="w-[160px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] outline-none"
            >
              <option value="">{t("stockStatusLabel")}</option>
              <option value="in_stock">充足</option>
              <option value="low_stock">低於安全量</option>
              <option value="out_of_stock">缺貨</option>
            </select>
          </div>

          <InventoryTable
            items={filtered}
            loading={loading}
            onItemsChanged={fetchItems}
          />
        </div>
      </div>

      <CreateInventoryItemModal
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSuccess={() => {
          setCreateOpen(false);
          fetchItems();
        }}
      />
    </div>
  );
}
