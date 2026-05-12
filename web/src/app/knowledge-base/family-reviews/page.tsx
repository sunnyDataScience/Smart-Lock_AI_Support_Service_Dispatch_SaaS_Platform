"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ShieldCheck, X, Check, XCircle } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type FamilyReview = components["schemas"]["FamilyReview"];
type FamilyReviewPendingItem = components["schemas"]["FamilyReviewPendingItem"];
type FamilyReviewPendingResponse =
  components["schemas"]["FamilyReviewPendingResponse"];
type FamilyReviewAction = components["schemas"]["FamilyReviewAction"];

function formatFamilyReviewError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

const ACTION_BADGE: Record<FamilyReviewAction, { bg: string; text: string }> = {
  approved: { bg: "#DCFCE7", text: "#166534" },
  rejected: { bg: "#FEE2E2", text: "#B91C1C" },
};

const PAGE_SIZE = 20;

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("zh-TW", { hour12: false });
}

interface SubmitTarget {
  draftId: string;
  title: string;
  defaultAction: FamilyReviewAction;
}

export default function FamilyReviewsPage() {
  const tF = useTranslations("kb.familyReviews");

  const ACTION_LABEL: Record<FamilyReviewAction, string> = useMemo(
    () => ({
      approved: tF("actionApprove"),
      rejected: tF("actionReject"),
    }),
    [tF],
  );

  const ACTION_FILTERS: { label: string; value: FamilyReviewAction | "" }[] = useMemo(
    () => [
      { label: tF("filterAll"), value: "" },
      { label: tF("filterApproved"), value: "approved" },
      { label: tF("filterRejected"), value: "rejected" },
    ],
    [tF],
  );

  // Pending list — 不分頁，保留 page-local state
  const [pending, setPending] = useState<FamilyReviewPendingItem[]>([]);
  const [pendingLoading, setPendingLoading] = useState(true);
  const [pendingError, setPendingError] = useState<string | null>(null);

  // History list — cursor-paginated，用 hook
  const [actionFilter, setActionFilter] = useState<FamilyReviewAction | "">("");
  const {
    items: history,
    cursor,
    hasMore,
    loading: historyLoading,
    error: historyError,
    loadMore: loadMoreHistory,
    refresh: refreshHistory,
  } = usePaginatedFetch<FamilyReview>({
    path: "/api/v1/family-reviews",
    pageSize: PAGE_SIZE,
    query: actionFilter ? { action: actionFilter } : undefined,
    queryKey: `action=${actionFilter}`,
    formatError: formatFamilyReviewError,
  });

  const [actionError, setActionError] = useState<string | null>(null);
  const [target, setTarget] = useState<SubmitTarget | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // page-level error 合併 pending fetch / history fetch / handleSubmit 三個來源
  const error = pendingError || historyError || actionError;
  const clearError = () => {
    setPendingError(null);
    setActionError(null);
  };

  const fetchPending = useCallback(async () => {
    setPendingLoading(true);
    try {
      const res = await api.get<FamilyReviewPendingResponse>(
        "/api/v1/family-reviews/pending",
      );
      setPending(res.data ?? []);
      setPendingError(null);
    } catch (e) {
      setPendingError(formatFamilyReviewError(e));
    } finally {
      setPendingLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  const handleSubmit = async (
    draftId: string,
    action: FamilyReviewAction,
    comment: string,
  ) => {
    setSubmitting(true);
    setActionError(null);
    try {
      await api.post("/api/v1/family-reviews", {
        sop_draft_id: draftId,
        action,
        comment: comment.trim() || undefined,
      });
      setTarget(null);
      await Promise.all([fetchPending(), refreshHistory()]);
    } catch (e) {
      setActionError(formatFamilyReviewError(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col bg-[var(--bg-surface)]">
          <div className="flex items-center justify-between px-8 py-5">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-7 w-7 text-[var(--primary)]" />
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                {tF("title")}
              </h1>
              <span className="text-[13px] text-[var(--text-secondary)]">
                {tF("summary", {
                  pending: pending.length,
                  history: history.length,
                  plus: hasMore ? "+" : "",
                })}
              </span>
            </div>
          </div>
        </div>

        {error && (
          <div className="mx-8 mt-4 flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{error}</span>
            <button
              onClick={clearError}
              className="text-red-400 hover:text-red-600"
              title={tF("errorClose")}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        <div className="flex flex-1 flex-col gap-6 overflow-auto pl-14 pr-4 py-6 md:px-8">
          {/* Pending Section */}
          <section className="flex flex-col gap-3">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">
              {tF("pendingTitle")}
            </h2>
            <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <div
                className="flex items-center bg-[#F8FAFC] px-4 text-xs font-semibold text-[var(--text-secondary)]"
                style={{ height: 44 }}
              >
                <div className="flex-1">{tF("colSopTitle")}</div>
                <div className="w-[180px]">{tF("colReviewer")}</div>
                <div className="w-[200px]">{tF("colApprovedAt")}</div>
                <div className="w-[180px]">{tF("colWaiting")}</div>
                <div className="w-[180px] text-right">{tF("colAction")}</div>
              </div>

              {pendingLoading && pending.length === 0 && (
                <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                  {tF("loading")}
                </div>
              )}

              {!pendingLoading && pending.length === 0 && (
                <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                  {tF("noPending")}
                </div>
              )}

              {pending.map((item) => (
                <div
                  key={item.sop_draft_id}
                  className="flex items-center border-t border-t-[var(--border)] px-4"
                  style={{ minHeight: 56 }}
                >
                  <div className="flex-1 text-[13px] font-medium text-[var(--text-primary)]">
                    {item.title}
                    <div className="font-['IBM_Plex_Mono'] text-[11px] text-[var(--text-secondary)]">
                      {item.sop_draft_id.slice(0, 8)}…
                    </div>
                  </div>
                  <div className="w-[180px] text-[13px] text-[var(--text-secondary)]">
                    {item.admin_reviewer || "—"}
                  </div>
                  <div className="w-[200px] font-['IBM_Plex_Mono'] text-[12px] text-[var(--text-secondary)]">
                    {formatTime(item.admin_approved_at)}
                  </div>
                  <div className="w-[180px] text-[13px] text-[var(--text-secondary)]">
                    {formatRelative(item.awaiting_family_review_since)}
                  </div>
                  <div className="flex w-[180px] justify-end gap-2">
                    <button
                      onClick={() =>
                        setTarget({
                          draftId: item.sop_draft_id,
                          title: item.title,
                          defaultAction: "approved",
                        })
                      }
                      className="inline-flex items-center gap-1 rounded-md bg-[#22C55E] px-3 py-[6px] text-[12px] font-medium text-white hover:bg-[#16A34A]"
                    >
                      <Check className="h-[12px] w-[12px]" /> {tF("actionApprove")}
                    </button>
                    <button
                      onClick={() =>
                        setTarget({
                          draftId: item.sop_draft_id,
                          title: item.title,
                          defaultAction: "rejected",
                        })
                      }
                      className="inline-flex items-center gap-1 rounded-md bg-[#EF4444] px-3 py-[6px] text-[12px] font-medium text-white hover:bg-[#DC2626]"
                    >
                      <XCircle className="h-[12px] w-[12px]" /> {tF("actionReject")}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* History Section */}
          <section className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-[var(--text-primary)]">
                {tF("historyTitle")}
              </h2>
              <div className="flex items-center gap-2">
                {ACTION_FILTERS.map((f) => {
                  const active = actionFilter === f.value;
                  return (
                    <button
                      key={f.value || "all"}
                      onClick={() => setActionFilter(f.value)}
                      className={`rounded-md px-3 py-[6px] text-[12px] font-medium ${
                        active
                          ? "bg-[var(--primary)] text-white"
                          : "border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                      }`}
                    >
                      {f.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <div
                className="flex items-center bg-[#F8FAFC] px-4 text-xs font-semibold text-[var(--text-secondary)]"
                style={{ height: 44 }}
              >
                <div className="w-[180px]">{tF("colTime")}</div>
                <div className="w-[100px]">{tF("colResult")}</div>
                <div className="w-[200px]">{tF("colDraft")}</div>
                <div className="w-[200px]">{tF("colReviewerHistory")}</div>
                <div className="flex-1">{tF("colNote")}</div>
              </div>

              {historyLoading && history.length === 0 && (
                <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                  {tF("loading")}
                </div>
              )}

              {!historyLoading && history.length === 0 && (
                <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                  {tF("noHistory")}
                </div>
              )}

              {history.map((row) => (
                <div
                  key={row.id}
                  className="flex items-start border-t border-t-[var(--border)] px-4 py-3"
                >
                  <div className="w-[180px] font-['IBM_Plex_Mono'] text-[12px] text-[var(--text-secondary)]">
                    {formatRelative(row.created_at)}
                  </div>
                  <div className="w-[100px]">
                    <span
                      className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                      style={{
                        backgroundColor: ACTION_BADGE[row.action].bg,
                        color: ACTION_BADGE[row.action].text,
                      }}
                    >
                      {ACTION_LABEL[row.action]}
                    </span>
                  </div>
                  <div className="w-[200px] font-['IBM_Plex_Mono'] text-[12px] text-[var(--text-secondary)]">
                    {row.sop_draft_id.slice(0, 8)}…
                  </div>
                  <div className="w-[200px] font-['IBM_Plex_Mono'] text-[12px] text-[var(--text-secondary)]">
                    {row.reviewer_id.slice(0, 8)}…
                  </div>
                  <div className="flex-1 whitespace-pre-wrap text-[13px] text-[var(--text-primary)]">
                    {row.comment || "—"}
                  </div>
                </div>
              ))}
            </div>

            {hasMore && (
              <div className="flex justify-center pt-2">
                <button
                  onClick={loadMoreHistory}
                  disabled={historyLoading || !cursor}
                  className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {historyLoading ? tF("loading") : tF("loadMore")}
                </button>
              </div>
            )}
          </section>
        </div>
      </div>

      {target && (
        <SubmitModal
          target={target}
          submitting={submitting}
          onClose={() => setTarget(null)}
          onSubmit={(action, comment) =>
            handleSubmit(target.draftId, action, comment)
          }
        />
      )}
    </div>
  );
}

interface SubmitModalProps {
  target: SubmitTarget;
  submitting: boolean;
  onClose: () => void;
  onSubmit: (action: FamilyReviewAction, comment: string) => void;
}

function SubmitModal({ target, submitting, onClose, onSubmit }: SubmitModalProps) {
  const t = useTranslations("kb.familyReviews");
  const [action, setAction] = useState<FamilyReviewAction>(target.defaultAction);
  const [comment, setComment] = useState("");
  const trimmed = comment.trim();
  const tooLong = comment.length > 1000;
  const requireComment = action === "rejected" && trimmed.length === 0;
  const disabled = submitting || tooLong || requireComment;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-[520px] rounded-xl bg-[var(--bg-surface)] p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-[var(--text-primary)]">
            {t("modalTitle")}
          </h3>
          <button
            onClick={onClose}
            disabled={submitting}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-4 rounded-md bg-[#F8FAFC] px-3 py-2 text-[13px] text-[var(--text-secondary)]">
          {target.title}
          <div className="mt-1 font-['IBM_Plex_Mono'] text-[11px]">
            {target.draftId}
          </div>
        </div>

        <div className="mt-4 flex gap-2">
          <button
            onClick={() => setAction("approved")}
            disabled={submitting}
            className={`flex-1 rounded-md py-2 text-sm font-medium ${
              action === "approved"
                ? "bg-[#22C55E] text-white"
                : "border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-secondary)]"
            }`}
          >
            {t("actionApprove")}
          </button>
          <button
            onClick={() => setAction("rejected")}
            disabled={submitting}
            className={`flex-1 rounded-md py-2 text-sm font-medium ${
              action === "rejected"
                ? "bg-[#EF4444] text-white"
                : "border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-secondary)]"
            }`}
          >
            {t("actionReject")}
          </button>
        </div>

        <div className="mt-4">
          <label className="text-[13px] font-medium text-[var(--text-secondary)]">
            {t("noteLabel")} {action === "rejected" && <span className="text-red-500">*</span>}
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={submitting}
            placeholder={
              action === "rejected"
                ? t("notePlaceholderReject")
                : t("notePlaceholderApprove")
            }
            rows={4}
            className="mt-1 w-full rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] text-[var(--text-primary)] outline-none focus:border-[var(--primary)] disabled:opacity-50"
          />
          <div className="mt-1 flex items-center justify-between text-[11px]">
            <span
              className={tooLong ? "text-red-600" : "text-[var(--text-secondary)]"}
            >
              {comment.length} / 1000
            </span>
            {requireComment && (
              <span className="text-red-600">{t("noteRequired")}</span>
            )}
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={submitting}
            className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            onClick={() => onSubmit(action, comment)}
            disabled={disabled}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? t("submitting") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}
