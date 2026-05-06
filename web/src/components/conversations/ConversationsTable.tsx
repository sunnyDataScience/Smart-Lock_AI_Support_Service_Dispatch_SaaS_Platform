"use client";

import SolidBadge from "@/components/ui/SolidBadge";
import DataTable, { type ColumnDef } from "@/components/ui/DataTable";
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
  active: "var(--badge-info-fg)",
  waiting_human: "var(--badge-danger-fg)",
  closed: "var(--badge-success-fg)",
};

const RESOLUTION_LABEL: Record<string, string> = {
  case_library: "案例庫",
  rag: "RAG",
  human: "人工",
};

const columns: ColumnDef<Conversation>[] = [
  {
    key: "id",
    label: "對話編號",
    width: "w-[160px]",
    priority: "primary",
    cardLabel: "ID",
    render: (conv) => (
      <span className="font-mono text-[12px] text-[var(--text-primary)]">
        {conv.id.slice(0, 8)}
      </span>
    ),
  },
  {
    key: "customer",
    label: "客戶名稱",
    width: "w-[140px]",
    priority: "primary",
    cardLabel: "客戶",
    render: (conv) => (
      <div className="flex flex-col">
        <span className="text-[13px] font-medium text-[var(--text-primary)]">
          {conv.display_name || "—"}
        </span>
        {conv.line_user_id && (
          <span className="font-mono text-[11px] text-[var(--text-disabled)]">
            {conv.line_user_id.slice(0, 10)}
          </span>
        )}
      </div>
    ),
  },
  {
    key: "status",
    label: "狀態",
    width: "w-[100px]",
    priority: "secondary",
    render: (conv) => {
      const status = conv.status as ConversationStatus;
      return <SolidBadge label={STATUS_LABEL[status]} color={STATUS_COLOR[status]} />;
    },
  },
  {
    key: "messages",
    label: "訊息數",
    width: "w-[80px]",
    priority: "secondary",
    cardLabel: "訊息數",
    render: (conv) => String(conv.message_count),
  },
  {
    key: "resolution",
    label: "解決層級",
    width: "w-[120px]",
    priority: "secondary",
    cardLabel: "解決層級",
    render: (conv) =>
      conv.resolution_layer ? RESOLUTION_LABEL[conv.resolution_layer] ?? "—" : "—",
  },
  {
    key: "time",
    label: "更新時間",
    width: "flex-1",
    priority: "secondary",
    cardLabel: "更新",
    render: (conv) => (
      <span className="text-[12px] text-[var(--text-tertiary)]">
        {formatRelative(conv.updated_at)}
      </span>
    ),
  },
];

interface Props {
  items: Conversation[];
  loading?: boolean;
}

export default function ConversationsTable({ items, loading = false }: Props) {
  return (
    <DataTable<Conversation>
      items={items}
      rowKey={(c) => c.id}
      columns={columns}
      loading={loading}
      rowHref={(c) => `/conversations/${c.id}`}
      emptyText="沒有符合條件的對話"
      ariaLabel="對話列表"
    />
  );
}
