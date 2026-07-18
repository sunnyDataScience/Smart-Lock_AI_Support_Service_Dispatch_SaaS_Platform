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
import { useTranslations } from "@/components/i18n/LocaleProvider";

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

// UAT W6-1：label 全數走 i18n（namespace: admin.exceptions）——此處只留值域
const TYPE_VALUES = [
  "no_show", "customer_absent", "scope_change_rejected", "material_shortage",
  "delay_severe", "appearance_refused", "payment_failed", "quality_complaint",
  "schedule_conflict", "other",
] as const;

const RETURN_PATH_VALUES = [
  "continue", "requote", "reschedule", "reassign", "new_wo",
  "cancel", "refund", "rma", "dispute",
] as const;

const STATUS_TABS = ["all", "open", "investigating", "escalated", "resolved", "closed"];
const SEVERITY_VALUES = ["low", "medium", "high", "critical"] as const;
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
  const t = useTranslations("admin.exceptions");
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
      setError(t("selectPathFirst"));
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
            <h1 className="flex items-center gap-2 text-2xl font-semibold text-[var(--text-primary)]">
              <AlertTriangle size={22} className="text-amber-500" />
              {t("title")}
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {t("subtitle")}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowOpen((v) => !v)}
              className="flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <Plus size={16} /> {t("openException")}
            </button>
            <button
              type="button"
              onClick={fetchList}
              disabled={loading}
              className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> {t("refresh")}
            </button>
          </div>
        </header>

        {showOpen && (
          <div className="mb-4 grid grid-cols-1 gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4 md:grid-cols-6">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">{t("fieldType")}</span>
              <select value={newType} onChange={(e) => setNewType(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1.5 text-[var(--text-primary)]">
                {TYPE_VALUES.map((v) => <option key={v} value={v}>{t(`type.${v}`)}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">{t("fieldSeverity")}</span>
              <select value={newSeverity} onChange={(e) => setNewSeverity(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1.5 text-[var(--text-primary)]">
                {SEVERITY_VALUES.map((s) => <option key={s} value={s}>{t(`severity.${s}`)}</option>)}
              </select>
            </label>
            <div className="flex flex-col gap-1 text-sm md:col-span-2">
              <span className="text-[var(--text-secondary)]">{t("fieldWorkOrder")}</span>
              {/* 用公單號 / 客戶名搜尋，回傳工單 UUID；取代原本手貼 UUID（非 UUID 會讓後端 500） */}
              <WorkOrderPicker value={newWo} onChange={setNewWo} />
            </div>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">{t("fieldDescription")}</span>
              <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1.5 text-[var(--text-primary)]" />
            </label>
            <div className="flex items-end">
              <button type="button" onClick={openException} className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">{t("submit")}</button>
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
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${active ? "bg-blue-600 text-white" : "border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] hover:bg-[var(--bg-page)]"}`}
              >
                {t(`status.${s}`)}
              </button>
            );
          })}
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        {/* UAT W6-4 同型修正：表格外層可橫捲 */}
        <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-[var(--bg-page)] text-left text-xs uppercase text-[var(--text-secondary)]">
              <tr>
                <th className="px-4 py-3">{t("cols.type")}</th>
                <th className="px-4 py-3">{t("cols.severity")}</th>
                <th className="px-4 py-3">{t("cols.status")}</th>
                <th className="px-4 py-3">{t("cols.workOrder")}</th>
                <th className="px-4 py-3">{t("cols.description")}</th>
                <th className="px-4 py-3">{t("cols.createdAt")}</th>
                <th className="px-4 py-3">{t("cols.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {items.length === 0 && !loading && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-[var(--text-disabled)]">{t("empty")}</td></tr>
              )}
              {items.map((it) => {
                const sev = SEVERITY_BG[it.severity] ?? SEVERITY_BG.low;
                const done = it.status === "resolved" || it.status === "closed";
                // 高/緊急 + 有關聯工單 + 仍處理中 → 工單已被暫停（high_risk_hold），以徽章顯示
                const holdActive = !done && (it.severity === "high" || it.severity === "critical") && !!it.work_order_id;
                const typeLabel = (TYPE_VALUES as readonly string[]).includes(it.exception_type)
                  ? t(`type.${it.exception_type}`)
                  : it.exception_type;
                const statusLabel = STATUS_TABS.includes(it.status)
                  ? t(`status.${it.status}`)
                  : it.status;
                const severityLabel = (SEVERITY_VALUES as readonly string[]).includes(it.severity)
                  ? t(`severity.${it.severity}`)
                  : it.severity;
                return (
                  <tr key={it.id}>
                    <td className="px-4 py-3 font-medium text-[var(--text-primary)]">{typeLabel}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: sev.bg, color: sev.text }}>
                        {severityLabel}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">
                      <div className="flex flex-col gap-1">
                        <span>{statusLabel}</span>
                        {holdActive && (
                          <span className="inline-flex w-fit items-center gap-1 rounded-full bg-[#fef0ef] px-2 py-0.5 text-[11px] font-medium text-[#d70015]">
                            <PauseCircle size={11} /> {t("holdBadge")}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {it.work_order_no ? (
                        <span className="font-mono font-medium text-[var(--text-primary)]">{it.work_order_no}</span>
                      ) : it.work_order_id ? (
                        <span className="font-mono text-[var(--text-disabled)]">{it.work_order_id.slice(0, 8)}</span>
                      ) : (
                        <span className="text-[var(--text-disabled)]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">
                      {done && it.return_path
                        ? <span className="text-green-700">→ {(RETURN_PATH_VALUES as readonly string[]).includes(it.return_path) ? t(`returnPath.${it.return_path}`) : it.return_path}</span>
                        : (it.description || "—")}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">{it.created_at ? new Date(it.created_at).toLocaleString("zh-TW") : "—"}</td>
                    <td className="px-4 py-3">
                      {done ? (
                        <span className="text-xs text-[var(--text-disabled)]">{t("closedTag")}</span>
                      ) : (
                        <div className="flex items-center gap-2">
                          <select
                            value={resolvePath[it.id] ?? ""}
                            onChange={(e) => setResolvePath((m) => ({ ...m, [it.id]: e.target.value }))}
                            className="rounded border border-[var(--border)] bg-[var(--bg-surface)] px-1.5 py-1 text-xs text-[var(--text-primary)]"
                          >
                            <option value="">{t("pathPlaceholder")}</option>
                            {RETURN_PATH_VALUES.map((v) => <option key={v} value={v}>{t(`returnPath.${v}`)}</option>)}
                          </select>
                          <button type="button" onClick={() => resolveException(it.id)} className="rounded bg-green-600 px-2 py-1 text-xs font-medium text-white hover:bg-green-700">{t("resolve")}</button>
                          <button type="button" onClick={() => escalateException(it.id)} className="rounded border border-[var(--border)] px-2 py-1 text-xs text-[var(--text-primary)] hover:bg-[var(--bg-page)]">{t("escalate")}</button>
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
