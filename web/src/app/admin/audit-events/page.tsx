"use client";

import { useMemo, useState } from "react";
import { Check, ChevronDown, ChevronRight, Copy, Download } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { AuditExportModal } from "@/components/admin/AuditExportModal";
import { ApiError, resolveTenantId } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type AuditLogEntry = components["schemas"]["AuditLogEntry"];
type AuditLogType = components["schemas"]["AuditLogType"];

function formatAuditError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

const LOG_TYPE_BADGE: Record<AuditLogType, { bg: string; text: string }> = {
  api_call: { bg: "#E0E7FF", text: "#4F46E5" },
  llm_interaction: { bg: "#DBEAFE", text: "#2563EB" },
  rag_retrieval: { bg: "#DCFCE7", text: "#16A34A" },
  admin_action: { bg: "#EDE9FE", text: "#7C3AED" },
  agent_message: { bg: "#CFFAFE", text: "#0891B2" },
};

const LOG_TYPE_OPTIONS: AuditLogType[] = [
  "admin_action",
  "agent_message",
  "llm_interaction",
  "rag_retrieval",
  "api_call",
];

const PAGE_SIZE = 20;

const COLUMN_KEYS = [
  { key: "time", width: "w-[180px]" },
  { key: "logType", width: "w-[120px]" },
  { key: "actor", width: "w-[260px]" },
  { key: "action", width: "flex-1" },
  { key: "spacer", width: "w-8" },
] as const;

function LogTypeBadge({ type }: { type: AuditLogType }) {
  const t = useTranslations("admin.audit");
  const style = LOG_TYPE_BADGE[type];
  return (
    <span
      className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
      style={{ backgroundColor: style.bg, color: style.text }}
    >
      {t(`logType.${type}`)}
    </span>
  );
}

function ExpandedJson({ payload }: { payload: Record<string, unknown> | null | undefined }) {
  const t = useTranslations("admin.audit");
  const obj = payload ?? {};
  const jsonStr = JSON.stringify(obj, null, 2);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);

  const handleCopy = async () => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(jsonStr);
        setCopyError(false);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      } else {
        setCopyError(true);
        setTimeout(() => setCopyError(false), 1500);
      }
    } catch {
      setCopyError(true);
      setTimeout(() => setCopyError(false), 1500);
    }
  };

  return (
    <div className="flex flex-col gap-3 px-4 pb-4">
      <pre className="overflow-x-auto rounded-lg bg-[#0F172A] p-4 font-['IBM_Plex_Mono'] text-xs leading-relaxed">
        {jsonStr.split("\n").map((line, i) => {
          const isBrace = line.trim() === "{" || line.trim() === "}";
          return (
            <div key={i} style={{ color: isBrace ? "#94A3B8" : "#4ADE80" }}>
              {line}
            </div>
          );
        })}
      </pre>
      <div className="flex items-center gap-3">
        <button
          onClick={handleCopy}
          className={`flex items-center gap-[6px] rounded px-[10px] py-1 transition-colors ${
            copied
              ? "bg-green-50 text-green-700"
              : copyError
                ? "bg-red-50 text-red-700"
                : "hover:bg-[var(--bg-page)] text-[var(--text-secondary)]"
          }`}
        >
          {copied ? (
            <Check className="h-[14px] w-[14px]" />
          ) : (
            <Copy className="h-[14px] w-[14px]" />
          )}
          <span className="text-xs font-medium">
            {copied ? t("json.copied") : copyError ? t("json.copyFailed") : t("json.copy")}
          </span>
        </button>
      </div>
    </div>
  );
}

function useFormatActor() {
  const t = useTranslations("admin.audit");
  return useMemo(
    () =>
      (actorId: string | null | undefined): { name: string; subtitle: string } => {
        if (!actorId) return { name: t("actor.system"), subtitle: "system" };
        return { name: t("actor.admin"), subtitle: actorId.slice(0, 8) };
      },
    [t],
  );
}

