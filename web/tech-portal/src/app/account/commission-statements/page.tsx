"use client";

/**
 * 派工獎金對帳單。
 *
 * UAT P2-5：對齊新端點 GET /api/v1/technicians/me/commission-statements
 * → {"data":{"items":[{period, gross_amount, commission_amount, status}]}}。
 * 404 / 錯誤一律顯示「暫無資料」空狀態（原「資料可能已被刪除」誤導文案不再出現）。
 * UAT P2-4：改用師傅站手機殼層 TechShell（底部導航＋返回 /account）。
 */

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import { api } from "@/lib/api";
import { formatNTD } from "@/lib/format";
import {
  STATEMENT_STATUS_LABEL,
  STATEMENT_STATUS_COLOR,
  type BadgeColor,
} from "@/components/phase-ii";

/** 新端點回傳項目（api/v1 technicians/me 範疇）。 */
interface CommissionStatementItem {
  period: string;
  gross_amount: string | number | null;
  commission_amount: string | number | null;
  status: string;
}

const STATUS_BG: Record<BadgeColor, { bg: string; text: string }> = {
  red: { bg: "#fef0ef", text: "#d70015" },
  orange: { bg: "#fff4e5", text: "#c5510b" },
  yellow: { bg: "#fef9c3", text: "#854d0e" },
  green: { bg: "#e8f5e9", text: "#15803d" },
  blue: { bg: "#dbeafe", text: "#1e3a8a" },
  purple: { bg: "#ede9fe", text: "#5b21b6" },
  gray: { bg: "#f4f4f5", text: "#52525b" },
};

export default function MyCommissionStatementsPage() {
  const [items, setItems] = useState<CommissionStatementItem[]>([]);
  const [loading, setLoading] = useState(false);

  async function fetchStatements() {
    setLoading(true);
    try {
      const res = await api.get<{
        data?: { items?: CommissionStatementItem[] };
      }>("/api/v1/technicians/me/commission-statements");
      setItems(res.data?.items ?? []);
    } catch {
      // UAT P2-5：端點未就緒（404）或其他錯誤 → 一律空狀態「暫無資料」，
      // 不顯示「資料可能已被刪除」等誤導文案。
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStatements();
  }, []);

  function renderBadge(status: string) {
    const color =
      (STATEMENT_STATUS_COLOR as Record<string, BadgeColor>)[status] ?? "gray";
    const sty = STATUS_BG[color];
    const label =
      (STATEMENT_STATUS_LABEL as Record<string, string>)[status] ?? status;
    return (
      <span
        className="whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium"
        style={{ backgroundColor: sty.bg, color: sty.text }}
      >
        {label}
      </span>
    );
  }

  return (
    <TechShell
      // 頁首走 shell 統一規格(h-14 bar;返回 /account)
      backHref="/account"
      title="派工獎金"
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
          每月派工獎金結算明細；金額有疑問請聯絡管理員。
        </p>

        {loading && items.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
            載入中…
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-40 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] text-[13px] text-[var(--text-secondary)]">
            暫無資料
          </div>
        ) : (
          items.map((s) => (
            <article
              key={s.period}
              className="flex flex-col gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]"
            >
              <div className="flex items-center justify-between">
                <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                  {s.period}
                </span>
                {renderBadge(s.status)}
              </div>
              <div className="grid grid-cols-2 gap-2 text-[13px]">
                <div>
                  <span className="block text-[11px] text-[var(--text-disabled)]">
                    毛額
                  </span>
                  <span className="font-medium text-[var(--text-primary)]">
                    {formatNTD(s.gross_amount)}
                  </span>
                </div>
                <div>
                  <span className="block text-[11px] text-[var(--text-disabled)]">
                    獎金
                  </span>
                  <span className="font-bold text-[#059669]">
                    {formatNTD(s.commission_amount)}
                  </span>
                </div>
              </div>
            </article>
          ))
        )}
      </div>
    </TechShell>
  );
}
