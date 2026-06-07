"use client";

/**
 * ScheduleReportModal — 通用排程報表 modal
 *
 * POST /tenants/{tid}/scheduled-reports
 *   body: { report_type, cadence, recipients, format, filters? }
 */

import { useState } from "react";
import {
  Modal,
  ModalContent,
  ModalDescription,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api, tenantPath } from "@/lib/api";

type ReportType = "kpi" | "revenue" | "technician_ranking" | "settlements";
type Cadence = "weekly" | "monthly" | "quarterly";
type Format = "csv" | "xlsx" | "pdf";

const REPORT_LABEL: Record<ReportType, string> = {
  kpi: "KPI 報表",
  revenue: "營收報表",
  technician_ranking: "技師排名",
  settlements: "結算報表",
};

export interface ScheduleReportModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reportType: ReportType;
  filters?: Record<string, unknown>;
  onSuccess?: () => void;
}

export default function ScheduleReportModal({
  open,
  onOpenChange,
  reportType,
  filters,
  onSuccess,
}: ScheduleReportModalProps) {
  const { toast } = useToast();
  const [cadence, setCadence] = useState<Cadence>("weekly");
  const [recipientsRaw, setRecipientsRaw] = useState("");
  const [format, setFormat] = useState<Format>("csv");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setCadence("weekly");
    setRecipientsRaw("");
    setFormat("csv");
    setError(null);
  }

  async function handleSubmit() {
    const recipients = recipientsRaw
      .split(/[,，;；\s]+/)
      .map((s) => s.trim())
      .filter((s) => /@/.test(s));
    if (recipients.length === 0) {
      setError("請至少填一個有效 email");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.post(tenantPath("/scheduled-reports"), {
        report_type: reportType,
        cadence,
        recipients,
        format,
        filters,
      });
      toast({
        variant: "success",
        title: "排程已建立",
        description: `${REPORT_LABEL[reportType]} (${cadence}, ${format})`,
      });
      reset();
      onOpenChange(false);
      onSuccess?.();
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <ModalContent size="md">
        <ModalHeader>
          <ModalTitle>排程 {REPORT_LABEL[reportType]}</ModalTitle>
          <ModalDescription>
            設定週/月/季定期 email 發送，cron 自動執行（roadmap）
          </ModalDescription>
        </ModalHeader>

        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              發送頻率
            </label>
            <select
              value={cadence}
              onChange={(e) => setCadence(e.target.value as Cadence)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              disabled={submitting}
            >
              <option value="weekly">每週</option>
              <option value="monthly">每月</option>
              <option value="quarterly">每季</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              收件人 Email <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={recipientsRaw}
              onChange={(e) => setRecipientsRaw(e.target.value)}
              placeholder="逗號或分號分隔多個 email"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              disabled={submitting}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              附件格式
            </label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value as Format)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              disabled={submitting}
            >
              <option value="csv">CSV</option>
              <option value="xlsx">Excel (XLSX)</option>
              <option value="pdf">PDF</option>
            </select>
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        <ModalFooter>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !recipientsRaw.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "建立中…" : "建立排程"}
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
