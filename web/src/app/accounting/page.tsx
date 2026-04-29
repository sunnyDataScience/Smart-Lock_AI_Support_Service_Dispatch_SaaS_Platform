"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  RefreshCw,
  Wallet,
  FileText,
  BarChart3,
  Calendar,
  ChevronDown,
  CheckCircle2,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import SettlementTable from "@/components/accounting/SettlementTable";
import ReconciliationsTable from "@/components/accounting/ReconciliationsTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type Settlement = components["schemas"]["Settlement"];
type SettlementPage = components["schemas"]["SettlementPage"];
type Reconciliation = components["schemas"]["Reconciliation"];
type ReconciliationPage = components["schemas"]["ReconciliationPage"];
type ReconciliationStatus = components["schemas"]["ReconciliationStatus"];
type ReconciliationApproveResponse = {
  reconciliation: Reconciliation;
  settlement: Settlement;
};

const RECON_STATUS_FILTERS: { value: ReconciliationStatus | ""; label: string }[] = [
  { value: "pending", label: "待核准" },
  { value: "approved", label: "已核准" },
  { value: "disputed", label: "爭議中" },
  { value: "", label: "全部" },
];

const tabs = [
  {
    icon: Wallet,
    label: "結算管理",
    href: "/accounting" as string | undefined,
    dot: false,
  },
  {
    icon: FileText,
    label: "發票管理",
    href: "/accounting/invoices" as string | undefined,
    dot: true,
  },
  {
    icon: BarChart3,
    label: "營收報表",
    href: "/accounting/revenue" as string | undefined,
    dot: false,
  },
];

const segments = [
  { label: "月結(5號)", active: true },
  { label: "雙週結", active: false },
  { label: "週結", active: false },
];

function formatTime(d: Date): string {
  return d.toLocaleTimeString("zh-TW", { hour12: false });
}

