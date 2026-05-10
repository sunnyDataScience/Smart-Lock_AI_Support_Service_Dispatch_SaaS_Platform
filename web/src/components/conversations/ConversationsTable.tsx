"use client";

import { useMemo } from "react";
import SolidBadge from "@/components/ui/SolidBadge";
import DataTable, { type ColumnDef } from "@/components/ui/DataTable";
import { formatRelative } from "@/lib/format";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type Conversation = components["schemas"]["Conversation"];
type ConversationStatus = components["schemas"]["ConversationStatus"];

const STATUS_COLOR: Record<ConversationStatus, string> = {
  active: "var(--badge-info-fg)",
  waiting_human: "var(--badge-danger-fg)",
  closed: "var(--badge-success-fg)",
};

interface Props {
  items: Conversation[];
  loading?: boolean;
}

export default function ConversationsTable({ items, loading = false }: Props) {
  const tCols = useTranslations("tables.conversations.cols");
  const tTable = useTranslations("tables.conversations");
  const tStatus = useTranslations("conversationStatus");
  const tResolution = useTranslations("resolutionLayer");

  const columns = useMemo<ColumnDef<Conversation>[]>(
    () => [
      {
        key: "id",
        label: tCols("id"),
        width: "w-[160px]",
        priority: "primary",
        cardLabel: tCols("idCard"),
        render: (conv) => (
          <span className="font-mono text-[12px] text-[var(--text-primary)]">
            {conv.id.slice(0, 8)}
          </span>
        ),
      },
      {
        key: "customer",
        label: tCols("customer"),
        width: "w-[140px]",
        priority: "primary",
        cardLabel: tCols("customerCard"),
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
        label: tCols("status"),
        width: "w-[100px]",
        priority: "secondary",
        render: (conv) => {
          const status = conv.status as ConversationStatus;
          return <SolidBadge label={tStatus(status)} color={STATUS_COLOR[status]} />;
        },
      },
      {
        key: "messages",
        label: tCols("messages"),
        width: "w-[80px]",
        priority: "secondary",
        cardLabel: tCols("messages"),
        render: (conv) => String(conv.message_count),
      },
      {
        key: "resolution",
        label: tCols("resolution"),
        width: "w-[120px]",
        priority: "secondary",
        cardLabel: tCols("resolution"),
        render: (conv) =>
          conv.resolution_layer
            ? (tResolution(conv.resolution_layer) ?? "—")
            : "—",
      },
      {
        key: "time",
        label: tCols("time"),
        width: "flex-1",
        priority: "secondary",
        cardLabel: tCols("timeCard"),
        render: (conv) => (
          <span className="text-[12px] text-[var(--text-tertiary)]">
            {formatRelative(conv.updated_at)}
          </span>
        ),
      },
    ],
    [tCols, tStatus, tResolution],
  );

  return (
    <DataTable<Conversation>
      items={items}
      rowKey={(c) => c.id}
      columns={columns}
      loading={loading}
      rowHref={(c) => `/conversations/${c.id}`}
      emptyText={tTable("empty")}
      ariaLabel={tTable("ariaLabel")}
    />
  );
}
