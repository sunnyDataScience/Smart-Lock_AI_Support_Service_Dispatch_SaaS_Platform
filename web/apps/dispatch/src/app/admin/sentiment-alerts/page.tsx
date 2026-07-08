"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, X, TrendingUp } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import { api } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { formatRelative } from "@shared/lib/format";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@shared/hooks/usePaginatedFetch";
import { auth } from "@shared/lib/api";
import type { components } from "@shared/types/api.generated";

type SentimentAlert = components["schemas"]["SentimentAlert"];
type SentimentAlertStatus = components["schemas"]["SentimentAlertStatus"];
type SentimentLabel = SentimentAlert["sentiment_label"];

function formatSentimentError(e: unknown): string {
  return friendlyError(e);
}

const STATUS_BADGE: Record<SentimentAlertStatus, { bg: string; text: string }> = {
  pending: { bg: "#FEE2E2", text: "#B91C1C" },
  acknowledged: { bg: "#FEF3C7", text: "#92400E" },
  resolved: { bg: "#DCFCE7", text: "#166534" },
};

const STATUS_OPTIONS: SentimentAlertStatus[] = ["pending", "acknowledged", "resolved"];

const LABEL_BADGE: Record<SentimentLabel, { bg: string; text: string }> = {
  very_negative: { bg: "#7F1D1D", text: "#FECACA" },
  negative: { bg: "#FEE2E2", text: "#B91C1C" },
  neutral: { bg: "#E5E7EB", text: "#374151" },
  positive: { bg: "#DCFCE7", text: "#166534" },
};

const PAGE_SIZE = 20;

const COLUMN_KEYS = [
  { key: "time", width: "w-[140px]" },
  { key: "status", width: "w-[100px]" },
  { key: "sentiment", width: "w-[100px]" },
  { key: "confidence", width: "w-[80px]" },
  { key: "messageSnippet", width: "flex-1" },
  { key: "keywords", width: "w-[180px]" },
  { key: "conversation", width: "w-[80px]" },
  { key: "action", width: "w-[160px]" },
] as const;

const NEXT_STATUS_OPTIONS: Record<SentimentAlertStatus, SentimentAlertStatus[]> = {
  pending: ["acknowledged", "resolved"],
  acknowledged: ["resolved"],
  resolved: [],
};

function formatConfidence(c: number): string {
  return `${Math.round(c * 100)}%`;
}

interface ActionTarget {
  alertId: string;
  toStatus: SentimentAlertStatus;
}

interface EscalateTarget {
  alertId: string;
}

type EscalateLevel = "operations_manager" | "tenant_admin";

interface EscalateResponse {
  alert_id: string;
  work_order_id: string;
  escalated_to_level: string;
  escalated_at: string;
}