export default function AccountingPage() {
  const pathname = usePathname();
  const [items, setItems] = useState<Settlement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const [recons, setRecons] = useState<Reconciliation[]>([]);
  const [reconsLoading, setReconsLoading] = useState(true);
  const [reconsError, setReconsError] = useState<string | null>(null);
  const [reconStatus, setReconStatus] = useState<ReconciliationStatus | "">(
    "pending",
  );
  const [approveTarget, setApproveTarget] = useState<Reconciliation | null>(
    null,
  );
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  const fetchSettlements = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<SettlementPage>(
        "/api/v1/accounting/settlements?limit=50",
      );
      setItems(res.items ?? []);
      setUpdatedAt(new Date());
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
  }, []);

  const fetchReconciliations = useCallback(
    async (statusFilter: ReconciliationStatus | "") => {
      setReconsLoading(true);
      setReconsError(null);
      try {
        const query: Record<string, string | number> = { limit: 50 };
        if (statusFilter) query.status = statusFilter;
        const res = await api.get<ReconciliationPage>(
          "/api/v1/accounting/reconciliations",
          { query },
        );
        setRecons(res.items ?? []);
      } catch (e) {
        setReconsError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        setReconsLoading(false);
      }
    },
    [],
  );

  const refreshAll = useCallback(() => {
    fetchSettlements();
    fetchReconciliations(reconStatus);
  }, [fetchSettlements, fetchReconciliations, reconStatus]);

  useEffect(() => {
    fetchSettlements();
  }, [fetchSettlements]);

  useEffect(() => {
    fetchReconciliations(reconStatus);
  }, [fetchReconciliations, reconStatus]);

  const handleApprove = async (recon: Reconciliation, note: string) => {
    setApproving(true);
    setApproveError(null);
    try {
      const trimmed = note.trim();
      const body = trimmed ? { note: trimmed } : {};
      await api.post<ReconciliationApproveResponse>(
        `/api/v1/accounting/reconciliations/${encodeURIComponent(recon.id)}/approve`,
        body,
      );
      setApproveTarget(null);
      setToast(
        `已核准對帳 ${recon.id.slice(0, 8)}（已建立 ${recon.technician_payout} 結算）`,
      );
      fetchReconciliations(reconStatus);
      fetchSettlements();
    } catch (e) {
      setApproveError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header + Tabs */}
        <div className="flex flex-col bg-[var(--bg-surface)]">
          {/* Header Row */}
          <div className="flex items-center justify-between px-8 py-5">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                財務結算管理
              </h1>
              <button
                onClick={refreshAll}
                disabled={loading || reconsLoading}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                title="重新整理"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${loading || reconsLoading ? "animate-spin" : ""}`}
                />
              </button>
              <span className="text-[13px] text-[var(--text-secondary)]">
                {updatedAt
                  ? `最後更新：${formatTime(updatedAt)}`
                  : "尚未載入"}
              </span>
              <span
                className="flex items-center gap-[6px] rounded-full px-3 py-1 text-xs font-medium"
                style={{
                  backgroundColor: error ? "#FEE2E2" : "#DCFCE7",
                  color: error ? "#B91C1C" : "#15803D",
                }}
              >
                <span
                  className="h-[6px] w-[6px] rounded-full"
                  style={{ backgroundColor: error ? "#DC2626" : "#22C55E" }}
                />
                {error ? "連線失敗" : "已連線"}
              </span>
            </div>
          </div>

          {/* Tab Bar */}
          <div className="flex border-b border-[var(--border)] px-8">
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              const content = (
                <>
                  <tab.icon
                    className={`h-[18px] w-[18px] ${
                      isActive
                        ? "text-[var(--primary)]"
                        : "text-[var(--text-secondary)]"
                    }`}
                  />
                  <span
                    className={`text-sm ${
                      isActive
                        ? "font-semibold text-[var(--primary)]"
                        : "font-medium text-[var(--text-secondary)]"
                    }`}
                  >
                    {tab.label}
                  </span>
                  {tab.dot && (
                    <span className="h-2 w-2 rounded-full bg-[#EF4444]" />
                  )}
                </>
              );

              const className = `flex items-center gap-2 px-4 py-3 ${
                isActive ? "border-b-2 border-[var(--primary)]" : ""
              }`;

              if (tab.href) {
                return (
                  <Link key={tab.label} href={tab.href} className={className}>
                    {content}
                  </Link>
                );
              }

              return (
                <div key={tab.label} className={className}>
                  {content}
                </div>
              );
            })}
          </div>
        </div>

        {/* Settlement Period Selector — disabled until period filter API lands */}
        <div className="flex items-center gap-4 px-8 py-4">
          {/* Month Dropdown — disabled */}
          <button
            disabled
            title="即將推出"
            className="flex cursor-not-allowed items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-[14px] py-2 opacity-60"
          >
            <Calendar className="h-4 w-4 text-[var(--text-disabled)]" />
            <span className="text-sm font-medium text-[var(--text-disabled)]">
              所有期間
            </span>
            <ChevronDown className="h-4 w-4 text-[var(--text-disabled)]" />
          </button>

          {/* Segmented Control — disabled */}
          <div
            className="flex rounded-md bg-[#F1F5F9] p-[3px] opacity-60"
            title="即將推出"
          >
            {segments.map((seg) => (
              <button
                key={seg.label}
                disabled
                title="即將推出"
                className={`cursor-not-allowed rounded px-[14px] py-[6px] text-[13px] ${
                  seg.active
                    ? "bg-[var(--bg-surface)] font-semibold text-[var(--text-disabled)] shadow-sm"
                    : "font-medium text-[var(--text-disabled)]"
                }`}
              >
                {seg.label}
              </button>
            ))}
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Total Badge — real count from API */}
          <div className="rounded-lg bg-[var(--primary)] px-5 py-[10px]">
            <span className="text-lg font-bold text-white">
              共 {items.length} 筆
            </span>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mx-8 mb-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Mock Data Notice */}
        <div className="mx-8 mb-2 rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
          對帳列表來自 listReconciliations、結算列表來自 listSettlements 即時資料；核准對帳同時建立對應結算。期間選擇器、批次確認/標記已付、結算詳情
          modal 待後續 endpoints 接入後上線。
        </div>

        {/* Body */}
        <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-2">
          {/* Reconciliations Section */}
          <section className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                  對帳記錄
                </h2>
                <span className="text-[13px] text-[var(--text-secondary)]">
                  共 {recons.length} 筆
                </span>
              </div>
              <div className="flex items-center gap-2">
                {RECON_STATUS_FILTERS.map((opt) => {
                  const isActive = opt.value === reconStatus;
                  return (
                    <button
                      key={opt.label}
                      onClick={() => setReconStatus(opt.value)}
                      className={`rounded-md px-3 py-[6px] text-[13px] font-medium transition ${
                        isActive
                          ? "bg-[var(--primary)] text-white"
                          : "border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                      }`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {reconsError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {reconsError}
              </div>
            )}

            <ReconciliationsTable
              items={recons}
              loading={reconsLoading}
              onApprove={(recon) => {
                setApproveError(null);
                setApproveTarget(recon);
              }}
              pendingApproveId={approving ? approveTarget?.id ?? null : null}
            />
          </section>

          {/* Settlements Section */}
          <section className="flex flex-col gap-3 pb-4">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                結算記錄
              </h2>
              <span className="text-[13px] text-[var(--text-secondary)]">
                共 {items.length} 筆
              </span>
            </div>
            <SettlementTable items={items} loading={loading} />
          </section>
        </div>
      </div>

      {approveTarget && (
        <ApproveReconciliationModal
          recon={approveTarget}
          pending={approving}
          error={approveError}
          onCancel={() => {
            if (approving) return;
            setApproveTarget(null);
            setApproveError(null);
          }}
          onConfirm={(note) => handleApprove(approveTarget, note)}
        />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
          <CheckCircle2 className="h-4 w-4" />
          {toast}
        </div>
      )}
    </div>
  );
}

function ApproveReconciliationModal({
  recon,
  pending,
  error,
  onCancel,
  onConfirm,
}: {
  recon: Reconciliation;
  pending: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (note: string) => void;
}) {
  const [note, setNote] = useState("");
  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={() => !pending && onCancel()}
    >
      <div
        className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-[var(--success)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            核准對帳
          </span>
        </div>
        <div className="mb-4 space-y-1 rounded-lg bg-[var(--bg-page)] p-3 text-[13px]">
          <div className="flex justify-between">
            <span className="text-[var(--text-secondary)]">對帳 ID</span>
            <span className="font-mono text-[var(--text-primary)]">
              {recon.id.slice(0, 8)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-secondary)]">技師</span>
            <span className="text-[var(--text-primary)]">
              {recon.technician_name ?? recon.technician_id.slice(0, 8)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-secondary)]">技師應領</span>
            <span className="font-mono font-semibold text-[var(--text-primary)]">
              NT$ {Number(recon.technician_payout).toLocaleString("en-US")}
            </span>
          </div>
        </div>
        <p className="mb-3 text-[13px] leading-[1.6] text-[var(--text-secondary)]">
          核准後將建立對應結算（status=pending），無法復原。可選填稽核備註：
        </p>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          disabled={pending}
          rows={3}
          placeholder="備註（選填，最多 500 字）"
          className="w-full resize-none rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:opacity-50"
        />

        {error && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={() => onConfirm(note)}
            disabled={pending}
            className="rounded-md bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "核准中…" : "確認核准"}
          </button>
        </div>
      </div>
    </div>
  );
}
