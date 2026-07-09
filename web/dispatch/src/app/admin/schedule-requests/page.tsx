"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  Clock,
  RefreshCw,
  X,
  XCircle,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type Status = "pending" | "approved" | "rejected" | "cancelled";
type ReqType = "leave" | "standby";

interface AdminScheduleRequest {
  id: string;
  type: ReqType;
  start_date: string;
  end_date: string;
  reason: string;
  status: Status;
  created_at: string;
  resolved_at?: string | null;
  resolution_note?: string | null;
  technician_user_id: string;
  technician_name?: string | null;
}

interface ListResponse {
  items: AdminScheduleRequest[];
}

const STATUS_TAB_VALUES: (Status | "all")[] = [
  "pending",
  "approved",
  "rejected",
  "cancelled",
  "all",
];

const TYPE_META: Record<ReqType, { bg: string; color: string }> = {
  leave: { bg: "#FEF3C7", color: "#92400E" },
  standby: { bg: "#DBEAFE", color: "#1E40AF" },
};

const STATUS_META: Record<Status, { bg: string; color: string }> = {
  pending: { bg: "#F1F5F9", color: "#475569" },
  approved: { bg: "#D1FAE5", color: "#065F46" },
  rejected: { bg: "#FEE2E2", color: "#991B1B" },
  cancelled: { bg: "#E2E8F0", color: "#475569" },
};

function formatErr(e: unknown): string {
  return friendlyError(e);
}

