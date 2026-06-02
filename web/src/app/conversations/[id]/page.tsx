"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ChevronLeft, Headphones, Plus } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import ChatTimeline from "@/components/conversations/ChatTimeline";
import DiagnosticReasoningPanel from "@/components/conversations/DiagnosticReasoningPanel";
import HandoverComposer from "@/components/conversations/HandoverComposer";
import { ApiError, api, getCurrentSession, tenantPath } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type Conversation = components["schemas"]["Conversation"];
type ConversationEnvelope = components["schemas"]["ConversationEnvelope"];
type Message = components["schemas"]["Message"];
type MessagePage = components["schemas"]["MessagePage"];
type ConversationStatus = components["schemas"]["ConversationStatus"];
type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardPage = components["schemas"]["ProblemCardPage"];
type ProblemCardStatus = components["schemas"]["ProblemCardStatus"];
type ProblemCardEnvelope = components["schemas"]["ProblemCardEnvelope"];
type ProblemCardCreateRequest = components["schemas"]["ProblemCardCreateRequest"];
type Urgency = components["schemas"]["Urgency"];

const URGENCY_OPTIONS: { value: Urgency; label: string }[] = [
  { value: "low", label: "低（一般諮詢）" },
  { value: "medium", label: "中（標準報修）" },
  { value: "high", label: "高（緊急）" },
];

const PC_STATUS_LABEL: Record<ProblemCardStatus, { label: string; bg: string; color: string }> = {
  draft: { label: "草稿", bg: "#EEF2FF", color: "#6366F1" },
  confirmed: { label: "已確認", bg: "#DBEAFE", color: "#3B82F6" },
  resolved: { label: "已解決", bg: "#D1FAE5", color: "#10B981" },
};

const STATUS_LABEL: Record<ConversationStatus, string> = {
  active: "進行中",
  waiting_human: "已升級",
  closed: "已結束",
};

const STATUS_COLOR: Record<ConversationStatus, { bg: string; text: string }> = {
  active: { bg: "#EFF6FF", text: "#2563EB" },
  waiting_human: { bg: "#FEF2F2", text: "#EF4444" },
  closed: { bg: "#ECFDF5", text: "#10B981" },
};

const RESOLUTION_LABEL: Record<string, string> = {
  case_library: "案例庫",
  rag: "RAG",
  human: "人工",
};

// Fallback tenant UUID for dev environments without a real session
const FALLBACK_TENANT_ID = "00000000-0000-0000-0000-000000000001";

