"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowUpCircle,
  CheckCircle2,
  MapPin,
  RefreshCw,
  Star,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import StatusBadge, { statusLabel } from "@/components/tech/StatusBadge";
import UrgencyBadge from "@/components/tech/UrgencyBadge";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];
type Technician = components["schemas"]["Technician"];
type TechnicianLevel = components["schemas"]["TechnicianLevel"];
type AssignReasonCode = components["schemas"]["WorkOrderAssignRequest"]["reason_code"];

interface Candidate {
  technician?: Technician;
  score?: number;
  distance_km?: number;
  skill_match?: number;
  availability_eta_minutes?: number;
}

interface CandidatesResponse {
  candidates?: Candidate[];
  total?: number;
  auto_dispatch_attempts?: {
    technician_id?: string;
    attempted_at?: string;
    outcome?: "accepted" | "declined" | "timeout";
  }[];
}

const REASON_OPTIONS: { value: AssignReasonCode; label: string }[] = [
  { value: "auto_dispatch_exhausted", label: "自動派工已窮盡" },
  { value: "customer_requested_specific_tech", label: "客戶指名" },
  { value: "skill_shortage_override", label: "技能不足但特殊覆蓋" },
  { value: "sla_rescue", label: "SLA 即將違反強制指派" },
  { value: "other", label: "其他（手填）" },
];

const LEVELS: TechnicianLevel[] = ["S", "A", "B", "C"];

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

