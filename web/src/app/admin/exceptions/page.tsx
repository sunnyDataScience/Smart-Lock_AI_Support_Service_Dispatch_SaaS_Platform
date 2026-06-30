"use client";

/**
 * CR-0041 M15 異常管理（exception_case control tower）。
 *
 * backend: GET/POST /tenants/{tid}/exception-cases；POST .../{id}:resolve|:escalate
 * 列出異常、開立、選 return_path 處理、升級。high/critical 會在工單設 high_risk_hold（擋派工/完工）。
 */

import { useEffect, useState } from "react";
import { RefreshCw, Plus, AlertTriangle, PauseCircle } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import WorkOrderPicker from "@/components/quotes/WorkOrderPicker";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

type ExceptionCase = {
  id: string;
  work_order_id: string | null;
  work_order_no: string | null; // 後端 LEFT JOIN work_orders 帶的公單號（顯示用，免露 UUID）
  exception_type: string;
  status: string;
  severity: string;
  description: string | null;
  return_path: string | null;
  resolution: string | null;
  created_at: string | null;
};

const TYPE_LABEL: Record<string, string> = {
  no_show: "放鴿子",
  customer_absent: "客戶不在",
  scope_change_rejected: "加價拒絕",
  material_shortage: "缺料",
  delay_severe: "嚴重延遲",
  appearance_refused: "拒絕施工",
  payment_failed: "付款失敗",
  quality_complaint: "品質客訴",
  schedule_conflict: "排班衝突",
  other: "其他",
};

const RETURN_PATHS: { value: string; label: string }[] = [
  { value: "continue", label: "繼續施工" },
  { value: "requote", label: "重報價" },
  { value: "reschedule", label: "改期" },
  { value: "reassign", label: "改派" },
  { value: "new_wo", label: "開新工單" },
  { value: "cancel", label: "取消" },
  { value: "refund", label: "退款" },
  { value: "rma", label: "客訴 RMA" },
  { value: "dispute", label: "爭議" },
];

const STATUS_TABS = ["all", "open", "investigating", "escalated", "resolved", "closed"];
const STATUS_LABEL: Record<string, string> = {
  all: "全部",
  open: "開立",
  investigating: "處理中",
  escalated: "已升級",
  resolved: "已處理",
  closed: "已關閉",
};
const SEVERITY_LABEL: Record<string, string> = {
  low: "低", medium: "中", high: "高", critical: "緊急",
};
const SEVERITY_BG: Record<string, { bg: string; text: string }> = {
  critical: { bg: "#fef0ef", text: "#d70015" },
  high: { bg: "#fff4e5", text: "#c5510b" },
  medium: { bg: "#fef9c3", text: "#854d0e" },
  low: { bg: "#f4f4f5", text: "#52525b" },
};

function formatError(e: unknown): string {
  return friendlyError(e);
}

