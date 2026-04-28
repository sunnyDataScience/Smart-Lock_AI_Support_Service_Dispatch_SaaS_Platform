"use client";

import { useEffect, useMemo, useState } from "react";
import { Image as ImageIcon, ChevronDown, RefreshCw } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import DisputesTable from "@/components/admin/DisputesTable";
import { ApiError, api } from "@/lib/api";
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

          <div className="rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
            列表為 listDisputes 即時資料；類型 chips 為視覺索引（尚未連動 dispute_type filter）。
            雙方證據面板與調解處理表單為示意 UI，待 submitDisputeResolution 寫入 endpoint
            與證據檔案上傳路徑上線後接入；證據縮圖暫不渲染。
          </div>

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
            </div>
          )}

          {/* Evidence Panel — UI 示意（待證據上傳路徑上線） */}
          <div className="flex overflow-hidden rounded-lg border-l-4 border-l-[#BFDBFE] bg-[var(--bg-surface)] opacity-90">
            <div className="flex flex-1 flex-col gap-3 p-5">
              <div className="flex items-center justify-between">
                <span className="text-[15px] font-semibold text-[#2563EB]">
                  客戶方證據
                </span>
                <span className="text-[11px] text-[var(--text-disabled)]">
                  {selected ? `${evidenceItems(selected.evidence, "customer").length} 件（縮圖即將推出）` : "—"}
                </span>
              </div>
              <div className="flex gap-[10px]">
                <ImagePlaceholder />
                <ImagePlaceholder />
              </div>
              <p className="text-[13px] leading-[1.5] text-[var(--text-disabled)]">
                證據縮圖渲染待媒體上傳路徑上線後接入。
              </p>
            </div>

            <div className="w-px bg-[var(--border)]" />

            <div className="flex flex-1 flex-col gap-3 p-5">
              <div className="flex items-center justify-between">
                <span className="text-[15px] font-semibold text-[#D97706]">
                  技師方證據
                </span>
                <span className="text-[11px] text-[var(--text-disabled)]">
                  {selected ? `${evidenceItems(selected.evidence, "technician").length} 件（縮圖即將推出）` : "—"}
                </span>
              </div>
              <div className="flex gap-[10px]">
                <ImagePlaceholder />
                <ImagePlaceholder />
              </div>
              <p className="text-[13px] leading-[1.5] text-[var(--text-disabled)]">
                證據縮圖渲染待媒體上傳路徑上線後接入。
              </p>
            </div>
          </div>

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
    </div>
  );
}
