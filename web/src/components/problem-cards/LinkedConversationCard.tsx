"use client";

import { ChevronDown } from "lucide-react";

interface Message {
  type: "user" | "ai" | "system";
  text: string;
  time?: string;
  width?: number;
}

const messages: Message[] = [
  {
    type: "user",
    text: "你好，我的Yale YDM-4109電子鎖突然無法用密碼開門了，按鍵有反應但輸入密碼後不會開鎖。",
    time: "14:23",
    width: 320,
  },
  {
    type: "ai",
    text: "您好！我了解您的Yale YDM-4109遇到密碼無法解鎖的問題。請問螢幕上是否顯示任何錯誤代碼？另外電池最後一次更換是什麼時候？",
    time: "14:24 · AI 助理",
    width: 320,
  },
  {
    type: "user",
    text: "螢幕顯示錯誤代碼E3，電池上個月剛換新的。",
    time: "14:25",
    width: 280,
  },
  {
    type: "ai",
    text: "感謝您提供的資訊。錯誤代碼E3通常表示離合器模組問題。結合您的狀況，初步判斷可能是離合器齒輪磨損導致傳動力不足。建議安排技師現場檢修。",
    time: "14:26 · AI 助理 · 信心度 78%",
    width: 320,
  },
  {
    type: "system",
    text: "系統：已將此對話升級至 L3 派工處理",
  },
];

function UserMessage({ msg }: { msg: Message }) {
  return (
    <div className="flex w-full justify-end">
      <div
        className="flex flex-col gap-[6px] rounded-bl-xl rounded-br-xl rounded-tl-xl rounded-tr bg-[#EFF6FF] px-[14px] py-[10px]"
        style={{ maxWidth: msg.width }}
      >
        <span className="text-[13px] text-[var(--text-primary)]">
          {msg.text}
        </span>
        <span className="text-right text-[11px] text-[var(--text-secondary)]">
          {msg.time}
        </span>
      </div>
    </div>
  );
}

function AiMessage({ msg }: { msg: Message }) {
  return (
    <div className="flex gap-2">
      <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-[14px] bg-[#2563EB]">
        <span className="text-[11px] font-bold text-white">AI</span>
      </div>
      <div
        className="flex flex-col gap-[6px] rounded-bl-xl rounded-br-xl rounded-tl rounded-tr-xl bg-[#F8FAFC] px-[14px] py-[10px]"
        style={{ maxWidth: msg.width }}
      >
        <span className="text-[13px] text-[var(--text-primary)]">
          {msg.text}
        </span>
        <span className="text-[11px] text-[var(--text-secondary)]">
          {msg.time}
        </span>
      </div>
    </div>
  );
}

function SystemMessage({ msg }: { msg: Message }) {
  return (
    <div className="flex w-full justify-center">
      <span className="text-[12px] italic text-[var(--text-disabled)]">
        {msg.text}
      </span>
    </div>
  );
}

export default function LinkedConversationCard() {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2">
          <ChevronDown className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
          <span className="text-[15px] font-semibold text-[var(--text-primary)]">
            關聯對話紀錄（12 則訊息）
          </span>
        </div>
        <span className="text-[13px] font-medium text-[#2563EB]">
          在對話管理中檢視完整紀錄 →
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex flex-col gap-4 px-6 py-5">
        <p className="text-center text-[12px] text-[var(--text-secondary)]">
          2026年4月22日 14:23
        </p>

        {messages.map((msg, i) => {
          if (msg.type === "user") return <UserMessage key={i} msg={msg} />;
          if (msg.type === "ai") return <AiMessage key={i} msg={msg} />;
          return <SystemMessage key={i} msg={msg} />;
        })}
      </div>
    </div>
  );
}
