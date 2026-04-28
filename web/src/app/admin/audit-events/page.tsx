"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, ChevronDown, ChevronRight, Copy } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type AuditLogEntry = components["schemas"]["AuditLogEntry"];
type AuditLogPage = components["schemas"]["AuditLogPage"];
type AuditLogType = components["schemas"]["AuditLogType"];

const LOG_TYPE_LABEL: Record<AuditLogType, string> = {
  api_call: "API 呼叫",
  llm_interaction: "LLM 互動",
  rag_retrieval: "RAG 檢索",
  admin_action: "管理操作",
  agent_message: "Agent 訊息",
};

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

const columns = [
  { label: "時間", width: "w-[180px]" },
  { label: "事件類型", width: "w-[120px]" },
  { label: "操作者", width: "w-[260px]" },
  { label: "動作", width: "flex-1" },
  { label: "", width: "w-8" },
];

function formatActor(actorId: string | null | undefined): { name: string; subtitle: string } {
  if (!actorId) return { name: "系統", subtitle: "system" };
  return { name: `Admin`, subtitle: actorId.slice(0, 8) };
}

function LogTypeBadge({ type }: { type: AuditLogType }) {
  const style = LOG_TYPE_BADGE[type];
  return (
    <span
      className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
      style={{ backgroundColor: style.bg, color: style.text }}
    >
      {LOG_TYPE_LABEL[type]}
    </span>
  );
}

function ExpandedJson({ payload }: { payload: Record<string, unknown> | null | undefined }) {
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
            {copied ? "已複製" : copyError ? "複製失敗" : "Copy JSON"}
          </span>
        </button>
      </div>
    </div>
  );
}

export default function AuditEventsPage() {
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logType, setLogType] = useState<AuditLogType | "">("");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const fetchPage = useCallback(
    async (afterCursor: string | null, append: boolean, filter: AuditLogType | "") => {
      setLoading(true);
      setError(null);
      try {
        const query: Record<string, string | number> = { limit: PAGE_SIZE };
        if (afterCursor) query.cursor = afterCursor;
        if (filter) query.log_type = filter;
        const res = await api.get<AuditLogPage>("/api/v1/audit-logs", { query });
        const newItems = res.items ?? [];
        setItems((prev) => (append ? [...prev, ...newItems] : newItems));
        setCursor(res.next_cursor ?? null);
        setHasMore(!!res.has_more);
      } catch (e) {
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    fetchPage(null, false, logType);
  }, [fetchPage, logType]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              稽核日誌
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                事件類型
              </span>
              <select
                value={logType}
                onChange={(e) => {
                  setLogType(e.target.value as AuditLogType | "");
                  setExpandedRow(null);
                }}
                className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
              >
                <option value="">全部</option>
                {LOG_TYPE_OPTIONS.map((t) => (
                  <option key={t} value={t}>
                    {LOG_TYPE_LABEL[t]}
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
                  清除篩選
                </span>
              </button>
            )}

            <span className="ml-auto text-[13px] text-[var(--text-secondary)]">
              {loading ? "載入中…" : `共 ${items.length} 筆${hasMore ? "+" : ""}`}
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center bg-[#F8FAFC] px-4" style={{ height: 44 }}>
              {columns.map((col, i) => (
                <div key={i} className={`flex h-full items-center ${col.width}`}>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.label}
                  </span>
                </div>
              ))}
            </div>

            {items.length === 0 && !loading && (
              <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                沒有符合條件的稽核紀錄
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
                onClick={() => fetchPage(cursor, true, logType)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? "載入中…" : "載入更多"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
