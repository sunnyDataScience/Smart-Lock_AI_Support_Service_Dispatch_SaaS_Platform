"use client";

/**
 * ScheduledReportsListModal — 已排程報表清單（UAT R3 G5-P3）
 *
 * 原排程功能 write-only（建立後無檢視/取消 UI）；後端 list / cancel 端點既有：
 *   GET    /tenants/{tid}/scheduled-reports          → { items: [...] }
 *   DELETE /tenants/{tid}/scheduled-reports/{id}     → is_active=false
 * 本 modal 補精簡清單＋逐筆取消。
 */

import { useCallback, useEffect, useState } from "react";
import {
  Modal,
  ModalContent,
  ModalDescription,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";

interface ScheduledReportItem {
  id: string;
  report_type: string;
  cadence: string;
  recipients: string[];
  format: string;
  next_run_at?: string | null;
  is_active?: boolean;
}

interface ListResponse {
  items?: ScheduledReportItem[];
}

export interface ScheduledReportsListModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const REPORT_TYPE_KEYS = new Set([
  "kpi",
  "revenue",
  "technician_ranking",
  "settlements",
]);
const CADENCE_KEYS = new Set(["weekly", "monthly", "quarterly"]);

function formatNextRun(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function ScheduledReportsListModal({
  open,
  onOpenChange,
}: ScheduledReportsListModalProps) {
  const t = useTranslations("components.admin.scheduledReports");
  const { toast } = useToast();
  const [items, setItems] = useState<ScheduledReportItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<ListResponse>(tenantPath("/scheduled-reports"), {
        query: { active_only: true },
      });
      setItems(res.items ?? []);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void fetchList();
  }, [open, fetchList]);

  async function cancelSchedule(item: ScheduledReportItem) {
    if (cancellingId) return;
    if (!window.confirm(t("cancelConfirm"))) return;
    setCancellingId(item.id);
    setError(null);
    try {
      await api.delete(
        tenantPath(`/scheduled-reports/${encodeURIComponent(item.id)}`),
      );
      setItems((prev) => prev.filter((x) => x.id !== item.id));
      toast({ variant: "success", title: t("cancelledToast") });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setCancellingId(null);
    }
  }

  const typeLabel = (v: string) =>
    REPORT_TYPE_KEYS.has(v) ? t(`reportTypes.${v}`) : v;
  const cadenceLabel = (v: string) =>
    CADENCE_KEYS.has(v) ? t(`cadence.${v}`) : v;

  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent size="md">
        <ModalHeader>
          <ModalTitle>{t("title")}</ModalTitle>
          <ModalDescription>{t("description")}</ModalDescription>
        </ModalHeader>

        <div className="px-6 py-4">
          {error && (
            <div className="mb-3 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {loading && items.length === 0 ? (
            <div className="flex h-24 items-center justify-center text-[13px] text-[var(--text-secondary)]">
              {t("loading")}
            </div>
          ) : items.length === 0 ? (
            <div className="flex h-24 items-center justify-center text-[13px] text-[var(--text-secondary)]">
              {t("empty")}
            </div>
          ) : (
            <ul className="flex flex-col divide-y divide-[var(--border)]">
              {items.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center justify-between gap-3 py-3"
                >
                  <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
                    <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                      {typeLabel(item.report_type)} ·{" "}
                      {cadenceLabel(item.cadence)} ·{" "}
                      {(item.format || "").toUpperCase()}
                    </span>
                    <span
                      className="truncate text-[12px] text-[var(--text-secondary)]"
                      title={(item.recipients ?? []).join(", ")}
                    >
                      {t("recipients", {
                        list: (item.recipients ?? []).join(", ") || "—",
                      })}
                    </span>
                    <span className="text-[11px] text-[var(--text-disabled)]">
                      {t("nextRun", { date: formatNextRun(item.next_run_at) })}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => cancelSchedule(item)}
                    disabled={cancellingId !== null}
                    className="shrink-0 rounded-md border border-red-200 bg-white px-3 py-[6px] text-[12px] font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    {cancellingId === item.id ? t("cancelling") : t("cancel")}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <ModalFooter>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
          >
            {t("close")}
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
