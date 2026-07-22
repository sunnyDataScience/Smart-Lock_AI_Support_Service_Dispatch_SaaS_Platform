"use client";

import { use, useEffect, useState, type ReactNode } from "react";
import {
  CheckCircle2,
  ClipboardList,
  Download,
  Flag,
  Info,
  Pencil,
  Sparkles,
  UserSearch,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import FmeaDiagnosisCard from "@/components/problem-cards/FmeaDiagnosisCard";
import LinkedConversationCard from "@/components/problem-cards/LinkedConversationCard";
import ResolutionTimeline from "@/components/problem-cards/ResolutionTimeline";
import ProblemCardDetailSidebar from "@/components/problem-cards/ProblemCardDetailSidebar";
import { ApiError, api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import type { components } from "@/types/api.generated";

// UAT P2-8：後端 create/get 已收/回 location（服務地址），惟 api.generated 尚未含
// 該欄位——依 types/api.local.ts 慣例本地擴充（型別 SoT 更新後可移除）。
// CR-0178 UAT-0720-09 續：customer_name 同理（extracted_fields.customer_name 投影）。
type ProblemCard = components["schemas"]["ProblemCard"] & {
  location?: string | null;
  customer_name?: string | null;
};
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
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];

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

// CR-0128 報價先行：PC 階段報價列（listProblemCardQuotesV2 回傳形狀）
type PcQuote = {
  id: string;
  version: number;
  state: string;
  total_amount: string | null;
  deposit_required: string | null;
  expiry_at: string | null;
  work_order_id: string | null;
  quote_number: string | null;
  created_at: string | null;
};

const QUOTE_STATE_LABEL: Record<string, { label: string; cls: string }> = {
  draft: { label: "草稿", cls: "bg-[#F1F5F9] text-[#475569]" },
  pending_approval: { label: "送審中", cls: "bg-[#FEF9C3] text-[#854D0E]" },
  approved: { label: "已核准", cls: "bg-[#E0F2FE] text-[#0369A1]" },
  sent: { label: "已送客戶", cls: "bg-[#EDE9FE] text-[#6D28D9]" },
  accepted: { label: "客戶已確認", cls: "bg-[#DCFCE7] text-[#166534]" },
  rejected: { label: "已拒絕", cls: "bg-[#FEE2E2] text-[#991B1B]" },
  expired: { label: "已過期", cls: "bg-[#FEE2E2] text-[#991B1B]" },
  superseded: { label: "已被取代", cls: "bg-[#F1F5F9] text-[#94A3B8]" },
  retrospective_audit_only: { label: "急件補審中", cls: "bg-[#FFEDD5] text-[#9A3412]" },
};

// 急件 carve-out 四類（13_Security 無關——ADR-015①；跳過報價直接開單、事後 4h 補審）
const EMERGENCY_CLASS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "非急件（走報價先行）" },
  { value: "locked_out", label: "急件：被鎖門外" },
  { value: "trapped_inside", label: "急件：人困屋內" },
  { value: "safety_risk", label: "急件：安全風險" },
  { value: "angry_high_risk", label: "急件：高風險客訴" },
];

