"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowUpCircle,
  CheckCircle2,
  Info,
  MapPin,
  RefreshCw,
  Star,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import StatusBadge, { statusLabel } from "@shared/components/tech/StatusBadge";
import UrgencyBadge from "@shared/components/tech/UrgencyBadge";
import { ApiError, api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { useLocale, useTranslations } from "@shared/components/i18n/LocaleProvider";
import type { components } from "@shared/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];
type Technician = components["schemas"]["Technician"];
type TechnicianLevel = components["schemas"]["TechnicianLevel"];
type AssignReasonCode = components["schemas"]["WorkOrderAssignRequest"]["reason_code"];

interface ScoreDimension {
  factor: number;
  weight: number;
  contribution: number;
  rationale: string;
}

interface Candidate {
  technician?: Technician;
  score?: number;
  distance_km?: number;
  skill_match?: number;
  availability_eta_minutes?: number;
  // CR-0114 R4：鎖品牌授權標示（true=已授權 / false=未授權 / null=無授權資料可判）
  brand_authorized?: boolean | null;
  score_breakdown?: {
    skill?: ScoreDimension;
    distance?: ScoreDimension;
    rating?: ScoreDimension;
  };
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

const REASON_VALUES: AssignReasonCode[] = [
  "auto_dispatch_exhausted",
  "customer_requested_specific_tech",
  "skill_shortage_override",
  "sla_rescue",
  "other",
];

const LEVELS: TechnicianLevel[] = ["S", "A", "B", "C"];

function formatErr(e: unknown): string {
  return friendlyError(e);
}

export default function DispatchManualPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const workOrderId = searchParams.get("work_order_id") ?? "";
  const t = useTranslations("admin.dispatchManual");
  const tReasons = useTranslations("admin.dispatchManual.reasons");
  const { locale } = useLocale();

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
        tenantPath(`/work-orders/${encodeURIComponent(workOrderId)}`),
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
        tenantPath("/dispatch:candidates"),
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
      setSubmitError(t("errors.otherRequired"));
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.post<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}:assign`),
        {
          technician_id: selectedTechId,
          reason_code: reasonCode,
          ...(reasonText.trim() ? { reason_text: reasonText.trim() } : {}),
          override_flags: { allow_circuit: false, allow_cross_area: false },
        },
      );
      setActionMsg(t("actionMsg.assignedTo", { name: selectedTech?.name ?? t("actionMsg.fallbackTech") }));
      setReasonModalOpen(false);
      setReasonText("");
      // 返回 A28 派工佇列
      setTimeout(() => router.push("/admin/dispatch-queue"), 1500);
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 409) {
          if (e.errorCode === "TECHNICIAN_CIRCUIT_BREAKER_OPEN") {
            setSubmitError(t("errors.circuitBreaker"));
          } else if (e.errorCode === "WORK_ORDER_CONFLICT") {
            setSubmitError(t("errors.conflict"));
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
    const reason = window.prompt(t("errors.escalatePrompt"));
    if (!reason || reason.trim().length === 0) return;
    setEscalateBusy(true);
    try {
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}:escalate`),
        { level: "operations_manager", reason: reason.trim() },
      );
      setActionMsg(t("actionMsg.escalated"));
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setEscalateBusy(false);
    }
  }

  async function cancelOrder() {
    if (!wo || escalateBusy) return;
    if (!window.confirm(t("errors.cancelConfirm"))) return;
    setEscalateBusy(true);
    try {
      await api.post(tenantPath(`/work-orders/${encodeURIComponent(wo.id)}/cancel`), {
        reason: "manual_dispatch_cancel",
      });
      setActionMsg(t("actionMsg.cancelled"));
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
              {t("missingParam.title")}
            </h2>
            <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
              {t("missingParam.hint")}
              <code className="mx-1 rounded bg-[#F1F5F9] px-1 py-[1px] font-mono text-[12px]">
                {t("missingParam.queryHint")}
              </code>
            </p>
            <Link
              href="/admin/dispatch-queue"
              className="mt-4 inline-block rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#1D4ED8]"
            >
              {t("missingParam.goQueue")}
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
            {t("breadcrumb")}
          </span>
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-bold text-[#0F172A]">
              {t("title")}
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
              {t("refresh")}
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
              {t("ctxLoading")}
            </div>
          ) : !wo ? (
            <div className="text-[13px] text-red-700">
              {t("ctxNotFound", { id: workOrderId })}
            </div>
          ) : (
            <>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
                      {t("ctxOrderTitle", { id: wo.id.slice(0, 8) })}
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
                    {t("ctxAttempted")}
                  </span>
                  <span className="text-[20px] font-bold text-[var(--text-primary)]">
                    {attempts.length}
                  </span>
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {" "}
                    {t("ctxTimes")}
                  </span>
                </div>
              </div>
              {attempts.length > 0 && (
                <details className="rounded-md bg-[#F8FAFC] px-3 py-2 text-[12px] text-[var(--text-secondary)]">
                  <summary className="cursor-pointer font-medium">
                    {t("ctxAttemptHistory", { count: String(attempts.length) })}
                  </summary>
                  <ul className="mt-2 flex flex-col gap-1">
                    {attempts.map((a, i) => (
                      <li key={i} className="flex justify-between">
                        <span>
                          {a.technician_id?.slice(0, 8) ?? "-"}：{" "}
                          {a.outcome === "declined"
                            ? t("ctxAttemptOutcome.declined")
                            : a.outcome === "timeout"
                              ? t("ctxAttemptOutcome.timeout")
                              : a.outcome === "accepted"
                                ? t("ctxAttemptOutcome.accepted")
                                : a.outcome ?? "-"}
                        </span>
                        <span>
                          {a.attempted_at
                            ? new Date(a.attempted_at).toLocaleString(locale)
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
              {t("filters.title")}
            </h3>

            <div className="mb-4">
              <span className="mb-1 block text-[12px] font-medium text-[var(--text-secondary)]">
                {t("filters.techLevel")}
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
                {t("filters.minRating", { value: ratingMin.toFixed(1) })}
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
              {t("filters.excludeCircuit")}
            </label>

            <div className="mb-2 border-t border-[var(--border)] pt-3">
              <span className="mb-1 block text-[12px] font-medium text-[var(--text-secondary)]">
                {t("filters.sortLabel")}
              </span>
              <select
                value={sortBy}
                onChange={(e) =>
                  setSortBy(e.target.value as "score" | "distance" | "rating")
                }
                className="w-full rounded-md border border-[var(--border)] px-2 py-1 text-[12px]"
              >
                <option value="score">{t("filters.sort.score")}</option>
                <option value="distance">{t("filters.sort.distance")}</option>
                <option value="rating">{t("filters.sort.rating")}</option>
              </select>
            </div>
          </aside>

          {/* candidate_list */}
          <section className="flex flex-1 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                {t("candidates.summary", {
                  count: String(filtered.length),
                  available:
                    totalAvailable > 0
                      ? t("candidates.available", { total: String(totalAvailable) })
                      : "",
                })}
              </span>
              {selectedTech && (
                <span className="text-[12px] text-[var(--primary)]">
                  {t("candidates.selected", { name: selectedTech.name })}
                </span>
              )}
            </div>

            <div className="flex-1 overflow-auto">
              {loading && filtered.length === 0 ? (
                <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
                  {t("candidates.loading")}
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex h-60 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
                  <AlertTriangle className="h-10 w-10 text-amber-500" />
                  <p className="text-[14px]">{t("candidates.emptyTitle")}</p>
                  <p className="text-[12px]">{t("candidates.emptyHint")}</p>
                </div>
              ) : (
                <table className="w-full text-[13px]">
                  <thead className="sticky top-0 bg-[#F8FAFC] text-left text-[12px] font-medium text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 w-10"></th>
                      <th className="px-3 py-2">{t("candidates.cols.tech")}</th>
                      <th className="px-3 py-2 text-center">{t("candidates.cols.level")}</th>
                      <th className="px-3 py-2 text-right">{t("candidates.cols.score")}</th>
                      <th className="px-3 py-2 text-right">{t("candidates.cols.distance")}</th>
                      <th className="px-3 py-2 text-right">{t("candidates.cols.rating")}</th>
                      <th className="px-3 py-2 text-right">{t("candidates.cols.skill")}</th>
                      <th className="px-3 py-2 text-center">{t("candidates.cols.availability")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {filtered.map((c) => {
                      const tech = c.technician;
                      if (!tech) return null;
                      const isSelected = selectedTechId === tech.id;
                      // CR-0117 S5：熔斷判準改真訊號 availability（=technicians.online_state）。
                      // 舊判準 circuit_breaker_until 後端恒回 null（DB 無此欄）→ 永遠 false，
                      // 真熔斷中的技師反而不會被鎖定/標記。
                      const isCircuit = tech.availability === "circuit_breaker_open";
                      const availColor =
                        tech.availability === "available"
                          ? "#10B981"
                          : tech.availability === "busy"
                            ? "#EF4444"
                            : "#94A3B8";
                      return (
                        <tr
                          key={tech.id}
                          onClick={() => !isCircuit && setSelectedTechId(tech.id)}
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
                                !isCircuit && setSelectedTechId(tech.id)
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
                                {tech.name}
                              </span>
                              {/* CR-0114 R4：鎖品牌授權標示（全部師傅可見,已/未授權標示） */}
                              {c.brand_authorized === true && (
                                <span className="rounded bg-green-100 px-2 py-[1px] text-[10px] font-bold text-green-700">
                                  已授權
                                </span>
                              )}
                              {c.brand_authorized === false && (
                                <span className="rounded bg-amber-100 px-2 py-[1px] text-[10px] font-bold text-amber-700">
                                  未授權
                                </span>
                              )}
                              {isCircuit && (
                                <span className="rounded bg-red-100 px-2 py-[1px] text-[10px] font-bold text-red-700">
                                  {t("candidates.circuitBadge")}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-3 text-center">
                            <span className="inline-block rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] font-bold text-[var(--text-primary)]">
                              {tech.level}
                            </span>
                          </td>
                          <td className="px-3 py-3 text-right">
                            <ScoreCell candidate={c} />
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
                              {tech.rating.toFixed(1)}
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
                                ? t("candidates.etaImmediate")
                                : t("candidates.etaMinutes", { min: String(c.availability_eta_minutes) })
                              : tech.availability}
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
              ? t("panel.willAssign", { id: wo?.id.slice(0, 8) ?? "-", name: selectedTech.name })
              : t("panel.noTech")}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={cancelOrder}
              disabled={!wo || escalateBusy}
              className="flex items-center gap-1 rounded-md border border-red-200 bg-white px-3 py-2 text-[13px] font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              <XCircle className="h-4 w-4" />
              {t("panel.cancelOrder")}
            </button>
            <button
              type="button"
              onClick={escalateOrder}
              disabled={!wo || escalateBusy}
              className="flex items-center gap-1 rounded-md border border-amber-200 bg-white px-3 py-2 text-[13px] font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50"
            >
              <ArrowUpCircle className="h-4 w-4" />
              {t("panel.escalate")}
            </button>
            {wo && (
              <Link
                href={`/my-orders/${wo.id}/reschedule?from=staff_assist`}
                className="flex items-center gap-1 rounded-md border border-blue-200 bg-white px-3 py-2 text-[13px] font-medium text-blue-700 hover:bg-blue-50"
              >
                <ArrowUpCircle className="h-4 w-4 rotate-90" />
                {t("panel.reschedule")}
              </Link>
            )}
            <button
              type="button"
              onClick={() => setReasonModalOpen(true)}
              disabled={!selectedTechId || !wo}
              className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
            >
              <Zap className="h-4 w-4" />
              {selectedTech
                ? t("panel.assignActionTo", { name: selectedTech.name })
                : t("panel.assignAction")}
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
                {t("modal.title")}
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
              {t("modal.intro", {
                name: selectedTech?.name ?? "",
                level: selectedTech?.level ?? "",
              })}
            </p>

            <div className="mb-3 flex flex-col gap-2">
              {REASON_VALUES.map((value) => (
                <label
                  key={value}
                  className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-[13px] ${
                    reasonCode === value
                      ? "border-[var(--primary)] bg-[#EFF6FF]"
                      : "border-[var(--border)] bg-white"
                  }`}
                >
                  <input
                    type="radio"
                    checked={reasonCode === value}
                    onChange={() => setReasonCode(value)}
                    className="h-4 w-4 accent-[var(--primary)]"
                  />
                  {tReasons(value)}
                </label>
              ))}
            </div>

            {(reasonCode === "other" || reasonText) && (
              <label className="mb-3 flex flex-col gap-1">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                  {t("modal.extra")} {reasonCode === "other" && <span className="text-red-500">*</span>}
                </span>
                <textarea
                  value={reasonText}
                  onChange={(e) => setReasonText(e.target.value)}
                  rows={3}
                  maxLength={500}
                  placeholder={t("modal.extraPlaceholder")}
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
                {t("modal.cancel")}
              </button>
              <button
                type="button"
                onClick={submitAssign}
                disabled={submitting}
                className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-60"
              >
                {submitting ? t("modal.submitting") : t("modal.submit")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


/**
 * 推薦分數 + hover tooltip 顯示 score breakdown（F4）
 */
function ScoreCell({ candidate }: { candidate: Candidate }) {
  const t = useTranslations("admin.dispatchManual.scoreCell");
  const tDim = useTranslations("admin.dispatchManual.scoreCell.dim");
  const score = candidate.score ?? 0;
  const breakdown = candidate.score_breakdown;
  if (!breakdown) {
    return (
      <span className="font-semibold text-[var(--primary)]">
        {score.toFixed(2)}
      </span>
    );
  }
  const dims: { key: "skill" | "distance" | "rating"; dim: ScoreDimension | undefined }[] =
    [
      { key: "skill", dim: breakdown.skill },
      { key: "distance", dim: breakdown.distance },
      { key: "rating", dim: breakdown.rating },
    ];
  return (
    <div className="group relative inline-flex items-center justify-end gap-1">
      <span className="font-semibold text-[var(--primary)]">
        {score.toFixed(2)}
      </span>
      <Info className="h-3 w-3 text-[var(--text-disabled)] group-hover:text-[var(--primary)]" />

      {/* tooltip */}
      <div className="invisible absolute right-0 top-full z-20 mt-1 w-[320px] rounded-lg border border-[var(--border)] bg-white p-3 text-left opacity-0 shadow-2xl transition-opacity group-hover:visible group-hover:opacity-100">
        <div className="mb-2 flex items-center justify-between border-b border-[var(--border)] pb-2">
          <span className="text-[12px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
          <span className="text-[14px] font-bold text-[var(--primary)]">
            {score.toFixed(2)}
          </span>
        </div>
        <ul className="flex flex-col gap-2">
          {dims.map(({ key, dim }) =>
            dim ? (
              <li key={key} className="flex flex-col gap-[2px]">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-medium text-[var(--text-primary)]">
                    {tDim(key)}
                    <span className="ml-1 text-[var(--text-disabled)]">
                      {t("weight", { weight: String(dim.weight) })}
                    </span>
                  </span>
                  <span className="font-mono text-[var(--text-secondary)]">
                    {t("contribution", { value: dim.contribution.toFixed(1) })}
                  </span>
                </div>
                {/* progress bar */}
                <div className="h-1 w-full overflow-hidden rounded-full bg-[#F1F5F9]">
                  <div
                    className="h-full bg-[var(--primary)]"
                    style={{ width: `${Math.min(100, dim.factor * 100)}%` }}
                  />
                </div>
                <span className="text-[10px] leading-[1.4] text-[var(--text-secondary)]">
                  {dim.rationale}
                </span>
              </li>
            ) : null,
          )}
        </ul>
        <p className="mt-2 border-t border-[var(--border)] pt-2 text-[10px] text-[var(--text-disabled)]">
          {t("formula")}
        </p>
      </div>
    </div>
  );
}
