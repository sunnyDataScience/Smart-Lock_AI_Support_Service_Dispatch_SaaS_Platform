"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { CalendarClock, ArrowRight, CheckCircle2 } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SubflowHeader from "@/components/tech/SubflowHeader";
import { ApiError, api } from "@/lib/api";

const DELAY_OPTIONS = [
  { value: 15, label: "+15 分鐘" },
  { value: 30, label: "+30 分鐘" },
  { value: 60, label: "+60 分鐘" },
  { value: 120, label: "+2 小時" },
];

const REASON_OPTIONS = [
  "前一單延長",
  "塞車 / 路況",
  "客戶尚未到場",
  "材料尚未到貨",
  "其他",
];

export default function DelayPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();

  const [delayMinutes, setDelayMinutes] = useState(30);
  const [reason, setReason] = useState(REASON_OPTIONS[0]);
  const [reasonText, setReasonText] = useState("");
  const [notify, setNotify] = useState<"customer_only" | "customer_and_staff">(
    "customer_only",
  );
  const [submitting, setSubmitting] = useState(false);
  const [submitOk, setSubmitOk] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function submit() {
    if (submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.post(`/api/v1/work-orders/${encodeURIComponent(id)}/delay`, {
        delay_minutes: delayMinutes,
        reason,
        reason_text: reason === "其他" ? reasonText.trim() : undefined,
        notify,
      });
      setSubmitOk(true);
      setTimeout(() => router.push(`/my-orders/${id}`), 1500);
    } catch (e) {
      setSubmitError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <TechShell>
      <SubflowHeader workOrderId={id} title="延遲通知" />

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          延遲通知已送出
        </div>
      )}

      {submitError && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {submitError}
        </div>
      )}

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          延遲時長
        </span>
        <div className="flex flex-wrap gap-2">
          {DELAY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setDelayMinutes(opt.value)}
              className={`rounded-md border px-3 py-2 text-[13px] font-medium ${
                delayMinutes === opt.value
                  ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                  : "border-[var(--border)] bg-white text-[var(--text-primary)]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <label className="mt-2 flex items-center gap-2 text-[12px]">
          <span className="text-[var(--text-secondary)]">自訂分鐘數</span>
          <input
            type="number"
            min={5}
            max={300}
            value={delayMinutes}
            onChange={(e) => setDelayMinutes(parseInt(e.target.value) || 0)}
            className="w-24 rounded-md border border-[var(--border)] px-2 py-1"
          />
        </label>
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          延遲原因
        </span>
        <div className="flex flex-col gap-2">
          {REASON_OPTIONS.map((r) => (
            <label
              key={r}
              className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-[13px] ${
                reason === r
                  ? "border-[var(--primary)] bg-[#EFF6FF]"
                  : "border-[var(--border)] bg-white"
              }`}
            >
              <input
                type="radio"
                checked={reason === r}
                onChange={() => setReason(r)}
                className="h-4 w-4 accent-[var(--primary)]"
              />
              {r}
            </label>
          ))}
        </div>
        {reason === "其他" && (
          <textarea
            value={reasonText}
            onChange={(e) => setReasonText(e.target.value)}
            rows={2}
            placeholder="補充說明..."
            className="mt-2 rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
          />
        )}
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          通知對象
        </span>
        {(
          [
            ["customer_only", "僅通知客戶"],
            ["customer_and_staff", "通知客戶與調度員"],
          ] as const
        ).map(([v, label]) => (
          <label key={v} className="flex items-center gap-2 text-[13px]">
            <input
              type="radio"
              checked={notify === v}
              onChange={() => setNotify(v)}
              className="h-4 w-4 accent-[var(--primary)]"
            />
            {label}
          </label>
        ))}
      </section>

      <div className="mx-4 mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-[12px] text-blue-900">
        <span className="font-semibold">需要重新選時段？</span>
        <p className="mt-1">
          若延遲超過 1 小時或客戶要求換日，建議直接走改期流程：
        </p>
        <Link
          href={`/my-orders/${id}/reschedule?from=delay`}
          className="mt-2 inline-flex items-center gap-1 text-[var(--primary)] hover:underline"
        >
          <CalendarClock className="h-3 w-3" />
          前往改期日曆
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      <div className="mt-4 flex gap-2 px-4 pb-4">
        <button
          type="button"
          onClick={() => router.push(`/my-orders/${id}`)}
          className="h-12 flex-1 rounded-lg border border-[var(--border)] text-[14px] font-medium text-[var(--text-primary)]"
        >
          取消
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={submitting}
          className="h-12 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white disabled:opacity-60"
        >
          {submitting ? "送出中…" : "送出延遲通知"}
        </button>
      </div>
    </TechShell>
  );
}