// CR-0132 雙 gate（15_SDS §4.6）——分流＋RMA spine 選項
const TRIAGE_TIER_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "未分流" },
  { value: "L1", label: "L1 — AI 直接回" },
  { value: "L2", label: "L2 — 遠端指導（文字/電話）" },
  { value: "L3", label: "L3 — 現場派工" },
];
const RESOLUTION_CHANNEL_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "未設定" },
  { value: "ai_auto", label: "AI 自動" },
  { value: "line_text_cs", label: "文字客服" },
  { value: "phone_callback", label: "電話回撥" },
  { value: "onsite", label: "現場派工" },
];
const DISPOSITION_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "未分類" },
  { value: "replacement", label: "換貨" },
  { value: "repair", label: "維修" },
  { value: "software_update", label: "軟體更新" },
  { value: "user_education", label: "誤操作教育" },
  { value: "onsite_service", label: "現場服務" },
  { value: "ntf", label: "NTF 無法重現" },
];

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
  const router = useRouter();
  const [card, setCard] = useState<ProblemCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  // UAT P3：404／無效 id（如誤入 /problem-cards/new）→ 顯示「找不到此問題卡」
  // 而非通用連線錯誤誤導使用者
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionPending, setActionPending] = useState<
    | "confirm"
    | "resolve"
    | "update"
    | "auto"
    | "export"
    | "match"
    | "convert"
    | null
  >(null);
  const [actionError, setActionError] = useState<string | null>(null);
  // CR-0042：轉單 422 結構化錯誤（缺漏欄位 / 重複客戶）供 ConvertModal 顯示 + 主管 override
  const [convertErr, setConvertErr] = useState<{
    message: string;
    missing: { field: string; tier: string }[];
    incomplete: boolean;
    duplicate: boolean;
  } | null>(null);
  const [actionToast, setActionToast] = useState<string | null>(null);
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [convertModalOpen, setConvertModalOpen] = useState(false);
  const [diagnosisModalOpen, setDiagnosisModalOpen] = useState(false); // CR-0132 雙 gate 診斷/知識欄位
  const [autoResolveResult, setAutoResolveResult] = useState<ResolveResponse | null>(null);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [matchResult, setMatchResult] = useState<DispatchCandidate[] | null>(null);
  const [matchUrgency, setMatchUrgency] = useState<AutoMatchUrgency>("normal");
  // CR-0128 報價先行：PC 階段報價 + 急件標記
  const [pcQuotes, setPcQuotes] = useState<PcQuote[] | null>(null);
  const [quotePending, setQuotePending] = useState(false);
  const [emergencyPending, setEmergencyPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // 非 UUID 的路徑段（如 /problem-cards/new）不打 API：後端 ::uuid cast 會炸出
    // 5xx，friendlyError 會誤導成「連線失敗／系統問題」。直接視為找不到。
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setNotFound(false);
    (async () => {
      try {
        const res = await api.get<ProblemCardEnvelope>(
          tenantPath(`/problem-cards/${encodeURIComponent(id)}`),
        );
        if (!cancelled) setCard(res.data ?? null);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setNotFound(true);
        } else {
          setError(
            friendlyError(e),
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  // CR-0128：載入 PC 階段報價（confirmed 卡才有報價先行語意；失敗不阻斷頁面）
  useEffect(() => {
    if (!card || card.status !== "confirmed") return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ data: PcQuote[] }>(
          tenantPath(`/problem-cards/${encodeURIComponent(id)}/quotes`),
        );
        if (!cancelled) setPcQuotes(res.data ?? []);
      } catch {
        if (!cancelled) setPcQuotes([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, card]);

  useEffect(() => {
    if (!actionToast) return;
    const t = setTimeout(() => setActionToast(null), 2400);
    return () => clearTimeout(t);
  }, [actionToast]);

  const formatActionError = (e: unknown): string =>
    friendlyError(e);

  const handleConfirm = async () => {
    setActionPending("confirm");
    setActionError(null);
    try {
      const res = await api.post<ProblemCardEnvelope>(
        tenantPath(`/problem-cards/${encodeURIComponent(id)}/confirm`),
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
        tenantPath(`/problem-cards/${encodeURIComponent(id)}`),
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
      // CR-0009 step-extend：problem_cards_v2 補 exportProblemCardV2
      const res = await api.get<ProblemCardExport>(
        tenantPath(`/problem-cards/${encodeURIComponent(card.id)}/export`),
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
        tenantPath("/dispatch:auto-match"),
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
      // Track B S6: 解決方案引擎 v2（tenant-scoped，problemCardId 走 path）
      const res = await api.post<ResolveResponse>(
        tenantPath(`/problem-cards/${encodeURIComponent(card.id)}:resolve-suggest`),
      );
      setAutoResolveResult(res);
      setActionToast(`自動解決：${RESOLVE_LAYER_BADGE[res.layer].label}`);
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  // CR-0128：PC 階段建報價 → 導向報價工作台編明細/送客戶
  const handleCreatePcQuote = async () => {
    setQuotePending(true);
    setActionError(null);
    try {
      const res = await api.post<{ data: { id: string } }>(
        tenantPath(`/problem-cards/${encodeURIComponent(id)}/quotes`),
        { urgent: false },
      );
      const qid = res.data?.id;
      setActionToast("報價已建立，前往報價工作台編輯明細");
      if (qid) router.push(`/admin/quotes?open=${encodeURIComponent(qid)}`);
    } catch (e) {
      setActionError(friendlyError(e));
    } finally {
      setQuotePending(false);
    }
  };

  // CR-0128：急件標記（emergency_class 四類；空值=清除回報價先行）
  const handleEmergencyChange = async (value: string) => {
    setEmergencyPending(true);
    setActionError(null);
    try {
      const res = await api.patch<ProblemCardEnvelope>(
        tenantPath(`/problem-cards/${encodeURIComponent(id)}`),
        { emergency_class: value } satisfies Partial<ProblemCardUpdateRequest>,
      );
      setCard(res.data ?? null);
      setActionToast(value ? "已標記急件——開單將跳過報價、事後 4h 補審" : "已清除急件標記");
    } catch (e) {
      setActionError(friendlyError(e));
    } finally {
      setEmergencyPending(false);
    }
  };

  // CR-0132：診斷/知識欄位（雙 gate）PATCH，成功後重載 card（後端會重算完整度/knowledge_ready）
  const handleDiagnosisSave = async (patch: ProblemCardUpdateRequest) => {
    setActionPending("update");
    setActionError(null);
    try {
      const res = await api.patch<ProblemCardEnvelope>(
        tenantPath(`/problem-cards/${encodeURIComponent(id)}`),
        patch,
      );
      setCard(res.data ?? null);
      setDiagnosisModalOpen(false);
      setActionToast("診斷/知識欄位已更新");
    } catch (e) {
      setActionError(friendlyError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleConvertToWO = async (
    info: {
      customer_address: string;
      customer_name?: string;
      customer_phone?: string;
    },
    overrideReason?: string,
  ) => {
    setActionPending("convert");
    setActionError(null);
    setConvertErr(null);
    try {
      // CR-0009 step-extend：problem_cards_v2 補 convertProblemCardToWorkOrderV2
      // CR-0022：AI 草擬卡無 profile 地址，必須在開單時由客服填服務地址（HITL）。
      // CR-0042：主管 override 走 query param override_reason（後端 assert_completeness 接）。
      const res = await api.post<WorkOrderEnvelope>(
        tenantPath(`/problem-cards/${encodeURIComponent(id)}/convert-to-work-order`),
        {
          customer_address: info.customer_address,
          ...(info.customer_name ? { customer_name: info.customer_name } : {}),
          ...(info.customer_phone ? { customer_phone: info.customer_phone } : {}),
        },
        overrideReason && overrideReason.trim()
          ? { query: { override_reason: overrideReason.trim() } }
          : undefined,
      );
      const woId = res.data?.id;
      setConvertModalOpen(false);
      setActionToast(woId ? `工單已建立：${woId.slice(0, 8)}，前往工單` : "工單已建立");
      // 開單成功後直接導向新工單頁：給明確成功回饋（原本只跳 toast、停在問題卡頁、
      // 開單鈕還在 → 看起來像沒成功），並讓客服接續派工。
      if (woId) {
        router.push(`/work-orders/${encodeURIComponent(woId)}`);
      }
    } catch (e) {
      // CR-0042：解析結構化 422 — 缺漏欄位 / 重複客戶交給 ConvertModal 顯示；其餘走 generic
      if (e instanceof ApiError && e.status === 422 && e.errorCode === "INCOMPLETE_PROBLEM_CARD") {
        const missing = Array.isArray(e.details)
          ? (e.details as { field: string; tier: string }[])
          : [];
        setConvertErr({ message: e.message, missing, incomplete: true, duplicate: false });
      } else if (e instanceof ApiError && e.errorCode === "DUPLICATE_CUSTOMER") {
        setConvertErr({ message: e.message, missing: [], incomplete: false, duplicate: true });
      } else {
        setActionError(formatActionError(e));
      }
    } finally {
      setActionPending(null);
    }
  };

  const handleResolve = async (layer: ResolutionLayer) => {
    setActionPending("resolve");
    setActionError(null);
    try {
      const res = await api.post<ProblemCardEnvelope>(
        tenantPath(`/problem-cards/${encodeURIComponent(id)}/resolve`),
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

  // UAT P3：找不到問題卡（404 / 無效 id，如 /problem-cards/new）→ 專屬空狀態＋返回列表
  if (notFound) {
    return (
      <div className="flex h-full bg-[var(--bg-page)]">
        <Sidebar />
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-8">
          <span className="text-[20px] font-bold text-[var(--text-primary)]">找不到此問題卡</span>
          <p className="text-[13px] text-[var(--text-secondary)]">
            此問題卡不存在或已被刪除，請回列表重新選取。
          </p>
          <Link
            href="/problem-cards"
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90"
          >
            ← 返回問題卡片列表
          </Link>
        </div>
      </div>
    );
  }

  const canConfirm = card?.status === "draft";
  const canResolve = card?.status === "confirmed";
  const canConvertToWO = card?.status === "confirmed";
  // CR-0128 報價先行 gate（BR-WO-01）：無客戶確認報價且非急件 → 開單會被後端 425 擋
  const isEmergency = Boolean(card?.emergency_class);
  const hasAcceptedQuote = (pcQuotes ?? []).some((q) => q.state === "accepted");
  const quoteGateSatisfied = isEmergency || hasAcceptedQuote;
  const canEdit = card?.status === "draft" || card?.status === "confirmed";
  const canAutoResolve =
    card != null &&
    card.status !== "resolved" &&
    Boolean((card.brand || card.model || card.symptom || "").trim());

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
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
                    title="自動匹配緊急程度（選「緊急」時分數會加成 5%）"
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
              {canConvertToWO && (
                <button
                  onClick={() => {
                    setActionError(null);
                    setConvertModalOpen(true);
                  }}
                  disabled={actionPending !== null || (pcQuotes !== null && !quoteGateSatisfied)}
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  title={
                    pcQuotes !== null && !quoteGateSatisfied
                      ? "報價先行（BR-WO-01）：須客戶確認報價後才可開單派工；急件請先標記急件類別"
                      : "將此問題卡轉為工單，進入派工流程"
                  }
                >
                  <ClipboardList className="h-4 w-4" />
                  {actionPending === "convert" ? "建立中…" : "開單"}
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
                FMEA 診斷鏈與解決嘗試歷程為示意內容（智慧診斷功能尚未啟用）；關聯對話與工單資訊為即時資料。
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

            {card && card.status === "confirmed" && (
              <section className="rounded-xl border border-[var(--border)] bg-white p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-[15px] font-bold text-[var(--text-primary)]">
                      線上報價（報價先行）
                    </h2>
                    <p className="mt-1 text-[12px] leading-[1.6] text-[var(--text-secondary)]">
                      流程：問題卡 → 報價 → 客戶 LINE 確認 → 開單派工（BR-WO-01）。
                      急件標記後可跳過報價直接開單，事後 4 小時內補審。
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={card.emergency_class ?? ""}
                      onChange={(e) => handleEmergencyChange(e.target.value)}
                      disabled={emergencyPending || actionPending !== null}
                      className="rounded-md border border-[var(--border)] bg-white px-2 py-[6px] text-[12px] text-[var(--text-primary)] focus:outline-none disabled:opacity-50"
                      title="急件 carve-out：標記後開單跳過報價（ADR-015①），系統將建補審佔位報價"
                    >
                      {EMERGENCY_CLASS_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                    <button
                      onClick={handleCreatePcQuote}
                      disabled={quotePending || actionPending !== null}
                      className="inline-flex items-center gap-2 rounded-md border border-[var(--primary)] bg-white px-3 py-[6px] text-[13px] font-semibold text-[var(--primary)] transition hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {quotePending ? "建立中…" : "建立報價"}
                    </button>
                  </div>
                </div>
                {pcQuotes === null ? (
                  <p className="mt-3 text-[12px] text-[var(--text-secondary)]">報價載入中…</p>
                ) : pcQuotes.length === 0 ? (
                  <p className="mt-3 rounded-md border border-[#FDE68A] bg-[#FFFBEB] px-3 py-2 text-[12px] text-[#92400E]">
                    尚無報價——{isEmergency ? "已標記急件，可直接開單（事後補審）" : "須先建立報價並取得客戶確認才能開單"}。
                  </p>
                ) : (
                  <div className="mt-3 flex flex-col gap-2">
                    {pcQuotes.map((q) => {
                      const st = QUOTE_STATE_LABEL[q.state] ?? { label: q.state, cls: "bg-[#F1F5F9] text-[#475569]" };
                      return (
                        <div key={q.id} className="flex items-center gap-3 rounded-md border border-[var(--border)] px-3 py-2 text-[13px]">
                          <span className="font-mono text-[12px] text-[var(--text-secondary)]">
                            {q.quote_number ?? `Q${q.version}`}
                          </span>
                          <span className={`rounded px-2 py-[2px] text-[11px] font-semibold ${st.cls}`}>{st.label}</span>
                          <span className="text-[var(--text-primary)]">
                            {q.total_amount ? `NT$ ${q.total_amount}` : "（未有明細）"}
                          </span>
                          <Link
                            href={`/admin/quotes?open=${encodeURIComponent(q.id)}`}
                            className="ml-auto text-[12px] font-semibold text-[var(--primary)] hover:underline"
                          >
                            編輯明細／送客戶 →
                          </Link>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            )}

            {/* CR-0132 雙 gate（15_SDS §4.6）：進料閘（派工）＋知識閘（精煉）完整度 */}
            {card && (
              <section className="rounded-xl border border-[var(--border)] bg-white p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-[15px] font-bold text-[var(--text-primary)]">
                      診斷雙 gate（分流 · 知識）
                    </h2>
                    <p className="mt-1 text-[12px] leading-[1.6] text-[var(--text-secondary)]">
                      進料閘（Gate①）管能否派工；知識閘（Gate②）管能否進知識精煉。
                      未過知識閘不擋結案，但卡會留在「待補知識佇列」。
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setActionError(null);
                      setDiagnosisModalOpen(true);
                    }}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-white px-3 py-[6px] text-[13px] font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Pencil className="h-4 w-4" />
                    編輯診斷/知識
                  </button>
                </div>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <GateBar
                    label="進料閘（Gate① · 派工）"
                    score={card.intake_completeness ?? null}
                    hint="必填：聯絡電話 / 品牌 / 型號 / 失效模式 / 分流層（L3 另加地址）"
                  />
                  <GateBar
                    label="知識閘（Gate② · 精煉）"
                    score={card.resolution_completeness ?? null}
                    hint="必填：根因 / 分類 / 矯正措施 / 驗證 / 處置 / 管道 / 解決者（L3 另加韌體/序號）"
                    ready={card.knowledge_ready ?? false}
                  />
                </div>
                {(card.triage_tier || card.resolution_channel || card.disposition) && (
                  <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-[var(--text-secondary)]">
                    {card.triage_tier && (
                      <span><span className="text-[var(--text-disabled)]">分流：</span>{card.triage_tier}</span>
                    )}
                    {card.resolution_channel && (
                      <span><span className="text-[var(--text-disabled)]">管道：</span>
                        {RESOLUTION_CHANNEL_OPTIONS.find((o) => o.value === card.resolution_channel)?.label ?? card.resolution_channel}</span>
                    )}
                    {card.disposition && (
                      <span><span className="text-[var(--text-disabled)]">處置：</span>
                        {DISPOSITION_OPTIONS.find((o) => o.value === card.disposition)?.label ?? card.disposition}</span>
                    )}
                  </div>
                )}
              </section>
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
                  {card?.conversation_id ? (
                    <Link
                      href={`/conversations/${card.conversation_id}`}
                      className="font-mono text-[13px] text-[#2563EB] hover:underline"
                    >
                      {card.conversation_id.slice(0, 8)}
                    </Link>
                  ) : (
                    // UAT P1-1:手建卡(電話進線)無 LINE 對話
                    <span className="text-[14px] text-[var(--text-primary)]">—(客服手建)</span>
                  )}
                </div>
                {/* UAT P2-8：顯示服務地址（location，客服手建卡／後續補登） */}
                <div className="col-span-2 flex flex-col gap-1">
                  <span className="text-[13px] font-medium text-[var(--text-secondary)]">服務地址</span>
                  <span className="text-[14px] font-medium text-[var(--text-primary)]">
                    {card?.location || "—"}
                  </span>
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

      {diagnosisModalOpen && card && (
        <DiagnosisModal
          initial={card}
          pending={actionPending === "update"}
          onCancel={() => setDiagnosisModalOpen(false)}
          onSubmit={handleDiagnosisSave}
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

      {convertModalOpen && card && (
        <ConvertModal
          pending={actionPending === "convert"}
          error={convertErr}
          initialAddress={card?.location ?? undefined}
          initialPhone={card?.contact_phone ?? undefined}
          initialName={card?.customer_name ?? undefined}
          onCancel={() => {
            setConvertModalOpen(false);
            setConvertErr(null);
          }}
          onSubmit={handleConvertToWO}
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

const FIELD_LABEL: Record<string, string> = {
  brand: "品牌",
  model: "型號",
  symptom: "故障症狀",
  urgency: "急迫度",
  customer_address: "服務地址",
  problem_type: "問題類型",
  serial_number: "鎖體序號",
  door_type: "門型",
  door_status: "門況",
  network_status: "網路狀態",
};
const TIER_LABEL: Record<string, { label: string; cls: string }> = {
  required: { label: "必填", cls: "bg-[#FEE2E2] text-[#B91C1C]" },
  pre_dispatch: { label: "派工前", cls: "bg-[#FEF3C7] text-[#92400E]" },
  optional: { label: "選填", cls: "bg-[#F1F5F9] text-[var(--text-secondary)]" },
};

function ConvertModal({
  pending,
  error,
  initialAddress,
  initialPhone,
  initialName,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  error: {
    message: string;
    missing: { field: string; tier: string }[];
    incomplete: boolean;
    duplicate: boolean;
  } | null;
  /** UAT P2-8：問題卡已有服務地址（location）時預填（可改） */
  initialAddress?: string;
  /** CR-0178 UAT-0720-09：問題卡已有聯絡電話（contact_phone）時預填（可改；留空送出後端仍 fallback 帶卡上電話） */
  initialPhone?: string;
  /** CR-0178 UAT-0720-09 續：問題卡已有客戶姓名（extracted_fields.customer_name）時預填（可改） */
  initialName?: string;
  onCancel: () => void;
  onSubmit: (
    info: {
      customer_address: string;
      customer_name?: string;
      customer_phone?: string;
    },
    overrideReason?: string,
  ) => Promise<void>;
}) {
  const [address, setAddress] = useState(initialAddress ?? "");
  const [name, setName] = useState(initialName ?? "");
  const [phone, setPhone] = useState(initialPhone ?? "");
  const [overrideReason, setOverrideReason] = useState("");
  const canSubmit = address.trim().length > 0 && !pending;
  const submit = (override?: string) =>
    onSubmit(
      {
        customer_address: address.trim(),
        customer_name: name.trim() || undefined,
        customer_phone: phone.trim() || undefined,
      },
      override,
    );

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-[var(--primary)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            轉為工單
          </span>
        </div>
        <p className="mb-3 text-[13px] text-[var(--text-secondary)]">
          請填寫服務地址後開單（AI 草擬卡未含地址，需客服確認）。地址為必填，缺地址無法派工。
        </p>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              服務地址 <span className="text-[var(--error)]">*</span>
            </span>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              maxLength={300}
              placeholder="例：新北市林口區民富街 83 號 1 樓"
              className="rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-[13px] outline-none focus:border-[var(--primary)]"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">聯絡人（選填）</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={80}
              placeholder="客戶姓名（留空沿用問題卡／客戶資料）"
              className="rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-[13px] outline-none focus:border-[var(--primary)]"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">聯絡電話（選填）</span>
            <input
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              maxLength={30}
              placeholder="09xx-xxx-xxx（留空沿用問題卡／客戶資料）"
              className="rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-[13px] outline-none focus:border-[var(--primary)]"
            />
          </label>
        </div>
        {/* CR-0042 重複客戶 422 → 欄位級提示 */}
        {error?.duplicate && (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800">
            ⚠ 此電話已有客戶資料：{error.message}
          </div>
        )}

        {/* CR-0042 完整度不足 422 → 結構化缺漏欄位 + 主管 override */}
        {error?.incomplete && (
          <div className="mt-3 flex flex-col gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2.5">
            <span className="text-[12px] font-semibold text-red-700">問題卡完整度不足，缺以下欄位：</span>
            <div className="flex flex-wrap gap-1.5">
              {error.missing.length === 0 ? (
                <span className="text-[12px] text-red-700">{error.message}</span>
              ) : (
                error.missing.map((m) => (
                  <span key={m.field} className="inline-flex items-center gap-1 rounded bg-white px-2 py-[2px] text-[12px] text-[var(--text-primary)]">
                    {FIELD_LABEL[m.field] ?? "其他必填欄位"}
                    <span className={`rounded px-1 text-[10px] ${(TIER_LABEL[m.tier] ?? TIER_LABEL.optional).cls}`}>
                      {(TIER_LABEL[m.tier] ?? TIER_LABEL.optional).label}
                    </span>
                  </span>
                ))
              )}
            </div>
            <label className="mt-1 flex flex-col gap-1">
              <span className="text-[11px] text-[var(--text-secondary)]">主管強制開單原因（填寫後可略過完整度檢查）</span>
              <input
                type="text"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                maxLength={500}
                placeholder="例：客戶現場急修，欄位事後補登"
                className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] outline-none focus:border-[var(--primary)]"
              />
            </label>
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          {error?.incomplete ? (
            <button
              onClick={() => submit(overrideReason)}
              disabled={!canSubmit || overrideReason.trim().length < 4}
              className="rounded-md bg-[#B45309] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pending ? "建立中…" : "主管強制開單"}
            </button>
          ) : (
            <button
              onClick={() => submit()}
              disabled={!canSubmit}
              className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pending ? "建立中…" : "確認開單"}
            </button>
          )}
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
  // brand/model 生成型別為 nullable：以空字串起始，避免 input value 收到 null
  const [brand, setBrand] = useState(initial.brand ?? "");
  const [model, setModel] = useState(initial.model ?? "");
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


// CR-0132：雙 gate 完整度進度條（分數 null=未起算）
function GateBar({
  label,
  score,
  hint,
  ready,
}: {
  label: string;
  score: number | null;
  hint: string;
  ready?: boolean;
}) {
  const pct = score === null ? 0 : Math.round(score * 100);
  const full = score !== null && score >= 1;
  const barColor = full ? "bg-[#16A34A]" : pct >= 50 ? "bg-[#F59E0B]" : "bg-[#DC2626]";
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">{label}</span>
        <div className="flex items-center gap-2">
          {ready !== undefined && (
            <span
              className={`rounded px-2 py-[1px] text-[11px] font-semibold ${
                ready ? "bg-[#DCFCE7] text-[#166534]" : "bg-[#F1F5F9] text-[#64748B]"
              }`}
            >
              {ready ? "知識就緒" : "待補"}
            </span>
          )}
          <span className="text-[12px] font-mono text-[var(--text-secondary)]">
            {score === null ? "未起算" : `${pct}%`}
          </span>
        </div>
      </div>
      <div className="h-[6px] w-full overflow-hidden rounded-full bg-[var(--border)]">
        <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] leading-[1.5] text-[var(--text-disabled)]">{hint}</span>
    </div>
  );
}

// CR-0132：診斷/知識欄位編輯 modal（分流 Gate① + RMA spine Gate②，漸進補寫）
function DiagnosisModal({
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
  const [triageTier, setTriageTier] = useState(initial.triage_tier ?? "");
  const [contactPhone, setContactPhone] = useState(initial.contact_phone ?? "");
  const [failureMode, setFailureMode] = useState(initial.failure_mode ?? "");
  const [resolutionChannel, setResolutionChannel] = useState(initial.resolution_channel ?? "");
  const [rootCause, setRootCause] = useState(initial.root_cause ?? "");
  const [rootCauseCategory, setRootCauseCategory] = useState(initial.root_cause_category ?? "");
  const [correctiveAction, setCorrectiveAction] = useState(initial.corrective_action ?? "");
  const [verification, setVerification] = useState<boolean | null>(initial.verification ?? null);
  const [disposition, setDisposition] = useState(initial.disposition ?? "");
  const [firmwareVersion, setFirmwareVersion] = useState(initial.firmware_version ?? "");
  const [serial, setSerial] = useState(initial.serial ?? "");

  const isL3 = triageTier === "L3";

  const buildPatch = (): ProblemCardUpdateRequest => {
    const p: ProblemCardUpdateRequest = {};
    const set = <K extends keyof ProblemCardUpdateRequest>(
      key: K,
      cur: ProblemCardUpdateRequest[K],
      orig: unknown,
    ) => {
      if (cur !== (orig ?? "")) p[key] = cur;
    };
    set("triage_tier", triageTier, initial.triage_tier);
    set("contact_phone", contactPhone, initial.contact_phone);
    set("failure_mode", failureMode, initial.failure_mode);
    set("resolution_channel", resolutionChannel, initial.resolution_channel);
    set("root_cause", rootCause, initial.root_cause);
    set("root_cause_category", rootCauseCategory, initial.root_cause_category);
    set("corrective_action", correctiveAction, initial.corrective_action);
    set("disposition", disposition, initial.disposition);
    set("firmware_version", firmwareVersion, initial.firmware_version);
    set("serial", serial, initial.serial);
    if (verification !== (initial.verification ?? null) && verification !== null) {
      p.verification = verification;
    }
    return p;
  };

  const patch = buildPatch();
  const dirty = Object.keys(patch).length > 0;

  const field = (labelTxt: string, node: ReactNode) => (
    <label className="flex flex-col gap-1">
      <span className="text-[12px] font-medium text-[var(--text-secondary)]">{labelTxt}</span>
      {node}
    </label>
  );
  const inputCls =
    "rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:opacity-50";

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4 py-8"
      onClick={() => !pending && onCancel()}
    >
      <div
        className="max-h-full w-full max-w-[640px] overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-1 flex items-center gap-2">
          <Pencil className="h-5 w-5 text-[var(--text-primary)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            編輯診斷 / 知識欄位
          </span>
        </div>
        <p className="mb-4 text-[13px] text-[var(--text-secondary)]">
          分流欄（進料閘）與失效分析 spine（知識閘）——漸進補寫，儲存後系統自動重算完整度。
        </p>

        <h3 className="mb-2 text-[13px] font-bold text-[#0369A1]">進料閘（Gate① · 決定能否派工）</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {field("分流層", (
            <select value={triageTier} onChange={(e) => setTriageTier(e.target.value)} disabled={pending} className={inputCls}>
              {TRIAGE_TIER_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ))}
          {field("聯絡電話", (
            <input value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} disabled={pending} maxLength={50} className={inputCls} />
          ))}
          {field("失效模式", (
            <input value={failureMode} onChange={(e) => setFailureMode(e.target.value)} disabled={pending} maxLength={60} placeholder="如 motor_stuck / battery_drain" className={inputCls} />
          ))}
          {field("處理管道", (
            <select value={resolutionChannel} onChange={(e) => setResolutionChannel(e.target.value)} disabled={pending} className={inputCls}>
              {RESOLUTION_CHANNEL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ))}
        </div>

        <h3 className="mb-2 mt-5 text-[13px] font-bold text-[#9333EA]">知識閘（Gate② · 失效分析 spine · 精煉素材）</h3>
        <div className="flex flex-col gap-3">
          {field("根因", (
            <textarea value={rootCause} onChange={(e) => setRootCause(e.target.value)} disabled={pending} rows={2} className={inputCls} />
          ))}
          <div className="grid gap-3 sm:grid-cols-2">
            {field("根因分類", (
              <input value={rootCauseCategory} onChange={(e) => setRootCauseCategory(e.target.value)} disabled={pending} maxLength={60} placeholder="如 mechanical / firmware / user_error" className={inputCls} />
            ))}
            {field("處置分類", (
              <select value={disposition} onChange={(e) => setDisposition(e.target.value)} disabled={pending} className={inputCls}>
                {DISPOSITION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            ))}
          </div>
          {field("矯正措施 / 處置步驟", (
            <textarea value={correctiveAction} onChange={(e) => setCorrectiveAction(e.target.value)} disabled={pending} rows={2} className={inputCls} />
          ))}
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={verification === true}
              onChange={(e) => setVerification(e.target.checked)}
              disabled={pending}
              className="h-4 w-4 rounded border-[var(--border)]"
            />
            <span className="text-[13px] text-[var(--text-primary)]">已驗證修復（8D D6——未驗證的解法不入知識庫）</span>
          </label>
          {isL3 && (
            <div className="grid gap-3 sm:grid-cols-2 rounded-lg border border-[#DDD6FE] bg-[#FAF5FF] p-3">
              <span className="col-span-full text-[11px] font-semibold text-[#7C3AED]">L3 現場額外（RMA 批次瑕疵關聯）</span>
              {field("韌體版本", (
                <input value={firmwareVersion} onChange={(e) => setFirmwareVersion(e.target.value)} disabled={pending} maxLength={50} className={inputCls} />
              ))}
              {field("鎖體序號", (
                <input value={serial} onChange={(e) => setSerial(e.target.value)} disabled={pending} maxLength={100} className={inputCls} />
              ))}
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-2">
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
