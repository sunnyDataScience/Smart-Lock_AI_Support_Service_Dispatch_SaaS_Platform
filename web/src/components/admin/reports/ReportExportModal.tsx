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
import { ApiError, api } from "@/lib/api";

/**
 * ReportExportModal — E7x §4.2 P1 報表匯出 UI（KPI / 營收 / 技師排行 / 結算）。
 *
 * 對應 BE GET /api/v1/reports/export（operationId: exportReport），role gate
 * admin / operations_manager / accountant。CSV 路徑串流下載；PDF 在後端目前
 * 一律 422（缺 reportlab/weasyprint dep），本 modal 僅暴露 CSV。
 *
 * 注意：accounting report_type 在 BE/openapi spec 目前 **未列入 enum**
 *   （僅 kpi/revenue/technician_ranking）。仍保留 type 以利未來擴充；
 *   呼叫時 BE 會回 422，使用者會看到對應的 error toast。
 */

export type ReportType = "kpi" | "revenue" | "technician_ranking" | "accounting";

const REPORT_LABELS: Record<ReportType, { title: string; description: string }> = {
  kpi: {
    title: "匯出 KPI 報表",
    description: "依當前期間（today / 7d / 30d / 90d）匯出 CSV。",
  },
  revenue: {
    title: "匯出營收報表",
    description: "依當前日期範圍與品牌切片匯出 CSV。",
  },
  technician_ranking: {
    title: "匯出技師排行報表",
    description: "依當前日期範圍匯出技師排行 CSV。",
  },
  accounting: {
    title: "匯出結算報表",
    description: "依當前期間匯出結算 CSV（後端 endpoint 待 V1.1 補上）。",
  },
};

export type ReportExportFilters = Record<
  string,
  string | number | boolean | undefined | null
>;

export interface ReportExportModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reportType: ReportType;
  /** 由父頁面傳入的當前 filter（例如 period / from / to / brand），會帶到 query string。 */
  filters: ReportExportFilters;
  /** 自訂 filter 摘要 render；未傳則用 DefaultFilterSummary。 */
  filterSummary?: React.ReactNode;
}

export function ReportExportModal({
  open,
  onOpenChange,
  reportType,
  filters,
  filterSummary,
}: ReportExportModalProps) {
  const [submitting, setSubmitting] = useState(false);
  const { toast } = useToast();

  async function handleExport() {
    setSubmitting(true);
    // 組 query — 過濾掉 undefined/null/空字串，後端視為「不過濾」
    const query: Record<string, string> = {
      report_type: reportType,
      format: "csv",
    };
    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) continue;
      const str = String(value);
      if (str.length === 0) continue;
      query[key] = str;
    }

    const today = new Date().toISOString().slice(0, 10);
    const filename = `${reportType}-${today}.csv`;

    try {
      await api.download("/api/v1/reports/export", { query, filename });
      toast({
        title: "匯出完成",
        description: filename,
        variant: "success",
      });
      onOpenChange(false);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e);
      toast({ title: "匯出失敗", description: msg, variant: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  const label = REPORT_LABELS[reportType];

  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent size="md">
        <ModalHeader>
          <ModalTitle>{label.title}</ModalTitle>
          <ModalDescription>{label.description}</ModalDescription>
        </ModalHeader>

        <div className="flex flex-col gap-4 px-6 py-4">
          <section>
            <h3 className="mb-2 text-[13px] font-semibold text-[var(--text-secondary)]">
              使用目前篩選條件
            </h3>
            <div className="rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-[13px] text-[var(--text-primary)]">
              {filterSummary ?? <DefaultFilterSummary filters={filters} />}
            </div>
          </section>

          <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-[12px] text-blue-900">
            <strong>格式：</strong>CSV（PDF 暫不支援，將於 V1.1 補上）
          </div>
        </div>

        <ModalFooter>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
            className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {submitting ? "匯出中…" : "開始匯出"}
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

function DefaultFilterSummary({ filters }: { filters: ReportExportFilters }) {
  const items = Object.entries(filters)
    .filter(([, v]) => v !== undefined && v !== null && String(v).length > 0)
    .map(([k, v]) => ({ label: k, value: String(v) }));

  if (items.length === 0) {
    return (
      <span className="text-[var(--text-secondary)]">
        無篩選條件 — 將匯出全部
      </span>
    );
  }
  return (
    <ul className="flex flex-col gap-1">
      {items.map((it) => (
        <li key={it.label} className="flex gap-2">
          <span className="min-w-[72px] text-[var(--text-secondary)]">
            {it.label}
          </span>
          <span className="font-['IBM_Plex_Mono'] text-[12px]">{it.value}</span>
        </li>
      ))}
    </ul>
  );
}
