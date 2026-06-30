"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";
import { useToast } from "@/components/ui/Toast";

type Settlement = components["schemas"]["Settlement"];
type SettlementStatus = components["schemas"]["SettlementStatus"];
type PaymentMethod = NonNullable<Settlement["payment_method"]>;

interface Props {
  items: Settlement[];
  loading?: boolean;
  onItemsChanged?: () => void;
}

// Tone（顏色）固定；label 由 i18n 提供。
// 'confirmed' = 批次確認後中間態（後端 SettlementStatus 已補；前端生成型別待 TS
// 產生器修復後同步，故用 string key + 下方 lookup fallback 安全處理）。
const STATUS_TONE: Record<string, { textColor: string; bgColor: string }> = {
  pending: { textColor: "#B45309", bgColor: "#FEF3C7" },
  confirmed: { textColor: "#1E40AF", bgColor: "#DBEAFE" },
  paid: { textColor: "#10B981", bgColor: "#D1FAE5" },
  failed: { textColor: "#B91C1C", bgColor: "#FEE2E2" },
};

function formatAmount(amount: string, currency: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `${currency} ${amount}`;
  return `${currency} ${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-TW", { hour12: false });
}

export default function SettlementTable({ items, loading, onItemsChanged }: Props) {
  const t = useTranslations("components.accounting.settlementTable");
  const { toast } = useToast();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchSubmitting, setBatchSubmitting] = useState(false);

  function toggleId(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (selectedIds.size === items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((i) => i.id)));
    }
  }

  async function doBatch(action: "confirm" | "mark_paid") {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setBatchSubmitting(true);
    try {
      const res = await api.post<{ data: { updated: number; skipped: number } }>(
        tenantPath("/settlements:batch"),
        { settlement_ids: ids, action },
      );
      toast({
        variant: "success",
        title: action === "confirm" ? "批次確認完成" : "批次標記已付完成",
        description: `更新 ${res.data.updated} 筆 / 略過 ${res.data.skipped} 筆`,
      });
      setSelectedIds(new Set());
      // 清 GET 快取再 refetch：否則列表從 30s 舊快取讀回、狀態更新看不到
      // （cache key 含完整 URL，用廣域 "GET:" 清）。
      cacheInvalidate("GET:");
      onItemsChanged?.();
    } catch (e) {
      const msg =
        friendlyError(e);
      toast({ variant: "error", title: "批次操作失敗", description: msg });
    } finally {
      setBatchSubmitting(false);
    }
  }

  const columns = useMemo(
    () => [
      { label: t("cols.technician"), width: "w-[150px] shrink-0" },
      { label: t("cols.amount"), width: "w-[140px] shrink-0" },
      { label: t("cols.status"), width: "w-[100px] shrink-0" },
      { label: t("cols.paymentMethod"), width: "w-[110px] shrink-0" },
      { label: t("cols.paidAt"), width: "w-[160px] shrink-0" },
      { label: t("cols.createdAt"), width: "flex-1 min-w-[160px] min-w-0" },
    ],
    [t],
  );

  const statusLabels: Record<string, string> = useMemo(
    () => ({
      pending: t("status.pending"),
      confirmed: t("status.confirmed"),
      paid: t("status.paid"),
      failed: t("status.failed"),
    }),
    [t],
  );

  const paymentMethodLabel: Record<PaymentMethod, string> = useMemo(
    () => ({
      bank_transfer: t("paymentMethod.bank_transfer"),
      other: t("paymentMethod.other"),
    }),
    [t],
  );

  const comingSoon = t("comingSoon");

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-[var(--bg-surface)]">
      {/* Batch Action Bar */}
      <div className="flex items-center gap-3 border-b border-[var(--border)] px-8 py-3">
        <input
          type="checkbox"
          checked={selectedIds.size === items.length && items.length > 0}
          onChange={toggleAll}
          className="h-4 w-4 rounded border-[1.5px] border-[var(--border)]"
        />
        <span className="text-[13px] text-[var(--text-secondary)]">
          {t("batchSelectAll")}（已選 {selectedIds.size}）
        </span>
        <button
          onClick={() => doBatch("confirm")}
          disabled={selectedIds.size === 0 || batchSubmitting}
          title={selectedIds.size === 0 ? t("batchHint") : undefined}
          className="rounded-md bg-[var(--primary)] px-4 py-[7px] text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {t("batchConfirm")}
        </button>
        <button
          onClick={() => doBatch("mark_paid")}
          disabled={selectedIds.size === 0 || batchSubmitting}
          title={selectedIds.size === 0 ? t("batchHint") : undefined}
          className="rounded-md border border-[var(--border)] px-4 py-[7px] text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {t("batchMarkPaid")}
        </button>
        {/* 0 選取時批次鈕 disabled（按了沒反應），顯示提示說明需先勾選。*/}
        {selectedIds.size === 0 && (
          <span className="text-[12px] text-[var(--text-disabled)]">
            {t("batchHint")}
          </span>
        )}
      </div>

      {/* Header Row */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-8">
        {columns.map((col) => (
          <div
            key={col.label}
            className={`flex items-center px-2 ${col.width}`}
          >
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {/* Empty / Loading state */}
      {loading && items.length === 0 && (
        <div className="flex h-[160px] items-center justify-center text-sm text-[var(--text-secondary)]">
          {t("loading")}
        </div>
      )}
      {!loading && items.length === 0 && (
        <div className="flex h-[160px] items-center justify-center text-sm text-[var(--text-secondary)]">
          {t("empty")}
        </div>
      )}

      {/* Data Rows */}
      {items.map((s) => {
        // fallback：後端可能回前端生成型別尚未含的 'confirmed'，避免 tone undefined。
        const tone = STATUS_TONE[s.status] ?? STATUS_TONE.pending;
        const methodLabel = s.payment_method
          ? paymentMethodLabel[s.payment_method]
          : "—";
        return (
          <div
            key={s.id}
            className="flex h-[48px] items-center border-b border-[var(--border)] px-8"
          >
            <input
              type="checkbox"
              checked={selectedIds.has(s.id)}
              onChange={() => toggleId(s.id)}
              className="mr-2 h-4 w-4 rounded border-[1.5px] border-[var(--border)]"
            />

            {/* Technician */}
            <div className="flex w-[150px] shrink-0 items-center px-2">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                {s.technician_name || s.technician_id.slice(0, 8)}
              </span>
            </div>

            {/* Amount */}
            <div className="flex w-[140px] shrink-0 items-center px-2">
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {formatAmount(s.amount, s.currency)}
              </span>
            </div>

            {/* Status */}
            <div className="flex w-[100px] shrink-0 items-center px-2">
              <span
                className="rounded-full px-[10px] py-[3px] text-xs font-medium"
                style={{ color: tone.textColor, backgroundColor: tone.bgColor }}
              >
                {statusLabels[s.status] ?? s.status}
              </span>
            </div>

            {/* Payment Method */}
            <div className="flex w-[110px] shrink-0 items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {methodLabel}
              </span>
            </div>

            {/* Paid At */}
            <div className="flex w-[160px] shrink-0 items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {formatDateTime(s.paid_at)}
              </span>
            </div>

            {/* Created At */}
            <div className="flex min-w-0 flex-1 min-w-[160px] items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {formatDateTime(s.created_at)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
