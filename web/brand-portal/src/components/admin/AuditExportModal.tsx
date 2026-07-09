"use client";

import { useState } from "react";
import { Download } from "lucide-react";
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

/**
 * AuditExportModal — F-020 / E7x §4.2 P1 稽核日誌匯出 UI。
 *
 * 1. 接收上層稽核頁面當前已套用的篩選條件（read-only summary）
 * 2. 讓使用者選擇 CSV / JSON 格式
 * 3. 呼叫 POST /tenants/{tenantId}/audit/exports，取回 streaming blob
 * 4. 觸發瀏覽器下載，檔名 audit-events-YYYY-MM-DD-HHmm.{csv,json}
 *
 * 200 (text/csv | application/json) → 立即下載 + success toast
 * 202 (job_id) → toast 提示「資料量過大，已轉背景處理，完成後寄信」
 * 4xx/5xx → error toast
 */

export interface AuditExportFilters {
  /** OpenAPI log_type → 對應後端 event_types。空 = 不過濾。 */
  log_type?: string | null;
  /** 起始 / 結束時間（ISO 8601）。 */
  from?: string | null;
  to?: string | null;
  actor_id?: string | null;
  resource_type?: string | null;
}

export interface AuditExportModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  filters: AuditExportFilters;
  /** 將篩選條件 render 成人類可讀摘要（為了讓上層自由 i18n / label） */
  filterSummary?: React.ReactNode;
}

type ExportFormat = "csv" | "json";

export function AuditExportModal({
  open,
  onOpenChange,
  filters,
  filterSummary,
}: AuditExportModalProps) {
  const t = useTranslations("components.admin.auditExport");
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [submitting, setSubmitting] = useState(false);
  const { toast } = useToast();

  const FORMAT_LABEL: Record<ExportFormat, string> = {
    csv: t("formatLabel.csv"),
    json: t("formatLabel.json"),
  };

  async function handleExport() {
    setSubmitting(true);
    // OpenAPI body：log_type 在後端對應 event_types 陣列；前端只暴露單選，
    // 所以包成長度 1 陣列；空字串/null → 略過（後端視為不過濾）。
    const body: Record<string, unknown> = { format };
    if (filters.log_type) body.event_types = [filters.log_type];
    if (filters.from) body.from = filters.from;
    if (filters.to) body.to = filters.to;
    if (filters.actor_id) body.actor_id = filters.actor_id;
    if (filters.resource_type) body.resource_type = filters.resource_type;

    // CR-0002-α：遷至 tenant-scoped v2 端點（POST /tenants/{tenantId}/audit/exports）
    try {
      const { blob, filename } = await api.downloadPost(
        tenantPath("/audit/exports"),
        body,
      );
      // 後端可能把 application/json 同時用於同步 JSON stream 與異步 202 job
      // 回應，靠 blob 的 size 與 type 區分太脆弱 — 改靠下載成功事實本身：
      // 若 filename 為 download（後端沒給 content-disposition）通常就是 job
      // 200 路徑會回 .csv / .json filename。
      if (blob.size === 0) {
        toast({
          title: t("toast.failTitle"),
          description: t("toast.emptyBody"),
          variant: "error",
        });
        return;
      }
      api.triggerDownload(blob, filename);
      toast({
        title: t("toast.successTitle"),
        description: filename,
        variant: "success",
      });
      onOpenChange(false);
    } catch (e) {
      toast({ title: t("toast.failTitle"), description: friendlyError(e), variant: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent size="md">
        <ModalHeader>
          <ModalTitle>{t("title")}</ModalTitle>
          <ModalDescription>{t("description")}</ModalDescription>
        </ModalHeader>

        <div className="flex flex-col gap-4 px-6 py-4">
          <section>
            <h3 className="mb-2 text-[13px] font-semibold text-[var(--text-secondary)]">
              {t("useCurrentFilters")}
            </h3>
            <div className="rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-[13px] text-[var(--text-primary)]">
              {filterSummary ?? <DefaultFilterSummary filters={filters} />}
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-[13px] font-semibold text-[var(--text-secondary)]">
              {t("format")}
            </h3>
            <div className="flex gap-4">
              {(["csv", "json"] as ExportFormat[]).map((opt) => (
                <label
                  key={opt}
                  className="flex cursor-pointer items-center gap-2 text-[13px] text-[var(--text-primary)]"
                >
                  <input
                    type="radio"
                    name="audit-export-format"
                    value={opt}
                    checked={format === opt}
                    onChange={() => setFormat(opt)}
                    className="h-4 w-4 accent-[var(--primary)]"
                  />
                  {FORMAT_LABEL[opt]}
                </label>
              ))}
            </div>
          </section>
        </div>

        <ModalFooter>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
            className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("actions.cancel")}
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {submitting ? t("actions.exporting") : t("actions.export")}
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

function DefaultFilterSummary({ filters }: { filters: AuditExportFilters }) {
  const t = useTranslations("components.admin.auditExport");
  const items: { label: string; value: string }[] = [];
  if (filters.log_type) items.push({ label: t("filters.logType"), value: filters.log_type });
  if (filters.from) items.push({ label: t("filters.from"), value: filters.from });
  if (filters.to) items.push({ label: t("filters.to"), value: filters.to });
  if (filters.actor_id) items.push({ label: t("filters.actor"), value: filters.actor_id });
  if (filters.resource_type)
    items.push({ label: t("filters.resourceType"), value: filters.resource_type });

  if (items.length === 0) {
    return (
      <span className="text-[var(--text-secondary)]">{t("filters.none")}</span>
    );
  }
  return (
    <ul className="flex flex-col gap-1">
      {items.map((it) => (
        <li key={it.label} className="flex gap-2">
          <span className="min-w-[72px] text-[var(--text-secondary)]">{it.label}</span>
          <span className="font-['IBM_Plex_Mono'] text-[12px]">{it.value}</span>
        </li>
      ))}
    </ul>
  );
}
