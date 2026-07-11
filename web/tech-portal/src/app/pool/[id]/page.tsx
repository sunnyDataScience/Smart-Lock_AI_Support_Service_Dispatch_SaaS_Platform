"use client";

// 案件池工單詳情（接單前）——業主 UAT 裁決（2026-07-11）：
// 案件池不可一鍵接單，需先進詳情頁看清楚 → 按「接受工單」→ 確認視窗二次確認。
// 隱私最小揭露：接單前不顯示客戶姓名/電話（接單後於我的工單完整呈現）。

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, Clock, DoorOpen, MapPin, Wrench } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import UrgencyBadge from "@/components/tech/UrgencyBadge";
import {
  Modal,
  ModalContent,
  ModalDescription,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from "@/components/ui/Modal";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];

export default function PoolOrderDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;
  const t = useTranslations("techPortal.pool");
  const tCommon = useTranslations("techPortal.common");

  const [wo, setWo] = useState<WorkOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [conflict, setConflict] = useState(false);

  const fetchOrder = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(id)}`),
      );
      setWo(res.data ?? null);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  // 可接條件對齊 pool 列表（DB created→API inquiring 未派工、assigned 已派待接受）；
  // assigned 是否派給自己由後端 accept 仲裁（非本人 → 409 顯示已被接走）。
  const acceptable =
    !!wo && (wo.status === "inquiring" || wo.status === "assigned");

  async function confirmAccept() {
    if (!wo || accepting) return;
    setAccepting(true);
    setError(null);
    try {
      const res = await api.post<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}:accept`),
      );
      router.replace(`/my-orders/${res.data?.id ?? wo.id}`);
    } catch (e) {
      setConfirmOpen(false);
      if (e instanceof ApiError && e.status === 409) {
        setConflict(true);
      } else {
        setError(friendlyError(e));
      }
      setAccepting(false);
    }
  }

  const device = wo ? [wo.brand, wo.model].filter(Boolean).join(" ") : "";
  const problem = wo
    ? [wo.problem_type, wo.service_category].filter(Boolean).join(" · ")
    : "";
  const door = wo
    ? [
        wo.door_type,
        wo.door_thickness,
        wo.is_interior_door ? t("fieldInteriorDoor") : null,
      ]
        .filter(Boolean)
        .join(" · ")
    : "";

  return (
    <TechShell
      backHref="/pool"
      kicker={`#${id.slice(0, 8)}`}
      title={t("detailTitle")}
      actions={wo ? <UrgencyBadge urgency={wo.urgency} /> : undefined}
    >
      {error && (
        <div className="m-4 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}
      {conflict && (
        <div className="m-4 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] text-amber-800">
          {t("conflictTaken")}
        </div>
      )}

      {loading && !wo ? (
        <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
          {t("loading")}
        </div>
      ) : !wo ? (
        <div className="flex h-60 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
          <AlertCircle className="h-10 w-10 text-[var(--text-disabled)]" />
          <p className="text-[14px]">{tCommon("notFound")}</p>
          <Link
            href="/pool"
            className="text-[12px] text-[var(--primary)] hover:underline"
          >
            {t("backToPool")}
          </Link>
        </div>
      ) : (
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-4 py-4 pb-28">
          {/* 服務地址 */}
          <section className="flex flex-col gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--text-secondary)]">
              <MapPin className="h-3.5 w-3.5" />
              {t("fieldAddress")}
            </span>
            <p className="text-[15px] font-semibold text-[var(--text-primary)]">
              {wo.address}
            </p>
            <span className="text-[12px] text-[var(--text-secondary)]">
              {wo.district}
            </span>
          </section>

          {/* 設備與問題 */}
          <section className="flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
            <div className="flex flex-col gap-1">
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--text-secondary)]">
                <Wrench className="h-3.5 w-3.5" />
                {t("fieldDevice")}
              </span>
              <p className="text-[14px] text-[var(--text-primary)]">
                {device || "—"}
              </p>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[11px] font-medium text-[var(--text-secondary)]">
                {t("fieldProblem")}
              </span>
              <p className="text-[14px] text-[var(--text-primary)]">
                {problem || "—"}
              </p>
            </div>
            {door && (
              <div className="flex flex-col gap-1">
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--text-secondary)]">
                  <DoorOpen className="h-3.5 w-3.5" />
                  {t("fieldDoor")}
                </span>
                <p className="text-[14px] text-[var(--text-primary)]">{door}</p>
              </div>
            )}
          </section>

          {/* 報酬與時間 */}
          <section className="flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-[var(--text-secondary)]">
                {t("fieldReward")}
              </span>
              <span className="text-[16px] font-bold text-[#059669]">
                {wo.estimated_reward
                  ? t("estimatedReward", { amount: wo.estimated_reward })
                  : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between text-[12px] text-[var(--text-secondary)]">
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {t("fieldCreated")}
              </span>
              <span>{formatRelative(wo.created_at)}</span>
            </div>
            {wo.scheduled_time && (
              <div className="flex items-center justify-between text-[12px] text-[var(--text-secondary)]">
                <span>{t("fieldScheduled")}</span>
                <span>{wo.scheduled_time}</span>
              </div>
            )}
          </section>

          <p className="px-1 text-[12px] text-[var(--text-disabled)]">
            {t("privacyNote")}
          </p>

          {/* 底部固定接單列 */}
          <div className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--border)] bg-[var(--bg-surface)]/95 px-4 py-3 backdrop-blur md:pl-[calc(var(--tech-sidebar-w,240px)+1rem)]">
            <div className="mx-auto max-w-2xl">
              {acceptable && !conflict ? (
                <button
                  type="button"
                  onClick={() => setConfirmOpen(true)}
                  disabled={accepting}
                  className="h-12 w-full rounded-full bg-[var(--primary)] text-[15px] font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-60"
                >
                  {t("accept")}
                </button>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <p className="text-[13px] text-[var(--text-secondary)]">
                    {t("detailUnavailable")}
                  </p>
                  <Link
                    href="/pool"
                    className="text-[13px] font-medium text-[var(--primary)] hover:underline"
                  >
                    {t("backToPool")}
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* 接單二次確認視窗 */}
          <Modal open={confirmOpen} onOpenChange={setConfirmOpen}>
            <ModalContent size="sm">
              <ModalHeader>
                <ModalTitle>{t("confirmTitle")}</ModalTitle>
                <ModalDescription>{t("confirmDesc")}</ModalDescription>
              </ModalHeader>
              <div className="flex flex-col gap-1 px-6 py-4 text-[13px] text-[var(--text-primary)]">
                <span className="font-semibold">{wo.address}</span>
                <span className="text-[var(--text-secondary)]">
                  {device}
                  {wo.estimated_reward
                    ? ` · ${t("estimatedReward", { amount: wo.estimated_reward })}`
                    : ""}
                </span>
              </div>
              <ModalFooter>
                <button
                  type="button"
                  onClick={() => setConfirmOpen(false)}
                  disabled={accepting}
                  className="h-10 rounded-full border border-[var(--border)] px-4 text-[14px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-60"
                >
                  {t("confirmCancel")}
                </button>
                <button
                  type="button"
                  onClick={confirmAccept}
                  disabled={accepting}
                  className="h-10 rounded-full bg-[var(--primary)] px-5 text-[14px] font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-60"
                >
                  {accepting ? t("accepting") : t("confirmAccept")}
                </button>
              </ModalFooter>
            </ModalContent>
          </Modal>
        </div>
      )}
    </TechShell>
  );
}