export default function ConversationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  // CR-0003 P2-W2：tenant-scoped v2 端點（FR-0018）
  const session = getCurrentSession();
  const tenantId = session?.tenantId ?? FALLBACK_TENANT_ID;

  const [conv, setConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [problemCards, setProblemCards] = useState<ProblemCard[]>([]);
  const [pcLoading, setPcLoading] = useState(false);
  const [pcError, setPcError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [showCreatePc, setShowCreatePc] = useState(false);
  const [creatingPc, setCreatingPc] = useState(false);
  const [createPcError, setCreatePcError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  const handleCreatePc = async (req: ProblemCardCreateRequest) => {
    setCreatingPc(true);
    setCreatePcError(null);
    try {
      const res = await api.post<ProblemCardEnvelope>(
        tenantPath("/problem-cards"),
        req,
      );
      const created = res.data;
      if (created) {
        setProblemCards((prev) => [created, ...prev]);
        setToast(`已建立問題卡 ${created.id.slice(0, 8)}`);
      }
      setShowCreatePc(false);
    } catch (e) {
      setCreatePcError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setCreatingPc(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setNotFound(false);
      setPcLoading(true);
      setPcError(null);
      setProblemCards([]);
      try {
        // CR-0003 P2-W2：遷移至 tenant-scoped v2 端點（FR-0018）
        const convPath = tenantPath(`/conversations/${encodeURIComponent(id)}`);
        const msgsPath = tenantPath(`/conversations/${encodeURIComponent(id)}/messages`);
        const [envelope, page, pcPage] = await Promise.all([
          api.get<ConversationEnvelope>(convPath),
          api.get<MessagePage>(msgsPath, {
            query: { limit: 100 },
          }),
          api
            .get<ProblemCardPage>(tenantPath("/problem-cards"), {
              query: { conversation_id: id, limit: 10 },
            })
            .catch((e: unknown): ProblemCardPage | null => {
              if (cancelled) return null;
              setPcError(
                e instanceof ApiError
                  ? `${e.errorCode} (${e.status})`
                  : e instanceof Error
                    ? e.message
                    : String(e),
              );
              return null;
            }),
        ]);
        if (cancelled) return;
        setConv(envelope.data ?? null);
        setMessages(page.items ?? []);
        setProblemCards((pcPage?.items ?? []) as ProblemCard[]);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setNotFound(true);
        } else {
          setError(
            e instanceof ApiError
              ? `${e.errorCode} (${e.status})：${e.message}`
              : e instanceof Error
                ? e.message
                : String(e),
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setPcLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, tenantId]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-6">
          <div className="flex items-center gap-3">
            <Link
              href="/conversations"
              className="flex items-center gap-[6px] rounded-md px-[10px] py-[6px] text-[13px] font-medium text-[var(--text-secondary)]"
            >
              <ChevronLeft className="h-4 w-4" />
              返回列表
            </Link>

            <div className="h-6 w-px bg-[var(--border)]" />

            <span
              className="font-mono text-[13px] font-medium text-[var(--text-secondary)]"
              title={id}
            >
              {conv?.document_number ?? id.slice(0, 8)}
            </span>

            {conv && (
              <>
                <span
                  className="flex items-center gap-1 rounded-full px-[10px] py-[3px]"
                  style={{
                    backgroundColor: STATUS_COLOR[conv.status as ConversationStatus].bg,
                  }}
                >
                  <span
                    className="h-[6px] w-[6px] rounded-full"
                    style={{ backgroundColor: STATUS_COLOR[conv.status as ConversationStatus].text }}
                  />
                  <span
                    className="text-[12px] font-medium"
                    style={{ color: STATUS_COLOR[conv.status as ConversationStatus].text }}
                  >
                    {STATUS_LABEL[conv.status as ConversationStatus]}
                  </span>
                </span>

                <span className="text-[16px] font-bold text-[var(--text-primary)]">
                  {conv.display_name || "—"}
                </span>
              </>
            )}
          </div>
        </header>

        {notFound ? (
          <div className="flex flex-1 items-center justify-center text-sm text-[var(--text-secondary)]">
            找不到此對話
          </div>
        ) : error ? (
          <div className="m-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : (
          <div className="flex flex-1 overflow-hidden">
            <div className="flex flex-1 flex-col overflow-hidden">
              {conv?.status === "waiting_human" && (
                <div className="flex items-center gap-2 border-b border-[#FECACA] bg-[#FEF2F2] px-4 py-2 text-[13px] font-medium text-[#B91C1C]">
                  <Headphones className="h-4 w-4" />
                  接管模式：此對話已升級為人工，您發送的訊息將直接推送給用戶
                </div>
              )}

              <div className="flex flex-1 overflow-hidden">
                <ChatTimeline messages={messages} loading={loading} />
              </div>

              <HandoverComposer
                conversationId={id}
                tenantId={tenantId}
                enabled={conv?.status === "waiting_human"}
                onSent={(msg) =>
                  // messages 由 API 以 DESC 回傳（新→舊），ChatTimeline 內部
                  // reverse 為 ASC 顯示。新送出的訊息應 prepend 到 DESC 列表
                  // 最前端，才能在 ASC timeline 底部正確呈現。
                  setMessages((prev) => [msg, ...prev])
                }
              />
            </div>

            <aside className="flex w-[380px] flex-col gap-4 overflow-auto border-l border-[var(--border)] bg-[var(--bg-surface)] p-6">
              <DiagnosticReasoningPanel conversationId={id} />

              <div className="flex flex-col gap-3 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-4">
                <h3 className="text-[14px] font-semibold text-[#18181B]">客戶資訊</h3>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">顯示名稱</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv?.display_name || "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">LINE ID</span>
                    <span className="font-mono text-[12px] text-[#71717A]">
                      {conv?.line_user_id ? conv.line_user_id.slice(0, 12) + "…" : "—"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-3 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-4">
                <h3 className="text-[14px] font-semibold text-[#18181B]">對話資訊</h3>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">狀態</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv ? STATUS_LABEL[conv.status as ConversationStatus] : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">訊息數</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv?.message_count ?? "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">解決層級</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv?.resolution_layer
                        ? RESOLUTION_LABEL[conv.resolution_layer] ?? "—"
                        : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">建立時間</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv ? formatRelative(conv.created_at) : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">最後更新</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv ? formatRelative(conv.updated_at) : "—"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-3 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-[14px] font-semibold text-[#18181B]">關聯問題卡</h3>
                  {problemCards.length > 0 && (
                    <span className="text-[12px] text-[#A1A1AA]">
                      {problemCards.length} 張
                    </span>
                  )}
                </div>

                {pcError && (
                  <div className="rounded border border-red-200 bg-red-50 px-2 py-1 text-[11px] text-red-700">
                    載入失敗：{pcError}
                  </div>
                )}

                {pcLoading && problemCards.length === 0 && !pcError && (
                  <span className="text-[12px] text-[#A1A1AA]">載入中…</span>
                )}

                {!pcLoading && problemCards.length === 0 && !pcError && (
                  <div className="flex flex-col items-start gap-2">
                    <span className="text-[12px] text-[#A1A1AA]">
                      尚未建立問題卡
                    </span>
                    <button
                      onClick={() => {
                        setCreatePcError(null);
                        setShowCreatePc(true);
                      }}
                      className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-[6px] text-[12px] font-semibold text-white transition hover:opacity-90"
                    >
                      <Plus className="h-3 w-3" />
                      建立問題卡
                    </button>
                  </div>
                )}

                {problemCards.map((pc) => {
                  const style = PC_STATUS_LABEL[pc.status];
                  return (
                    <Link
                      key={pc.id}
                      href={`/problem-cards/${pc.id}`}
                      className="flex flex-col gap-1 rounded-md border border-[var(--border)] px-3 py-2 hover:bg-[#F8FAFC]"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[12px] font-semibold text-[var(--primary)]" title={pc.id}>
                          {pc.id.slice(0, 8)}
                        </span>
                        <span
                          className="rounded-full px-2 py-[1px] text-[11px] font-semibold"
                          style={{ color: style.color, backgroundColor: style.bg }}
                        >
                          {style.label}
                        </span>
                      </div>
                      <span className="text-[12px] text-[#18181B]">
                        {pc.brand || "—"} {pc.model || ""}
                      </span>
                      <span className="line-clamp-2 text-[11px] text-[#71717A]">
                        {pc.symptom || "（無症狀描述）"}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </aside>
          </div>
        )}
      </div>

      {showCreatePc && (
        <CreateProblemCardModal
          conversationId={id}
          pending={creatingPc}
          error={createPcError}
          onCancel={() => {
            if (creatingPc) return;
            setShowCreatePc(false);
            setCreatePcError(null);
          }}
          onSubmit={handleCreatePc}
        />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}

function CreateProblemCardModal({
  conversationId,
  pending,
  error,
  onCancel,
  onSubmit,
}: {
  conversationId: string;
  pending: boolean;
  error: string | null;
  onCancel: () => void;
  onSubmit: (req: ProblemCardCreateRequest) => void;
}) {
  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [symptom, setSymptom] = useState("");
  const [urgency, setUrgency] = useState<Urgency>("medium");
  const [category, setCategory] = useState("");
  const [location, setLocation] = useState("");

  const handleSubmit = () => {
    if (!brand.trim()) {
      alert("請填寫品牌");
      return;
    }
    if (!model.trim()) {
      alert("請填寫型號");
      return;
    }
    if (!symptom.trim()) {
      alert("請填寫症狀描述");
      return;
    }
    const req: ProblemCardCreateRequest = {
      conversation_id: conversationId,
      brand: brand.trim(),
      model: model.trim(),
      symptom: symptom.trim(),
      urgency,
    };
    if (category.trim()) req.category = category.trim();
    if (location.trim()) req.location = location.trim();
    onSubmit(req);
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-[480px] max-h-[90vh] overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center gap-2">
          <Plus className="h-5 w-5 text-[var(--primary)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            建立問題卡
          </span>
        </div>

        <p className="mb-4 text-[12px] text-[var(--text-secondary)]">
          將此對話手動建立為問題卡（每個對話最多一張，狀態起始為「草稿」）。
        </p>

        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <FieldLabel label="品牌" required>
              <input
                type="text"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                disabled={pending}
                maxLength={50}
                placeholder="例：Yale"
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
              />
            </FieldLabel>
            <FieldLabel label="型號" required>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={pending}
                maxLength={100}
                placeholder="例：YDM-4109"
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
              />
            </FieldLabel>
          </div>

          <FieldLabel label="症狀描述" required>
            <textarea
              value={symptom}
              onChange={(e) => setSymptom(e.target.value)}
              disabled={pending}
              maxLength={1000}
              rows={3}
              placeholder="例：電池電量低、無法解鎖（多項以「、」分隔）"
              className="w-full resize-none rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
            />
          </FieldLabel>

          <FieldLabel label="緊急度" required>
            <select
              value={urgency}
              onChange={(e) => setUrgency(e.target.value as Urgency)}
              disabled={pending}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
            >
              {URGENCY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </FieldLabel>

          <div className="grid grid-cols-2 gap-3">
            <FieldLabel label="類別（選填）">
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={pending}
                maxLength={100}
                placeholder="例：電池 / WiFi / 密碼"
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
              />
            </FieldLabel>
            <FieldLabel label="地點（選填）">
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                disabled={pending}
                maxLength={255}
                placeholder="例：台北市中山區"
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
              />
            </FieldLabel>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            type="button"
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={pending}
            type="button"
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "建立中…" : "確認建立"}
          </button>
        </div>
      </div>
    </div>
  );
}

function FieldLabel({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[12px] font-medium text-[var(--text-secondary)]">
        {label}
        {required && <span className="ml-[2px] text-[var(--status-danger)]">*</span>}
      </span>
      {children}
    </div>
  );
}
