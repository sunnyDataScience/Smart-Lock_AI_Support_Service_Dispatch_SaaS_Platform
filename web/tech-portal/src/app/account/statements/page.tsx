"use client";

/**
 * 技師薪資對帳單（含申訴期限提示）。
 *
 * 對應 backend: GET /tenants/{tid}/tech-statements?technician_id={technicians.id}
 * UAT P2-4：改用師傅站手機殼層 TechShell（底部導航＋返回 /account），
 * 桌面殼層 Sidebar 與 FR- 內部規格文字不再對使用者露出。
 */

import { useEffect, useState } from "react";
import { RefreshCw, AlertTriangle } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import {
  type TechStatement,
  STATEMENT_STATUS_LABEL,
  STATEMENT_STATUS_COLOR,
  formatDecimal,
  daysUntilDeadline,
  type BadgeColor,
} from "@/components/phase-ii";

const STATUS_BG: Record<BadgeColor, { bg: string; text: string }> = {
  red: { bg: "#fef0ef", text: "#d70015" },
  orange: { bg: "#fff4e5", text: "#c5510b" },
  yellow: { bg: "#fef9c3", text: "#854d0e" },
  green: { bg: "#e8f5e9", text: "#15803d" },
  blue: { bg: "#dbeafe", text: "#1e3a8a" },
  purple: { bg: "#ede9fe", text: "#5b21b6" },
  gray: { bg: "#f4f4f5", text: "#52525b" },
};

function formatError(e: unknown): string {
  return friendlyError(e);
}

export default function MyStatementsPage() {
  const [items, setItems] = useState<TechStatement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchStatements() {
    setLoading(true);
    setError(null);
    try {
      // 對帳單路由為 /tenants/{tid}/tech-statements?technician_id=（technicians.id）。
      // 先取 profile 拿 technician_id（JWT sub 為 user_id，非 technicians.id）。
      const profile = await api.get<{ data?: { id: string } }>(
        "/api/v1/technicians/me",
      );
      const techId = profile.data?.id;
      const res = await api.get<TechStatement[] | { items: TechStatement[] }>(
        tenantPath("/tech-statements"),
        techId ? { query: { technician_id: techId } } : undefined,
      );
      const list = Array.isArray(res) ? res : res.items ?? [];
      setItems(list);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStatements();
  }, []);

  function renderStatusBadge(status: TechStatement["status"]) {
    const color = STATEMENT_STATUS_COLOR[status];
    const sty = STATUS_BG[color];
    return (
      <span
        className="whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium"
        style={{ backgroundColor: sty.bg, color: sty.text }}
      >
        {STATEMENT_STATUS_LABEL[status]}
      </span>
    );
  }

  function renderDeadline(s: TechStatement) {
    if (s.status !== "pending_review" && s.status !== "disputed") return null;
    const days = daysUntilDeadline(s.dispute_window_ends_at);
    if (days === null) return null;
    if (days < 0)
      return <span className="text-[12px] italic text-[var(--text-disabled)]">申訴已截止</span>;
    const color =
      days < 3 ? "text-red-600" : days < 7 ? "text-orange-600" : "text-[var(--text-secondary)]";
    return (
      <span className={`text-[12px] font-medium ${color}`}>
        申訴期限剩 {days} 天
      </span>
    );
  }

  return (
    <TechShell
      // 頁首走 shell 統一規格(h-14 bar;返回 /account)
      backHref="/account"
      title="薪資對帳單"
      actions={
        <button
          type="button"
          onClick={fetchStatements}
          disabled={loading}
          className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          title="重新整理"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      }
    >
      <div className="flex flex-col gap-3 px-4 py-4">
        <p className="text-[12px] text-[var(--text-secondary)]">
          每月薪資結算明細；金額有疑問可於申訴期限內聯絡管理員。
        </p>

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
            {error}
          </div>
        )}

        {loading && items.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
            載入中…
          </div>
        ) : items.length === 0 && !error ? (
          <div className="flex h-40 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] text-[13px] text-[var(--text-secondary)]">
            暫無資料
          </div>
        ) : (
          // 手機以卡片列呈現（表格橫向塞不下）
          items.map((s) => {
            const totalDeduction =
              Number(s.travel_fee_deduction) +
              Number(s.cash_collection_deduction) +
              Number(s.dispute_hold_amount) +
              Number(s.other_deductions);
            return (
              <article
                key={s.id}
                className="flex flex-col gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                    {s.period_year} / {String(s.period_month).padStart(2, "0")}
                  </span>
                  {renderStatusBadge(s.status)}
                </div>
                <div className="grid grid-cols-2 gap-2 text-[13px]">
                  <div>
                    <span className="block text-[11px] text-[var(--text-disabled)]">
                      完工數
                    </span>
                    <span className="font-medium text-[var(--text-primary)]">
                      {s.total_completed_orders}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-[var(--text-disabled)]">
                      毛額
                    </span>
                    <span className="font-medium text-[var(--text-primary)]">
                      {formatDecimal(s.gross_amount)}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-[var(--text-disabled)]">
                      扣項
                    </span>
                    <span className="font-medium text-orange-600">
                      −{formatDecimal(String(totalDeduction))}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-[var(--text-disabled)]">
                      淨額
                    </span>
                    <span className="font-bold text-[#059669]">
                      {formatDecimal(s.net_amount)}
                    </span>
                  </div>
                </div>
                {renderDeadline(s)}
              </article>
            );
          })
        )}

        {items.some((s) => s.status === "disputed") && (
          <div className="flex items-start gap-2 rounded-2xl border border-orange-200 bg-orange-50 p-3 text-[13px] text-orange-800">
            <AlertTriangle size={18} className="mt-0.5 flex-shrink-0" />
            <div>
              您有申訴中的對帳單。管理員審核完成前金額暫不撥款，您仍可透過聯絡管理員補充佐證。
            </div>
          </div>
        )}
      </div>
    </TechShell>
  );
}