export default function SentimentAlertsPage() {
  const t = useTranslations("admin.sentiment");
  const tc = useTranslations("admin.common");
  const [statusFilter, setStatusFilter] = useState<SentimentAlertStatus | "">("");
  const [actionTarget, setActionTarget] = useState<ActionTarget | null>(null);
  const [escalateTarget, setEscalateTarget] = useState<EscalateTarget | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  // v2 tenant-scoped path（CR-0003 P2-W2 / FR-0018 / ADR-0048）
  const tenantId = auth.getTenantId();

  const {
    items,
    cursor,
    hasMore,
    loading,
    error: fetchError,
    loadMore,
    mutate,
  } = usePaginatedFetch<SentimentAlert>({
    path: `/tenants/${encodeURIComponent(tenantId)}/sentiment/alerts`,
    pageSize: PAGE_SIZE,
    query: statusFilter ? { status: statusFilter } : undefined,
    queryKey: `tenantId=${tenantId}&status=${statusFilter}`,
    formatError: formatSentimentError,
  });

  const [actionError, setActionError] = useState<string | null>(null);
  const error = fetchError || actionError;

  const statusLabel = useMemo<Record<SentimentAlertStatus, string>>(
    () => ({
      pending: t("status.pending"),
      acknowledged: t("status.acknowledged"),
      resolved: t("status.resolved"),
    }),
    [t],
  );

  const labelText = useMemo<Record<SentimentLabel, string>>(
    () => ({
      very_negative: t("label.very_negative"),
      negative: t("label.negative"),
      neutral: t("label.neutral"),
      positive: t("label.positive"),
    }),
    [t],
  );

  const actionLabel = useMemo<Record<SentimentAlertStatus, string>>(
    () => ({
      pending: "—",
      acknowledged: t("action.acknowledge"),
      resolved: t("action.resolve"),
    }),
    [t],
  );

  const handleUpdated = (updated: SentimentAlert) => {
    // optimistic local update via hook mutate API (per Phase 3.3 backlog §C2)
    mutate((prev) => prev.map((it) => (it.id === updated.id ? updated : it)));
  };

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 text-[#DC2626]" />
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                {t("title")}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-[13px] text-[var(--text-secondary)]">{t("filterLabel")}</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as SentimentAlertStatus | "")}
                className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
              >
                <option value="">{tc("all")}</option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {statusLabel[s]}
                  </option>
                ))}
              </select>
            </div>

            {statusFilter && (
              <button
                onClick={() => setStatusFilter("")}
                className="rounded-md px-3 py-2"
              >
                <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                  {tc("clearFilter")}
                </span>
              </button>
            )}

            <span className="ml-auto text-[13px] text-[var(--text-secondary)]">
              {loading
                ? tc("loading")
                : hasMore
                  ? tc("totalCountMore", { count: items.length })
                  : tc("totalCount", { count: items.length })}
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center bg-[#F8FAFC] px-4" style={{ height: 44 }}>
              {COLUMN_KEYS.map((col) => (
                <div key={col.key} className={`flex h-full items-center ${col.width}`}>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {t(`cols.${col.key}`)}
                  </span>
                </div>
              ))}
            </div>

            {items.length === 0 && !loading && (
              <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                {t("empty")}
              </div>
            )}

            {items.map((row) => {
              const status = row.status as SentimentAlertStatus;
              const label = row.sentiment_label as SentimentLabel;
              const sBadge = STATUS_BADGE[status];
              const lBadge = LABEL_BADGE[label];
              const keywords = row.detected_keywords ?? [];
              const message = row.consumer_message ?? "";
              return (
                <div
                  key={row.id}
                  className="flex items-center border-t border-t-[var(--border)] px-4"
                  style={{ minHeight: 56 }}
                >
                  <div className="flex h-full w-[140px] items-center">
                    <span className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-primary)]">
                      {formatRelative(row.created_at)}
                    </span>
                  </div>

                  <div className="flex h-full w-[100px] items-center">
                    <span
                      className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                      style={{ backgroundColor: sBadge.bg, color: sBadge.text }}
                    >
                      {statusLabel[status]}
                    </span>
                  </div>

                  <div className="flex h-full w-[100px] items-center">
                    <span
                      className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                      style={{ backgroundColor: lBadge.bg, color: lBadge.text }}
                    >
                      {labelText[label]}
                    </span>
                  </div>

                  <div className="flex h-full w-[80px] items-center">
                    <span className="font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-primary)]">
                      {formatConfidence(row.confidence)}
                    </span>
                  </div>

                  <div className="flex h-full flex-1 items-center pr-3">
                    <span
                      className="line-clamp-2 text-[13px] text-[var(--text-primary)]"
                      title={message}
                    >
                      {message || "—"}
                    </span>
                  </div>

                  <div className="flex h-full w-[180px] flex-wrap items-center gap-1 py-2">
                    {keywords.length === 0 ? (
                      <span className="text-xs text-[var(--text-disabled)]">—</span>
                    ) : (
                      keywords.slice(0, 4).map((kw, i) => (
                        <span
                          key={i}
                          className="rounded bg-[#F1F5F9] px-[6px] py-[1px] text-[11px] text-[var(--text-secondary)]"
                        >
                          {kw}
                        </span>
                      ))
                    )}
                  </div>

                  <div className="flex h-full w-[80px] items-center">
                    <Link
                      href={`/conversations/${row.conversation_id}`}
                      className="font-['IBM_Plex_Mono'] text-xs text-[var(--primary)] hover:underline"
                    >
                      {row.conversation_id.slice(0, 8)}
                    </Link>
                  </div>

                  <div className="flex h-full w-[160px] flex-wrap items-center gap-2">
                    {NEXT_STATUS_OPTIONS[status].length === 0 ? (
                      <span className="text-xs text-[var(--text-disabled)]">{t("alreadyResolved")}</span>
                    ) : (
                      <>
                        {NEXT_STATUS_OPTIONS[status].map((next) => (
                          <button
                            key={next}
                            disabled={savingId === row.id}
                            onClick={() =>
                              setActionTarget({ alertId: row.id, toStatus: next })
                            }
                            className={`rounded-md border px-3 py-1 text-xs font-medium transition disabled:opacity-50 ${
                              next === "resolved"
                                ? "border-green-300 bg-green-50 text-green-700 hover:bg-green-100"
                                : "border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100"
                            }`}
                          >
                            {actionLabel[next]}
                          </button>
                        ))}
                        {status === "pending" && (
                          <button
                            disabled={savingId === row.id}
                            onClick={() => setEscalateTarget({ alertId: row.id })}
                            className="inline-flex items-center gap-1 rounded-md border border-red-300 bg-red-50 px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-100 disabled:opacity-50"
                            title={t("escalate.tooltip")}
                          >
                            <TrendingUp className="h-3 w-3" />
                            {t("escalate.button")}
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {hasMore && (
            <div className="flex justify-center pt-2">
              <button
                disabled={loading}
                onClick={loadMore}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? tc("loading") : tc("loadMore")}
              </button>
            </div>
          )}
        </div>
      </div>

      {actionTarget && (
        <UpdateAlertModal
          target={actionTarget}
          saving={savingId === actionTarget.alertId}
          onClose={() => setActionTarget(null)}
          onSubmit={async (note) => {
            setSavingId(actionTarget.alertId);
            try {
              // v2 tenant-scoped path（CR-0003 P2-W2 / FR-0018）
              const tId = auth.getTenantId();
              const updated = await api.patch<SentimentAlert>(
                `/tenants/${encodeURIComponent(tId)}/sentiment/alerts/${actionTarget.alertId}`,
                { status: actionTarget.toStatus, admin_note: note ?? undefined },
              );
              handleUpdated(updated);
              setActionTarget(null);
            } catch (e) {
              setActionError(formatSentimentError(e));
            } finally {
              setSavingId(null);
            }
          }}
        />
      )}

      {escalateTarget && (
        <EscalateAlertModal
          target={escalateTarget}
          saving={savingId === escalateTarget.alertId}
          onClose={() => setEscalateTarget(null)}
          onSubmit={async (level, reason) => {
            setSavingId(escalateTarget.alertId);
            try {
              const tId = auth.getTenantId();
              const result = await api.post<EscalateResponse>(
                `/tenants/${encodeURIComponent(tId)}/sentiment/alerts/${escalateTarget.alertId}:escalate-to-work-order`,
                { level, reason },
              );
              // 後端會把 alert 從 pending 升 acknowledged — optimistic 反映
              mutate((prev) =>
                prev.map((it) =>
                  it.id === escalateTarget.alertId
                    ? { ...it, status: "acknowledged" as SentimentAlertStatus }
                    : it,
                ),
              );
              setEscalateTarget(null);
              // 提示已升級的工單 — 用 alert 暫代（避免新增 toast 系統）
              window.alert(
                t("escalate.successAlert", { woId: result.work_order_id.slice(0, 8) }),
              );
            } catch (e) {
              setActionError(formatSentimentError(e));
            } finally {
              setSavingId(null);
            }
          }}
        />
      )}
    </div>
  );
}

interface EscalateAlertModalProps {
  target: EscalateTarget;
  saving: boolean;
  onClose: () => void;
  onSubmit: (level: EscalateLevel, reason: string) => Promise<void>;
}

function EscalateAlertModal({ target: _target, saving, onClose, onSubmit }: EscalateAlertModalProps) {
  const t = useTranslations("admin.sentiment");
  const tc = useTranslations("admin.common");
  const [level, setLevel] = useState<EscalateLevel>("operations_manager");
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();
  const tooLong = trimmed.length > 500;
  const canSubmit = !saving && trimmed.length > 0 && !tooLong;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={onClose}
    >
      <div
        className="flex w-full max-w-md flex-col gap-4 rounded-lg bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {t("escalate.modalTitle")}
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            aria-label={t("modal.closeAria")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="text-xs text-[var(--text-secondary)]">
          {t("escalate.modalHint")}
        </p>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-[var(--text-primary)]">
            {t("escalate.levelLabel")}
          </label>
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value as EscalateLevel)}
            className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm"
          >
            <option value="operations_manager">{t("escalate.level.operations_manager")}</option>
            <option value="tenant_admin">{t("escalate.level.tenant_admin")}</option>
          </select>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-[var(--text-primary)]">
            {t("escalate.reasonLabel")}
            <span className="ml-1 text-red-500">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("escalate.reasonPlaceholder")}
            rows={4}
            className="rounded-md border border-[var(--border)] px-3 py-2 text-sm focus:border-[var(--primary)] focus:outline-none"
          />
          <div className="flex justify-between text-xs text-[var(--text-secondary)]">
            <span className={tooLong ? "text-red-600" : ""}>
              {tooLong ? t("escalate.reasonOverLimit") : `${trimmed.length}/500`}
            </span>
            {trimmed.length === 0 && (
              <span className="text-red-500">{t("modal.required")}</span>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={saving}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {tc("cancel")}
          </button>
          <button
            onClick={() => onSubmit(level, trimmed)}
            disabled={!canSubmit}
            className="inline-flex items-center gap-1 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            <TrendingUp className="h-3.5 w-3.5" />
            {saving ? tc("submitting") : t("escalate.submitButton")}
          </button>
        </div>
      </div>
    </div>
  );
}

interface UpdateAlertModalProps {
  target: ActionTarget;
  saving: boolean;
  onClose: () => void;
  onSubmit: (note: string) => Promise<void>;
}

function UpdateAlertModal({ target, saving, onClose, onSubmit }: UpdateAlertModalProps) {
  const t = useTranslations("admin.sentiment");
  const tc = useTranslations("admin.common");
  const [note, setNote] = useState("");
  const trimmed = note.trim();
  const tooLong = trimmed.length > 1000;
  const noteRequired = target.toStatus === "resolved";
  const canSubmit = !saving && !tooLong && (!noteRequired || trimmed.length > 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={onClose}
    >
      <div
        className="flex w-full max-w-md flex-col gap-4 rounded-lg bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {target.toStatus === "resolved" ? t("modal.titleResolve") : t("modal.titleAcknowledge")}
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            aria-label={t("modal.closeAria")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-[var(--text-primary)]">
            {t("modal.noteLabel")}{noteRequired && <span className="ml-1 text-red-500">*</span>}
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={
              target.toStatus === "resolved"
                ? t("modal.notePlaceholderResolve")
                : t("modal.notePlaceholderAcknowledge")
            }
            rows={4}
            className="rounded-md border border-[var(--border)] px-3 py-2 text-sm focus:border-[var(--primary)] focus:outline-none"
          />
          <div className="flex justify-between text-xs text-[var(--text-secondary)]">
            <span className={tooLong ? "text-red-600" : ""}>
              {tooLong ? t("modal.noteOverLimit") : t("modal.noteCount", { count: trimmed.length })}
            </span>
            {noteRequired && trimmed.length === 0 && (
              <span className="text-red-500">{t("modal.required")}</span>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={saving}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {tc("cancel")}
          </button>
          <button
            onClick={() => onSubmit(trimmed)}
            disabled={!canSubmit}
            className={`rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50 ${
              target.toStatus === "resolved"
                ? "bg-green-600 hover:bg-green-700"
                : "bg-amber-600 hover:bg-amber-700"
            }`}
          >
            {saving
              ? tc("submitting")
              : target.toStatus === "resolved"
                ? t("modal.submitResolve")
                : t("modal.submitAcknowledge")}
          </button>
        </div>
      </div>
    </div>
  );
}
