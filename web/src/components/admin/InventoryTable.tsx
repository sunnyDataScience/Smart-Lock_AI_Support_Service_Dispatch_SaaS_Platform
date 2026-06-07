"use client";

import { useMemo, useState } from "react";
import type { components } from "@/types/api.generated";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import RestockInventoryModal from "./RestockInventoryModal";
import EditInventoryItemModal from "./EditInventoryItemModal";
import InventoryLogModal from "./InventoryLogModal";

type InventoryItem = components["schemas"]["InventoryItem"];
type StockStatus = components["schemas"]["InventoryStockStatus"];

interface Props {
  items: InventoryItem[];
  loading?: boolean;
  onItemsChanged?: () => void;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
}

export default function InventoryTable({ items, loading, onItemsChanged }: Props) {
  const t = useTranslations("components.admin.inventory");
  const [restockItem, setRestockItem] = useState<InventoryItem | null>(null);
  const [editItem, setEditItem] = useState<InventoryItem | null>(null);
  const [logItem, setLogItem] = useState<InventoryItem | null>(null);

  const columns = useMemo(
    () => [
      { key: "name", label: t("cols.name"), width: "w-[200px] shrink-0" },
      { key: "partNumber", label: t("cols.partNumber"), width: "w-[140px] shrink-0" },
      { key: "category", label: t("cols.category"), width: "w-[120px] shrink-0" },
      { key: "quantity", label: t("cols.quantity"), width: "w-[150px] shrink-0" },
      { key: "reorderPoint", label: t("cols.reorderPoint"), width: "w-[100px] shrink-0" },
      { key: "lastRestocked", label: t("cols.lastRestocked"), width: "w-[140px] shrink-0" },
      { key: "actions", label: t("cols.actions"), width: "flex-1 min-w-0" },
    ],
    [t],
  );

  const STATUS_BADGE: Record<
    StockStatus,
    { label: string; textColor: string; bgColor: string } | null
  > = {
    in_stock: null,
    low_stock: { label: t("badge.lowStock"), textColor: "#B45309", bgColor: "#FFFBEB" },
    out_of_stock: { label: t("badge.outOfStock"), textColor: "#DC2626", bgColor: "#FEF2F2" },
  };

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center border-b border-[var(--border)] bg-[#F8FAFC]">
        {columns.map((col) => (
          <div
            key={col.key}
            className={`flex items-center px-3 ${col.width}`}
          >
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {loading && items.length === 0 ? (
        <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
          {t("loading")}
        </div>
      ) : items.length === 0 ? (
        <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
          {t("empty")}
        </div>
      ) : (
        items.map((row, idx) => {
          const badge = STATUS_BADGE[row.stock_status];
          const stockColor =
            row.stock_status === "out_of_stock"
              ? "text-[#DC2626]"
              : row.stock_status === "low_stock"
                ? "text-[#B45309]"
                : "text-[var(--text-primary)]";
          return (
            <div
              key={row.id}
              className={`flex h-[52px] items-center bg-[var(--bg-surface)] ${
                idx < items.length - 1
                  ? "border-b border-[var(--border)]"
                  : ""
              }`}
            >
              <div className="flex w-[200px] shrink-0 items-center px-3">
                <span className="truncate text-[13px] font-medium text-[var(--text-primary)]">
                  {row.name}
                </span>
              </div>

              <div className="flex w-[140px] shrink-0 items-center px-3">
                <span className="font-mono text-xs text-[var(--text-secondary)]">
                  {row.part_number}
                </span>
              </div>

              <div className="flex w-[120px] shrink-0 items-center px-3">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  {row.category}
                </span>
              </div>

              <div className="flex w-[150px] shrink-0 items-center gap-2 px-3">
                <span className={`text-[13px] font-semibold ${stockColor}`}>
                  {row.quantity_on_hand}
                </span>
                {badge && (
                  <span
                    className="rounded-[10px] px-2 py-[2px] text-[11px] font-semibold"
                    style={{
                      color: badge.textColor,
                      backgroundColor: badge.bgColor,
                    }}
                  >
                    {badge.label}
                  </span>
                )}
              </div>

              <div className="flex w-[100px] shrink-0 items-center px-3">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  {row.reorder_point}
                </span>
              </div>

              <div className="flex w-[140px] shrink-0 items-center px-3">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  {formatDate(row.last_restocked_at)}
                </span>
              </div>

              <div className="flex min-w-0 flex-1 items-center justify-end gap-[6px] px-3">
                <button
                  onClick={() => setRestockItem(row)}
                  className="rounded-md bg-[var(--primary)] px-3 py-[5px] text-xs font-medium text-white hover:opacity-90"
                >
                  {t("actions.restock")}
                </button>
                <button
                  onClick={() => setEditItem(row)}
                  className="rounded-md border border-[var(--border)] px-3 py-[5px] text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                >
                  {t("actions.edit")}
                </button>
                <button
                  onClick={() => setLogItem(row)}
                  className="rounded-md border border-[var(--border)] px-3 py-[5px] text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                >
                  {t("actions.log")}
                </button>
              </div>
            </div>
          );
        })
      )}

      <RestockInventoryModal
        open={!!restockItem}
        onOpenChange={(o) => {
          if (!o) setRestockItem(null);
        }}
        itemId={restockItem?.id ?? null}
        itemName={restockItem?.name ?? ""}
        currentQuantity={restockItem?.quantity_on_hand ?? 0}
        onSuccess={() => {
          setRestockItem(null);
          onItemsChanged?.();
        }}
      />

      <EditInventoryItemModal
        open={!!editItem}
        onOpenChange={(o) => {
          if (!o) setEditItem(null);
        }}
        item={editItem}
        onSuccess={() => {
          setEditItem(null);
          onItemsChanged?.();
        }}
      />

      <InventoryLogModal
        open={!!logItem}
        onOpenChange={(o) => {
          if (!o) setLogItem(null);
        }}
        itemId={logItem?.id ?? null}
        itemName={logItem?.name ?? ""}
      />
    </div>
  );
}
