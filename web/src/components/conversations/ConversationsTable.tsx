"use client";

import Link from "next/link";
import SolidBadge from "@/components/ui/SolidBadge";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type Conversation = components["schemas"]["Conversation"];
type ConversationStatus = components["schemas"]["ConversationStatus"];

const STATUS_LABEL: Record<ConversationStatus, string> = {
  active: "進行中",
  waiting_human: "已升級",
  closed: "已結束",
};

const STATUS_COLOR: Record<ConversationStatus, string> = {
  active: "#2563EB",
  waiting_human: "#EF4444",
  closed: "#10B981",
};

const columns = [
  { key: "id", label: "對話編號", width: "w-[160px]" },
  { key: "customer", label: "客戶名稱", width: "w-[140px]" },
  { key: "status", label: "狀態", width: "w-[100px]" },
  { key: "messages", label: "訊息數", width: "w-[80px]" },
  { key: "resolution", label: "解決層級", width: "w-[120px]" },
  { key: "time", label: "更新時間", width: "flex-1" },
] as const;

const RESOLUTION_LABEL: Record<string, string> = {
  case_library: "案例庫",
  rag: "RAG",
  human: "人工",
};

interface Props {
  items: Conversation[];
  loading?: boolean;
}

export default function ConversationsTable({ items, loading = false }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center bg-[#F1F5F9] px-4">
        {columns.map((col) => (
          <div
            key={col.key}
            className={`flex items-center px-2 ${col.width}`}
          >
            <span className="text-[12px] font-semibold uppercase tracking-wider text-[#71717A]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {items.length === 0 && !loading && (
        <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
          沒有符合條件的對話
        </div>
      )}

      {items.map((conv, idx) => {
        const status = conv.status as ConversationStatus;
        const layer = conv.resolution_layer
          ? RESOLUTION_LABEL[conv.resolution_layer] ?? "—"
          : "—";
        return (
          <Link
            key={conv.id}
            href={`/conversations/${conv.id}`}
            className={`flex h-12 items-center border-b border-[var(--border)] px-4 hover:bg-[#EFF6FF] ${
              idx % 2 === 0 ? "bg-[var(--bg-page)]" : "bg-white"
            }`}
          >
            <div className="flex w-[160px] items-center px-2">
              <span className="font-mono text-[12px] text-[#18181B]">
                {conv.id.slice(0, 8)}
              </span>
            </div>
            <div className="flex w-[140px] flex-col px-2">
              <span className="text-[13px] font-medium text-[#18181B]">
                {conv.display_name || "—"}
              </span>
              <span className="font-mono text-[11px] text-[#A1A1AA]">
                {conv.line_user_id ? conv.line_user_id.slice(0, 10) : ""}
              </span>
            </div>
            <div className="w-[100px] px-2">
              <SolidBadge label={STATUS_LABEL[status]} color={STATUS_COLOR[status]} />
            </div>
            <div className="w-[80px] px-2">
              <span className="text-[13px] text-[#18181B]">
                {conv.message_count}
              </span>
            </div>
            <div className="w-[120px] px-2">
              <span className="text-[13px] text-[#71717A]">{layer}</span>
            </div>
            <div className="flex-1 px-2">
              <span className="text-[13px] text-[#71717A]">
                {formatRelative(conv.updated_at)}
              </span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