export default function ExceptionsPage() {
  const [items, setItems] = useState<ExceptionCase[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [showOpen, setShowOpen] = useState(false);

  // open form
  const [newType, setNewType] = useState("material_shortage");
  const [newSeverity, setNewSeverity] = useState("medium");
  const [newWo, setNewWo] = useState("");
  const [newDesc, setNewDesc] = useState("");

  // per-row resolve state
  const [resolvePath, setResolvePath] = useState<Record<string, string>>({});

  async function fetchList() {
    setLoading(true);
    setError(null);
    try {
      const q = statusFilter === "all" ? "?limit=100" : `?status=${statusFilter}&limit=100`;
      const res = await api.get<{ items: ExceptionCase[]; total: number }>(
        tenantPath(`/exception-cases${q}`),
      );
      setItems(res.items ?? []);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function openException() {
    setError(null);
    try {
      await api.post(tenantPath("/exception-cases"), {
        exception_type: newType,
        severity: newSeverity,
        work_order_id: newWo.trim() || null,
        description: newDesc.trim() || null,
      });
      setShowOpen(false);
      setNewWo("");
      setNewDesc("");
      await fetchList();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function resolveException(id: string) {
    const rp = resolvePath[id];
    if (!rp) {
      setError("請先選擇處理方式（return_path）");
      return;
    }
    setError(null);
    try {
      await api.post(tenantPath(`/exception-cases/${encodeURIComponent(id)}:resolve`), {
        return_path: rp,
      });
      await fetchList();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function escalateException(id: string) {
    setError(null);
    try {
      await api.post(tenantPath(`/exception-cases/${encodeURIComponent(id)}:escalate`), {});
      await fetchList();
    } catch (e) {
      setError(formatError(e));
    }
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold text-gray-900">
              <AlertTriangle size={22} className="text-amber-500" />
              異常管理
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              統一追蹤並處理工單異常：缺料、加價拒絕、取消、爭議、安全風險等。標記為「高 / 緊急」的案件會自動暫停關聯工單，待處理後恢復。
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowOpen((v) => !v)}
              className="flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <Plus size={16} /> 開立異常
            </button>
            <button
              type="button"
              onClick={fetchList}
              disabled={loading}
              className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> 重新整理
            </button>
          </div>
        </header>

        {showOpen && (
          <div className="mb-4 grid grid-cols-1 gap-3 rounded-lg border border-gray-200 bg-white p-4 md:grid-cols-6">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">類型</span>
              <select value={newType} onChange={(e) => setNewType(e.target.value)} className="rounded border border-gray-300 px-2 py-1.5">
                {Object.entries(TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">嚴重度</span>
              <select value={newSeverity} onChange={(e) => setNewSeverity(e.target.value)} className="rounded border border-gray-300 px-2 py-1.5">
                {["low", "medium", "high", "critical"].map((s) => <option key={s} value={s}>{SEVERITY_LABEL[s]}</option>)}
              </select>
            </label>
            <div className="flex flex-col gap-1 text-sm md:col-span-2">
              <span className="text-gray-500">關聯工單（選填）</span>
              {/* 用公單號 / 客戶名搜尋，回傳工單 UUID；取代原本手貼 UUID（非 UUID 會讓後端 500） */}
              <WorkOrderPicker value={newWo} onChange={setNewWo} />
            </div>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">說明</span>
              <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} className="rounded border border-gray-300 px-2 py-1.5" />
            </label>
            <div className="flex items-end">
              <button type="button" onClick={openException} className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">送出</button>
            </div>
          </div>
        )}

        <div className="mb-4 flex flex-wrap gap-2">
          {STATUS_TABS.map((s) => {
            const active = statusFilter === s;
            return (
              <button
                key={s}
                type="button"
                onClick={() => setStatusFilter(s)}
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${active ? "bg-blue-600 text-white" : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"}`}
              >
                {STATUS_LABEL[s]}
              </button>
            );
          })}
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">類型</th>
                <th className="px-4 py-3">嚴重度</th>
                <th className="px-4 py-3">狀態</th>
                <th className="px-4 py-3">工單</th>
                <th className="px-4 py-3">說明 / 處理</th>
                <th className="px-4 py-3">建立時間</th>
                <th className="px-4 py-3">動作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.length === 0 && !loading && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">目前無異常案件</td></tr>
              )}
              {items.map((it) => {
                const sev = SEVERITY_BG[it.severity] ?? SEVERITY_BG.low;
                const done = it.status === "resolved" || it.status === "closed";
                // 高/緊急 + 有關聯工單 + 仍處理中 → 工單已被暫停（high_risk_hold），以徽章顯示
                const holdActive = !done && (it.severity === "high" || it.severity === "critical") && !!it.work_order_id;
                return (
                  <tr key={it.id}>
                    <td className="px-4 py-3 font-medium text-gray-900">{TYPE_LABEL[it.exception_type] ?? it.exception_type}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: sev.bg, color: sev.text }}>
                        {SEVERITY_LABEL[it.severity] ?? it.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      <div className="flex flex-col gap-1">
                        <span>{STATUS_LABEL[it.status] ?? it.status}</span>
                        {holdActive && (
                          <span className="inline-flex w-fit items-center gap-1 rounded-full bg-[#fef0ef] px-2 py-0.5 text-[11px] font-medium text-[#d70015]">
                            <PauseCircle size={11} /> 已暫停工單
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {it.work_order_no ? (
                        <span className="font-mono font-medium text-gray-700">{it.work_order_no}</span>
                      ) : it.work_order_id ? (
                        <span className="font-mono text-gray-400">{it.work_order_id.slice(0, 8)}</span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {done && it.return_path
                        ? <span className="text-green-700">→ {RETURN_PATHS.find((r) => r.value === it.return_path)?.label ?? it.return_path}</span>
                        : (it.description || "—")}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{it.created_at ? new Date(it.created_at).toLocaleString("zh-TW") : "—"}</td>
                    <td className="px-4 py-3">
                      {done ? (
                        <span className="text-xs text-gray-400">已結案</span>
                      ) : (
                        <div className="flex items-center gap-2">
                          <select
                            value={resolvePath[it.id] ?? ""}
                            onChange={(e) => setResolvePath((m) => ({ ...m, [it.id]: e.target.value }))}
                            className="rounded border border-gray-300 px-1.5 py-1 text-xs"
                          >
                            <option value="">處理方式…</option>
                            {RETURN_PATHS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                          </select>
                          <button type="button" onClick={() => resolveException(it.id)} className="rounded bg-green-600 px-2 py-1 text-xs font-medium text-white hover:bg-green-700">處理</button>
                          <button type="button" onClick={() => escalateException(it.id)} className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50">升級</button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
