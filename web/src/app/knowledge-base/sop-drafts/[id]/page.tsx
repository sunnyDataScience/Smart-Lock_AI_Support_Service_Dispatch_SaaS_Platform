"use client";

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  X,
  CircleCheck,
  CircleX,
  PackageCheck,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, tenantPath } from "@/lib/api";
import { kbDocumentToSopDraft, type KBDocumentSop } from "@/lib/kb-adapter";
import type { components } from "@/types/api.generated";
import { formatRelative } from "@/lib/format";

type SopDraft = components["schemas"]["SopDraft"];
type SopDraftEnvelope = components["schemas"]["SopDraftEnvelope"];
type SopDraftStatus = components["schemas"]["SopDraftStatus"];
type CaseEntryEnvelope = components["schemas"]["CaseEntryEnvelope"];

type Toast = { kind: "success" | "error"; text: string } | null;

function formatApiError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

export default function SopReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const tR = useTranslations("kb.sopDrafts.review");

  const statusConfig: Record<
    SopDraftStatus,
    { label: string; bg: string; text: string }
  > = useMemo(
    () => ({
      draft: { label: tR("statusDraft"), bg: "#F1F5F9", text: "var(--text-disabled)" },
      under_review: {
        label: tR("statusUnderReview"),
        bg: "var(--status-warning)",
        text: "#92400E",
      },
      approved: {
        label: tR("statusApproved"),
        bg: "var(--status-success)",
        text: "#FFFFFF",
      },
      rejected: {
        label: tR("statusRejected"),
        bg: "var(--status-danger)",
        text: "#FFFFFF",
      },
    }),
    [tR],
  );
  const [draft, setDraft] = useState<SopDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState<
    null | "approve" | "reject" | "adopt"
  >(null);
  const [toast, setToast] = useState<Toast>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        // CR-0006 step 3/3：v2 GET → KBDocumentSop → adapter → SopDraft
        const doc = await api.get<KBDocumentSop>(
          tenantPath(`/sops/drafts/${encodeURIComponent(id)}`),
        );
        if (!cancelled) setDraft(doc?.id ? kbDocumentToSopDraft(doc) : null);
      } catch (e) {
        if (!cancelled) setError(formatApiError(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const status = draft?.status;
  const statusInfo = status ? statusConfig[status] : null;
  const canReview = status === "under_review" && !submitting;
  const canAdopt = status === "approved" && !submitting;

  async function handleReview(decision: "approve" | "reject") {
    if (!draft || !canReview) return;
    setSubmitting(decision);
    try {
      const res = await api.post<SopDraftEnvelope>(
        `/sops/${id}/review/dual`,
        { decision, comment: comment.trim() || undefined },
      );
      if (res.data) {
        setDraft(res.data as SopDraft);
        setComment("");
        setToast({
          kind: "success",
          text: decision === "approve" ? tR("approveToast") : tR("rejectToast"),
        });
      }
    } catch (e) {
      setToast({ kind: "error", text: formatApiError(e) });
    } finally {
      setSubmitting(null);
    }
  }

  async function handleAdopt() {
    if (!draft || !canAdopt) return;
    setSubmitting("adopt");
    try {
      const res = await api.post<CaseEntryEnvelope>(
        `/api/v1/sop-drafts/${id}/adopt`,
        {},
      );
      // adopt 成功 → draft 後端已轉 published（API 端 SopDraftStatus 仍映射為 approved）
      // 為了反映「已採納」狀態，重新撈一次 draft；同時提示可前往新案例
      try {
        // CR-0006 step 3/3：refresh via v2
        const refreshed = await api.get<KBDocumentSop>(
          tenantPath(`/sops/drafts/${encodeURIComponent(id)}`),
        );
        if (refreshed?.id) setDraft(kbDocumentToSopDraft(refreshed));
      } catch {
        // ignore — 採納本身已成功
      }
      const newCaseId = res.data?.id;
      setToast({
        kind: "success",
        text: newCaseId
          ? tR("adoptToastWithCase", { id: newCaseId.slice(0, 8) })
          : tR("adoptToastNoCase"),
      });
      if (newCaseId) {
        // 給 toast 一點時間後再跳轉
        setTimeout(() => router.push(`/knowledge-base/cases`), 1200);
      }
    } catch (e) {
      setToast({ kind: "error", text: formatApiError(e) });
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Review Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link
              href="/knowledge-base/sop-drafts"
              className="flex items-center gap-[6px] text-sm text-[var(--primary)]"
            >
              <ArrowLeft className="h-4 w-4" />
              {tR("back")}
            </Link>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {loading ? tR("loading") : (draft?.title ?? "—")}
            </h1>
            {draft && (
              <span
                className="font-mono text-[12px] font-medium text-[var(--text-secondary)]"
                title={draft.id}
              >
                {draft.document_number ?? draft.id.slice(0, 8)}
              </span>
            )}
            {statusInfo && (
              <span
                className="rounded-full px-3 py-1 text-xs font-semibold"
                style={{
                  backgroundColor: statusInfo.bg,
                  color: statusInfo.text,
                }}
              >
                {statusInfo.label}
              </span>
            )}
          </div>
          <Link
            href="/knowledge-base/sop-drafts"
            className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-[var(--bg-page)]"
          >
            <X className="h-5 w-5 text-[var(--text-secondary)]" />
          </Link>
        </div>

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {toast && (
          <div
            className={`mx-8 mt-4 rounded-lg border px-4 py-3 text-sm ${
              toast.kind === "success"
                ? "border-green-200 bg-green-50 text-green-700"
                : "border-red-200 bg-red-50 text-red-700"
            }`}
          >
            {toast.text}
          </div>
        )}

        {/* Two-Column Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left: AI Content */}
          <div className="flex-1 overflow-auto border-r border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <div className="flex flex-col gap-5">
              <h2 className="text-[22px] font-bold text-[var(--text-primary)]">
                {draft?.title ?? (loading ? tR("loading") : "—")}
              </h2>

              <h3 className="text-base font-semibold text-[var(--text-primary)]">
                {tR("stepsTitle")}
              </h3>

              {/* Steps */}
              {draft && draft.steps.length > 0 ? (
                <div className="flex flex-col gap-4">
                  {draft.steps.map((step) => (
                    <div key={step.order} className="flex gap-3">
                      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-xs font-bold text-white">
                        {step.order}
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-sm font-semibold text-[var(--text-primary)]">
                          {step.title}
                        </span>
                        <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
                          {step.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                !loading && (
                  <p className="text-[13px] text-[var(--text-secondary)]">
                    {tR("noSteps")}
                  </p>
                )
              )}

              {/* Source Card */}
              {draft?.problem_card_id && (
                <div className="flex flex-col gap-2 rounded-lg bg-[#EFF6FF] p-4">
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {tR("sourceCard")}
                  </span>
                  <Link
                    href={`/problem-cards/${draft.problem_card_id}`}
                    className="text-sm font-medium text-[var(--primary)]"
                  >
                    {draft.problem_card_id.slice(0, 8)}
                  </Link>
                </div>
              )}

              {/* Meta */}
              {draft && (
                <div className="flex flex-col gap-1 text-xs text-[var(--text-secondary)]">
                  <span>{tR("createdAt", { time: formatRelative(draft.created_at) })}</span>
                  {draft.reviewed_at && (
                    <span>{tR("reviewedAt", { time: formatRelative(draft.reviewed_at) })}</span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Right: Review Tools */}
          <div className="flex w-[42%] flex-col gap-5 overflow-auto bg-[var(--bg-page)] p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)]">
              {tR("toolsTitle")}
            </h3>

            {/* Workflow info banner */}
            <div className="rounded-lg border border-[var(--border)] bg-[#EFF6FF] px-4 py-3 text-[12px] leading-relaxed text-[var(--text-secondary)]">
              {tR("workflowPrefix")}
              <span className="font-semibold text-[var(--text-primary)]">
                {tR("workflowStep1")}
              </span>
              {tR("workflowMid")}
              <span className="font-semibold text-[var(--text-primary)]">
                {tR("workflowStep2")}
              </span>
              {tR("workflowSuffix")}
            </div>

            {/* Comment textarea */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold text-[var(--text-primary)]">
                {tR("commentLabel")}
                <span className="ml-1 text-xs font-normal text-[var(--text-secondary)]">
                  {tR("commentMeta")}
                </span>
              </label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value.slice(0, 1000))}
                placeholder={
                  canReview
                    ? tR("commentPlaceholderActive")
                    : status === "under_review"
                      ? ""
                      : tR("commentPlaceholderDisabled")
                }
                disabled={!canReview}
                className="h-[140px] w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-[14px] py-3 text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)] focus:border-[var(--primary)] disabled:cursor-not-allowed disabled:bg-[#F8FAFC] disabled:text-[var(--text-disabled)]"
              />
              <span className="self-end text-[11px] text-[var(--text-disabled)]">
                {comment.length} / 1000
              </span>
            </div>

            {/* Existing review comment */}
            {draft?.review_comment && (
              <div className="flex flex-col gap-2">
                <span className="text-sm font-semibold text-[var(--text-primary)]">
                  {tR("existingReview")}
                </span>
                <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-3 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                  {draft.review_comment}
                </div>
                {draft.reviewed_at && (
                  <span className="text-[11px] text-[var(--text-disabled)]">
                    {formatRelative(draft.reviewed_at)}
                  </span>
                )}
              </div>
            )}

            {/* Divider */}
            <div className="h-px bg-[var(--border)]" />

            {/* Action Buttons */}
            <div className="flex flex-col gap-[10px]">
              <button
                disabled={!canReview}
                onClick={() => handleReview("approve")}
                title={canReview ? tR("approveTitle") : tR("approveDisabledTitle")}
                className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-[var(--status-success)] text-sm font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
              >
                <CircleCheck className="h-[18px] w-[18px]" />
                {submitting === "approve" ? tR("submitting") : tR("approve")}
              </button>
              <button
                disabled={!canReview}
                onClick={() => handleReview("reject")}
                title={canReview ? tR("rejectTitle") : tR("rejectDisabledTitle")}
                className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-[var(--status-danger)] text-sm font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
              >
                <CircleX className="h-[18px] w-[18px]" />
                {submitting === "reject" ? tR("submitting") : tR("reject")}
              </button>
              <button
                disabled={!canAdopt}
                onClick={handleAdopt}
                title={canAdopt ? tR("adoptTitle") : tR("adoptDisabledTitle")}
                className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-[var(--primary)] text-sm font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
              >
                <PackageCheck className="h-[18px] w-[18px]" />
                {submitting === "adopt" ? tR("submitting") : tR("adopt")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
