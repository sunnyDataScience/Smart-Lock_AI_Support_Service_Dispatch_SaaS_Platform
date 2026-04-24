"use client";

import Link from "next/link";
import SolidBadge from "@/components/ui/SolidBadge";

interface Conversation {
  id: string;
  customer: string;
  status: { label: string; color: string };
  channel: { label: string; color: string };
  time: string;
  lastMessage: string;
  isNew?: boolean;
}

const statusColors: Record<string, string> = {
  收集中: "#2563EB",
  處理中: "#F59E0B",
  待處理: "#94A3B8",
  已解決: "#10B981",
  已升級: "#EF4444",
};

const channelColors: Record<string, string> = {
  LINE: "#10B981",
  Web: "#2563EB",
};

const conversations: Conversation[] = [
  {
    id: "CONV-A8F3D21E",
    customer: "陳小姐",
    status: { label: "收集中", color: statusColors["收集中"] },
    channel: { label: "LINE", color: channelColors["LINE"] },
    time: "5 分鐘前",
    lastMessage: "您好，我家的Yale電子鎖無法正常開關...",
    isNew: true,
  },
  {
    id: "CONV-B7E2C19D",
    customer: "林先生",
    status: { label: "處理中", color: statusColors["處理中"] },
    channel: { label: "Web", color: channelColors["Web"] },
    time: "12 分鐘前",
    lastMessage: "AI已為您分析問題，建議更換電池...",
  },
  {
    id: "CONV-C6D1B08C",
    customer: "王太太",
    status: { label: "待處理", color: statusColors["待處理"] },
    channel: { label: "LINE", color: channelColors["LINE"] },
    time: "25 分鐘前",
    lastMessage: "密碼鎖一直嗶嗶叫，怎麼辦？",
  },
  {
    id: "CONV-D5C0A97B",
    customer: "張先生",
    status: { label: "已解決", color: statusColors["已解決"] },
    channel: { label: "Web", color: channelColors["Web"] },
    time: "1 小時前",
    lastMessage: "感謝您的協助，問題已解決",
  },
  {
    id: "CONV-E4B9986A",
    customer: "劉小姐",
    status: { label: "已升級", color: statusColors["已升級"] },
    channel: { label: "LINE", color: channelColors["LINE"] },
    time: "2 小時前",
    lastMessage: "已轉接人工客服處理...",
  },
  {
    id: "CONV-F3A8875B",
    customer: "黃先生",
    status: { label: "收集中", color: statusColors["收集中"] },
    channel: { label: "LINE", color: channelColors["LINE"] },
    time: "3 小時前",
    lastMessage: "我的Samsung電子鎖螢幕不亮...",
  },
  {
    id: "CONV-G2B7764C",
    customer: "李太太",
    status: { label: "已解決", color: statusColors["已解決"] },
    channel: { label: "Web", color: channelColors["Web"] },
    time: "昨天",
    lastMessage: "好的，謝謝回覆",
  },
  {
    id: "CONV-H1C6653D",
    customer: "趙先生",
    status: { label: "待處理", color: statusColors["待處理"] },
    channel: { label: "LINE", color: channelColors["LINE"] },
    time: "昨天",
    lastMessage: "請問Philips的鎖可以加裝指紋嗎？",
  },
];

const columns = [
  { key: "id", label: "對話編號", width: "w-[160px]" },
  { key: "customer", label: "客戶名稱", width: "w-[100px]" },
  { key: "status", label: "狀態", width: "w-[100px]" },
  { key: "channel", label: "頻道", width: "w-[80px]" },
  { key: "time", label: "建立時間", width: "w-[100px]" },
  { key: "lastMessage", label: "最後訊息預覽", width: "flex-1" },
] as const;

export default function ConversationsTable() {
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

      {conversations.map((conv, idx) => (
        <Link
          key={conv.id}
          href={`/conversations/${conv.id}`}
          className={`flex h-12 items-center border-b border-[var(--border)] px-4 hover:bg-[#EFF6FF] ${
            conv.isNew
              ? "bg-[var(--primary-light)]"
              : idx % 2 === 0
                ? "bg-[var(--bg-page)]"
                : "bg-white"
          }`}
        >
          <div className="flex w-[160px] items-center gap-2 px-2">
            {conv.isNew && (
              <div className="h-2 w-2 rounded-full bg-[var(--primary)]" />
            )}
            <span className="text-[13px] font-medium text-[#18181B]">
              {conv.id}
            </span>
          </div>
          <div className="w-[100px] px-2">
            <span className="text-[13px] text-[#18181B]">{conv.customer}</span>
          </div>
          <div className="w-[100px] px-2">
            <SolidBadge label={conv.status.label} color={conv.status.color} />
          </div>
          <div className="w-[80px] px-2">
            <SolidBadge label={conv.channel.label} color={conv.channel.color} />
          </div>
          <div className="w-[100px] px-2">
            <span className="text-[13px] text-[#71717A]">{conv.time}</span>
          </div>
          <div className="flex-1 px-2">
            <span className="text-[13px] text-[#71717A]">
              {conv.lastMessage}
            </span>
          </div>
        </Link>
      ))}

      <div className="flex h-[52px] items-center justify-between px-4">
        <span className="text-[13px] text-[#71717A]">
          顯示 1-20 筆，共 156 筆
        </span>
        <div className="flex gap-1">
          {["1", "2", "3", "...", "8"].map((page, i) => (
            <button
              key={i}
              className={`flex h-8 w-8 items-center justify-center rounded-md text-[13px] ${
                page === "1"
                  ? "bg-[var(--primary)] font-semibold text-white"
                  : "font-medium text-[#71717A]"
              }`}
            >
              {page}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
