"use client";

import { use, useEffect, useState } from "react";
import {
  CheckCircle2,
  Download,
  Flag,
  Info,
  Pencil,
  Sparkles,
  UserSearch,
  X,
} from "lucide-react";
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
type ProblemCardUpdateRequest = components["schemas"]["ProblemCardUpdateRequest"];
type ResolveResponse = components["schemas"]["ResolveResponse"];
type ResolveLayer = ResolveResponse["layer"];
type ProblemCardExport = components["schemas"]["ProblemCardExport"];
type ExportFormat = NonNullable<ProblemCardExport["format"]>;
type DispatchAutoMatchResponse = components["schemas"]["DispatchAutoMatchResponse"];
type DispatchCandidate = components["schemas"]["DispatchCandidate"];
type DispatchAutoMatchRequest = components["schemas"]["DispatchAutoMatchRequest"];
type AutoMatchUrgency = NonNullable<DispatchAutoMatchRequest["urgency"]>;

const EXPORT_FORMATS: { value: ExportFormat; label: string; mime: string; ext: string }[] = [
  { value: "pdf", label: "PDF", mime: "application/pdf", ext: "pdf" },
  { value: "json", label: "JSON", mime: "application/json", ext: "json" },
  { value: "csv", label: "CSV", mime: "text/csv;charset=utf-8", ext: "csv" },
];

