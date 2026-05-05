"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Phone,
  Navigation,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import StatusBadge, { statusLabel } from "@/components/tech/StatusBadge";
import UrgencyBadge from "@/components/tech/UrgencyBadge";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];
type CompletionReport = components["schemas"]["CompletionReport"];

const TERMINAL_STATUSES: WorkOrder["status"][] = [
  "completed",
  "billed",
  "paid",
  "closed",
  "cancelled",
];

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

export default function MyOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();

  const [wo, setWo] = useState<WorkOrder | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Completion form state
  const [showForm, setShowForm] = useState(false);
  const [summary, setSummary] = useState("");
  const [actualAmount, setActualAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitOk, setSubmitOk] = useState(false);

  const fetchOrder = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(id)}`,
      );
      setWo(res.data ?? null);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  async function submitCompletion() {
    if (!wo || submitting) return;
    if (summary.trim().length < 5) {
      setSubmitError("請輸入完工摘要（至少 5 字）");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const body: CompletionReport = {
        summary: summary.trim(),
        ...(actualAmount.trim() ? { actual_amount: actualAmount.trim() } : {}),
      };
      const res = await api.post<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(wo.id)}/complete`,
        body,
      );
      setWo(res.data ?? wo);
      setSubmitOk(true);
      setShowForm(false);
    } catch (e) {
      setSubmitError(formatErr(e));
    } finally {
      setSubmitting(false);
    }
  }

  const isTerminal = wo ? TERMINAL_STATUSES.includes(wo.status) : false;
  const canComplete =
    wo &&
    !isTerminal &&
    ["accepted", "scheduled", "assigned", "en_route", "arrived", "in_progress"].includes(
      wo.status,
    );

  return (
    <TechShell>
      {/* detail_header */}
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[var(--border)] bg-white px-2 py-3">
        <button
          type="button"
          onClick={() => router.push("/my-orders")}
          className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          aria-label="返回"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex flex-1 flex-col">
          <span className="text-[11px] text-[var(--text-disabled)]">
            #{id.slice(0, 8)}
          </span>
          <span className="text-[14px] font-semibold text-[var(--text-primary)]">
            工單詳情
          </span>
        </div>
        {wo && (
          <div className="flex items-center gap-1 pr-2">
            <UrgencyBadge urgency={wo.urgency} />
            <StatusBadge status={wo.status} />
          </div>
        )}
      </div>

      {error && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          完工報告已提交，等待客戶確認
        </div>
      )}

      {loading && !wo ? (
        <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
          載入中…
        </div>
      ) : !wo ? (
        <div className="flex h-60 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
          <AlertCircle className="h-10 w-10 text-[var(--text-disabled)]" />
          <p className="text-[14px]">找不到工單</p>
          <Link
            href="/my-orders"
            className="text-[12px] text-[var(--primary)] hover:underline"
          >
            返回列表
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-4 px-4 py-4 pb-24">
          {/* address_section */}
          <section className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              服務地址
            </span>
            <p className="text-[16px] font-semibold text-[var(--text-primary)]">
              {wo.address}
            </p>
            <span className="text-[12px] text-[var(--text-secondary)]">
              {wo.district}
            </span>
            <a
              href={`https://maps.google.com/?q=${encodeURIComponent(wo.address)}`}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex h-11 items-center justify-center gap-1 rounded-lg border border-[var(--border)] text-[14px] font-medium text-[var(--primary)] hover:bg-[#EFF6FF]"
            >
              <Navigation className="h-4 w-4" />
              導航前往
            </a>
          </section>

          {/* device_section */}
          <section className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              鎖具資訊
            </span>
            <div className="flex items-center gap-2">
              <span className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[13px] font-medium text-[var(--text-primary)]">
                {wo.brand}
              </span>
              <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                {wo.model}
              </span>
            </div>
          </section>

          {/* service_info_section */}
          <section className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              服務資訊
            </span>
            <div className="grid grid-cols-2 gap-2 text-[13px]">
              <div>
                <span className="block text-[11px] text-[var(--text-disabled)]">
                  狀態
                </span>
                <span className="font-medium text-[var(--text-primary)]">
                  {statusLabel(wo.status)}
                </span>
              </div>
              {wo.estimated_reward && (
                <div>
                  <span className="block text-[11px] text-[var(--text-disabled)]">
                    預估佣金
                  </span>
                  <span className="font-bold text-[#059669]">
                    ${wo.estimated_reward}
                  </span>
                </div>
              )}
              {wo.scheduled_time && (
                <div>
                  <span className="block text-[11px] text-[var(--text-disabled)]">
                    預約時間
                  </span>
                  <span className="font-medium text-[var(--text-primary)]">
                    {new Date(wo.scheduled_time).toLocaleString("zh-TW")}
                  </span>
                </div>
              )}
              {wo.completion_time && (
                <div>
                  <span className="block text-[11px] text-[var(--text-disabled)]">
                    完工時間
                  </span>
                  <span className="font-medium text-[var(--text-primary)]">
                    {new Date(wo.completion_time).toLocaleString("zh-TW")}
                  </span>
                </div>
              )}
            </div>
          </section>

          {/* customer_section（電話需從 ProblemCard 取，MVP 先省）*/}
          <section className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              客戶資訊
            </span>
            <Link
              href={`/problem-cards/${wo.problem_card_id}`}
              className="text-[13px] text-[var(--primary)] hover:underline"
            >
              查看問題卡 →
            </Link>
            <button
              type="button"
              disabled
              className="mt-2 inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-[#94A3B8] text-[14px] font-semibold text-white opacity-60"
              title="客戶電話需後端提供 — MVP 待補"
            >
              <Phone className="h-4 w-4" />
              撥打客戶電話（待補）
            </button>
          </section>

          {/* action_section */}
          {canComplete && !showForm && (
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => setShowForm(true)}
                className="h-12 rounded-lg bg-[var(--primary)] text-[15px] font-semibold text-white hover:bg-[#1D4ED8]"
              >
                完工回報
              </button>
              <Link
                href={`/my-orders/${wo.id}/reschedule`}
                className="flex h-11 items-center justify-center rounded-lg border border-[var(--border)] bg-white text-[14px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
              >
                改期
              </Link>
            </div>
          )}

          {showForm && (
            <section className="flex flex-col gap-3 rounded-xl border border-[var(--primary)] bg-white p-4 shadow-sm">
              <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                完工報告
              </span>

              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  作業摘要 <span className="text-red-500">*</span>
                </span>
                <textarea
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  rows={4}
                  placeholder="例：更換鎖芯、測試開關正常、與客戶確認完成。"
                  className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  實收金額（NT$）
                </span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={actualAmount}
                  onChange={(e) => setActualAmount(e.target.value)}
                  placeholder="例：1500"
                  className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
                />
              </label>

              {submitError && (
                <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                  {submitError}
                </div>
              )}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  disabled={submitting}
                  className="h-11 flex-1 rounded-lg border border-[var(--border)] text-[14px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={submitCompletion}
                  disabled={submitting}
                  className="h-11 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-60"
                >
                  {submitting ? "提交中…" : "提交完工"}
                </button>
              </div>

              <p className="text-[11px] text-[var(--text-disabled)]">
                註：照片上傳、零件清單、簽章等完整欄位於後續迭代補上
              </p>
            </section>
          )}

          {isTerminal && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-page)] p-4 text-center text-[13px] text-[var(--text-secondary)]">
              此工單已 {statusLabel(wo.status)}，無法再操作
            </div>
          )}
        </div>
      )}
    </TechShell>
  );
}
