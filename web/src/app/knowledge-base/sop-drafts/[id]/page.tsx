"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  X,
  CircleCheck,
  CircleX,
  MessageSquare,
  Save,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";
import { formatRelative } from "@/lib/format";

type SopDraft = components["schemas"]["SopDraft"];
type SopDraftEnvelope = components["schemas"]["SopDraftEnvelope"];
type SopDraftStatus = components["schemas"]["SopDraftStatus"];

const statusConfig: Record<
  SopDraftStatus,
  { label: string; bg: string; text: string }
> = {
  draft: { label: "草稿", bg: "#F1F5F9", text: "var(--text-disabled)" },
  under_review: {
    label: "待審核",
    bg: "var(--status-warning)",
    text: "#92400E",
  },
  approved: {
    label: "已核准",
    bg: "var(--status-success)",
    text: "#FFFFFF",
  },
  rejected: {
    label: "已拒絕",
    bg: "var(--status-danger)",
    text: "#FFFFFF",
  },
};

export default function SopReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [draft, setDraft] = useState<SopDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.get<SopDraftEnvelope>(
          `/api/v1/sop-drafts/${id}`,
        );
        if (!cancelled) setDraft((res.data as SopDraft) ?? null);
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof ApiError
              ? `${e.errorCode} (${e.status})：${e.message}`
              : e instanceof Error
                ? e.message
                : String(e),
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const status = draft?.status;
  const statusInfo = status ? statusConfig[status] : null;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Review Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <div className="flex items-center gap-4">
            <Link
              href="/knowledge-base/sop-drafts"
              className="flex items-center gap-[6px] text-sm text-[var(--primary)]"
            >
              <ArrowLeft className="h-4 w-4" />
              返回 SOP 草稿列表
            </Link>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {loading ? "載入中…" : (draft?.title ?? "—")}
            </h1>
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

        {/* Two-Column Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left: AI Content */}
          <div className="flex-1 overflow-auto border-r border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <div className="flex flex-col gap-5">
              <h2 className="text-[22px] font-bold text-[var(--text-primary)]">
                {draft?.title ?? (loading ? "載入中…" : "—")}
              </h2>

              <h3 className="text-base font-semibold text-[var(--text-primary)]">
                SOP 步驟
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
                    尚無步驟內容
                  </p>
                )
              )}

              {/* Source Card */}
              {draft?.problem_card_id && (
                <div className="flex flex-col gap-2 rounded-lg bg-[#EFF6FF] p-4">
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    來源問題卡
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
                  <span>建立於 {formatRelative(draft.created_at)}</span>
                  {draft.reviewed_at && (
                    <span>審核於 {formatRelative(draft.reviewed_at)}</span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Right: Review Tools */}
          <div className="flex w-[42%] flex-col gap-5 overflow-auto bg-[var(--bg-page)] p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)]">
              審核工具
            </h3>

            {/* Pending banner */}
            <div className="rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[12px] leading-relaxed text-[#92400E]">
              審核與採納功能即將推出（reviewSopDraft、adoptSopDraft 等寫入
              endpoints 待後續 Phase 接入），目前僅顯示草稿內容與既有審核紀錄。
            </div>

            {/* Notes (disabled) */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold text-[var(--text-primary)]">
                審核意見
              </label>
              <textarea
                placeholder="即將推出"
                disabled
                className="h-[140px] w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-[14px] py-3 text-[13px] text-[var(--text-disabled)] outline-none placeholder:text-[var(--text-disabled)] disabled:cursor-not-allowed disabled:opacity-60"
                title="即將推出"
              />
            </div>

            {/* Existing review comment */}
            {draft?.review_comment && (
              <div className="flex flex-col gap-2">
                <span className="text-sm font-semibold text-[var(--text-primary)]">
                  審核紀錄
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

            {/* Action Buttons (all disabled) */}
            <div className="flex flex-col gap-[10px]">
              <button
                disabled
                title="即將推出"
                className="flex h-[42px] cursor-not-allowed items-center justify-center gap-2 rounded-lg bg-[var(--status-success)] text-sm font-semibold text-white opacity-50"
              >
                <CircleCheck className="h-[18px] w-[18px]" />
                核准並發布
              </button>
              <button
                disabled
                title="即將推出"
                className="flex h-[42px] cursor-not-allowed items-center justify-center gap-2 rounded-lg bg-[var(--status-danger)] text-sm font-semibold text-white opacity-50"
              >
                <CircleX className="h-[18px] w-[18px]" />
                拒絕
              </button>
              <button
                disabled
                title="即將推出"
                className="flex h-[42px] cursor-not-allowed items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] text-sm font-semibold text-[var(--text-disabled)] opacity-60"
              >
                <MessageSquare className="h-[18px] w-[18px]" />
                要求修改
              </button>
              <button
                disabled
                title="即將推出"
                className="flex h-[42px] cursor-not-allowed items-center justify-center gap-2 rounded-lg text-sm font-medium text-[var(--text-disabled)] opacity-60"
              >
                <Save className="h-[18px] w-[18px]" />
                暫存審核意見
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
