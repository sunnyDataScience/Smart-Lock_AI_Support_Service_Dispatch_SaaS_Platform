"use client";

import {
  Sparkles,
  ThumbsUp,
  ThumbsDown,
  Flag,
} from "lucide-react";

interface CustomerMessageProps {
  text: string;
  time: string;
  tag?: { label: string; color: string; bg: string };
  variant?: "primary" | "light";
}

function CustomerMessage({
  text,
  time,
  tag,
  variant = "primary",
}: CustomerMessageProps) {
  const bubbleClass =
    variant === "primary"
      ? "bg-[var(--primary)] text-white"
      : "bg-[var(--primary-light)] text-[#18181B]";

  return (
    <div className="flex w-full justify-end">
      <div className="flex flex-col items-end gap-1">
        <div className={`max-w-[522px] rounded-[16px_4px_16px_16px] px-4 py-3 ${bubbleClass}`}>
          <p className="text-[15px] leading-[1.5]">{text}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[#A1A1AA]">{time}</span>
          {tag && (
            <span
              className="rounded-md px-2 py-[2px] text-[11px] font-medium"
              style={{ color: tag.color, backgroundColor: tag.bg }}
            >
              {tag.label}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

interface AiMessageProps {
  text: string;
  time: string;
  thumbUpActive?: boolean;
  thumbDownActive?: boolean;
  flagged?: boolean;
  flagColor?: string;
}

function AiMessage({
  text,
  time,
  thumbUpActive = false,
  thumbDownActive = false,
  flagged = false,
  flagColor,
}: AiMessageProps) {
  return (
    <div className="flex w-full flex-col gap-[6px]">
      <div className="flex items-center gap-[6px]">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#EFF6FF]">
          <Sparkles className="h-[14px] w-[14px] text-[var(--primary)]" />
        </div>
        <span className="text-[12px] font-semibold text-[var(--primary)]">
          AI 助理
        </span>
      </div>
      <div className="flex flex-col gap-1">
        <div
          className={`overflow-hidden rounded-[4px_16px_16px_16px] border-[1.5px] border-[var(--border)] ${
            flagColor ? "flex" : ""
          }`}
        >
          {flagColor && (
            <div
              className="w-[2px] self-stretch"
              style={{ backgroundColor: flagColor }}
            />
          )}
          <div className="px-4 py-3">
            <p className="max-w-[490px] whitespace-pre-line text-[15px] leading-[1.5] text-[#18181B]">
              {text}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[12px] text-[#A1A1AA]">{time}</span>
          <div className="flex items-center gap-1">
            <ThumbsUp
              className={`h-4 w-4 ${
                thumbUpActive ? "text-[var(--success)]" : "text-[#D4D4D8]"
              }`}
            />
            <ThumbsDown
              className={`h-4 w-4 ${
                thumbDownActive ? "text-[var(--error)]" : "text-[#D4D4D8]"
              }`}
            />
            {flagged && (
              <Flag className="h-4 w-4 text-[var(--warning)]" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SystemMessage({ text }: { text: string }) {
  return (
    <div className="flex w-full justify-center">
      <div className="rounded-lg bg-[#F1F5F9] px-4 py-[6px]">
        <span className="text-[12px] text-[#71717A]">{text}</span>
      </div>
    </div>
  );
}

function DateSeparator({ date }: { date: string }) {
  return (
    <div className="flex w-full items-center gap-3">
      <div className="h-px flex-1 bg-[#D4D4D8]" />
      <span className="text-[12px] font-medium text-[#A1A1AA]">{date}</span>
      <div className="h-px flex-1 bg-[#D4D4D8]" />
    </div>
  );
}

export default function ChatTimeline() {
  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto bg-[var(--bg-page)] p-6">
      <DateSeparator date="2026年4月22日" />

      <CustomerMessage
        text="你好，我家的Yale YDM-4109電子鎖突然無法用密碼開門了，按鍵有反應但輸入密碼後不會解鎖。"
        time="14:23"
        tag={{ label: "原始", color: "#A1A1AA", bg: "#F1F5F9" }}
        variant="primary"
      />

      <AiMessage
        text={`您好！我了解您的Yale YDM-4109電子鎖遇到密碼無法解鎖的問題。請問：\n\n1. 這個問題是什麼時候開始的？\n2. 電池最後一次更換是什麼時候？\n3. 螢幕上是否有顯示任何錯誤代碼？\n\n這些資訊將幫助我更準確地判斷問題原因。`}
        time="14:23"
        thumbUpActive
      />

      <CustomerMessage
        text="大概兩天前開始的，電池上個月才換新的，螢幕有顯示一個鎖頭圖案。"
        time="14:25"
        tag={{ label: "已整理", color: "#2563EB", bg: "#EFF6FF" }}
        variant="light"
      />

      <SystemMessage text="AI 已收集足夠資訊，開始進行診斷分析" />

      <AiMessage
        text={`根據您提供的資訊，我的初步診斷如下：\n\n🔍 問題判斷：鎖體離合器故障\n📋 可能原因：離合器磨損導致密碼驗證通過但無法驅動鎖舌\n⚠️ 建議處理：需要技師現場更換離合器組件\n\n信心度：87%\n\n是否需要為您安排技師上門維修？`}
        time="14:26"
        thumbDownActive
        flagged
        flagColor="#F59E0B"
      />
    </div>
  );
}
