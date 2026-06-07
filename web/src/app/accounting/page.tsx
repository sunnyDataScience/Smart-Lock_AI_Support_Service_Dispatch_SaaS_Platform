"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  RefreshCw,
  Wallet,
  FileText,
  BarChart3,
  BookText,
  Calendar,
  ChevronDown,
  CheckCircle2,
  Download,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import SettlementTable from "@/components/accounting/SettlementTable";
import ReconciliationsTable from "@/components/accounting/ReconciliationsTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, tenantPath } from "@/lib/api";
import type { components } from "@/types/api.generated";
import { ReportExportModal } from "@/components/admin/reports/ReportExportModal";

type Settlement = components["schemas"]["Settlement"];
type SettlementPage = components["schemas"]["SettlementPage"];
type Reconciliation = components["schemas"]["Reconciliation"];
type ReconciliationPage = components["schemas"]["ReconciliationPage"];
type ReconciliationStatus = components["schemas"]["ReconciliationStatus"];
type ReconciliationApproveResponse = {
  reconciliation: Reconciliation;
  settlement: Settlement;
};

function formatTime(d: Date): string {
  return d.toLocaleTimeString("zh-TW", { hour12: false });
}

export default function AccountingPage() {
  const pathname = usePathname();
  const tPage = useTranslations("accounting");
  const tTabs = useTranslations("accounting.tabs");
  const tCommon = useTranslations("accounting.common");
  const tS = useTranslations("accounting.settlements");

  const RECON_STATUS_FILTERS: { value: ReconciliationStatus | ""; label: string }[] = useMemo(
    () => [
      { value: "pending", label: tS("filterPending") },
      { value: "approved", label: tS("filterApproved") },
      { value: "disputed", label: tS("filterDisputed") },
      { value: "", label: tS("filterAll") },
    ],
    [tS],
  );

  const tabs = useMemo(
    () => [
      {
        icon: Wallet,
        label: tTabs("settlements"),
        href: "/accounting" as string | undefined,
        dot: false,
      },
      {
        icon: FileText,
        label: tTabs("invoices"),
        href: "/accounting/invoices" as string | undefined,
        dot: true,
      },
      {
        icon: BookText,
        label: tTabs("vouchers"),
        href: "/accounting/vouchers" as string | undefined,
        dot: false,
      },
      {
        icon: BarChart3,
        label: tTabs("revenue"),
        href: "/accounting/revenue" as string | undefined,
        dot: false,
      },
    ],
    [tTabs],
  );

  const SEGMENTS = useMemo(
    () => [
      { value: "month", label: tS("segMonth") },
      { value: "biweek", label: tS("segBiweek") },
      { value: "week", label: tS("segWeek") },
    ],
    [tS],
  );
  const [settlementCycle, setSettlementCycle] = useState<"month" | "biweek" | "week">("month");
  const [periodFilter, setPeriodFilter] = useState<"last3m" | "last6m" | "all">("last3m");
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
  const [exportOpen, setExportOpen] = useState(false);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  const fetchSettlements = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // CR-0008（2026-06-04 業主裁 HD-01=last_3_months / HD-02=period_end_desc）
      // 遷 v1 → v2 tenant-scoped；v2 預設過濾「最近 3 個月」+ 排序 period_end desc
      const res = await api.get<SettlementPage>(
        tenantPath("/settlements?limit=50"),
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
          tenantPath("/accounting/reconciliations"),
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
      // P3.5-KEEP: v2 對帳改 dual-sign（:review→:co-sign，兩個不同 user），單簽 approve 無 drop-in；需 dual-sign UX rework（two-step review→co-sign UI），屬產品工作。legacy 單簽暫留。
      await api.post<ReconciliationApproveResponse>(
        `/api/v1/accounting/reconciliations/${encodeURIComponent(recon.id)}/approve`,
        body,
      );
      setApproveTarget(null);
      setToast(
        tS("approveToast", {
          id: recon.id.slice(0, 8),
          payout: recon.technician_payout,
        }),
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
                {tPage("pageTitle")}
              </h1>
              <button
                onClick={refreshAll}
                disabled={loading || reconsLoading}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                title={tCommon("refresh")}
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${loading || reconsLoading ? "animate-spin" : ""}`}
                />
              </button>
              <button
                onClick={() => setExportOpen(true)}
                title={tS("exportTitle")}
                className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 hover:bg-[var(--bg-page)]"
              >
                <Download className="h-4 w-4 text-[var(--text-secondary)]" />
                <span className="text-[13px] text-[var(--text-primary)]">
                  {tCommon("exportCsv")}
                </span>
              </button>
              <span className="text-[13px] text-[var(--text-secondary)]">
                {updatedAt
                  ? tCommon("lastUpdated", { time: formatTime(updatedAt) })
                  : tCommon("notLoaded")}
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
                {error ? tCommon("disconnected") : tCommon("connected")}
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

        <div className="flex items-center gap-4 px-8 py-4">
          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value as any)}
            className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-[14px] py-2 text-sm text-[var(--text-primary)] outline-none"
          >
            <option value="last3m">最近 3 個月</option>
            <option value="last6m">最近 6 個月</option>
            <option value="all">{tS("allPeriods")}</option>
          </select>

          <div className="flex rounded-md bg-[#F1F5F9] p-[3px]">
            {SEGMENTS.map((seg) => (
              <button
                key={seg.value}
                onClick={() => setSettlementCycle(seg.value as any)}
                className={`rounded px-[14px] py-[6px] text-[13px] ${
                  seg.value === settlementCycle
                    ? "bg-[var(--bg-surface)] font-semibold text-[var(--text-primary)] shadow-sm"
                    : "font-medium text-[var(--text-secondary)] hover:bg-white"
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
              {tS("totalBadge", { count: items.length })}
            </span>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mx-8 mb-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Body */}
        <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-2">
          {/* Reconciliations Section */}
          <section className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                  {tS("reconTitle")}
                </h2>
                <span className="text-[13px] text-[var(--text-secondary)]">
                  {tCommon("totalCount", { count: recons.length })}
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
                {tS("settlementTitle")}
              </h2>
              <span className="text-[13px] text-[var(--text-secondary)]">
                {tCommon("totalCount", { count: items.length })}
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

      <ReportExportModal
        open={exportOpen}
        onOpenChange={setExportOpen}
        reportType="accounting"
        filters={{ status: reconStatus || undefined }}
      />
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
  const t = useTranslations("accounting.settlements.approveModal");
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
            {t("title")}
          </span>
        </div>
        <div className="mb-4 space-y-1 rounded-lg bg-[var(--bg-page)] p-3 text-[13px]">
          <div className="flex justify-between">
            <span className="text-[var(--text-secondary)]">{t("reconId")}</span>
            <span className="font-mono text-[var(--text-primary)]">
              {recon.id.slice(0, 8)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-secondary)]">{t("technician")}</span>
            <span className="text-[var(--text-primary)]">
              {recon.technician_name ?? recon.technician_id.slice(0, 8)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-secondary)]">{t("payout")}</span>
            <span className="font-mono font-semibold text-[var(--text-primary)]">
              NT$ {Number(recon.technician_payout).toLocaleString("en-US")}
            </span>
          </div>
        </div>
        <p className="mb-3 text-[13px] leading-[1.6] text-[var(--text-secondary)]">
          {t("desc")}
        </p>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          disabled={pending}
          rows={3}
          placeholder={t("notePlaceholder")}
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
            {t("cancel")}
          </button>
          <button
            onClick={() => onConfirm(note)}
            disabled={pending}
            className="rounded-md bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("approving") : t("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
