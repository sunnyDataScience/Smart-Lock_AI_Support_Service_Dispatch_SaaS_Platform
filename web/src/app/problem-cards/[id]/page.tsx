"use client";

import { use, useEffect, useState } from "react";
import { Info } from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import FmeaDiagnosisCard from "@/components/problem-cards/FmeaDiagnosisCard";
import LinkedConversationCard from "@/components/problem-cards/LinkedConversationCard";
import ResolutionTimeline from "@/components/problem-cards/ResolutionTimeline";
import ProblemCardDetailSidebar from "@/components/problem-cards/ProblemCardDetailSidebar";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardEnvelope = components["schemas"]["ProblemCardEnvelope"];
type ProblemCardStatus = components["schemas"]["ProblemCardStatus"];
type Urgency = components["schemas"]["Urgency"];

const statusLabel: Record<ProblemCardStatus, string> = {
  draft: "待確認",
  confirmed: "已確認",
  resolved: "已解決",
};

const urgencyLabel: Record<Urgency, string> = {
  low: "低",
  medium: "中",
  high: "高",
};

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function ProblemCardDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const [card, setCard] = useState<ProblemCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await api.get<ProblemCardEnvelope>(
          `/api/v1/problem-cards/${encodeURIComponent(id)}`,
        );
        if (!cancelled) setCard(res.data ?? null);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
          <Link
            href="/problem-cards"
            className="text-[14px] font-medium text-[#2563EB]"
          >
            ← 返回問題卡片列表
          </Link>

          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 問題卡片 &gt; {id.slice(0, 8)}
          </span>

          <div className="flex w-full items-center gap-3">
            <span className="font-mono text-[14px] text-[var(--text-secondary)]">
              {id.slice(0, 8)}
            </span>
            <h1 className="flex-1 text-[24px] font-bold text-[var(--text-primary)]">
              {loading
                ? "載入中…"
                : card?.symptom || "（無症狀描述）"}
            </h1>
            {card && (
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-[#DBEAFE] px-3 py-1 text-[12px] font-medium text-[#2563EB]">
                  {statusLabel[card.status]}
                </span>
                <span className="rounded-full bg-[#FEF3C7] px-3 py-1 text-[12px] font-medium text-[#D97706]">
                  緊急度：{urgencyLabel[card.urgency]}
                </span>
              </div>
            )}
          </div>
        </div>

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            載入問題卡失敗：{error}
          </div>
        )}

        <div className="flex flex-1 gap-6 overflow-auto px-8 py-6">
          <div className="flex flex-1 flex-col gap-5">
            <div className="flex items-start gap-2 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3">
              <Info className="mt-[2px] h-4 w-4 flex-shrink-0 text-[#64748B]" />
              <span className="text-[13px] leading-[1.6] text-[#475569]">
                以下 FMEA 診斷鏈、解決時間軸與關聯對話為示意，待診斷引擎模組接入後將顯示真實資料。
              </span>
            </div>

            <FmeaDiagnosisCard />

            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-6">
              <h2 className="text-[18px] font-semibold text-[var(--text-primary)]">
                症狀描述
              </h2>
              <p className="mt-4 text-[14px] leading-[1.6] text-[var(--text-primary)]">
                {card?.symptom || "—"}
              </p>
            </div>

            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-6">
              <h2 className="text-[18px] font-semibold text-[var(--text-primary)]">
                裝置屬性
              </h2>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1">
                  <span className="text-[13px] font-medium text-[var(--text-secondary)]">品牌</span>
                  <span className="text-[14px] font-medium text-[var(--text-primary)]">
                    {card?.brand || "—"}
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[13px] font-medium text-[var(--text-secondary)]">型號</span>
                  <span className="text-[14px] font-medium text-[var(--text-primary)]">
                    {card?.model || "—"}
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[13px] font-medium text-[var(--text-secondary)]">類別</span>
                  <span className="text-[14px] font-medium text-[var(--text-primary)]">
                    {card?.category || "—"}
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[13px] font-medium text-[var(--text-secondary)]">關聯對話</span>
                  {card ? (
                    <Link
                      href={`/conversations/${card.conversation_id}`}
                      className="font-mono text-[13px] text-[#2563EB] hover:underline"
                    >
                      {card.conversation_id.slice(0, 8)}
                    </Link>
                  ) : (
                    <span className="text-[14px] text-[var(--text-primary)]">—</span>
                  )}
                </div>
              </div>

              {card?.media_urls && card.media_urls.length > 0 && (
                <div className="mt-6 flex flex-col gap-2">
                  <span className="text-[13px] font-medium text-[var(--text-secondary)]">附件</span>
                  <ul className="list-disc pl-5 text-[13px] text-[#2563EB]">
                    {card.media_urls.map((url) => (
                      <li key={url}>
                        <a href={url} target="_blank" rel="noreferrer" className="hover:underline">
                          {url}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <LinkedConversationCard conversationId={card?.conversation_id} />
            <ResolutionTimeline />
          </div>

          <ProblemCardDetailSidebar card={card} loading={loading} />
        </div>
      </div>
    </div>
  );
}