export default function DispatchManualPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const workOrderId = searchParams.get("work_order_id") ?? "";

  const [wo, setWo] = useState<WorkOrder | null>(null);
  const [woLoading, setWoLoading] = useState(false);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [totalAvailable, setTotalAvailable] = useState(0);
  const [attempts, setAttempts] = useState<
    NonNullable<CandidatesResponse["auto_dispatch_attempts"]>
  >([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedLevels, setSelectedLevels] = useState<Set<TechnicianLevel>>(
    new Set(["S", "A", "B"]),
  );
  const [excludeCircuit, setExcludeCircuit] = useState(true);
  const [ratingMin, setRatingMin] = useState(0);

  // Selection / sort
  const [sortBy, setSortBy] = useState<"score" | "distance" | "rating">("score");
  const [selectedTechId, setSelectedTechId] = useState<string | null>(null);

  // Modal state
  const [reasonModalOpen, setReasonModalOpen] = useState(false);
  const [reasonCode, setReasonCode] = useState<AssignReasonCode>(
    "auto_dispatch_exhausted",
  );
  const [reasonText, setReasonText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Escalate / cancel state
  const [escalateBusy, setEscalateBusy] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const fetchWorkOrder = useCallback(async () => {
    if (!workOrderId) return;
    setWoLoading(true);
    try {
      const res = await api.get<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(workOrderId)}`,
      );
      setWo(res.data ?? null);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setWoLoading(false);
    }
  }, [workOrderId]);

  const fetchCandidates = useCallback(async () => {
    if (!workOrderId) return;
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number | boolean> = {
        work_order_id: workOrderId,
        exclude_circuit: excludeCircuit,
      };
      if (ratingMin > 0) query.rating_min = ratingMin;
      // Note: levels filter is array; api util encodes as single string;
      // 後端應接受 comma-separated。MVP 用單值不過濾 levels server-side，client-side filter。
      const res = await api.get<CandidatesResponse>(
        "/api/v1/dispatch/candidates",
        { query },
      );
      setCandidates(res.candidates ?? []);
      setTotalAvailable(res.total ?? 0);
      setAttempts(res.auto_dispatch_attempts ?? []);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, [workOrderId, excludeCircuit, ratingMin]);

  useEffect(() => {
    fetchWorkOrder();
    fetchCandidates();
  }, [fetchWorkOrder, fetchCandidates]);

  // Client-side filter + sort
  const filtered = useMemo(() => {
    const filteredList = candidates.filter((c) => {
      if (!c.technician) return false;
      if (!selectedLevels.has(c.technician.level)) return false;
      return true;
    });
    const sorted = [...filteredList].sort((a, b) => {
      if (sortBy === "score") return (b.score ?? 0) - (a.score ?? 0);
      if (sortBy === "distance")
        return (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity);
      return (b.technician?.rating ?? 0) - (a.technician?.rating ?? 0);
    });
    return sorted;
  }, [candidates, selectedLevels, sortBy]);

  const selectedTech = useMemo(
    () => filtered.find((c) => c.technician?.id === selectedTechId)?.technician,
    [filtered, selectedTechId],
  );

  function toggleLevel(level: TechnicianLevel) {
    setSelectedLevels((prev) => {
      const next = new Set(prev);
      if (next.has(level)) next.delete(level);
      else next.add(level);
      return next;
    });
  }

  async function submitAssign() {
    if (!wo || !selectedTechId || submitting) return;
    if (reasonCode === "other" && reasonText.trim().length < 10) {
      setSubmitError("「其他」理由需填 10–500 字");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.post<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(wo.id)}/assign`,
        {
          technician_id: selectedTechId,
          reason_code: reasonCode,
          ...(reasonText.trim() ? { reason_text: reasonText.trim() } : {}),
          override_flags: { allow_circuit: false, allow_cross_area: false },
        },
      );
      setActionMsg(`已指派給 ${selectedTech?.name ?? "技師"}`);
      setReasonModalOpen(false);
      setReasonText("");
      // 返回 A28 派工佇列
      setTimeout(() => router.push("/admin/dispatch-queue"), 1500);
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 409) {
          if (e.errorCode === "TECHNICIAN_CIRCUIT_BREAKER_OPEN") {
            setSubmitError("技師熔斷中，需 operations_manager 雙簽（MVP 待補）");
          } else if (e.errorCode === "WORK_ORDER_CONFLICT") {
            setSubmitError("工單已被其他人指派，請重新整理");
          } else {
            setSubmitError(formatErr(e));
          }
        } else {
          setSubmitError(formatErr(e));
        }
      } else {
        setSubmitError(formatErr(e));
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function escalateOrder() {
    if (!wo || escalateBusy) return;
    const reason = window.prompt("升級至上層覆審的原因（必填）：");
    if (!reason || reason.trim().length === 0) return;
    setEscalateBusy(true);
    try {
      await api.post(
        `/api/v1/work-orders/${encodeURIComponent(wo.id)}/escalate`,
        { level: "operations_manager", reason: reason.trim() },
      );
      setActionMsg("已升級至 operations_manager，等候主管處理");
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setEscalateBusy(false);
    }
  }

  async function cancelOrder() {
    if (!wo || escalateBusy) return;
    if (!window.confirm("確定取消此工單並全額退款？此操作會通知客戶。")) return;
    setEscalateBusy(true);
    try {
      await api.post(`/api/v1/work-orders/${encodeURIComponent(wo.id)}/cancel`, {
        reason: "manual_dispatch_cancel",
      });
      setActionMsg("工單已取消");
      setTimeout(() => router.push("/admin/dispatch-queue"), 1500);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setEscalateBusy(false);
    }
  }

  // -- Render guards --
  if (!workOrderId) {
    return (
      <div className="flex h-full bg-[var(--bg-page)]">
        <Sidebar />
        <div className="flex flex-1 items-center justify-center">
          <div className="rounded-xl border border-[var(--border)] bg-white p-8 text-center shadow-sm">
            <AlertTriangle className="mx-auto h-10 w-10 text-amber-500" />
            <h2 className="mt-3 text-[18px] font-semibold text-[var(--text-primary)]">
              缺少工單參數
            </h2>
            <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
              請從派工佇列監控 (A28) 點「人工介入」進入，或在 URL 加上
              <code className="mx-1 rounded bg-[#F1F5F9] px-1 py-[1px] font-mono text-[12px]">
                ?work_order_id=xxx
              </code>
            </p>
            <Link
              href="/admin/dispatch-queue"
              className="mt-4 inline-block rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#1D4ED8]"
            >
              前往派工佇列
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* Page Header */}
        <div className="flex flex-col gap-1 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 派工管理 &gt; 人工介入
          </span>
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-bold text-[#0F172A]">
              派工人工介入
            </h1>
            <button
              type="button"
              onClick={() => {
                fetchWorkOrder();
                fetchCandidates();
              }}
              disabled={loading || woLoading}
              className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              <RefreshCw
                className={`h-4 w-4 ${loading || woLoading ? "animate-spin" : ""}`}
              />
              重新整理
            </button>
          </div>
        </div>

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-[13px] text-red-700">
            {error}
          </div>
        )}
        {actionMsg && (
          <div className="mx-8 mt-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-[13px] text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            {actionMsg}
          </div>
        )}

        {/* context_panel */}
        <section
          className={`mx-8 mt-4 flex flex-col gap-3 rounded-xl border p-4 shadow-sm ${
            wo?.urgency === "high"
              ? "border-red-200 bg-red-50"
              : "border-[var(--border)] bg-white"
          }`}
        >
          {woLoading ? (
            <div className="text-[13px] text-[var(--text-secondary)]">
              載入工單中…
            </div>
          ) : !wo ? (
            <div className="text-[13px] text-red-700">
              找不到工單 (id: {workOrderId})
            </div>
          ) : (
            <>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
                      工單 #{wo.id.slice(0, 8)}
                    </h2>
                    <StatusBadge status={wo.status} />
                    <UrgencyBadge urgency={wo.urgency} />
                  </div>
                  <p className="mt-1 text-[14px] text-[var(--text-primary)]">
                    {wo.address}
                  </p>
                  <p className="text-[12px] text-[var(--text-secondary)]">
                    {wo.district} · {wo.brand} {wo.model}
                  </p>
                </div>
                <div className="text-right">
                  <span className="block text-[11px] text-[var(--text-disabled)]">
                    已嘗試派工
                  </span>
                  <span className="text-[20px] font-bold text-[var(--text-primary)]">
                    {attempts.length}
                  </span>
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {" "}
                    次
                  </span>
                </div>
              </div>
              {attempts.length > 0 && (
                <details className="rounded-md bg-[#F8FAFC] px-3 py-2 text-[12px] text-[var(--text-secondary)]">
                  <summary className="cursor-pointer font-medium">
                    自動派工嘗試紀錄 ({attempts.length})
                  </summary>
                  <ul className="mt-2 flex flex-col gap-1">
                    {attempts.map((a, i) => (
                      <li key={i} className="flex justify-between">
                        <span>
                          {a.technician_id?.slice(0, 8) ?? "-"}：{" "}
                          {a.outcome === "declined"
                            ? "拒接"
                            : a.outcome === "timeout"
                              ? "逾時"
                              : a.outcome === "accepted"
                                ? "已接"
                                : a.outcome ?? "-"}
                        </span>
                        <span>
                          {a.attempted_at
                            ? new Date(a.attempted_at).toLocaleString("zh-TW")
                            : "-"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </section>

        {/* Body：filter_sidebar + candidate_list */}
        <div className="mx-8 mt-4 flex flex-1 gap-4 overflow-hidden">
          {/* filter_sidebar */}
          <aside className="w-[240px] flex-shrink-0 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <h3 className="mb-3 text-[14px] font-semibold text-[var(--text-primary)]">
              篩選
            </h3>

            <div className="mb-4">
              <span className="mb-1 block text-[12px] font-medium text-[var(--text-secondary)]">
                技師分級
              </span>
              <div className="flex flex-wrap gap-2">
                {LEVELS.map((lv) => (
                  <button
                    key={lv}
                    onClick={() => toggleLevel(lv)}
                    className={`rounded border px-2 py-1 text-[12px] font-semibold ${
                      selectedLevels.has(lv)
                        ? "border-[var(--primary)] bg-[#EFF6FF] text-[var(--primary)]"
                        : "border-[var(--border)] bg-white text-[var(--text-secondary)]"
                    }`}
                  >
                    {lv}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-4">
              <span className="mb-1 block text-[12px] font-medium text-[var(--text-secondary)]">
                最低評分：{ratingMin.toFixed(1)}
              </span>
              <input
                type="range"
                min={0}
                max={5}
                step={0.5}
                value={ratingMin}
                onChange={(e) => setRatingMin(parseFloat(e.target.value))}
                className="w-full accent-[var(--primary)]"
              />
            </div>

            <label className="mb-4 flex items-center gap-2 text-[12px] text-[var(--text-primary)]">
              <input
                type="checkbox"
                checked={excludeCircuit}
                onChange={(e) => setExcludeCircuit(e.target.checked)}
                className="h-4 w-4 accent-[var(--primary)]"
              />
              排除熔斷中技師
            </label>

            <div className="mb-2 border-t border-[var(--border)] pt-3">
              <span className="mb-1 block text-[12px] font-medium text-[var(--text-secondary)]">
                排序方式
              </span>
              <select
                value={sortBy}
                onChange={(e) =>
                  setSortBy(e.target.value as "score" | "distance" | "rating")
                }
                className="w-full rounded-md border border-[var(--border)] px-2 py-1 text-[12px]"
              >
                <option value="score">綜合分數</option>
                <option value="distance">距離最近</option>
                <option value="rating">評分最高</option>
              </select>
            </div>
          </aside>

          {/* candidate_list */}
          <section className="flex flex-1 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                候選技師（共 {filtered.length} 位
                {totalAvailable > 0 ? ` / 總 ${totalAvailable} 位可用` : ""}）
              </span>
              {selectedTech && (
                <span className="text-[12px] text-[var(--primary)]">
                  已選：{selectedTech.name}
                </span>
              )}
            </div>

            <div className="flex-1 overflow-auto">
              {loading && filtered.length === 0 ? (
                <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
                  載入中…
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex h-60 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
                  <AlertTriangle className="h-10 w-10 text-amber-500" />
                  <p className="text-[14px]">無符合條件的技師</p>
                  <p className="text-[12px]">請放寬篩選條件，或考慮升級主管</p>
                </div>
              ) : (
                <table className="w-full text-[13px]">
                  <thead className="sticky top-0 bg-[#F8FAFC] text-left text-[12px] font-medium text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 w-10"></th>
                      <th className="px-3 py-2">技師</th>
                      <th className="px-3 py-2 text-center">分級</th>
                      <th className="px-3 py-2 text-right">綜合分</th>
                      <th className="px-3 py-2 text-right">距離</th>
                      <th className="px-3 py-2 text-right">評分</th>
                      <th className="px-3 py-2 text-right">技能匹配</th>
                      <th className="px-3 py-2 text-center">可用性</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {filtered.map((c) => {
                      const t = c.technician;
                      if (!t) return null;
                      const isSelected = selectedTechId === t.id;
                      const isCircuit = !!t.circuit_breaker_until;
                      const availColor =
                        t.availability === "available"
                          ? "#10B981"
                          : t.availability === "busy"
                            ? "#EF4444"
                            : "#94A3B8";
                      return (
                        <tr
                          key={t.id}
                          onClick={() => !isCircuit && setSelectedTechId(t.id)}
                          className={`cursor-pointer transition ${
                            isSelected
                              ? "bg-[#EFF6FF]"
                              : isCircuit
                                ? "opacity-50"
                                : "hover:bg-[#F8FAFC]"
                          }`}
                        >
                          <td className="px-3 py-3">
                            <input
                              type="radio"
                              checked={isSelected}
                              onChange={() =>
                                !isCircuit && setSelectedTechId(t.id)
                              }
                              disabled={isCircuit}
                              className="h-4 w-4 cursor-pointer accent-[var(--primary)]"
                            />
                          </td>
                          <td className="px-3 py-3">
                            <div className="flex items-center gap-2">
                              <span
                                className="inline-block h-2 w-2 rounded-full"
                                style={{ backgroundColor: availColor }}
                              />
                              <span className="font-medium text-[var(--text-primary)]">
                                {t.name}
                              </span>
                              {isCircuit && (
                                <span className="rounded bg-red-100 px-2 py-[1px] text-[10px] font-bold text-red-700">
                                  熔斷
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-3 text-center">
                            <span className="inline-block rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] font-bold text-[var(--text-primary)]">
                              {t.level}
                            </span>
                          </td>
                          <td className="px-3 py-3 text-right font-semibold text-[var(--primary)]">
                            {(c.score ?? 0).toFixed(2)}
                          </td>
                          <td className="px-3 py-3 text-right text-[var(--text-secondary)]">
                            {c.distance_km != null ? (
                              <span className="inline-flex items-center gap-1">
                                <MapPin className="h-3 w-3" />
                                {c.distance_km.toFixed(1)} km
                              </span>
                            ) : (
                              "-"
                            )}
                          </td>
                          <td className="px-3 py-3 text-right">
                            <span className="inline-flex items-center gap-1 font-medium text-amber-600">
                              <Star className="h-3 w-3 fill-amber-400" />
                              {t.rating.toFixed(1)}
                            </span>
                          </td>
                          <td className="px-3 py-3 text-right text-[var(--text-secondary)]">
                            {c.skill_match != null
                              ? `${Math.round(c.skill_match * 100)}%`
                              : "-"}
                          </td>
                          <td className="px-3 py-3 text-center text-[12px] text-[var(--text-secondary)]">
                            {c.availability_eta_minutes != null
                              ? c.availability_eta_minutes === 0
                                ? "立即"
                                : `${c.availability_eta_minutes} 分後`
                              : t.availability}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </div>

        {/* assign_action_panel */}
        <div className="sticky bottom-0 mt-4 flex items-center justify-between gap-3 border-t border-[var(--border)] bg-white px-8 py-3 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
          <span className="text-[13px] text-[var(--text-secondary)]">
            {selectedTech
              ? `將指派工單 #${wo?.id.slice(0, 8) ?? "-"} 給 ${selectedTech.name}`
              : "請從候選列表中選擇技師"}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={cancelOrder}
              disabled={!wo || escalateBusy}
              className="flex items-center gap-1 rounded-md border border-red-200 bg-white px-3 py-2 text-[13px] font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              <XCircle className="h-4 w-4" />
              取消工單
            </button>
            <button
              type="button"
              onClick={escalateOrder}
              disabled={!wo || escalateBusy}
              className="flex items-center gap-1 rounded-md border border-amber-200 bg-white px-3 py-2 text-[13px] font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50"
            >
              <ArrowUpCircle className="h-4 w-4" />
              升級主管
            </button>
            {wo && (
              <Link
                href={`/my-orders/${wo.id}/reschedule?from=staff_assist`}
                className="flex items-center gap-1 rounded-md border border-blue-200 bg-white px-3 py-2 text-[13px] font-medium text-blue-700 hover:bg-blue-50"
              >
                <ArrowUpCircle className="h-4 w-4 rotate-90" />
                改期 + 通知客戶
              </Link>
            )}
            <button
              type="button"
              onClick={() => setReasonModalOpen(true)}
              disabled={!selectedTechId || !wo}
              className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
            >
              <Zap className="h-4 w-4" />
              指派{selectedTech ? ` 給 ${selectedTech.name}` : ""}
            </button>
          </div>
        </div>
      </div>

      {/* decision_reason_modal */}
      {reasonModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => !submitting && setReasonModalOpen(false)}
        >
          <div
            className="w-[480px] rounded-xl bg-white p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[16px] font-semibold text-[var(--text-primary)]">
                指派理由
              </h3>
              <button
                type="button"
                onClick={() => !submitting && setReasonModalOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mb-3 text-[12px] text-[var(--text-secondary)]">
              指派至 <strong>{selectedTech?.name}</strong>（
              {selectedTech?.level} 級），請選擇理由（稽核用）：
            </p>

            <div className="mb-3 flex flex-col gap-2">
              {REASON_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-[13px] ${
                    reasonCode === opt.value
                      ? "border-[var(--primary)] bg-[#EFF6FF]"
                      : "border-[var(--border)] bg-white"
                  }`}
                >
                  <input
                    type="radio"
                    checked={reasonCode === opt.value}
                    onChange={() => setReasonCode(opt.value)}
                    className="h-4 w-4 accent-[var(--primary)]"
                  />
                  {opt.label}
                </label>
              ))}
            </div>

            {(reasonCode === "other" || reasonText) && (
              <label className="mb-3 flex flex-col gap-1">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  補充說明 {reasonCode === "other" && <span className="text-red-500">*</span>}
                </span>
                <textarea
                  value={reasonText}
                  onChange={(e) => setReasonText(e.target.value)}
                  rows={3}
                  maxLength={500}
                  placeholder="10–500 字"
                  className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
                />
              </label>
            )}

            {submitError && (
              <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                {submitError}
              </div>
            )}

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setReasonModalOpen(false)}
                disabled={submitting}
                className="rounded-md border border-[var(--border)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={submitAssign}
                disabled={submitting}
                className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-60"
              >
                {submitting ? "提交中…" : "確認指派"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
