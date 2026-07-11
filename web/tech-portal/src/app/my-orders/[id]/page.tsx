"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Phone,
  Navigation,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  MapPin,
} from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import StatusBadge from "@/components/tech/StatusBadge";
import UrgencyBadge from "@/components/tech/UrgencyBadge";
import SignaturePad from "@/components/tech/SignaturePad";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];
type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardEnvelope = components["schemas"]["ProblemCardEnvelope"];

const TERMINAL_STATUSES: WorkOrder["status"][] = [
  "completed",
  "billed",
  "paid",
  "closed",
  "cancelled",
];

// CR-0100：完工功能測試 6 項（業主裁決預設）。技師逐項勾 pass/fail/na（選填）。
const FUNCTION_TEST_ITEMS: ReadonlyArray<{ key: string; label: string }> = [
  { key: "fingerprint", label: "指紋解鎖" },
  { key: "password", label: "密碼解鎖" },
  { key: "card", label: "卡片(RFID)" },
  { key: "app", label: "App/藍牙" },
  { key: "mechanical_key", label: "機械鑰匙" },
  { key: "battery", label: "電池電壓" },
];

const FUNCTION_TEST_RESULTS: ReadonlyArray<{
  value: "pass" | "fail" | "na";
  label: string;
  color: string;
}> = [
  { value: "pass", label: "通過", color: "var(--success, #16a34a)" },
  { value: "fail", label: "失敗", color: "var(--error, #dc2626)" },
  { value: "na", label: "不適用", color: "var(--text-disabled, #94a3b8)" },
];

function formatErr(e: unknown): string {
  return friendlyError(e);
}

