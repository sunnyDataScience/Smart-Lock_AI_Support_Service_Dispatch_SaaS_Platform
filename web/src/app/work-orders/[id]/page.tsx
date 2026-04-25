"use client";

import {
  ChevronLeft,
  Copy,
  FileText,
  ChevronUp,
  ChevronDown,
  ArrowRight,
  Images,
  Package,
  ExternalLink,
  Lock,
  ClipboardCheck,
  CircleCheck,
  CircleX,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import WorkOrderDetailSidebar from "@/components/work-orders/WorkOrderDetailSidebar";

/* ── SLA Timeline ─────────────────────────────── */

const slaNodes = [
  { label: "建立", time: "09:00", done: true },
  { label: "派工", time: "09:15", done: true },
  { label: "接受", time: "09:32", done: true },
  { label: "進行中", time: "10:45", active: true },
  { label: "完工" },
  { label: "確認" },
];

function SlaTimeline() {
  return (
    <div className="flex flex-col gap-2 rounded-lg bg-[var(--bg-page)] p-3">
      <div className="flex items-center justify-between">
        {slaNodes.map((n) => (
          <div key={n.label} className="flex flex-col items-center gap-1">
            {n.active ? (
              <div className="h-4 w-4 rounded-full border-[3px] border-[var(--primary)] bg-white" />
            ) : n.done ? (
              <div className="h-3 w-3 rounded-full bg-[var(--success)]" />
            ) : (
              <div className="h-3 w-3 rounded-full border-[1.5px] border-[#CBD5E1] bg-white" />
            )}
            <span
              className={`text-[11px] ${n.active ? "font-semibold text-[var(--primary)]" : "text-[var(--text-secondary)]"}`}
            >
              {n.label}
            </span>
            {n.time && (
              <span className="text-[10px] text-[var(--text-disabled)]">
                {n.time}
              </span>
            )}
          </div>
        ))}
        <span className="text-[14px] font-semibold text-[var(--warning)]">
          剩餘 02:15
        </span>
      </div>
      <div className="h-2 w-full rounded bg-[var(--border)]">
        <div className="h-2 w-[60%] rounded bg-[var(--primary)]" />
      </div>
    </div>
  );
}

/* ── Problem Card Summary ──────────────────────── */

const diagChain = [
  { label: "症狀", value: "指紋無法解鎖" },
  { label: "故障", value: "指紋模組失效" },
  { label: "失效模式", value: "感測器磨損" },
  { label: "缺陷", value: "模組老化" },
];

const domainAttrs = [
  [
    { label: "品牌", value: "Yale" },
    { label: "型號", value: "YDM-4109" },
  ],
  [
    { label: "安裝年份", value: "2024" },
    { label: "問題類型", value: "指紋模組故障" },
  ],
];

function ProblemCardSummary() {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <FileText className="h-5 w-5 text-[var(--primary)]" />
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          問題診斷摘要
        </span>
        <span className="rounded bg-[var(--primary-light)] px-2 py-1 text-[12px] text-[var(--primary)]">
          ProblemCard
        </span>
        <div className="flex-1" />
        <span className="text-[12px] text-[var(--success)]">
          AI 診斷信心度 87%
        </span>
        <ChevronUp className="h-4 w-4 text-[var(--text-secondary)]" />
      </div>

      {/* Symptom */}
      <div className="flex flex-col gap-2">
        <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
          症狀描述
        </span>
        <p className="text-[16px] leading-[1.5] text-[var(--text-primary)]">
          客戶反映電子鎖指紋辨識功能異常，多次嘗試均無法解鎖。密碼功能正常，但指紋模組疑似故障。已使用超過2年，未曾更換指紋模組。
        </p>
      </div>

      {/* Domain Attributes */}
      <div className="flex flex-col gap-4">
        {domainAttrs.map((row, ri) => (
          <div key={ri} className="flex gap-4">
            {row.map((a) => (
              <div key={a.label} className="flex flex-1 flex-col gap-1">
                <span className="text-[12px] text-[var(--text-secondary)]">
                  {a.label}
                </span>
                <span className="text-[14px] font-medium text-[var(--text-primary)]">
                  {a.value}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Resolution Level */}
      <div className="flex flex-col gap-2">
        <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
          解決層級
        </span>
        <span className="inline-flex w-fit rounded bg-[#FEF3C7] px-2 py-1 text-[13px] font-medium text-[#92400E]">
          Level 3 — 現場維修
        </span>
      </div>

      {/* Diagnostic Chain */}
      <div className="flex items-center gap-2">
        {diagChain.map((n, i) => (
          <div key={n.label} className="contents">
            <div className="flex flex-1 flex-col gap-1 rounded-lg bg-[#F1F5F9] p-3">
              <span className="text-[11px] text-[var(--text-secondary)]">
                {n.label}
              </span>
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {n.value}
              </span>
            </div>
            {i < diagChain.length - 1 && (
              <ArrowRight className="h-4 w-4 flex-shrink-0 text-[var(--text-disabled)]" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── LINE Media Gallery ────────────────────────── */

const mediaTabs = [
  { label: "全部", active: true },
  { label: "圖片", active: false },
  { label: "影片", active: false },
  { label: "Issue 包", active: false },
];

function LineMediaGallery() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Images className="h-5 w-5 text-[var(--primary)]" />
          <span className="text-[20px] font-semibold text-[var(--text-primary)]">
            客戶上傳媒體
          </span>
          <span className="rounded bg-[var(--primary-light)] px-2 py-1 text-[11px] font-semibold text-[var(--primary)]">
            LINE
          </span>
          <span className="text-[12px] text-[var(--text-secondary)]">
            共 8 筆（5 圖片・2 影片・1 檔案）
          </span>
        </div>
        <div className="flex gap-1">
          {mediaTabs.map((t) => (
            <span
              key={t.label}
              className={`rounded px-3 py-1 text-[12px] font-medium ${t.active ? "bg-[var(--primary)] text-white" : "bg-[var(--bg-page)] text-[var(--text-secondary)]"}`}
            >
              {t.label}
            </span>
          ))}
        </div>
      </div>

      {/* Bundle 1 - Expanded */}
      <div className="flex flex-col rounded-lg border border-[var(--border)]">
        <div className="flex items-center gap-3 rounded-t-lg bg-[#F8FAFC] p-3">
          <Package className="h-5 w-5 text-[var(--primary)]" />
          <div className="flex flex-1 flex-col gap-[2px]">
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              我家的電子鎖指紋完全沒反應，已經試了好幾次都打不開...
            </span>
            <span className="text-[11px] text-[var(--text-secondary)]">
              提交時間 2026-04-22 09:15
            </span>
          </div>
          <span className="rounded bg-[#E2E8F0] px-2 py-[3px] text-[11px] text-[#334155]">
            5 圖片
          </span>
          <span className="rounded bg-[#E2E8F0] px-2 py-[3px] text-[11px] text-[#334155]">
            1 影片
          </span>
          <span className="rounded bg-[#D1FAE5] px-2 py-[3px] text-[11px] text-[#065F46]">
            AI 已分析
          </span>
          <ChevronUp className="h-4 w-4 text-[var(--text-secondary)]" />
        </div>
        <div className="flex flex-col gap-4 p-4">
          <p className="text-[14px] leading-[1.5] text-[var(--text-primary)]">
            我家的電子鎖指紋完全沒反應，已經試了好幾次都打不開，門鈴按了也沒聲音。之前換過一次電池，但問題還是一樣。請問是不是感測器壞了？可以派人來看看嗎？
          </p>
          <div className="flex gap-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className={`h-[128px] w-[128px] flex-shrink-0 rounded-lg ${i % 2 === 0 ? "bg-[#CBD5E1]" : "bg-[#E2E8F0]"}`}
              />
            ))}
            <div className="relative h-[128px] w-[128px] flex-shrink-0 overflow-hidden rounded-lg bg-[#94A3B8]">
              <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                <span className="text-[14px] font-medium text-white">
                  ▶ 0:15
                </span>
              </div>
            </div>
          </div>
          {/* AI Analysis */}
          <div className="flex flex-col gap-2 rounded-lg border-l-[3px] border-[#10B981] bg-[#ECFDF5] p-3">
            <span className="text-[12px] font-semibold text-[#065F46]">
              AI 圖像分析
            </span>
            <div className="flex flex-wrap gap-[6px]">
              {["指紋模組", "螢幕顯示", "電池槽", "外觀完整"].map((kw) => (
                <span
                  key={kw}
                  className="rounded bg-[#D1FAE5] px-2 py-[2px] text-[11px] text-[#065F46]"
                >
                  {kw}
                </span>
              ))}
            </div>
            <span className="text-[12px] text-[var(--primary)]">
              → 關聯 ProblemCard #PC-0421
            </span>
          </div>
        </div>
      </div>

      {/* Bundle 2 - Collapsed */}
      <div className="flex flex-col rounded-lg border border-[var(--border)]">
        <div className="flex items-center gap-3 rounded-lg bg-[#F8FAFC] p-3">
          <Package className="h-5 w-5 text-[var(--primary)]" />
          <div className="flex flex-1 flex-col gap-[2px]">
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              補充一下，密碼解鎖是正常的，只有指紋有問題
            </span>
            <span className="text-[11px] text-[var(--text-secondary)]">
              提交時間 2026-04-22 10:30
            </span>
          </div>
          <span className="rounded bg-[#E2E8F0] px-2 py-[3px] text-[11px] text-[#334155]">
            1 訊息
          </span>
          <span className="rounded bg-[#FEF3C7] px-2 py-[3px] text-[11px] text-[#92400E]">
            補充
          </span>
          <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
        </div>
      </div>
    </div>
  );
}

/* ── Work Timeline ─────────────────────────────── */

interface TimelineEvent {
  color: string;
  badge: { text: string; textColor: string; bg: string };
  title: string;
  detail?: string;
  time: string;
  scores?: { label: string }[];
  matchScore?: string;
}

const events: TimelineEvent[] = [
  {
    color: "#3B82F6",
    badge: { text: "技師 李建宏", textColor: "#1E40AF", bg: "#DBEAFE" },
    title: "狀態變更：已接受 → 進行中",
    detail: "技師已抵達現場，開始維修作業",
    time: "2026-04-22 14:30:00",
  },
  {
    color: "#3B82F6",
    badge: { text: "技師 李建宏", textColor: "#1E40AF", bg: "#DBEAFE" },
    title: "狀態變更：已派工 → 已接受",
    time: "2026-04-22 13:45:00",
  },
  {
    color: "#2563EB",
    badge: { text: "系統", textColor: "#64748B", bg: "#F1F5F9" },
    title: "AI 匹配完成",
    time: "2026-04-22 13:30:00",
    scores: [
      { label: "距離 92%" },
      { label: "技能 95%" },
      { label: "評分 96%" },
      { label: "負荷 88%" },
    ],
    matchScore: "匹配分數：93",
  },
  {
    color: "#2563EB",
    badge: { text: "管理員 王小明", textColor: "#1E40AF", bg: "#DBEAFE" },
    title: "技師指派：李建宏",
    time: "2026-04-22 13:31:00",
  },
  {
    color: "#94A3B8",
    badge: { text: "系統", textColor: "#64748B", bg: "#F1F5F9" },
    title: "工單自動建立",
    detail: "由 LINE 對話 #CONV-20260422-0158 自動觸發建立",
    time: "2026-04-22 13:00:00",
  },
  {
    color: "#94A3B8",
    badge: { text: "系統", textColor: "#64748B", bg: "#F1F5F9" },
    title: "ProblemCard 診斷完成",
    detail: "信心度 87%，建議 Level 3 現場維修",
    time: "2026-04-22 13:00:05",
  },
];

function WorkTimeline() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <div className="flex items-center justify-between">
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          工單歷程
        </span>
        <button className="flex items-center gap-[6px] rounded-md border border-[var(--border)] px-3 py-[6px]">
          <span className="text-[13px] text-[var(--text-secondary)]">全部</span>
          <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
        </button>
      </div>

      <div className="relative">
        <div className="absolute bottom-0 left-[5px] top-[6px] w-[2px] bg-[var(--border)]" />
        <div className="flex flex-col gap-5">
          {events.map((ev, i) => (
            <div key={i} className="flex gap-4 pt-[2px]">
              <div
                className="relative z-10 mt-[2px] h-3 w-3 flex-shrink-0 rounded-full"
                style={{ backgroundColor: ev.color }}
              />
              <div className="flex flex-col gap-1">
                <span
                  className="inline-flex w-fit rounded px-2 py-[2px] text-[11px]"
                  style={{
                    color: ev.badge.textColor,
                    backgroundColor: ev.badge.bg,
                  }}
                >
                  {ev.badge.text}
                </span>
                <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                  {ev.title}
                </span>
                {ev.scores && (
                  <div className="flex gap-[6px]">
                    {ev.scores.map((s) => (
                      <span
                        key={s.label}
                        className="rounded bg-[#D1FAE5] px-2 py-[2px] text-[11px] text-[#065F46]"
                      >
                        {s.label}
                      </span>
                    ))}
                  </div>
                )}
                {ev.matchScore && (
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {ev.matchScore}
                  </span>
                )}
                {ev.detail && (
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {ev.detail}
                  </span>
                )}
                <span className="text-[11px] text-[var(--text-disabled)]">
                  {ev.time}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <button className="flex h-9 items-center justify-center rounded-md border border-[var(--border)]">
        <span className="text-[13px] text-[var(--primary)]">載入更多歷程</span>
      </button>
    </div>
  );
}

/* ── Conversation Thread ───────────────────────── */

interface ChatMsg {
  sender: string;
  content: string;
  time: string;
  isBot?: boolean;
  isSystem?: boolean;
}

const messages: ChatMsg[] = [
  {
    sender: "陳小姐",
    content: "我家的電子鎖指紋解鎖完全沒反應，已經試了好幾次了",
    time: "09:12",
  },
  {
    sender: "SmartLock Bot",
    content: "收到您的問題。請問您的鎖具品牌和型號是？",
    time: "09:12",
    isBot: true,
  },
  { sender: "陳小姐", content: "Yale YDM-4109", time: "09:13" },
  {
    sender: "SmartLock Bot",
    content: "了解，YDM-4109 指紋模組問題。請問密碼解鎖是否正常？",
    time: "09:13",
    isBot: true,
  },
  {
    sender: "陳小姐",
    content: "密碼是正常的，就只有指紋不行",
    time: "09:14",
  },
  {
    sender: "SmartLock Bot",
    content:
      "初步判斷為指紋模組故障，已為您建立維修工單 WO-20260422-0001。",
    time: "09:15",
    isBot: true,
  },
  {
    sender: "",
    content: "--- 對話已轉接至工單處理流程 ---",
    time: "",
    isSystem: true,
  },
];

function ConversationThread() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          LINE 對話記錄
        </span>
        <div className="flex items-center gap-[6px]">
          <span className="text-[13px] text-[var(--primary)]">
            在新視窗開啟
          </span>
          <ExternalLink className="h-[14px] w-[14px] text-[var(--primary)]" />
        </div>
      </div>

      <div className="flex max-h-[360px] flex-col gap-3 overflow-auto rounded-lg bg-[var(--bg-page)] p-4">
        {messages.map((m, i) =>
          m.isSystem ? (
            <div key={i} className="flex justify-center py-2">
              <span className="text-[12px] text-[var(--text-disabled)]">
                {m.content}
              </span>
            </div>
          ) : (
            <div
              key={i}
              className={`flex flex-col gap-1 ${m.isBot ? "items-end" : ""}`}
            >
              <div
                className={`flex max-w-[320px] flex-col gap-1 p-3 ${
                  m.isBot
                    ? "rounded-[12px_4px_12px_12px] bg-[var(--primary-light)]"
                    : "rounded-[4px_12px_12px_12px] bg-[var(--bg-surface)]"
                }`}
              >
                <span className="text-[11px] font-semibold text-[var(--text-secondary)]">
                  {m.sender}
                </span>
                <span className="text-[14px] text-[var(--text-primary)]">
                  {m.content}
                </span>
                <span className="text-right text-[11px] text-[var(--text-disabled)]">
                  {m.time}
                </span>
              </div>
            </div>
          ),
        )}
      </div>

      <div className="flex items-center justify-center gap-[6px] rounded-b-lg bg-[#F1F5F9] px-4 py-2">
        <Lock className="h-3 w-3 text-[var(--text-disabled)]" />
        <span className="text-[12px] text-[var(--text-disabled)]">
          唯讀模式 — 此為 LINE 對話備份
        </span>
      </div>
    </div>
  );
}

/* ── Completion Report ─────────────────────────── */

const svcItems = [
  { name: "指紋模組更換", qty: "1", price: "NT$ 2,800", sub: "NT$ 2,800" },
  { name: "現場維修工資", qty: "1", price: "NT$ 1,200", sub: "NT$ 1,200" },
  { name: "出勤費", qty: "1", price: "NT$ 300", sub: "NT$ 300" },
];

const funcTests = [
  { label: "指紋解鎖", pass: true },
  { label: "密碼解鎖", pass: true },
  { label: "卡片解鎖", pass: true },
  { label: "APP 連線", pass: true },
  { label: "自動上鎖", pass: true },
  { label: "電池電壓 (偏低，建議更換)", pass: false },
];

function CompletionReport() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="h-5 w-5 text-[var(--success)]" />
          <span className="text-[20px] font-semibold text-[var(--text-primary)]">
            完工報告
          </span>
        </div>
        <span className="text-[12px] text-[var(--text-secondary)]">
          提交時間：2026-04-22 16:45
        </span>
      </div>

      {/* Photos */}
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
          現場照片
        </span>
        <div className="flex items-center gap-2">
          {["維修前", "維修中", "維修後", "測試"].map((lbl, i) => (
            <div
              key={lbl}
              className="relative h-24 w-24 flex-shrink-0 rounded-lg bg-[#E2E8F0]"
            >
              <span
                className={`absolute left-0 top-0 rounded-br rounded-tl-lg px-[6px] py-[2px] text-[10px] font-medium text-white ${
                  lbl === "維修前" || lbl === "維修後" || lbl === "測試"
                    ? "bg-[var(--success)]"
                    : "bg-[var(--primary)]"
                }`}
              >
                {lbl}
              </span>
            </div>
          ))}
          <div className="flex h-24 w-24 flex-shrink-0 items-center justify-center rounded-lg bg-[#1E293B80]">
            <span className="text-[20px] font-bold text-white">+3</span>
          </div>
        </div>
      </div>

      {/* Service Items Table */}
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
          服務項目
        </span>
        <div className="overflow-hidden rounded-lg border border-[var(--border)]">
          <div className="flex bg-[#F8FAFC] px-3 py-2">
            <span className="flex-1 text-[12px] font-semibold text-[var(--text-secondary)]">
              項目名稱
            </span>
            <span className="w-[50px] text-center text-[12px] font-semibold text-[var(--text-secondary)]">
              數量
            </span>
            <span className="w-[80px] text-right text-[12px] font-semibold text-[var(--text-secondary)]">
              單價
            </span>
            <span className="w-[80px] text-right text-[12px] font-semibold text-[var(--text-secondary)]">
              小計
            </span>
          </div>
          {svcItems.map((r) => (
            <div
              key={r.name}
              className="flex border-t border-[var(--border)] px-3 py-2"
            >
              <span className="flex-1 text-[13px] text-[var(--text-primary)]">
                {r.name}
              </span>
              <span className="w-[50px] text-center text-[13px] text-[var(--text-primary)]">
                {r.qty}
              </span>
              <span className="w-[80px] text-right text-[13px] text-[var(--text-primary)]">
                {r.price}
              </span>
              <span className="w-[80px] text-right text-[13px] text-[var(--text-primary)]">
                {r.sub}
              </span>
            </div>
          ))}
          <div className="flex bg-[#F8FAFC] px-3 py-[10px]">
            <span className="flex-1 text-[14px] font-bold text-[var(--text-primary)]">
              合計
            </span>
            <span className="w-[80px] text-right text-[14px] font-bold text-[var(--text-primary)]">
              NT$ 4,300
            </span>
          </div>
        </div>
      </div>

      {/* Parts Used */}
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
          使用零件
        </span>
        <div className="overflow-hidden rounded-lg border border-[var(--border)]">
          <div className="flex bg-[#F8FAFC] px-3 py-2">
            <span className="flex-1 text-[12px] font-semibold text-[var(--text-secondary)]">
              零件名稱
            </span>
            <span className="w-[100px] text-[12px] font-semibold text-[var(--text-secondary)]">
              零件編號
            </span>
            <span className="w-[50px] text-center text-[12px] font-semibold text-[var(--text-secondary)]">
              數量
            </span>
            <span className="w-[80px] text-right text-[12px] font-semibold text-[var(--text-secondary)]">
              單價
            </span>
          </div>
          <div className="flex px-3 py-2">
            <span className="flex-1 text-[13px] text-[var(--text-primary)]">
              指紋感測模組
            </span>
            <span className="w-[100px] text-[12px] text-[var(--text-secondary)]">
              FP-YDM-4109
            </span>
            <span className="w-[50px] text-center text-[13px] text-[var(--text-primary)]">
              1
            </span>
            <span className="w-[80px] text-right text-[13px] text-[var(--text-primary)]">
              NT$ 2,800
            </span>
          </div>
        </div>
      </div>

      {/* Functional Tests */}
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
          功能測試
        </span>
        <div className="flex flex-col gap-[6px]">
          {funcTests.map((t) => (
            <div key={t.label} className="flex items-center gap-2">
              {t.pass ? (
                <CircleCheck className="h-[18px] w-[18px] text-[var(--success)]" />
              ) : (
                <CircleX className="h-[18px] w-[18px] text-[var(--error)]" />
              )}
              <span className="text-[13px] text-[var(--text-primary)]">
                {t.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Customer Signature */}
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
          客戶簽名確認
        </span>
        <div className="flex items-center gap-4">
          <div className="flex h-20 w-[200px] items-center justify-center rounded-lg border border-[var(--border)] bg-[#FAFAFA]">
            <span className="text-[14px] italic text-[var(--text-disabled)]">
              陳小姐 簽名
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[13px] text-[var(--text-primary)]">
              簽署人：陳小姐
            </span>
            <span className="text-[12px] text-[var(--text-secondary)]">
              簽署時間：2026-04-22 17:00
            </span>
            <span className="inline-flex w-fit rounded bg-[#D1FAE5] px-2 py-[2px] text-[11px] font-medium text-[#065F46]">
              已簽署
            </span>
          </div>
        </div>
      </div>

      {/* Satisfaction Rating */}
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
          客戶滿意度
        </span>
        <div className="flex items-center gap-3">
          {[1, 2, 3, 4].map((i) => (
            <span key={i} className="text-[24px] text-[var(--accent)]">
              ★
            </span>
          ))}
          <span className="text-[24px] text-[#E2E8F0]">★</span>
          <span className="text-[14px] font-medium text-[var(--text-primary)]">
            滿意
          </span>
        </div>
        <span className="text-[13px] italic text-[var(--text-secondary)]">
          「技師很專業，維修速度也快，非常感謝！」
        </span>
      </div>
    </div>
  );
}

/* ── Exception Records ─────────────────────────── */

function ExceptionRecords() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TriangleAlert className="h-5 w-5 text-[var(--error)]" />
          <span className="text-[20px] font-semibold text-[var(--text-primary)]">
            異常記錄
          </span>
        </div>
        <span className="rounded-full bg-[var(--error)] px-[10px] py-[2px] text-[12px] font-bold text-white">
          2
        </span>
      </div>

      {/* Exception 1 - Expanded */}
      <div className="overflow-hidden rounded-lg border border-[var(--border)]">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3">
          <span className="rounded bg-[#FEF3C7] px-2 py-[3px] text-[11px] font-semibold text-[#92400E]">
            範圍變更
          </span>
          <span className="flex-1 text-[14px] font-semibold text-[var(--text-primary)]">
            新增電池更換服務
          </span>
          <span className="text-[12px] text-[var(--text-secondary)]">
            04-22 15:30
          </span>
          <span className="rounded bg-[#D1FAE5] px-2 py-[2px] text-[11px] font-medium text-[#065F46]">
            已解決
          </span>
          <ChevronUp className="h-4 w-4 text-[var(--text-secondary)]" />
        </div>
        <div className="flex flex-col gap-3 p-4">
          <div className="flex flex-col gap-1">
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              原始範圍
            </span>
            <span className="text-[13px] text-[var(--text-primary)]">
              指紋模組更換
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              變更後範圍
            </span>
            <span className="text-[13px] text-[var(--text-primary)]">
              指紋模組更換 + 電池更換
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              變更原因
            </span>
            <span className="text-[13px] text-[var(--text-primary)]">
              維修過程中發現電池電壓偏低，建議一併更換以避免後續問題
            </span>
          </div>
        </div>
      </div>

      {/* Exception 2 - Collapsed */}
      <div className="overflow-hidden rounded-lg border border-[var(--error)] border-l-[3px]">
        <div className="flex items-center gap-3 bg-[var(--bg-surface)] px-4 py-3">
          <span className="rounded bg-[#FEE2E2] px-2 py-[3px] text-[11px] font-semibold text-[#991B1B]">
            客戶投訴
          </span>
          <span className="flex-1 text-[14px] font-semibold text-[var(--text-primary)]">
            維修後指紋登錄需多次嘗試
          </span>
          <span className="text-[12px] text-[var(--text-secondary)]">
            04-22 18:00
          </span>
          <span className="rounded bg-[#FEE2E2] px-2 py-[2px] text-[11px] font-medium text-[#991B1B]">
            待處理
          </span>
          <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
        </div>
      </div>
    </div>
  );
}

/* ── Main Page ─────────────────────────────────── */

export default function WorkOrderDetailPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 overflow-hidden">
        {/* Left Content */}
        <div className="flex flex-1 flex-col overflow-auto">
          {/* Detail Header */}
          <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
            <span className="text-[11px] text-[var(--text-secondary)]">
              首頁 &gt; 工單管理 &gt; 工單列表 &gt; WO-20260422-0001
            </span>
            <div className="flex items-center gap-3">
              <Link
                href="/work-orders"
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--bg-page)]"
              >
                <ChevronLeft className="h-5 w-5 text-[var(--text-secondary)]" />
              </Link>
              <span className="font-mono text-[28px] font-bold text-[var(--text-primary)]">
                WO-20260422-0001
              </span>
              <span className="rounded bg-[var(--primary-light)] px-2 py-1 text-[14px] font-semibold text-[var(--primary)]">
                進行中
              </span>
              <Copy className="h-4 w-4 text-[var(--text-secondary)]" />
            </div>
            <SlaTimeline />
          </div>

          <ProblemCardSummary />
          <LineMediaGallery />
          <WorkTimeline />
          <ConversationThread />
          <CompletionReport />
          <ExceptionRecords />
        </div>

        {/* Right Sidebar */}
        <WorkOrderDetailSidebar />
      </div>
    </div>
  );
}
