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
import StatusBadge from "@/components/tech/StatusBadge";
import UrgencyBadge from "@/components/tech/UrgencyBadge";
import SignaturePad from "@/components/tech/SignaturePad";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, tenantPath } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];

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
  const tStatus = useTranslations("status.workOrder");
  const t = useTranslations("techPortal.detail");
  const tForm = useTranslations("techPortal.detail.form");
  const tSub = useTranslations("techPortal.detail.subflows");
  const tCommon = useTranslations("techPortal.common");
  const tSig = useTranslations("techPortal.signature");

  const [wo, setWo] = useState<WorkOrder | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Completion form state
  const [showForm, setShowForm] = useState(false);
  const [summary, setSummary] = useState("");
  const [actualAmount, setActualAmount] = useState("");
  const [completionPhotos, setCompletionPhotos] = useState<
    { section: "before" | "during" | "after"; id: string; url: string; filename: string }[]
  >([]);
  const [photoUploading, setPhotoUploading] = useState<
    "before" | "during" | "after" | null
  >(null);
  // CR：完工簽名改用 canvas 雙簽名（與 /signature 頁一致），送 /signature 建 digital_signatures
  // 紀錄（完工硬閘 _signature_exists 認的是這個，非 /media 上傳的圖）。base64 dataURL。
  const [techSig, setTechSig] = useState("");
  const [custSig, setCustSig] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitOk, setSubmitOk] = useState(false);

  const fetchOrder = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(id)}`),
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

  async function uploadCompletionPhoto(
    section: "before" | "during" | "after",
    file: File,
  ) {
    if (!wo) return;
    setPhotoUploading(section);
    setSubmitError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      // section 值（before/during/after）對應 purpose completion_before/during/after。
      fd.append("purpose", `completion_${section}`);
      fd.append("work_order_id", wo.id);
      const res = await api.upload<{ id: string; url: string; filename: string }>(
        tenantPath("/media"),
        fd,
      );
      setCompletionPhotos((prev) => [
        ...prev,
        {
          section,
          id: res.id,
          url: res.url,
          filename: res.filename,
        },
      ]);
    } catch (e) {
      setSubmitError(formatErr(e));
    } finally {
      setPhotoUploading(null);
    }
  }

  async function submitCompletion() {
    if (!wo || submitting) return;
    if (summary.trim().length < 5) {
      setSubmitError(tForm("errorSummaryShort"));
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      // 1) 先送雙簽名 → 建 digital_signatures 紀錄。完工硬閘 _signature_exists 認的是
      //    這個（customer 簽名紀錄），非 /media 上傳的簽名圖。與 /signature 頁同一端點。
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}/signature`),
        {
          customer_signature: custSig,
          technician_signature: techSig,
          signed_at: new Date().toISOString(),
        },
      );
      // 2) CR-0039 正規完工硬閘 /onsite/completion（照片≥3 / 簽名紀錄存在）。
      //    signature_evidence_id 後端僅寫進稽核 summary、不驗證，傳標記即可。
      await api.post<{ work_order_id: string; completed_at: string | null }>(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}/onsite/completion`),
        {
          signature_evidence_id: "onsite-signature",
          photo_evidence_ids: completionPhotos.map((p) => p.id),
          notes: summary.trim(),
        },
      );
      setSubmitOk(true);
      setShowForm(false);
      setCompletionPhotos([]);
      setTechSig("");
      setCustSig("");
      // onsite/completion 回 {work_order_id, completed_at}（非 envelope）→ refetch 取最新狀態
      await fetchOrder();
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
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[var(--border)] bg-[var(--bg-surface)] px-2 py-3">
        <button
          type="button"
          onClick={() => router.push("/my-orders")}
          className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          aria-label={tCommon("back")}
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex flex-1 flex-col">
          <span className="text-[11px] text-[var(--text-disabled)]">
            #{id.slice(0, 8)}
          </span>
          <span className="text-[14px] font-semibold text-[var(--text-primary)]">
            {t("title")}
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
          {t("completionSubmitted")}
        </div>
      )}

      {loading && !wo ? (
        <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
          {tCommon("loading")}
        </div>
      ) : !wo ? (
        <div className="flex h-60 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
          <AlertCircle className="h-10 w-10 text-[var(--text-disabled)]" />
          <p className="text-[14px]">{tCommon("notFound")}</p>
          <Link
            href="/my-orders"
            className="text-[12px] text-[var(--primary)] hover:underline"
          >
            {tCommon("backToList")}
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-4 px-4 py-4 pb-24">
          {/* address_section */}
          <section className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              {t("address")}
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
              className="mt-2 inline-flex h-11 items-center justify-center gap-1 rounded-lg border border-[var(--border)] text-[14px] font-medium text-[var(--primary)] hover:bg-[var(--primary-light)]"
            >
              <Navigation className="h-4 w-4" />
              {t("navigate")}
            </a>
          </section>

          {/* device_section */}
          <section className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              {t("device")}
            </span>
            <div className="flex items-center gap-2">
              <span className="rounded bg-[var(--surface-strong)] px-2 py-[2px] text-[13px] font-medium text-[var(--text-primary)]">
                {wo.brand}
              </span>
              <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                {wo.model}
              </span>
            </div>
          </section>

          {/* service_info_section */}
          <section className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              {t("service")}
            </span>
            <div className="grid grid-cols-2 gap-2 text-[13px]">
              <div>
                <span className="block text-[11px] text-[var(--text-disabled)]">
                  {t("status")}
                </span>
                <span className="font-medium text-[var(--text-primary)]">
                  {tStatus(wo.status)}
                </span>
              </div>
              {wo.estimated_reward && (
                <div>
                  <span className="block text-[11px] text-[var(--text-disabled)]">
                    {t("estimatedReward")}
                  </span>
                  <span className="font-bold text-[#059669]">
                    ${wo.estimated_reward}
                  </span>
                </div>
              )}
              {wo.scheduled_time && (
                <div>
                  <span className="block text-[11px] text-[var(--text-disabled)]">
                    {t("scheduledTime")}
                  </span>
                  <span className="font-medium text-[var(--text-primary)]">
                    {new Date(wo.scheduled_time).toLocaleString("zh-TW")}
                  </span>
                </div>
              )}
              {wo.completion_time && (
                <div>
                  <span className="block text-[11px] text-[var(--text-disabled)]">
                    {t("completionTime")}
                  </span>
                  <span className="font-medium text-[var(--text-primary)]">
                    {new Date(wo.completion_time).toLocaleString("zh-TW")}
                  </span>
                </div>
              )}
            </div>
          </section>

          {/* customer_section（電話需從 ProblemCard 取，MVP 先省）*/}
          <section className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              {t("customer")}
            </span>
            <Link
              href={`/problem-cards/${wo.problem_card_id}`}
              className="text-[13px] text-[var(--primary)] hover:underline"
            >
              {t("viewProblemCard")}
            </Link>
            <button
              type="button"
              disabled
              className="mt-2 inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-[var(--text-tertiary)] text-[14px] font-semibold text-white opacity-60"
              title={t("callCustomerTitle")}
            >
              <Phone className="h-4 w-4" />
              {t("callCustomer")}
            </button>
          </section>

          {/* action_section */}
          {canComplete && !showForm && (
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => setShowForm(true)}
                className="h-12 rounded-lg bg-[var(--primary)] text-[15px] font-semibold text-white hover:bg-[var(--primary-hover)]"
              >
                {t("completeCta")}
              </button>

              {/* Subflow CTAs */}
              <div className="grid grid-cols-2 gap-2">
                <Link
                  href={`/my-orders/${wo.id}/reschedule`}
                  className="flex h-11 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                >
                  {tSub("reschedule")}
                </Link>
                <Link
                  href={`/my-orders/${wo.id}/delay`}
                  className="flex h-11 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                >
                  {tSub("delay")}
                </Link>
                <Link
                  href={`/my-orders/${wo.id}/scope-change`}
                  className="flex h-11 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                >
                  {tSub("scopeChange")}
                </Link>
                <Link
                  href={`/my-orders/${wo.id}/material-request`}
                  className="flex h-11 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                >
                  {tSub("materialRequest")}
                </Link>
                <Link
                  href={`/my-orders/${wo.id}/door-check`}
                  className="flex h-11 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                >
                  {tSub("doorCheck")}
                </Link>
                <Link
                  href={`/my-orders/${wo.id}/signature`}
                  className="flex h-11 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                >
                  {tSub("signature")}
                </Link>
              </div>
            </div>
          )}

          {showForm && (
            <section className="flex flex-col gap-3 rounded-xl border border-[var(--primary)] bg-[var(--bg-surface)] p-4 shadow-sm">
              <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                {tForm("title")}
              </span>

              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  {tForm("summaryLabel")} <span className="text-red-500">*</span>
                </span>
                <textarea
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  rows={4}
                  placeholder={tForm("summaryPlaceholder")}
                  className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  {tForm("amountLabel")}
                </span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={actualAmount}
                  onChange={(e) => setActualAmount(e.target.value)}
                  placeholder={tForm("amountPlaceholder")}
                  className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
                />
              </label>

              {/* 完工照片上傳（before / after） */}
              <div className="flex flex-col gap-2">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  {tForm("photosLabel")}
                </span>
                <div className="grid grid-cols-3 gap-2">
                  {(["before", "during", "after"] as const).map((section) => (
                    <label
                      key={section}
                      className="flex h-20 cursor-pointer items-center justify-center gap-1 rounded-md border-2 border-dashed border-[var(--border)] text-[12px] text-[var(--text-secondary)] hover:border-[var(--primary)]"
                    >
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) uploadCompletionPhoto(section, f);
                          e.target.value = "";
                        }}
                      />
                      {photoUploading === section
                        ? tCommon("uploading")
                        : tForm(
                            section === "before"
                              ? "photoBefore"
                              : section === "during"
                                ? "photoDuring"
                                : "photoAfter",
                          )}
                    </label>
                  ))}
                </div>
                {completionPhotos.length > 0 && (
                  <div className="flex flex-wrap gap-1 text-[11px] text-[var(--text-secondary)]">
                    {completionPhotos.map((p) => (
                      <span
                        key={p.id}
                        className="rounded bg-[var(--surface-strong)] px-2 py-[2px]"
                      >
                        [{p.section}] {p.filename.slice(0, 16)}
                      </span>
                    ))}
                  </div>
                )}
                <span
                  className={
                    completionPhotos.length >= 3
                      ? "text-[11px] text-[#15803D]"
                      : "text-[11px] text-[#B45309]"
                  }
                >
                  {tForm("photosCounter", { n: completionPhotos.length })}
                </span>
              </div>

              {/* CR-0039 完工簽名（雙 canvas 簽名 → /signature 建 digital_signatures；硬閘必填）*/}
              <div className="flex flex-col gap-3">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  {tForm("signatureLabel")} <span className="text-red-500">*</span>
                </span>
                <SignaturePad label={tSig("techLabel")} onChange={setTechSig} />
                <SignaturePad label={tSig("customerLabel")} onChange={setCustSig} />
              </div>

              <p className="rounded-md bg-[var(--bg-page)] px-3 py-2 text-[11px] text-[var(--text-secondary)]">
                {tForm("gateHint")}
              </p>

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
                  {tCommon("cancel")}
                </button>
                <button
                  type="button"
                  onClick={submitCompletion}
                  disabled={
                    submitting ||
                    completionPhotos.length < 3 ||
                    custSig.length <= 100 ||
                    techSig.length <= 100
                  }
                  className="h-11 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-60"
                >
                  {submitting ? tForm("submitting") : tForm("submit")}
                </button>
              </div>

              <p className="text-[11px] text-[var(--text-disabled)]">
                {tForm("note")}
              </p>
            </section>
          )}

          {isTerminal && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-page)] p-4 text-center text-[13px] text-[var(--text-secondary)]">
              {t("terminalNotice", { status: tStatus(wo.status) })}
            </div>
          )}
        </div>
      )}
    </TechShell>
  );
}
