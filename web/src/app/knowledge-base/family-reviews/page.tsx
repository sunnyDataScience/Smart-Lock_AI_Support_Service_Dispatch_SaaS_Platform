"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, X, Check, XCircle } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type FamilyReview = components["schemas"]["FamilyReview"];
type FamilyReviewPage = components["schemas"]["FamilyReviewPage"];
type FamilyReviewPendingItem = components["schemas"]["FamilyReviewPendingItem"];
type FamilyReviewPendingResponse =
  components["schemas"]["FamilyReviewPendingResponse"];
type FamilyReviewAction = components["schemas"]["FamilyReviewAction"];

const ACTION_LABEL: Record<FamilyReviewAction, string> = {
  approved: "通過",
  rejected: "退回",
};

const ACTION_BADGE: Record<FamilyReviewAction, { bg: string; text: string }> = {
  approved: { bg: "#DCFCE7", text: "#166534" },
  rejected: { bg: "#FEE2E2", text: "#B91C1C" },
};

const ACTION_FILTERS: { label: string; value: FamilyReviewAction | "" }[] = [
  { label: "全部", value: "" },
  { label: "通過", value: "approved" },
  { label: "退回", value: "rejected" },
];

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
  const [pending, setPending] = useState<FamilyReviewPendingItem[]>([]);
  const [pendingLoading, setPendingLoading] = useState(true);

  const [history, setHistory] = useState<FamilyReview[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState<FamilyReviewAction | "">("");

  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<SubmitTarget | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const fetchPending = useCallback(async () => {
    setPendingLoading(true);
    try {
      const res = await api.get<FamilyReviewPendingResponse>(
        "/api/v1/family-reviews/pending",
      );
      setPending(res.data ?? []);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setPendingLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(
    async (opts?: { append?: boolean; cursor?: string | null }) => {
      setHistoryLoading(true);
      try {
        const query: Record<string, string | number> = { limit: PAGE_SIZE };
        if (opts?.cursor) query.cursor = opts.cursor;
        if (actionFilter) query.action = actionFilter;
        const res = await api.get<FamilyReviewPage>("/api/v1/family-reviews", {
          query,
        });
        const items = res.items ?? [];
        setHistory((prev) => (opts?.append ? [...prev, ...items] : items));
        setCursor(res.next_cursor ?? null);
        setHasMore(res.has_more ?? false);
      } catch (e) {
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        setHistoryLoading(false);
      }
    },
    [actionFilter],
  );

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleSubmit = async (
    draftId: string,
    action: FamilyReviewAction,
    comment: string,
  ) => {
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/api/v1/family-reviews", {
        sop_draft_id: draftId,
        action,
        comment: comment.trim() || undefined,
      });
      setTarget(null);
      await Promise.all([fetchPending(), fetchHistory()]);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
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
                家族覆核
              </h1>
              <span className="text-[13px] text-[var(--text-secondary)]">
                · 待覆核 {pending.length} 筆 · 歷史 {history.length}
                {hasMore ? "+" : ""} 筆
              </span>
            </div>
          </div>
        </div>

        {error && (
          <div className="mx-8 mt-4 flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-600"
              title="關閉"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        <div className="flex flex-1 flex-col gap-6 overflow-auto pl-14 pr-4 py-6 md:px-8">
          {/* Pending Section */}
          <section className="flex flex-col gap-3">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">
              待覆核清單（管理員初審通過）
            </h2>
            <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <div
                className="flex items-center bg-[#F8FAFC] px-4 text-xs font-semibold text-[var(--text-secondary)]"
                style={{ height: 44 }}
              >
                <div className="flex-1">SOP 標題</div>
                <div className="w-[180px]">初審員</div>
                <div className="w-[200px]">初審通過時間</div>
                <div className="w-[180px]">等待時長</div>
                <div className="w-[180px] text-right">動作</div>
              </div>

              {pendingLoading && pending.length === 0 && (
                <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                  載入中…
                </div>
              )}

              {!pendingLoading && pending.length === 0 && (
                <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                  目前沒有待家族覆核的草稿
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
                      <Check className="h-[12px] w-[12px]" /> 通過
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
                      <XCircle className="h-[12px] w-[12px]" /> 退回
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
                覆核歷史
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
                <div className="w-[180px]">時間</div>
                <div className="w-[100px]">結果</div>
                <div className="w-[200px]">SOP 草稿</div>
                <div className="w-[200px]">覆核者</div>
                <div className="flex-1">備註</div>
              </div>

              {historyLoading && history.length === 0 && (
                <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                  載入中…
                </div>
              )}

              {!historyLoading && history.length === 0 && (
                <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                  沒有符合條件的覆核紀錄
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
                  onClick={() =>
                    fetchHistory({ append: true, cursor: cursor })
                  }
                  disabled={historyLoading}
                  className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {historyLoading ? "載入中…" : "載入更多"}
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
            提交家族覆核
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
            通過
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
            退回
          </button>
        </div>

        <div className="mt-4">
          <label className="text-[13px] font-medium text-[var(--text-secondary)]">
            備註 {action === "rejected" && <span className="text-red-500">*</span>}
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={submitting}
            placeholder={
              action === "rejected"
                ? "退回原因（必填）"
                : "可選：覆核意見、後續建議"
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
              <span className="text-red-600">退回必須填寫原因</span>
            )}
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={submitting}
            className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={() => onSubmit(action, comment)}
            disabled={disabled}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "提交中…" : "確認提交"}
          </button>
        </div>
      </div>
    </div>
  );
}
