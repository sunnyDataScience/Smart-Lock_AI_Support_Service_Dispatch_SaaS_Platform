"use client";

import { useEffect, useState } from "react";
import { Info, RefreshCw, Search } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import WarrantyClaimsTable from "@/components/admin/WarrantyClaimsTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WarrantyClaim = components["schemas"]["WarrantyClaim"];
type WarrantyClaimPage = components["schemas"]["WarrantyClaimPage"];
type WarrantyClaimStatus = components["schemas"]["WarrantyClaimStatus"];

interface StatusTab {
  label: string;
  value: WarrantyClaimStatus | "all";
}

const statusTabs: StatusTab[] = [
  { label: "全部", value: "all" },
  { label: "已申請", value: "filed" },
  { label: "處理中", value: "in_progress" },
  { label: "已核准", value: "approved" },
  { label: "已拒絕", value: "rejected" },
  { label: "已結案", value: "closed" },
];

export default function WarrantyClaimsPage() {
  const [activeTab, setActiveTab] = useState<StatusTab["value"]>("all");
  const [items, setItems] = useState<WarrantyClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchClaims = async (
    opts?: { append?: boolean; cursor?: string | null; status?: StatusTab["value"] },
  ) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 50 };
      const status = opts?.status ?? activeTab;
      if (status !== "all") query.status = status;
      if (opts?.cursor) query.cursor = opts.cursor;
      const res = await api.get<WarrantyClaimPage>("/api/v1/warranty-claims", { query });
      const newItems = res.items ?? [];
      setItems((prev) => (opts?.append ? [...prev, ...newItems] : newItems));
      setNextCursor(res.next_cursor ?? null);
      setHasMore(res.has_more ?? false);
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
    fetchClaims({ status: activeTab });
  }, [activeTab]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              保固申請管理
            </h1>
            <button
              onClick={() => fetchClaims({ status: activeTab })}
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
              共 {items.length}{hasMore ? "+" : ""} 筆
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex items-center gap-[10px] rounded-lg border border-[#BFDBFE] bg-[#EFF6FF] px-4 py-3">
            <Info className="h-5 w-5 shrink-0 text-[#1D4ED8]" />
            <span className="text-[13px] leading-[1.5] text-[#1D4ED8]">
              保固起算日以「交屋日期」為準，非「入住日期」。此為系統核心規則，所有保固計算均依據此原則。
            </span>
          </div>

          <div className="rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
            列表為 listWarrantyClaims 即時資料；保固期狀態（有效 / 寬限期 / 已過期）由前端依
            warranty_end_date 與 is_within_warranty 即時計算。檢視詳情、核准保固動作待
            warranty 寫入 endpoints 與證據上傳路徑上線後接入；證據縮圖暫不顯示。
          </div>

          <div className="flex items-center justify-between">
            <div className="flex overflow-hidden rounded-lg border border-[var(--border)]">
              {statusTabs.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => setActiveTab(tab.value)}
                  className={`px-4 py-2 text-[13px] font-medium ${
                    activeTab === tab.value
                      ? "bg-[var(--primary)] text-white"
                      : "bg-[var(--bg-surface)] text-[var(--text-secondary)]"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div
              className="flex w-[300px] cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 opacity-60"
              title="即將推出"
            >
              <Search className="h-4 w-4 text-[var(--text-disabled)]" />
              <input
                disabled
                type="text"
                placeholder="搜尋案件編號、設備或客戶..."
                className="flex-1 cursor-not-allowed bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)]"
              />
            </div>
          </div>

          <WarrantyClaimsTable items={items} loading={loading} />

          {hasMore && (
            <div className="flex justify-center">
              <button
                onClick={() => fetchClaims({ append: true, cursor: nextCursor, status: activeTab })}
                disabled={loading}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "載入中…" : "載入更多"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
