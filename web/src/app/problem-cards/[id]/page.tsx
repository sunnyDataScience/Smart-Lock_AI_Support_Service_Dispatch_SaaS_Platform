"use client";

import { use, useEffect, useState } from "react";
import { CheckCircle2, Flag, Info } from "lucide-react";
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
type ProblemCardResolveRequest = components["schemas"]["ProblemCardResolveRequest"];
type ResolutionLayer = ProblemCardResolveRequest["resolution_layer"];

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

const RESOLUTION_LAYER_OPTIONS: { value: ResolutionLayer; label: string; hint: string }[] = [
  { value: "L1", label: "L1 — AI 直接回覆", hint: "AI 已自動處理完畢" },
  { value: "L2", label: "L2 — 技師遠端指導", hint: "客服或技師遠端排除" },
  { value: "L3", label: "L3 — 現場派工", hint: "已派工技師到場處理" },
];

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function ProblemCardDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const [card, setCard] = useState<ProblemCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionPending, setActionPending] = useState<"confirm" | "resolve" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionToast, setActionToast] = useState<string | null>(null);
  const [resolveModalOpen, setResolveModalOpen] = useState(false);

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

  useEffect(() => {
    if (!actionToast) return;
    const t = setTimeout(() => setActionToast(null), 2400);
    return () => clearTimeout(t);
  }, [actionToast]);

  const formatActionError = (e: unknown): string =>
    e instanceof ApiError
      ? `${e.errorCode} (${e.status})：${e.message}`
      : e instanceof Error
        ? e.message
        : String(e);

  const handleConfirm = async () => {
    setActionPending("confirm");
    setActionError(null);
    try {
      const res = await api.post<ProblemCardEnvelope>(
        `/api/v1/problem-cards/${encodeURIComponent(id)}/confirm`,
      );
      setCard(res.data ?? null);
      setActionToast("問題卡已確認");
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleResolve = async (layer: ResolutionLayer) => {
    setActionPending("resolve");
    setActionError(null);
    try {
      const res = await api.post<ProblemCardEnvelope>(
        `/api/v1/problem-cards/${encodeURIComponent(id)}/resolve`,
        { resolution_layer: layer },
      );
      setCard(res.data ?? null);
      setResolveModalOpen(false);
      setActionToast(`問題卡已結案（${layer}）`);
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const canConfirm = card?.status === "draft";
  const canResolve = card?.status === "confirmed";

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

          {(canConfirm || canResolve) && (
            <div className="flex flex-wrap items-center gap-2">
              {canConfirm && (
                <button
                  onClick={handleConfirm}
                  disabled={actionPending !== null}
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {actionPending === "confirm" ? "處理中…" : "確認問題卡"}
                </button>
              )}
              {canResolve && (
                <button
                  onClick={() => {
                    setActionError(null);
                    setResolveModalOpen(true);
                  }}
                  disabled={actionPending !== null}
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Flag className="h-4 w-4" />
                  結案問題卡
                </button>
              )}
            </div>
          )}

          {actionError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              操作失敗：{actionError}
            </div>
          )}
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

      {resolveModalOpen && (
        <ResolveModal
          pending={actionPending === "resolve"}
          onCancel={() => setResolveModalOpen(false)}
          onSubmit={handleResolve}
        />
      )}

      {actionToast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
          {actionToast}
        </div>
      )}
    </div>
  );
}

function ResolveModal({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (layer: ResolutionLayer) => Promise<void>;
}) {
  const [layer, setLayer] = useState<ResolutionLayer>("L1");

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-2">
          <Flag className="h-5 w-5 text-[var(--success)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            結案問題卡
          </span>
        </div>
        <p className="mb-3 text-[13px] text-[var(--text-secondary)]">
          請選擇此案最終由哪一層解決，作為三層解決引擎的成效統計依據。
        </p>
        <div className="flex flex-col gap-2">
          {RESOLUTION_LAYER_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2 transition ${
                layer === opt.value
                  ? "border-[var(--success)] bg-[#ECFDF5]"
                  : "border-[var(--border)] hover:bg-[var(--bg-page)]"
              }`}
            >
              <input
                type="radio"
                name="resolution_layer"
                value={opt.value}
                checked={layer === opt.value}
                onChange={() => setLayer(opt.value)}
                className="mt-[3px]"
              />
              <div className="flex flex-col gap-[2px]">
                <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                  {opt.label}
                </span>
                <span className="text-[12px] text-[var(--text-secondary)]">
                  {opt.hint}
                </span>
              </div>
            </label>
          ))}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={() => onSubmit(layer)}
            disabled={pending}
            className="rounded-md bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : "確認結案"}
          </button>
        </div>
      </div>
    </div>
  );
}