export default function AuditEventsPage() {
  const t = useTranslations("admin.audit");
  const tc = useTranslations("admin.common");
  const formatActor = useFormatActor();
  const [logType, setLogType] = useState<AuditLogType | "">("");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);

  const logTypeLabel = useMemo<Record<AuditLogType, string>>(
    () => ({
      api_call: t("logType.api_call"),
      llm_interaction: t("logType.llm_interaction"),
      rag_retrieval: t("logType.rag_retrieval"),
      admin_action: t("logType.admin_action"),
      agent_message: t("logType.agent_message"),
    }),
    [t],
  );

  // CR-0002-α：遷至 tenant-scoped v2 端點（GET /tenants/{tenantId}/audit/events）
  const tenantId = resolveTenantId();
  const auditEventsPath = `/tenants/${encodeURIComponent(tenantId)}/audit/events`;

  const { items, cursor, hasMore, loading, error, loadMore } = usePaginatedFetch<AuditLogEntry>({
    path: auditEventsPath,
    pageSize: PAGE_SIZE,
    query: logType ? { log_type: logType } : undefined,
    queryKey: `logType=${logType}&tenant=${tenantId}`,
    formatError: formatAuditError,
  });

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {t("title")}
            </h1>
            <button
              type="button"
              onClick={() => setExportOpen(true)}
              className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              {t("export")}
            </button>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {t("filterLabel")}
              </span>
              <select
                value={logType}
                onChange={(e) => {
                  setLogType(e.target.value as AuditLogType | "");
                  setExpandedRow(null);
                }}
                className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
              >
                <option value="">{tc("all")}</option>
                {LOG_TYPE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {logTypeLabel[opt]}
                  </option>
                ))}
              </select>
            </div>

            {logType && (
              <button
                onClick={() => setLogType("")}
                className="rounded-md px-3 py-2"
              >
                <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                  {tc("clearFilter")}
                </span>
              </button>
            )}

            <span className="ml-auto text-[13px] text-[var(--text-secondary)]">
              {loading
                ? tc("loading")
                : hasMore
                  ? tc("totalCountMore", { count: items.length })
                  : tc("totalCount", { count: items.length })}
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center bg-[#F8FAFC] px-4" style={{ height: 44 }}>
              {COLUMN_KEYS.map((col) => (
                <div key={col.key} className={`flex h-full items-center ${col.width}`}>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.key === "spacer" ? "" : t(`cols.${col.key}`)}
                  </span>
                </div>
              ))}
            </div>

            {items.length === 0 && !loading && (
              <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                {t("empty")}
              </div>
            )}

            {items.map((row) => {
              const isExpanded = expandedRow === row.id;
              const actor = formatActor(row.actor_id);
              return (
                <div key={row.id}>
                  <div
                    className={`flex cursor-pointer items-center border-t border-t-[var(--border)] px-4 ${
                      isExpanded ? "bg-[#FAFBFC]" : ""
                    }`}
                    style={{ height: 48 }}
                    onClick={() => setExpandedRow(isExpanded ? null : row.id)}
                  >
                    <div className="flex h-full w-[180px] items-center">
                      <span className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-primary)]">
                        {formatRelative(row.created_at)}
                      </span>
                    </div>

                    <div className="flex h-full w-[120px] items-center">
                      <LogTypeBadge type={row.log_type} />
                    </div>

                    <div className="flex h-full w-[260px] flex-col justify-center">
                      <span className="text-[13px] font-medium text-[var(--text-primary)]">
                        {actor.name}
                      </span>
                      <span className="font-['IBM_Plex_Mono'] text-[11px] text-[var(--text-secondary)]">
                        {actor.subtitle}
                      </span>
                    </div>

                    <div className="flex h-full flex-1 items-center">
                      <span className="font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-primary)]">
                        {row.action}
                      </span>
                    </div>

                    <div className="flex h-full w-8 items-center justify-center">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-[var(--primary)]" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-[var(--text-disabled)]" />
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-[var(--border)] bg-[#FAFBFC]">
                      <ExpandedJson payload={row.details} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {hasMore && (
            <div className="flex justify-center pt-2">
              <button
                disabled={loading}
                onClick={loadMore}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? tc("loading") : tc("loadMore")}
              </button>
            </div>
          )}
        </div>
      </div>

      <AuditExportModal
        open={exportOpen}
        onOpenChange={setExportOpen}
        filters={{ log_type: logType || null }}
      />
    </div>
  );
}
