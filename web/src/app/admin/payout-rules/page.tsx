"use client";

import { useEffect, useState } from "react";
import { Banknote } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api, tenantPath } from "@/lib/api";

interface PayoutRule {
  rule_id: string;
  service_code: string;
  service_name: string;
  level_id: string;
  base_payout: string | number | null;
  night_surcharge_pct: string | number | null;
  urgent_surcharge_pct: string | number | null;
  currency: string | null;
  effective_date: string | null;
  decision_status: string | null;
  is_mock: boolean;
}
interface Resp {
  data: PayoutRule[];
  cost_visible: boolean;
  note: string;
}

function pct(v: string | number | null): string {
  if (v == null) return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return "—";
  return `${Math.round(n * 100)}%`;
}
function money(v: string | number | null, cur: string | null): string {
  if (v == null) return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return "—";
  return `${cur || "NT$"} ${n.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}`;
}

export default function PayoutRulesPage() {
  const [resp, setResp] = useState<Resp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<Resp>(tenantPath("/payout-rules"));
        if (!cancelled) setResp(res);
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? `${e.errorCode} (${e.status})：${e.message}` : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <Banknote className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">師傅拆帳規則</h1>
          {resp?.data?.some((r) => r.is_mock) && (
            <span className="rounded bg-[#FEF3C7] px-2 py-[2px] text-[11px] text-[#92400E]">示意資料</span>
          )}
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          )}
          {!resp ? (
            <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
          ) : resp.data.length === 0 ? (
            <p className="text-sm text-[var(--text-disabled)]">尚無拆帳規則</p>
          ) : (
            <>
              <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">服務代碼</th>
                      <th className="px-3 py-2 text-left">服務名稱</th>
                      <th className="px-3 py-2 text-left">等級</th>
                      {resp.cost_visible && <th className="px-3 py-2 text-right">基本拆帳</th>}
                      <th className="px-3 py-2 text-right">夜間加成</th>
                      <th className="px-3 py-2 text-right">急件加成</th>
                      <th className="px-3 py-2 text-left">生效日</th>
                      <th className="px-3 py-2 text-left">狀態</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resp.data.map((r) => (
                      <tr key={r.rule_id} className="border-t border-[var(--border)]">
                        <td className="px-3 py-2 font-mono text-[12px] text-[var(--text-secondary)]">{r.service_code}</td>
                        <td className="px-3 py-2 text-[var(--text-primary)]">{r.service_name}</td>
                        <td className="px-3 py-2 text-[var(--text-secondary)]">{r.level_id}</td>
                        {resp.cost_visible && (
                          <td className="px-3 py-2 text-right font-mono font-medium text-[var(--text-primary)]">
                            {money(r.base_payout, r.currency)}
                          </td>
                        )}
                        <td className="px-3 py-2 text-right">{pct(r.night_surcharge_pct)}</td>
                        <td className="px-3 py-2 text-right">{pct(r.urgent_surcharge_pct)}</td>
                        <td className="px-3 py-2 text-[var(--text-secondary)]">{r.effective_date?.slice(0, 10) || "—"}</td>
                        <td className="px-3 py-2">
                          <span className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] text-[var(--text-secondary)]">
                            {r.decision_status || "—"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!resp.cost_visible && (
                <p className="mt-2 text-[11px] text-[var(--text-disabled)]">基本拆帳金額僅後台財務角色可見。</p>
              )}
              <p className="mt-2 text-[12px] text-[var(--text-disabled)]">{resp.note}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
