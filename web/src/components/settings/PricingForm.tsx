"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type PricingRule = components["schemas"]["PricingRule"];
type PricingRulePage = components["schemas"]["PricingRulePage"];

const lockTypeLabel: Record<PricingRule["lock_type"], string> = {
  digital_deadbolt: "電子鎖（Deadbolt）",
  smart_lock: "智慧鎖（Smart Lock）",
  padlock: "掛鎖",
  other: "其他",
};

const difficultyLabel: Record<PricingRule["difficulty"], string> = {
  simple: "簡單",
  moderate: "中等",
  complex: "困難",
};

const difficultyColor: Record<
  PricingRule["difficulty"],
  { textColor: string; bgColor: string }
> = {
  simple: { textColor: "#16A34A", bgColor: "#DCFCE7" },
  moderate: { textColor: "#B45309", bgColor: "#FEF3C7" },
  complex: { textColor: "#B91C1C", bgColor: "#FEE2E2" },
};

function formatTwd(amount: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export default function PricingForm() {
  const [items, setItems] = useState<PricingRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<PricingRulePage>(
        "/api/v1/pricing/rules?limit=50",
      );
      setItems(res.items ?? []);
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
    fetchRules();
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-[var(--text-primary)]">
            報價規則 V2.0
          </span>
          <button
            onClick={fetchRules}
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
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          {updatedAt
            ? `最後更新：${updatedAt.toLocaleTimeString("zh-TW", { hour12: false })}`
            : "管理依品牌、鎖型、難度的基礎報價"}
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
        表格為 listPricingRules 即時資料（已過濾停用規則）。新增/編輯/重置按鈕
        待 createPricingRule、updatePricingRule 寫入 endpoints 接入後同步上線。
      </div>

      <div className="overflow-hidden rounded-lg border border-[var(--border)]">
        {/* Table Header */}
        <div className="flex items-center bg-[#F8FAFC] px-4 py-3">
          <div className="w-[140px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              品牌
            </span>
          </div>
          <div className="w-[180px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              鎖型
            </span>
          </div>
          <div className="w-[110px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              難度
            </span>
          </div>
          <div className="flex w-[140px] justify-end">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              基礎價
            </span>
          </div>
          <div className="flex flex-1 justify-center">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              加價條件
            </span>
          </div>
        </div>

        {/* Loading / Empty */}
        {loading && items.length === 0 && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            載入中…
          </div>
        )}
        {!loading && items.length === 0 && !error && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            尚無計價規則
          </div>
        )}

        {/* Data Rows */}
        {items.map((rule) => {
          const diffColor = difficultyColor[rule.difficulty];
          const surcharges = rule.surcharges ?? [];
          return (
            <div
              key={rule.id}
              className="flex items-start border-t border-[var(--border)] px-4 py-3"
            >
              <div className="w-[140px]">
                <span className="text-[13px] font-medium text-[var(--text-primary)]">
                  {rule.brand}
                </span>
              </div>
              <div className="w-[180px]">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  {lockTypeLabel[rule.lock_type] ?? rule.lock_type}
                </span>
              </div>
              <div className="w-[110px]">
                <span
                  className="rounded-md px-2 py-1 text-xs font-semibold"
                  style={{
                    color: diffColor.textColor,
                    backgroundColor: diffColor.bgColor,
                  }}
                >
                  {difficultyLabel[rule.difficulty] ?? rule.difficulty}
                </span>
              </div>
              <div className="flex w-[140px] justify-end">
                <span className="font-['IBM_Plex_Mono'] text-[13px] font-semibold text-[var(--text-primary)]">
                  {formatTwd(rule.base_price)}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-1 pl-4">
                {surcharges.length === 0 && (
                  <span className="text-[12px] text-[var(--text-disabled)]">
                    無加價條件
                  </span>
                )}
                {surcharges.map((s, idx) => (
                  <div
                    key={`${rule.id}-${idx}`}
                    className="flex items-center gap-2 text-[12px]"
                  >
                    <span className="font-medium text-[var(--text-primary)]">
                      {s.name}
                    </span>
                    {s.condition && (
                      <span className="text-[var(--text-secondary)]">
                        ({s.condition})
                      </span>
                    )}
                    <span className="font-['IBM_Plex_Mono'] font-semibold text-[var(--primary)]">
                      +{formatTwd(s.amount)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex justify-end gap-3">
        <button
          disabled
          title="即將推出"
          className="cursor-not-allowed rounded-lg border border-[var(--border)] px-5 py-[10px] opacity-60"
        >
          <span className="text-sm font-medium text-[var(--text-disabled)]">
            重置為預設
          </span>
        </button>
        <button
          disabled
          title="即將推出"
          className="cursor-not-allowed rounded-lg bg-[var(--primary)] px-5 py-[10px] opacity-60"
        >
          <span className="text-sm font-medium text-white">儲存規則</span>
        </button>
      </div>
    </div>
  );
}