export default function ScheduleRequestsPage() {
  const t = useTranslations("admin.scheduleRequests");
  const tc = useTranslations("admin.common");
  const [tab, setTab] = useState<Status | "all">("pending");
  const [items, setItems] = useState<AdminScheduleRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [resolveDialog, setResolveDialog] = useState<{
    id: string;
    decision: "approve" | "reject";
  } | null>(null);
  const [resolveNote, setResolveNote] = useState("");

  const tabLabel = useMemo<Record<Status | "all", string>>(
    () => ({
      pending: t("tabs.pending"),
      approved: t("tabs.approved"),
      rejected: t("tabs.rejected"),
      cancelled: t("tabs.cancelled"),
      all: t("tabs.all"),
    }),
    [t],
  );

  const typeLabel = useMemo<Record<ReqType, string>>(
    () => ({
      leave: t("type.leave"),
      standby: t("type.standby"),
    }),
    [t],
  );

  const statusLabel = useMemo<Record<Status, string>>(
    () => ({
      pending: t("status.pending"),
      approved: t("status.approved"),
      rejected: t("status.rejected"),
      cancelled: t("status.cancelled"),
    }),
    [t],
  );

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 100 };
      if (tab !== "all") query.status = tab;
      // CR-0002-α P3：遷移 GET /admin/schedule-requests → v2 GET tenantPath("/exceptions:inbox")
      // NOTE: 語意/response shape 重塑（exceptions inbox），欄位對齊待人工確認（ListResponse.items 假設沿用）
      const res = await api.get<ListResponse>(
        tenantPath("/exceptions:inbox"),
        { query },
      );
      setItems(res.items ?? []);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  async function resolve(id: string, decision: "approve" | "reject") {
    if (busy) return;
    setBusy(id);
    setError(null);
    try {
      // CR-0003 P3 收尾（2026-06-04）：approve + reject 統一走 v2 :approve
      // exceptions_v2.py:33 ExceptionDecision body 的 decision 欄位區分 approve/reject
      const body: { decision: "approve" | "reject"; note?: string } = {
        decision,
        ...(resolveNote.trim() ? { note: resolveNote.trim() } : {}),
      };
      await api.post(
        tenantPath(`/exceptions/${encodeURIComponent(id)}:approve`),
        body,
      );
      setActionMsg(decision === "approve" ? t("toast.approved") : t("toast.rejected"));
      setTimeout(() => setActionMsg(null), 2500);
      setResolveDialog(null);
      setResolveNote("");
      fetchItems();
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col gap-1 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <span className="text-[13px] text-[var(--text-secondary)]">
            {t("breadcrumb")}
          </span>
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-bold text-[#0F172A]">
              {t("title")}
            </h1>
            <button
              type="button"
              onClick={fetchItems}
              disabled={loading}
              className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              <RefreshCw
                className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
              />
              {tc("refresh")}
            </button>
          </div>
        </div>

        <div className="flex border-b border-[var(--border)] bg-[var(--bg-surface)] px-8">
          {STATUS_TAB_VALUES.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setTab(value)}
              className={`px-4 py-3 text-[13px] ${
                tab === value
                  ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                  : "font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {tabLabel[value]}
            </button>
          ))}
        </div>

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-[13px] text-red-700">
            {error}
          </div>
        )}
        {actionMsg && (
          <div className="mx-8 mt-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-[13px] text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            {actionMsg}
          </div>
        )}

        <main className="flex-1 overflow-auto px-8 py-6">
          {loading && items.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
              {tc("loading")}
            </div>
          ) : items.length === 0 ? (
            <div className="flex h-40 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
              <CalendarDays className="h-10 w-10 text-[var(--text-disabled)]" />
              <p className="text-[14px]">
                {tab === "pending"
                  ? t("emptyPending")
                  : t("emptyOther", { label: tabLabel[tab] })}
              </p>
            </div>
          ) : (
            <table className="w-full overflow-hidden rounded-lg border border-[var(--border)] bg-white text-[13px] shadow-sm">
              <thead className="bg-[#F8FAFC] text-left text-[12px] font-medium text-[var(--text-secondary)]">
                <tr>
                  <th className="px-3 py-2">{t("cols.technician")}</th>
                  <th className="px-3 py-2">{t("cols.type")}</th>
                  <th className="px-3 py-2">{t("cols.dateRange")}</th>
                  <th className="px-3 py-2">{t("cols.reason")}</th>
                  <th className="px-3 py-2">{t("cols.status")}</th>
                  <th className="px-3 py-2">{t("cols.createdAt")}</th>
                  <th className="px-3 py-2 text-right">{t("cols.actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {items.map((r) => {
                  const typeMeta = TYPE_META[r.type];
                  const statusMeta = STATUS_META[r.status];
                  return (
                    <tr key={r.id} className="hover:bg-[#F8FAFC]">
                      <td className="px-3 py-3 font-medium text-[var(--text-primary)]">
                        {r.technician_name ?? "—"}
                        <span className="block font-mono text-[10px] text-[var(--text-disabled)]">
                          #{r.technician_user_id.slice(0, 8)}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className="rounded px-2 py-[2px] text-[11px] font-semibold"
                          style={{
                            backgroundColor: typeMeta.bg,
                            color: typeMeta.color,
                          }}
                        >
                          {typeLabel[r.type]}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">
                        {r.start_date} ~ {r.end_date}
                      </td>
                      <td className="px-3 py-3 text-[var(--text-primary)]">
                        <div className="line-clamp-2 max-w-md">{r.reason}</div>
                        {r.resolution_note && (
                          <div className="mt-1 text-[11px] text-[var(--text-disabled)]">
                            {t("approvalNote", { note: r.resolution_note })}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className="rounded px-2 py-[2px] text-[11px] font-semibold"
                          style={{
                            backgroundColor: statusMeta.bg,
                            color: statusMeta.color,
                          }}
                        >
                          {statusLabel[r.status]}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-[11px] text-[var(--text-disabled)]">
                        <Clock className="mr-1 inline h-3 w-3" />
                        {new Date(r.created_at).toLocaleString("zh-TW", {
                          hour12: false,
                        })}
                      </td>
                      <td className="px-3 py-3 text-right">
                        {r.status === "pending" ? (
                          <div className="flex items-center justify-end gap-1">
                            <button
                              type="button"
                              onClick={() =>
                                setResolveDialog({
                                  id: r.id,
                                  decision: "approve",
                                })
                              }
                              disabled={busy === r.id}
                              className="rounded-md border border-green-300 bg-green-50 px-3 py-1 text-[12px] font-semibold text-green-700 hover:bg-green-100 disabled:opacity-50"
                            >
                              {t("approve")}
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                setResolveDialog({
                                  id: r.id,
                                  decision: "reject",
                                })
                              }
                              disabled={busy === r.id}
                              className="rounded-md border border-red-300 bg-red-50 px-3 py-1 text-[12px] font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50"
                            >
                              {t("reject")}
                            </button>
                          </div>
                        ) : (
                          <span className="text-[11px] text-[var(--text-disabled)]">
                            {r.resolved_at
                              ? new Date(r.resolved_at).toLocaleString("zh-TW", {
                                  hour12: false,
                                })
                              : "—"}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </main>
      </div>

      {/* resolve modal */}
      {resolveDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => !busy && setResolveDialog(null)}
        >
          <div
            className="w-[480px] rounded-xl bg-white p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[16px] font-semibold text-[var(--text-primary)]">
                {resolveDialog.decision === "approve"
                  ? t("modal.titleApprove")
                  : t("modal.titleReject")}
              </h3>
              <button
                type="button"
                onClick={() => !busy && setResolveDialog(null)}
                className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mb-3 text-[12px] text-[var(--text-secondary)]">
              {t("modal.noteLabel")}
            </p>
            <textarea
              value={resolveNote}
              onChange={(e) => setResolveNote(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder={t("modal.notePlaceholder")}
              className="w-full rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
            />

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setResolveDialog(null)}
                disabled={!!busy}
                className="rounded-md border border-[var(--border)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {tc("cancel")}
              </button>
              <button
                type="button"
                onClick={() =>
                  resolve(resolveDialog.id, resolveDialog.decision)
                }
                disabled={!!busy}
                className={`flex items-center gap-1 rounded-md px-4 py-2 text-[13px] font-semibold text-white disabled:opacity-60 ${
                  resolveDialog.decision === "approve"
                    ? "bg-green-600 hover:bg-green-700"
                    : "bg-red-600 hover:bg-red-700"
                }`}
              >
                {resolveDialog.decision === "approve" ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <XCircle className="h-4 w-4" />
                )}
                {busy
                  ? t("modal.processing")
                  : resolveDialog.decision === "approve"
                    ? t("modal.confirmApprove")
                    : t("modal.confirmReject")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
