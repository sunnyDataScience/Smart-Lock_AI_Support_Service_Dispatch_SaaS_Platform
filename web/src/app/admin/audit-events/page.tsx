"use client";

import { useState } from "react";
import {
  FileDown,
  Calendar,
  Search,
  ChevronDown,
  ChevronRight,
  Copy,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";

type EventType =
  | "使用者操作"
  | "系統事件"
  | "資料變更"
  | "權限變更"
  | "登入登出"
  | "API呼叫"
  | "錯誤事件";

const eventBadgeStyles: Record<EventType, { bg: string; text: string }> = {
  使用者操作: { bg: "#DBEAFE", text: "#2563EB" },
  系統事件: { bg: "#F1F5F9", text: "#64748B" },
  資料變更: { bg: "#DCFCE7", text: "#16A34A" },
  權限變更: { bg: "#EDE9FE", text: "#7C3AED" },
  登入登出: { bg: "#CFFAFE", text: "#0891B2" },
  API呼叫: { bg: "#E0E7FF", text: "#4F46E5" },
  錯誤事件: { bg: "#FEE2E2", text: "#DC2626" },
};

interface AuditRow {
  timestamp: string;
  eventType: EventType;
  operatorName: string;
  operatorRole: string;
  resource: string;
  action: string;
  isError?: boolean;
  expandedPayload?: object;
  expandedMeta?: { ip: string; browser: string };
}

const auditRows: AuditRow[] = [
  {
    timestamp: "2026/04/22 14:32:18",
    eventType: "使用者操作",
    operatorName: "王小明",
    operatorRole: "系統管理員",
    resource: "門鎖 A-201（2F 會議室）",
    action: "create",
  },
  {
    timestamp: "2026/04/22 14:28:05",
    eventType: "系統事件",
    operatorName: "系統排程",
    operatorRole: "自動化",
    resource: "韌體更新排程 v2.4.1",
    action: "update",
    expandedPayload: {
      event: "firmware.schedule.update",
      target: "lock-group-floor-2",
      version: "2.4.1",
      scheduledAt: "2026-04-22T14:30:00Z",
      affectedDevices: 12,
      status: "pending",
    },
    expandedMeta: {
      ip: "192.168.1.100",
      browser: "Chrome 124.0 / Windows 11",
    },
  },
  {
    timestamp: "2026/04/22 14:15:42",
    eventType: "資料變更",
    operatorName: "李美華",
    operatorRole: "設備管理員",
    resource: "門鎖 B-105（1F 大門）",
    action: "update",
  },
  {
    timestamp: "2026/04/22 13:58:30",
    eventType: "權限變更",
    operatorName: "王小明",
    operatorRole: "系統管理員",
    resource: "使用者 陳志偉",
    action: "update",
  },
  {
    timestamp: "2026/04/22 13:45:11",
    eventType: "登入登出",
    operatorName: "張雅婷",
    operatorRole: "一般使用者",
    resource: "管理後台",
    action: "login",
  },
  {
    timestamp: "2026/04/22 13:30:55",
    eventType: "API呼叫",
    operatorName: "外部系統",
    operatorRole: "API 金鑰 #47",
    resource: "/api/v2/locks/status",
    action: "read",
  },
  {
    timestamp: "2026/04/22 13:22:08",
    eventType: "錯誤事件",
    operatorName: "系統排程",
    operatorRole: "自動化",
    resource: "門鎖 C-301 連線逾時",
    action: "read",
    isError: true,
  },
  {
    timestamp: "2026/04/22 13:10:33",
    eventType: "使用者操作",
    operatorName: "陳志偉",
    operatorRole: "設備管理員",
    resource: "存取群組「訪客」",
    action: "delete",
  },
];

const columns = [
  { label: "時間戳", width: "w-[160px]" },
  { label: "事件類型", width: "w-[110px]" },
  { label: "操作者", width: "w-[140px]" },
  { label: "被操作資源", width: "flex-1" },
  { label: "動作", width: "w-[80px]" },
  { label: "", width: "w-8" },
];

function EventBadge({ type }: { type: EventType }) {
  const style = eventBadgeStyles[type];
  return (
    <span
      className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
      style={{ backgroundColor: style.bg, color: style.text }}
    >
      {type}
    </span>
  );
}

function ExpandedContent({
  payload,
  meta,
}: {
  payload: object;
  meta: { ip: string; browser: string };
}) {
  const jsonStr = JSON.stringify(payload, null, 2);

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
      <div className="flex items-center gap-6">
        <span className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-secondary)]">
          IP: {meta.ip}
        </span>
        <span className="text-xs text-[var(--text-secondary)]">
          {meta.browser}
        </span>
        <button className="flex items-center gap-[6px] rounded px-[10px] py-1">
          <Copy className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
          <span className="text-xs font-medium text-[var(--text-secondary)]">
            Copy JSON
          </span>
        </button>
      </div>
    </div>
  );
}