export default function MyOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const tStatus = useTranslations("status.workOrder");
  const t = useTranslations("techPortal.detail");
  const tForm = useTranslations("techPortal.detail.form");
  const tSub = useTranslations("techPortal.detail.subflows");
  const tCommon = useTranslations("techPortal.common");
  const tSig = useTranslations("techPortal.signature");

  const [wo, setWo] = useState<WorkOrder | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 問題診斷摘要（設計規格 12_tech problem_card_section）：best-effort 讀取，預設收合
  const [pc, setPc] = useState<ProblemCard | null>(null);
  const [pcOpen, setPcOpen] = useState(false);

  // Completion form state
  const [showForm, setShowForm] = useState(false);
  const [summary, setSummary] = useState("");
  // 到場回報（FR-0006 / 設計 12_tech_my_orders §accepted arrived_btn）
  const [arriving, setArriving] = useState(false);
  const [arriveError, setArriveError] = useState<string | null>(null);
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
  // CR-0100：功能測試逐項結果（選填，不擋完工）。key → pass/fail/na。
  const [funcTests, setFuncTests] = useState<
    Record<string, "pass" | "fail" | "na">
  >({});
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

  // 問題診斷摘要：工單載入後補抓問題卡（失敗只隱藏摘要區，不影響工單操作）
  const pcId = wo?.problem_card_id;
  useEffect(() => {
    if (!pcId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<ProblemCardEnvelope>(
          tenantPath(`/problem-cards/${encodeURIComponent(pcId)}`),
        );
        if (!cancelled) setPc(res.data ?? null);
      } catch {
        if (!cancelled) setPc(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pcId]);

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
      //    冪等：若已完整簽署（後端回 409 STATE_CONFLICT），紀錄本就存在 → 視為成功、續送完工。
      try {
        await api.post(
          tenantPath(`/work-orders/${encodeURIComponent(wo.id)}/signature`),
          {
            customer_signature: custSig,
            technician_signature: techSig,
            signed_at: new Date().toISOString(),
          },
        );
      } catch (sigErr) {
        if (!(sigErr instanceof ApiError && sigErr.status === 409)) throw sigErr;
        // 409 = 已完整簽署；digital_signatures 已存在，完工硬閘可過 → 不阻擋，續送完工。
      }
      // 2) CR-0039 正規完工硬閘 /onsite/completion（照片≥3 / 簽名紀錄存在）。
      //    signature_evidence_id 後端僅寫進稽核 summary、不驗證，傳標記即可。
      await api.post<{ work_order_id: string; completed_at: string | null }>(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}/onsite/completion`),
        {
          signature_evidence_id: "onsite-signature",
          photo_evidence_ids: completionPhotos.map((p) => p.id),
          notes: summary.trim(),
          // CR-0100：功能測試逐項結果（選填，已勾的才送）。
          function_tests: Object.entries(funcTests).map(([key, result]) => ({
            key,
            result,
          })),
        },
      );
      setSubmitOk(true);
      setShowForm(false);
      setCompletionPhotos([]);
      setTechSig("");
      setCustSig("");
      setFuncTests({});
      // onsite/completion 回 {work_order_id, completed_at}（非 envelope）→ refetch 取最新狀態
      await fetchOrder();
    } catch (e) {
      setSubmitError(formatErr(e));
    } finally {
      setSubmitting(false);
    }
  }

  // 到場回報：取瀏覽器 GPS → POST /onsite/arrival（door-check 有 arrival 前置閘
  // CR-0007 HD-01，未回報到場前門面檢核會 409）。成功後 refetch 帶回 actual_arrival。
  async function reportArrival() {
    if (!wo || arriving) return;
    if (!window.confirm(t("arrivedConfirm"))) return;
    setArriving(true);
    setArriveError(null);
    try {
      const gps = await new Promise<{ lat: number; lng: number }>(
        (resolve, reject) => {
          if (!navigator.geolocation) {
            reject(new Error(t("gpsUnavailable")));
            return;
          }
          navigator.geolocation.getCurrentPosition(
            (pos) =>
              resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
            () => reject(new Error(t("gpsDenied"))),
            { timeout: 10_000 },
          );
        },
      );
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}/onsite/arrival`),
        { arrived_at: new Date().toISOString(), gps },
      );
      await fetchOrder();
    } catch (e) {
      setArriveError(formatErr(e));
    } finally {
      setArriving(false);
    }
  }

  const isTerminal = wo ? TERMINAL_STATUSES.includes(wo.status) : false;
  const canComplete =
    wo &&
    !isTerminal &&
    ["accepted", "scheduled", "assigned", "en_route", "arrived", "in_progress"].includes(
      wo.status,
    );
  // 已接單且尚未回報到場 → 顯示「已到達現場」CTA（設計 spec accepted 狀態核心操作）
  const canReportArrival =
    wo &&
    !isTerminal &&
    !wo.actual_arrival &&
    ["assigned", "accepted", "en_route", "in_progress"].includes(wo.status);

  return (
    <TechShell
      // 頁首走 shell 統一規格(h-14 bar:返回 + 工單編號 kicker + 標題;badge 靠右 actions)
      backHref="/my-orders"
      kicker={`#${id.slice(0, 8)}`}
      title={t("title")}
      actions={
        wo ? (
          <>
            <UrgencyBadge urgency={wo.urgency} />
            <StatusBadge status={wo.status} />
          </>
        ) : undefined
      }
    >
      {error && (
        <div className="m-4 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
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
          <section className="flex flex-col gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
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
          <section className="flex flex-col gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              {t("device")}
            </span>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-[var(--surface-strong)] px-2 py-[2px] text-[13px] font-medium text-[var(--text-primary)]">
                {wo.brand}
              </span>
              <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                {wo.model}
              </span>
            </div>
          </section>

          {/* problem_card_section（設計規格 12_tech：問題診斷摘要，預設收合）*/}
          {pc && (
            <section className="flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
              <button
                type="button"
                onClick={() => setPcOpen((v) => !v)}
                aria-expanded={pcOpen}
                className="flex min-h-[44px] items-center justify-between gap-2 text-left"
              >
                <span className="flex items-center gap-2">
                  <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                    {t("pcSummaryTitle")}
                  </span>
                  {typeof pc.confidence_score === "number" && (
                    <span className="rounded-full bg-[#DBEAFE] px-2 py-[2px] text-[11px] font-medium text-[#1D4ED8]">
                      {t("pcConfidence", {
                        percent: Math.round(
                          pc.confidence_score <= 1
                            ? pc.confidence_score * 100
                            : pc.confidence_score,
                        ),
                      })}
                    </span>
                  )}
                </span>
                {pcOpen ? (
                  <ChevronUp className="h-5 w-5 shrink-0 text-[var(--text-secondary)]" />
                ) : (
                  <ChevronDown className="h-5 w-5 shrink-0 text-[var(--text-secondary)]" />
                )}
              </button>
              {pcOpen && (
                <div className="mt-2 flex flex-col gap-2 border-t border-[var(--border)] pt-3">
                  <p className="text-[14px] text-[var(--text-primary)]">
                    <span className="font-medium">{t("pcSymptom")}</span>
                    {pc.symptom || "—"}
                  </p>
                  <p className="text-[14px] text-[var(--text-secondary)]">
                    <span className="font-medium">{t("pcDiagnosis")}</span>
                    {[pc.failure_mode, pc.root_cause].filter(Boolean).join("；") ||
                      pc.category ||
                      "—"}
                  </p>
                </div>
              )}
            </section>
          )}

          {/* service_info_section */}
          <section className="flex flex-col gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
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

          {/* customer_section */}
          <section className="flex flex-col gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
            <span className="text-[11px] font-medium text-[var(--text-secondary)]">
              {t("customer")}
            </span>
            {wo.customer_name && (
              <span className="text-[14px] font-medium text-[var(--text-primary)]">
                {wo.customer_name}
              </span>
            )}
            {wo.customer_phone && (
              <a
                href={`tel:${wo.customer_phone}`}
                className="mt-2 inline-flex h-11 items-center justify-center gap-2 rounded-full bg-[var(--primary)] text-[14px] font-semibold text-white hover:bg-[var(--primary-hover)]"
              >
                <Phone className="h-4 w-4" />
                {t("callCustomer")}（{wo.customer_phone}）
              </a>
            )}
          </section>

          {/* action_section */}
          {canComplete && !showForm && (
            <div className="flex flex-col gap-2">
              {canReportArrival && (
                <>
                  <button
                    type="button"
                    onClick={reportArrival}
                    disabled={arriving}
                    className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-[#F59E0B] text-[15px] font-semibold text-white hover:bg-[#D97706] disabled:opacity-60"
                  >
                    <MapPin className="h-4 w-4" />
                    {arriving ? t("arrivedSubmitting") : t("arrivedCta")}
                  </button>
                  {arriveError && (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                      {arriveError}
                    </div>
                  )}
                </>
              )}
              {wo.actual_arrival && (
                <div className="flex items-center gap-1 text-[12px] text-[#15803D]">
                  <CheckCircle2 className="h-4 w-4" />
                  {t("arrivedAt", {
                    time: new Date(wo.actual_arrival).toLocaleString("zh-TW"),
                  })}
                </div>
              )}
              <button
                type="button"
                onClick={() => setShowForm(true)}
                className="h-12 rounded-full bg-[var(--primary)] text-[15px] font-semibold text-white hover:bg-[var(--primary-hover)]"
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
            <section className="flex flex-col gap-3 rounded-xl border border-[var(--primary)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
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
                  className="rounded-xl border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
                />
              </label>

              {/* 實收金額欄已移除：/onsite/completion 後端刻意 actual_amount=None
                  （完工金額由後續 AR/Payment 模組確認），原輸入框收值後從未送出。 */}

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
                        // 不設 capture：桌機/手機模擬器無相機會「點了沒反應」，真手機則被鎖
                        // 成只能即拍、無法選相簿現成照片。改用標準選擇器，手機仍可選拍照或相簿。
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
                        className="rounded-full bg-[var(--surface-strong)] px-2 py-[2px]"
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

              {/* CR-0100 功能測試逐項勾選（選填，不擋完工） */}
              <div className="flex flex-col gap-2">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  功能測試（選填）
                </span>
                <div className="flex flex-col gap-2">
                  {FUNCTION_TEST_ITEMS.map((item) => (
                    <div
                      key={item.key}
                      className="flex items-center justify-between gap-2"
                    >
                      <span className="text-[13px] text-[var(--text-primary)]">
                        {item.label}
                      </span>
                      <div className="flex gap-1">
                        {FUNCTION_TEST_RESULTS.map((r) => {
                          const selected = funcTests[item.key] === r.value;
                          return (
                            <button
                              key={r.value}
                              type="button"
                              onClick={() =>
                                setFuncTests((prev) => {
                                  if (prev[item.key] === r.value) {
                                    const next = { ...prev };
                                    delete next[item.key];
                                    return next;
                                  }
                                  return { ...prev, [item.key]: r.value };
                                })
                              }
                              className="h-8 rounded-md border px-2 text-[12px] font-medium"
                              style={
                                selected
                                  ? {
                                      backgroundColor: r.color,
                                      color: "#fff",
                                      borderColor: r.color,
                                    }
                                  : {
                                      borderColor: "var(--border)",
                                      color: "var(--text-secondary)",
                                    }
                              }
                            >
                              {r.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
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
                  className="h-11 flex-[2] rounded-full bg-[var(--primary)] text-[14px] font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-60"
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
