"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Image as ImageIcon, ChevronDown, RefreshCw, Upload } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import DisputesTable from "@/components/admin/DisputesTable";
import MediaGallery from "@/components/work-orders/MediaGallery";
import RealtimeIndicator from "@/components/realtime/RealtimeIndicator";
import { ApiError, api } from "@/lib/api";
import { useRealtimeChannel } from "@/lib/useRealtimeChannel";
import type { components } from "@/types/api.generated";

type Dispute = components["schemas"]["Dispute"];
type DisputePage = components["schemas"]["DisputePage"];
type DisputeStatus = components["schemas"]["DisputeStatus"];
type DisputeType = components["schemas"]["DisputeType"];

interface StatusTab {
  label: string;
  value: DisputeStatus | "all";
}

const statusTabs: StatusTab[] = [
  { label: "全部", value: "all" },
  { label: "待處理", value: "filed" },
  { label: "調解中", value: "in_review" },
  { label: "已結案", value: "resolved" },
  { label: "已駁回", value: "rejected" },
];

const typeBadges: { value: DisputeType; label: string; textColor: string; bgColor: string }[] = [
  { value: "pricing", label: "價格", textColor: "#2563EB", bgColor: "#DBEAFE" },
  { value: "quality", label: "品質", textColor: "#7C3AED", bgColor: "#EDE9FE" },
  { value: "warranty", label: "保固", textColor: "#059669", bgColor: "#D1FAE5" },
  { value: "cancellation_fee", label: "取消費", textColor: "#EA580C", bgColor: "#FFEDD5" },
  { value: "settlement", label: "結算", textColor: "#DB2777", bgColor: "#FCE7F3" },
];

function formatTwd(amount: string | null | undefined): string {
  if (!amount) return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function ImagePlaceholder() {
  return (
    <div className="flex h-[90px] w-[120px] items-center justify-center rounded-md bg-[#E2E8F0]">
      <ImageIcon className="h-6 w-6 text-[var(--text-disabled)]" />
    </div>
  );
}

/**
 * 爭議證據面板：上傳（雙方）+ MediaGallery 縮圖瀏覽
 */
function DisputeEvidencePanel({ disputeId }: { disputeId: string }) {
  const [uploading, setUploading] = useState<"customer" | "technician" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const customerInputRef = useRef<HTMLInputElement>(null);
  const technicianInputRef = useRef<HTMLInputElement>(null);

  async function handleUpload(
    side: "customer" | "technician",
    e: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(side);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append(
        "purpose",
        side === "customer"
          ? "dispute_evidence_customer"
          : "dispute_evidence_technician",
      );
      fd.append("dispute_id", disputeId);
      await api.upload("/api/v1/media", fd);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `${err.errorCode} (${err.status})：${err.message}`
          : err instanceof Error
            ? err.message
            : String(err),
      );
    } finally {
      setUploading(null);
      e.target.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
      <div className="flex items-center justify-between">
        <span className="text-[15px] font-semibold text-[var(--text-primary)]">
          爭議證據
        </span>
        <div className="flex items-center gap-2">
          <input
            ref={customerInputRef}
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={(e) => handleUpload("customer", e)}
          />
          <input
            ref={technicianInputRef}
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={(e) => handleUpload("technician", e)}
          />
          <button
            type="button"
            onClick={() => customerInputRef.current?.click()}
            disabled={uploading !== null}
            className="flex items-center gap-1 rounded-md border border-blue-300 bg-blue-50 px-3 py-1 text-[12px] font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-50"
          >
            <Upload className="h-3 w-3" />
            {uploading === "customer" ? "上傳中…" : "+ 客戶證據"}
          </button>
          <button
            type="button"
            onClick={() => technicianInputRef.current?.click()}
            disabled={uploading !== null}
            className="flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-3 py-1 text-[12px] font-semibold text-amber-700 hover:bg-amber-100 disabled:opacity-50"
          >
            <Upload className="h-3 w-3" />
            {uploading === "technician" ? "上傳中…" : "+ 技師證據"}
          </button>
        </div>
      </div>
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          {error}
        </div>
      )}
      <MediaGallery
        disputeId={disputeId}
        refreshKey={refreshKey}
        title="已上傳證據"
      />
    </div>
  );
}

function evidenceItems(evidence: Dispute["evidence"], side: "customer" | "technician"): unknown[] {
  if (!evidence || typeof evidence !== "object" || Array.isArray(evidence)) return [];
  const node = (evidence as Record<string, unknown>)[side];
  return Array.isArray(node) ? node : [];
}

