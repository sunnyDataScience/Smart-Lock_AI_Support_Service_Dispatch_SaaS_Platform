"use client";

import { useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { CalendarClock, ArrowRight, CheckCircle2 } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SubflowHeader from "@/components/tech/SubflowHeader";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, tenantPath } from "@/lib/api";

const DURATION_KEYS = [
  { value: 15, key: "min15" },
  { value: 30, key: "min30" },
  { value: 60, key: "min60" },
  { value: 120, key: "h2" },
] as const;

type ReasonKey =
  | "previousOrder"
  | "traffic"
  | "customerNotArrived"
  | "materialNotArrived"
  | "other";

const REASON_KEYS: ReasonKey[] = [
  "previousOrder",
  "traffic",
  "customerNotArrived",
  "materialNotArrived",
  "other",
];

// 後端介面語意：reason 為固定的 zh-TW 字串。i18n 後 UI 顯示用 i18n，但送往
// API 仍維持原始中文以保持 backend 行為不變。
const REASON_TO_API: Record<ReasonKey, string> = {
  previousOrder: "前一單延長",
  traffic: "塞車 / 路況",
  customerNotArrived: "客戶尚未到場",
  materialNotArrived: "材料尚未到貨",
  other: "其他",
};

export default function DelayPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();
  const t = useTranslations("techPortal.delay");
  const tDur = useTranslations("techPortal.delay.durations");
  const tReason = useTranslations("techPortal.delay.reasons");
  const tNotify = useTranslations("techPortal.delay.notify");
  const tCommon = useTranslations("techPortal.common");

  const durationOptions = useMemo(
    () => DURATION_KEYS.map((d) => ({ value: d.value, label: tDur(d.key) })),
    [tDur],
  );

  const [delayMinutes, setDelayMinutes] = useState(30);
  const [reasonKey, setReasonKey] = useState<ReasonKey>("previousOrder");
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
      await api.post(tenantPath(`/work-orders/${encodeURIComponent(id)}/notify-delay`), {
        delay_minutes: delayMinutes,
        reason: REASON_TO_API[reasonKey],
        reason_text: reasonKey === "other" ? reasonText.trim() : undefined,
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
      <SubflowHeader workOrderId={id} title={t("title")} />

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          {t("successSubmitted")}
        </div>
      )}

      {submitError && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {submitError}
        </div>
      )}

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("durationLabel")}
        </span>
        <div className="flex flex-wrap gap-2">
          {durationOptions.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setDelayMinutes(opt.value)}
              className={`rounded-md border px-3 py-2 text-[13px] font-medium ${
                delayMinutes === opt.value
                  ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                  : "border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <label className="mt-2 flex items-center gap-2 text-[12px]">
          <span className="text-[var(--text-secondary)]">{t("customMinutes")}</span>
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

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("reasonLabel")}
        </span>
        <div className="flex flex-col gap-2">
          {REASON_KEYS.map((r) => (
            <label
              key={r}
              className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-[13px] ${
                reasonKey === r
                  ? "border-[var(--primary)] bg-[var(--primary-light)]"
                  : "border-[var(--border)] bg-[var(--bg-surface)]"
              }`}
            >
              <input
                type="radio"
                checked={reasonKey === r}
                onChange={() => setReasonKey(r)}
                className="h-4 w-4 accent-[var(--primary)]"
              />
              {tReason(r)}
            </label>
          ))}
        </div>
        {reasonKey === "other" && (
          <textarea
            value={reasonText}
            onChange={(e) => setReasonText(e.target.value)}
            rows={2}
            placeholder={t("reasonOtherPlaceholder")}
            className="mt-2 rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
          />
        )}
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("notifyLabel")}
        </span>
        {(
          [
            ["customer_only", "customerOnly"],
            ["customer_and_staff", "customerAndStaff"],
          ] as const
        ).map(([v, lk]) => (
          <label key={v} className="flex items-center gap-2 text-[13px]">
            <input
              type="radio"
              checked={notify === v}
              onChange={() => setNotify(v)}
              className="h-4 w-4 accent-[var(--primary)]"
            />
            {tNotify(lk)}
          </label>
        ))}
      </section>

      <div className="mx-4 mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-[12px] text-blue-900">
        <span className="font-semibold">{t("rescheduleHintTitle")}</span>
        <p className="mt-1">{t("rescheduleHintBody")}</p>
        <Link
          href={`/my-orders/${id}/reschedule?from=delay`}
          className="mt-2 inline-flex items-center gap-1 text-[var(--primary)] hover:underline"
        >
          <CalendarClock className="h-3 w-3" />
          {t("rescheduleLink")}
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      <div className="mt-4 flex gap-2 px-4 pb-4">
        <button
          type="button"
          onClick={() => router.push(`/my-orders/${id}`)}
          className="h-12 flex-1 rounded-lg border border-[var(--border)] text-[14px] font-medium text-[var(--text-primary)]"
        >
          {tCommon("cancel")}
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={submitting}
          className="h-12 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white disabled:opacity-60"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </div>
    </TechShell>
  );
}