const RESOLVE_LAYER_BADGE: Record<ResolveLayer, { label: string; bg: string; text: string }> = {
  faq_match: { label: "L1 FAQ 命中", bg: "#DCFCE7", text: "#15803D" },
  knowledge_base_rag: { label: "L2 知識庫 RAG", bg: "#DBEAFE", text: "#1D4ED8" },
  llm_generation: { label: "L3 LLM 生成", bg: "#FEF3C7", text: "#B45309" },
  escalation: { label: "需人工介入", bg: "#FEE2E2", text: "#B91C1C" },
};

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
  const [actionPending, setActionPending] = useState<
    "confirm" | "resolve" | "update" | "auto" | "export" | "match" | null
  >(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionToast, setActionToast] = useState<string | null>(null);
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [autoResolveResult, setAutoResolveResult] = useState<ResolveResponse | null>(null);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [matchResult, setMatchResult] = useState<DispatchCandidate[] | null>(null);
  const [matchUrgency, setMatchUrgency] = useState<AutoMatchUrgency>("normal");

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

  const handleUpdate = async (patch: ProblemCardUpdateRequest) => {
    setActionPending("update");
    setActionError(null);
    try {
      const res = await api.patch<ProblemCardEnvelope>(
        `/api/v1/problem-cards/${encodeURIComponent(id)}`,
        patch,
      );
      setCard(res.data ?? null);
      setEditModalOpen(false);
      setActionToast("問題卡已更新");
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleExport = async (fmt: ExportFormat) => {
    if (!card) return;
    setActionPending("export");
    setActionError(null);
    setExportMenuOpen(false);
    try {
      const res = await api.get<ProblemCardExport>(
        `/api/v1/problem-cards/${encodeURIComponent(card.id)}/export`,
        { query: { format: fmt } },
      );
      const meta = EXPORT_FORMATS.find((f) => f.value === fmt)!;
      const bin = atob(res.content);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const blob = new Blob([bytes], { type: meta.mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `problem-card-${card.id.slice(0, 8)}.${meta.ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setActionToast(`已下載 ${meta.label}`);
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleAutoMatch = async () => {
    if (!card) return;
    setActionPending("match");
    setActionError(null);
    try {
      const body: DispatchAutoMatchRequest = {
        problem_card_id: card.id,
        urgency: matchUrgency,
        max_candidates: 5,
      };
      const res = await api.post<DispatchAutoMatchResponse>(
        "/api/v1/dispatch/auto-match",
        body,
      );
      setMatchResult(res.candidates ?? []);
      setActionToast(
        `已匹配 ${res.candidates?.length ?? 0} 位候選技師（${
          matchUrgency === "emergency" ? "緊急" : "一般"
        }）`,
      );
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleAutoResolve = async () => {
    if (!card) return;
    setActionPending("auto");
    setActionError(null);
    try {
      const res = await api.post<ResolveResponse>("/api/v1/resolve", {
        problem_card_id: card.id,
      });
      setAutoResolveResult(res);
      setActionToast(`自動解決：${RESOLVE_LAYER_BADGE[res.layer].label}`);
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
  const canEdit = card?.status === "draft" || card?.status === "confirmed";
  const canAutoResolve =
    card != null &&
    card.status !== "resolved" &&
    Boolean((card.brand || card.model || card.symptom || "").trim());

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

          {(canConfirm || canResolve || canEdit || canAutoResolve || card) && (
            <div className="flex flex-wrap items-center gap-2">
              {card && (
                <div className="relative">
                  <button
                    onClick={() => setExportMenuOpen((v) => !v)}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Download className="h-4 w-4" />
                    {actionPending === "export" ? "匯出中…" : "匯出"}
                  </button>
                  {exportMenuOpen && (
                    <div className="absolute right-0 top-full z-30 mt-1 w-32 overflow-hidden rounded-md border border-[var(--border)] bg-white shadow-lg">
                      {EXPORT_FORMATS.map((f) => (
                        <button
                          key={f.value}
                          onClick={() => handleExport(f.value)}
                          className="flex w-full items-center justify-between px-3 py-2 text-[13px] text-[var(--text-primary)] transition hover:bg-[var(--bg-page)]"
                        >
                          <span>{f.label}</span>
                          <span className="text-[11px] text-[var(--text-secondary)]">.{f.ext}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {canAutoResolve && (
                <button
                  onClick={handleAutoResolve}
                  disabled={actionPending !== null}
                  className="inline-flex items-center gap-2 rounded-md border border-[#7C3AED] bg-[#F5F3FF] px-4 py-2 text-[13px] font-semibold text-[#6D28D9] transition hover:bg-[#EDE9FE] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Sparkles className="h-4 w-4" />
                  {actionPending === "auto" ? "查詢中…" : "嘗試自動解決"}
                </button>
              )}
              {card && (
                <div className="inline-flex items-center gap-1 rounded-md border border-[#0EA5E9] bg-white p-[2px]">
                  <select
                    value={matchUrgency}
                    onChange={(e) => setMatchUrgency(e.target.value as AutoMatchUrgency)}
                    disabled={actionPending !== null}
                    className="rounded-l-md bg-transparent px-2 py-[6px] text-[12px] text-[#0369A1] focus:outline-none"
                    title="自動匹配緊急程度（emergency 會將分數加成 5%）"
                  >
                    <option value="normal">一般</option>
                    <option value="emergency">緊急</option>
                  </select>
                  <button
                    onClick={handleAutoMatch}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-r-md bg-[#0EA5E9] px-3 py-[6px] text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <UserSearch className="h-4 w-4" />
                    {actionPending === "match" ? "匹配中…" : "推薦技師"}
                  </button>
                </div>
              )}
              {canEdit && (
                <button
                  onClick={() => {
                    setActionError(null);
                    setEditModalOpen(true);
                  }}
                  disabled={actionPending !== null}
                  className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Pencil className="h-4 w-4" />
                  編輯問題卡
                </button>
              )}
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

            {autoResolveResult && (
              <AutoResolvePanel
                result={autoResolveResult}
                onClose={() => setAutoResolveResult(null)}
              />
            )}

            {matchResult && (
              <MatchResultPanel
                candidates={matchResult}
                onClose={() => setMatchResult(null)}
              />
            )}

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

      {editModalOpen && card && (
        <EditModal
          initial={card}
          pending={actionPending === "update"}
          onCancel={() => setEditModalOpen(false)}
          onSubmit={handleUpdate}
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

function AutoResolvePanel({
  result,
  onClose,
}: {
  result: ResolveResponse;
  onClose: () => void;
}) {
  const badge = RESOLVE_LAYER_BADGE[result.layer];
  const confidencePct =
    typeof result.confidence === "number"
      ? `${(result.confidence * 100).toFixed(0)}%`
      : "—";

  return (
    <div className="rounded-lg border border-[#DDD6FE] bg-[#FAF5FF] p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-[#7C3AED]" />
          <span className="text-[16px] font-semibold text-[var(--text-primary)]">
            自動解決結果
          </span>
          <span
            className="rounded-full px-2 py-[2px] text-[11px] font-semibold"
            style={{ backgroundColor: badge.bg, color: badge.text }}
          >
            {badge.label}
          </span>
          <span className="text-[12px] text-[var(--text-secondary)]">
            信心度 {confidencePct}
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-[var(--text-secondary)] transition hover:bg-white"
          title="關閉"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <pre className="mt-3 whitespace-pre-wrap break-words rounded-md border border-[#E9D5FF] bg-white px-4 py-3 font-sans text-[13px] leading-[1.7] text-[var(--text-primary)]">
        {result.answer || "（無回答內容）"}
      </pre>

      {result.sources && result.sources.length > 0 && (
        <div className="mt-3 flex flex-col gap-2">
          <span className="text-[12px] font-medium text-[var(--text-secondary)]">
            參考來源（{result.sources.length}）
          </span>
          <ul className="flex flex-col gap-2">
            {result.sources.map((src, idx) => (
              <li
                key={`${src.id ?? "src"}-${idx}`}
                className="rounded-md border border-[var(--border)] bg-white px-3 py-2"
              >
                <div className="flex items-center justify-between text-[12px] text-[var(--text-secondary)]">
                  <span>
                    {src.type === "manual" ? "手冊" : "案例"}
                    {src.id ? ` · ${src.id.slice(0, 8)}` : ""}
                  </span>
                  {typeof src.score === "number" && (
                    <span className="font-mono">
                      {src.score.toFixed(2)}
                    </span>
                  )}
                </div>
                {src.snippet && (
                  <p className="mt-1 text-[13px] leading-[1.6] text-[var(--text-primary)]">
                    {src.snippet}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function MatchResultPanel({
  candidates,
  onClose,
}: {
  candidates: DispatchCandidate[];
  onClose: () => void;
}) {
  return (
    <div className="rounded-lg border border-[#BAE6FD] bg-[#F0F9FF] p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <UserSearch className="h-5 w-5 text-[#0369A1]" />
          <span className="text-[16px] font-semibold text-[var(--text-primary)]">
            自動匹配候選技師
          </span>
          <span className="text-[12px] text-[var(--text-secondary)]">
            共 {candidates.length} 位
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-[var(--text-secondary)] transition hover:bg-white"
          title="關閉"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {candidates.length === 0 ? (
        <p className="mt-3 rounded-md border border-[#E0F2FE] bg-white px-4 py-3 text-[13px] text-[var(--text-secondary)]">
          目前找不到符合條件的候選技師，請手動於工單頁指派或調整匹配參數。
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {candidates.map((c, idx) => {
            const score = typeof c.score === "number" ? c.score : 0;
            const scorePct = (score * 100).toFixed(1);
            const scoreColor =
              score >= 0.7
                ? "bg-[#DCFCE7] text-[#15803D]"
                : score >= 0.4
                ? "bg-[#FEF3C7] text-[#B45309]"
                : "bg-[#F1F5F9] text-[var(--text-secondary)]";
            return (
              <li
                key={`${c.technician_id ?? "tech"}-${idx}`}
                className="rounded-md border border-[#E0F2FE] bg-white px-4 py-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-col gap-[2px]">
                    <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                      {c.technician_name || "（未命名技師）"}
                    </span>
                    <span className="text-[11px] font-mono text-[var(--text-secondary)]">
                      {c.technician_id ? c.technician_id.slice(0, 8) : "—"}
                    </span>
                  </div>
                  <span
                    className={`rounded-full px-2 py-[2px] text-[11px] font-semibold ${scoreColor}`}
                  >
                    {scorePct}
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-[12px] text-[var(--text-secondary)]">
                  <div className="flex flex-col">
                    <span className="text-[11px]">距離</span>
                    <span className="font-medium text-[var(--text-primary)]">
                      {typeof c.distance_km === "number"
                        ? `${c.distance_km.toFixed(1)} km`
                        : "—"}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[11px]">預估抵達</span>
                    <span className="font-medium text-[var(--text-primary)]">
                      {typeof c.eta_minutes === "number"
                        ? `${c.eta_minutes} 分鐘`
                        : "—"}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[11px]">評分</span>
                    <span className="font-medium text-[var(--text-primary)]">
                      {typeof c.rating === "number"
                        ? c.rating.toFixed(1)
                        : "—"}
                    </span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-3 text-[11px] leading-[1.6] text-[var(--text-secondary)]">
        分數綜合「品牌技能 × 0.4 + 距離 × 0.3 + 評分 × 0.3」並依緊急程度加成；實際指派請於工單頁完成。
      </p>
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

const URGENCY_OPTIONS: { value: Urgency; label: string }[] = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
];

function EditModal({
  initial,
  pending,
  onCancel,
  onSubmit,
}: {
  initial: ProblemCard;
  pending: boolean;
  onCancel: () => void;
  onSubmit: (patch: ProblemCardUpdateRequest) => Promise<void>;
}) {
  const [brand, setBrand] = useState(initial.brand);
  const [model, setModel] = useState(initial.model);
  const [symptom, setSymptom] = useState(initial.symptom);
  const [category, setCategory] = useState(initial.category ?? "");
  const [urgency, setUrgency] = useState<Urgency>(initial.urgency);

  const buildPatch = (): ProblemCardUpdateRequest => {
    const patch: ProblemCardUpdateRequest = {};
    if (brand !== initial.brand) patch.brand = brand;
    if (model !== initial.model) patch.model = model;
    if (symptom !== initial.symptom) patch.symptom = symptom;
    if (category !== (initial.category ?? "")) patch.category = category;
    if (urgency !== initial.urgency) patch.urgency = urgency;
    return patch;
  };

  const patch = buildPatch();
  const dirty = Object.keys(patch).length > 0;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={() => !pending && onCancel()}
    >
      <div
        className="w-full max-w-[520px] rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center gap-2">
          <Pencil className="h-5 w-5 text-[var(--text-primary)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            編輯問題卡
          </span>
        </div>
        <p className="mb-4 text-[13px] text-[var(--text-secondary)]">
          修改基本欄位；狀態變更請使用「確認」或「結案」按鈕。症狀以「、」分隔多個關鍵字。
        </p>

        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">品牌</span>
              <input
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                disabled={pending}
                maxLength={50}
                className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">型號</span>
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={pending}
                maxLength={100}
                className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none"
              />
            </label>
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              症狀（多個以「、」分隔）
            </span>
            <textarea
              value={symptom}
              onChange={(e) => setSymptom(e.target.value)}
              disabled={pending}
              rows={3}
              maxLength={1000}
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none"
            />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">類別</span>
              <input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={pending}
                placeholder="例：電池、WiFi、安裝"
                maxLength={100}
                className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">緊急度</span>
              <select
                value={urgency}
                onChange={(e) => setUrgency(e.target.value as Urgency)}
                disabled={pending}
                className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none"
              >
                {URGENCY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
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
            onClick={() => onSubmit(patch)}
            disabled={pending || !dirty}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : dirty ? "儲存變更" : "無變更"}
          </button>
        </div>
      </div>
    </div>
  );
}
