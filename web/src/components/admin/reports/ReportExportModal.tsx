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
 * admin / operations_manager / accountant。
 *
 * format：
 *   - csv → text/csv stream（行內 generator）
 *   - pdf → application/pdf（reportlab + STSong-Light，整檔）
 *
 * report_type=accounting：BE 透過 settlement_service.list_settlements 匯出
 * 結算列表（CSV 欄位含 settlement_id / technician / amount / status / paid_at）。
 */

export type ReportType = "kpi" | "revenue" | "technician_ranking" | "accounting";

const REPORT_LABELS: Record<ReportType, { title: string; description: string }> = {
  kpi: {
    title: "匯出 KPI 報表",
    description: "依當前期間（today / 7d / 30d / 90d）匯出 CSV / PDF。",
  },
  revenue: {
    title: "匯出營收報表",
    description: "依當前日期範圍與品牌切片匯出 CSV / PDF。",
  },
  technician_ranking: {
    title: "匯出技師排行報表",
    description: "依當前日期範圍匯出技師排行 CSV / PDF。",
  },
  accounting: {
    title: "匯出結算報表",
    description: "匯出結算列表（settlement / technician / amount / status）CSV / PDF。",
  },
};

type ExportFormat = "csv" | "pdf";

const FORMAT_LABEL: Record<ExportFormat, string> = {
  csv: "CSV（試算表）",
  pdf: "PDF（A4 列印）",
};

const FORMAT_CONTENT_TYPE: Record<ExportFormat, string> = {
  csv: "text/csv",
  pdf: "application/pdf",
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
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [submitting, setSubmitting] = useState(false);
  const { toast } = useToast();

  async function handleExport() {
    setSubmitting(true);
    // 組 query — 過濾掉 undefined/null/空字串，後端視為「不過濾」
    const query: Record<string, string> = {
      report_type: reportType,
      format,
    };
    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) continue;
      const str = String(value);
      if (str.length === 0) continue;
      query[key] = str;
    }

    const today = new Date().toISOString().slice(0, 10);
    const filename = `${reportType}-${today}.${format}`;

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

          <section>
            <h3 className="mb-2 text-[13px] font-semibold text-[var(--text-secondary)]">
              匯出格式
            </h3>
            <div className="flex gap-4">
              {(["csv", "pdf"] as ExportFormat[]).map((opt) => (
                <label
                  key={opt}
                  className="flex cursor-pointer items-center gap-2 text-[13px] text-[var(--text-primary)]"
                >
                  <input
                    type="radio"
                    name="report-export-format"
                    value={opt}
                    checked={format === opt}
                    onChange={() => setFormat(opt)}
                    className="h-4 w-4 accent-[var(--primary)]"
                  />
                  {FORMAT_LABEL[opt]}
                </label>
              ))}
            </div>
            <p className="mt-2 text-[12px] text-[var(--text-secondary)]">
              Content-Type：
              <span className="font-['IBM_Plex_Mono']">{FORMAT_CONTENT_TYPE[format]}</span>
            </p>
          </section>
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