export default function AuditEventsPage() {
  const [expandedRow, setExpandedRow] = useState<number | null>(1);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              稽核日誌
            </h1>
            <button className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2">
              <FileDown className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-sm font-medium text-[var(--text-secondary)]">
                匯出日誌
              </span>
            </button>
          </div>

          {/* Filter Bar */}
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
              <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">
                2026/04/15 - 2026/04/22
              </span>
            </button>

            <div className="flex flex-1 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
              <Search className="h-4 w-4 text-[var(--text-disabled)]" />
              <span className="text-[13px] text-[var(--text-disabled)]">
                搜尋操作者、資源或動作...
              </span>
            </div>

            <button className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                事件類型
              </span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>

            <button className="rounded-md px-3 py-2">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                清除篩選
              </span>
            </button>
          </div>

          {/* Record Count */}
          <span className="text-[13px] text-[var(--text-secondary)]">
            共 1,247 筆紀錄
          </span>

          {/* Audit Table */}
          <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            {/* Table Header */}
            <div className="flex items-center bg-[#F8FAFC] px-4" style={{ height: 44 }}>
              {columns.map((col) => (
                <div key={col.label || "arrow"} className={`flex h-full items-center ${col.width}`}>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.label}
                  </span>
                </div>
              ))}
            </div>

            {/* Table Rows */}
            {auditRows.map((row, idx) => {
              const isExpanded = expandedRow === idx;
              const isDeleteAction = row.action === "delete";

              return (
                <div key={idx}>
                  <div
                    className={`flex cursor-pointer items-center border-t px-4 ${
                      row.isError
                        ? "border-l-4 border-l-[#EF4444] border-t-transparent bg-[#FEF2F2] pl-3"
                        : "border-t-[var(--border)]"
                    } ${isExpanded ? "bg-[#FAFBFC]" : ""}`}
                    style={{ height: 48 }}
                    onClick={() => setExpandedRow(isExpanded ? null : idx)}
                  >
                    {/* Timestamp */}
                    <div className="flex h-full w-[160px] items-center">
                      <span className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-primary)]">
                        {row.timestamp}
                      </span>
                    </div>

                    {/* Event Type */}
                    <div className="flex h-full w-[110px] items-center">
                      <EventBadge type={row.eventType} />
                    </div>

                    {/* Operator */}
                    <div className="flex h-full w-[140px] flex-col justify-center">
                      <span className="text-[13px] font-medium text-[var(--text-primary)]">
                        {row.operatorName}
                      </span>
                      <span className="text-[11px] text-[var(--text-secondary)]">
                        {row.operatorRole}
                      </span>
                    </div>

                    {/* Resource */}
                    <div className="flex h-full flex-1 items-center">
                      <span
                        className="text-[13px]"
                        style={{
                          color: row.isError ? "#DC2626" : "var(--text-primary)",
                        }}
                      >
                        {row.resource}
                      </span>
                    </div>

                    {/* Action */}
                    <div className="flex h-full w-[80px] items-center">
                      <span
                        className="font-['IBM_Plex_Mono'] text-xs"
                        style={{
                          color: isDeleteAction ? "#DC2626" : "var(--text-primary)",
                        }}
                      >
                        {row.action}
                      </span>
                    </div>

                    {/* Arrow */}
                    <div className="flex h-full w-8 items-center justify-center">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-[var(--primary)]" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-[var(--text-disabled)]" />
                      )}
                    </div>
                  </div>

                  {/* Expanded Content */}
                  {isExpanded && row.expandedPayload && row.expandedMeta && (
                    <div className="border-t border-[var(--border)] bg-[#FAFBFC]">
                      <ExpandedContent
                        payload={row.expandedPayload}
                        meta={row.expandedMeta}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