export default function DisputesPage() {
  const [activeTab, setActiveTab] = useState<StatusTab["value"]>("all");
  const [items, setItems] = useState<Dispute[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Dispute decision modal state
  const [decisionModal, setDecisionModal] = useState<{
    decision: "resolve" | "escalate" | "reject";
  } | null>(null);
  const [decisionResolution, setDecisionResolution] = useState("");
  const [decisionAmount, setDecisionAmount] = useState("");
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  const fetchDisputes = async (status: StatusTab["value"]) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 50 };
      if (status !== "all") query.status = status;
      const res = await api.get<DisputePage>("/api/v1/disputes", { query });
      const newItems: Dispute[] = res.items ?? [];
      setItems(newItems);
      setSelectedId((prev) => (prev && newItems.some((i) => i.id === prev) ? prev : newItems[0]?.id ?? null));
      setUpdatedAt(new Date());
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDisputes(activeTab);
  }, [activeTab]);

  // 訂閱爭議事件，收到後重抓當前 tab
  const { status: rtStatus } = useRealtimeChannel({
    channelPath: "/realtime/disputes",
    onMessage: () => {
      fetchDisputes(activeTab);
    },
  });

  const selected = useMemo(
    () => items.find((i) => i.id === selectedId) ?? null,
    [items, selectedId],
  );

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <div className="flex items-center gap-3">
            <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
              爭議案件處理
            </h1>
            <RealtimeIndicator status={rtStatus} />
            <button
              onClick={() => fetchDisputes(activeTab)}
              disabled={loading}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              title="重新整理"
            >
              <RefreshCw
                className={`h-[14px] w-[14px] text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
              />
            </button>
            <span
              className="flex items-center gap-[6px] rounded-full px-3 py-1 text-xs font-medium"
              style={{
                backgroundColor: error ? "#FEE2E2" : "#DCFCE7",
                color: error ? "#B91C1C" : "#15803D",
              }}
            >
              <span
                className="h-[6px] w-[6px] rounded-full"
                style={{ backgroundColor: error ? "#DC2626" : "#22C55E" }}
              />
              {error ? "連線失敗" : "已連線"}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {updatedAt
                ? `最後更新：${updatedAt.toLocaleTimeString("zh-TW", { hour12: false })}`
                : "—"}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">·</span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              共 {items.length} 筆
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Filter Row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                類型
              </span>
              <div className="flex items-center gap-2">
                {typeBadges.map((badge) => (
                  <span
                    key={badge.value}
                    className="rounded-xl px-3 py-1 text-xs font-medium"
                    style={{
                      color: badge.textColor,
                      backgroundColor: badge.bgColor,
                    }}
                  >
                    {badge.label}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex overflow-hidden rounded-md border border-[var(--border)]">
              {statusTabs.map((tab, idx) => (
                <button
                  key={tab.value}
                  onClick={() => setActiveTab(tab.value)}
                  className={`px-[14px] py-[6px] text-[13px] font-medium ${
                    activeTab === tab.value
                      ? "bg-[var(--primary)] text-white"
                      : "bg-[var(--bg-surface)] text-[var(--text-secondary)]"
                  } ${idx > 0 ? "border-l border-[var(--border)]" : ""}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Dispute Table */}
          <DisputesTable
            items={items}
            loading={loading}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />

          {/* Selected description */}
          {selected && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
              <div className="mb-2 flex items-center gap-2">
                <span className="font-mono text-[12px] font-medium text-[var(--text-secondary)]">
                  {selected.id.slice(0, 8)}
                </span>
                <span className="text-[13px] font-semibold text-[var(--text-primary)]">爭議描述</span>
              </div>
              <p className="text-[13px] leading-[1.6] text-[var(--text-primary)]">
                {selected.description}
              </p>
              {selected.resolution && (
                <div className="mt-3 rounded-md bg-[#F8FAFC] p-3 text-[13px] leading-[1.6] text-[var(--text-secondary)]">
                  <span className="font-semibold text-[var(--text-primary)]">調解結果：</span>
                  {selected.resolution}
                  {selected.resolution_amount && (
                    <span className="ml-2 font-medium text-[var(--text-primary)]">
                      （{formatTwd(selected.resolution_amount)}）
                    </span>
                  )}
                </div>
              )}

              {/* Decision actions（filed/under_review/mediation 才能仲裁） */}
              {selected.status &&
                ["filed", "under_review", "mediation"].includes(
                  selected.status,
                ) && (
                  <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-[var(--border)] pt-4">
                    <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                      仲裁決定：
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setDecisionResolution("");
                        setDecisionAmount("");
                        setDecisionError(null);
                        setDecisionModal({ decision: "resolve" });
                      }}
                      className="rounded-md border border-green-300 bg-green-50 px-3 py-1 text-[12px] font-semibold text-green-700 hover:bg-green-100"
                    >
                      解決
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setDecisionResolution("");
                        setDecisionAmount("");
                        setDecisionError(null);
                        setDecisionModal({ decision: "reject" });
                      }}
                      className="rounded-md border border-amber-300 bg-amber-50 px-3 py-1 text-[12px] font-semibold text-amber-700 hover:bg-amber-100"
                    >
                      拒絕
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setDecisionResolution("");
                        setDecisionAmount("");
                        setDecisionError(null);
                        setDecisionModal({ decision: "escalate" });
                      }}
                      className="rounded-md border border-red-300 bg-red-50 px-3 py-1 text-[12px] font-semibold text-red-700 hover:bg-red-100"
                    >
                      升級
                    </button>
                  </div>
                )}
            </div>
          )}

          {/* Evidence — 上傳 + MediaGallery 雙方並列 */}
          {selected && (
            <DisputeEvidencePanel disputeId={selected.id} />
          )}

          {/* Resolution Form — disabled until submitDisputeResolution */}
          <div className="flex flex-col gap-4 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
            <div className="flex items-center justify-between">
              <span className="text-base font-semibold text-[var(--text-primary)]">
                調解處理
              </span>
              <span className="rounded-full bg-[#F1F5F9] px-3 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                即將推出
              </span>
            </div>

            <div className="flex flex-col gap-[6px]">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                調解備註
              </span>
              <textarea
                disabled
                placeholder="請輸入調解備註內容..."
                className="h-[100px] resize-none cursor-not-allowed rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 py-3 text-[13px] text-[var(--text-disabled)] outline-none placeholder:text-[var(--text-disabled)] opacity-60"
              />
            </div>

            <div className="flex gap-4">
              <div className="flex flex-1 flex-col gap-[6px]">
                <span className="text-[13px] font-medium text-[var(--text-primary)]">
                  調解金額 NT$
                </span>
                <input
                  disabled
                  type="text"
                  defaultValue={selected?.resolution_amount ?? ""}
                  className="h-10 cursor-not-allowed rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-disabled)] outline-none opacity-60"
                />
              </div>
              <div className="flex flex-1 flex-col gap-[6px]">
                <span className="text-[13px] font-medium text-[var(--text-primary)]">
                  調解方式
                </span>
                <button
                  disabled
                  className="flex h-10 cursor-not-allowed items-center justify-between rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60"
                >
                  <span className="text-[13px] text-[var(--text-disabled)]">
                    部分退款
                  </span>
                  <ChevronDown className="h-4 w-4 text-[var(--text-disabled)]" />
                </button>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                disabled
                title="即將推出"
                className="cursor-not-allowed rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] opacity-60"
              >
                儲存草稿
              </button>
              <button
                disabled
                title="即將推出"
                className="cursor-not-allowed rounded-md bg-[var(--primary)] px-5 py-[10px] text-sm font-medium text-white opacity-60"
              >
                確認調解結果
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Dispute decision modal */}
      {decisionModal && selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => !decisionBusy && setDecisionModal(null)}
        >
          <div
            className="w-[480px] rounded-xl bg-white p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-3 text-[16px] font-semibold text-[var(--text-primary)]">
              {decisionModal.decision === "resolve"
                ? "解決爭議"
                : decisionModal.decision === "reject"
                  ? "拒絕爭議申請"
                  : "升級爭議"}
            </h3>
            <p className="mb-3 text-[12px] text-[var(--text-secondary)]">
              dispute #{selected.id.slice(0, 8)} · 此操作將寫入稽核並透過 WS 推送
            </p>

            <label className="mb-3 flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                仲裁結果說明 <span className="text-red-500">*</span>
              </span>
              <textarea
                value={decisionResolution}
                onChange={(e) => setDecisionResolution(e.target.value)}
                rows={4}
                maxLength={2000}
                placeholder="例：經審查證據後，認定...，補償客戶 $500"
                className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
              />
              <span className="text-[10px] text-[var(--text-disabled)]">
                至少 5 字（{decisionResolution.trim().length}/5）
              </span>
            </label>

            {decisionModal.decision !== "escalate" && (
              <label className="mb-3 flex flex-col gap-1">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  調整金額（NT$，正=補償客戶 / 負=扣款；選填）
                </span>
                <input
                  type="number"
                  value={decisionAmount}
                  onChange={(e) => setDecisionAmount(e.target.value)}
                  placeholder="例：500 或 -200"
                  className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
                />
              </label>
            )}

            {decisionError && (
              <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                {decisionError}
              </div>
            )}

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setDecisionModal(null)}
                disabled={decisionBusy}
                className="rounded-md border border-[var(--border)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (decisionResolution.trim().length < 5) {
                    setDecisionError("仲裁結果說明至少 5 字");
                    return;
                  }
                  setDecisionBusy(true);
                  setDecisionError(null);
                  try {
                    const body: Record<string, unknown> = {
                      decision: decisionModal.decision,
                      resolution: decisionResolution.trim(),
                    };
                    if (
                      decisionModal.decision !== "escalate" &&
                      decisionAmount.trim()
                    ) {
                      const amount = parseFloat(decisionAmount);
                      if (!Number.isNaN(amount)) body.resolution_amount = amount;
                    }
                    await api.post(
                      `/api/v1/disputes/${encodeURIComponent(selected.id)}/decision`,
                      body,
                    );
                    setDecisionModal(null);
                    fetchDisputes(activeTab);
                  } catch (e) {
                    setDecisionError(
                      e instanceof ApiError
                        ? `${e.errorCode} (${e.status})：${e.message}`
                        : e instanceof Error
                          ? e.message
                          : String(e),
                    );
                  } finally {
                    setDecisionBusy(false);
                  }
                }}
                disabled={decisionBusy || decisionResolution.trim().length < 5}
                className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-60"
              >
                {decisionBusy ? "處理中…" : "確認"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
