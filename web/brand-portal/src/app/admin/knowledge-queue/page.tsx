"use client";

// CR-0132 / WBS 1.2.3：待補知識佇列——operational 已結（resolved）但知識閘（Gate②）
// 未過的問題卡。精煉服務（15_SDS §9）只汲取 knowledge_ready=true 的卡；本頁提示
// 小編/技師補完 RMA spine，點入問題卡即可編輯診斷/知識欄位。

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookMarked, RefreshCw } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type ProblemCard = components["schemas"]["ProblemCard"];

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "未起算" : `${Math.round(v * 100)}%`;
}

export default function KnowledgeQueuePage() {
  const [cards, setCards] = useState<ProblemCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloading, setReloading] = useState(false);

  const load = async () => {
    setReloading(true);
    setError(null);
    try {
      const res = await api.get<{ data: ProblemCard[] }>(
        tenantPath("/problem-cards/knowledge-queue?limit=200"),
      );
      setCards(res.data ?? []);
    } catch (e) {
      setError(friendlyError(e));
      setCards([]);
    } finally {
      setReloading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <BookMarked className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">待補知識佇列</h1>
          <button
            onClick={load}
            disabled={reloading}
            className="ml-auto inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-white px-3 py-[6px] text-[13px] font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${reloading ? "animate-spin" : ""}`} />
            重新整理
          </button>
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3">
            <span className="text-[13px] leading-[1.6] text-[#475569]">
              這些問題卡已結案（operational），但<strong>知識閘（Gate②）</strong>未過——失效分析
              spine 尚未補齊。精煉服務只汲取「知識就緒」的卡；請點入補完根因 / 矯正措施 /
              驗證 / 處置，補齊後自動離開本佇列。
            </span>
          </div>

          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              載入失敗：{error}
            </div>
          )}

          {cards === null ? (
            <p className="text-[13px] text-[var(--text-secondary)]">載入中…</p>
          ) : cards.length === 0 ? (
            <div className="rounded-lg border border-[#BBF7D0] bg-[#F0FDF4] px-4 py-6 text-center text-[14px] text-[#166534]">
              目前沒有待補知識的卡——所有已結案問題卡的知識閘皆已通過。
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
              <table className="w-full min-w-[720px] text-[13px]">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-[var(--bg-page)] text-left text-[12px] text-[var(--text-secondary)]">
                    <th className="px-4 py-3 font-semibold">問題卡</th>
                    <th className="px-4 py-3 font-semibold">品牌 / 型號</th>
                    <th className="px-4 py-3 font-semibold">分流</th>
                    <th className="px-4 py-3 font-semibold">知識閘完整度</th>
                    <th className="px-4 py-3 font-semibold">更新時間</th>
                    <th className="px-4 py-3 font-semibold" />
                  </tr>
                </thead>
                <tbody>
                  {cards.map((c) => (
                    <tr key={c.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-page)]">
                      <td className="px-4 py-3 font-mono text-[12px] text-[var(--text-secondary)]">
                        {c.id.slice(0, 8)}
                      </td>
                      <td className="px-4 py-3 text-[var(--text-primary)]">
                        {[c.brand, c.model].filter(Boolean).join(" ") || "—"}
                      </td>
                      <td className="px-4 py-3 text-[var(--text-secondary)]">{c.triage_tier ?? "—"}</td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-[#FEF3C7] px-2 py-[2px] text-[12px] font-semibold text-[#92400E]">
                          {pct(c.resolution_completeness)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[12px] text-[var(--text-secondary)]">
                        {c.updated_at ? formatRelative(c.updated_at) : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/problem-cards/${encodeURIComponent(c.id)}`}
                          className="text-[12px] font-semibold text-[var(--primary)] hover:underline"
                        >
                          補知識 →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
