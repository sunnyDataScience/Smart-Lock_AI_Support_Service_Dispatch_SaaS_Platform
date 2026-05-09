"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Trash2,
  CheckCircle2,
  Clock,
  X,
} from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api } from "@/lib/api";

type RequestItem = {
  id: string;
  type: "leave" | "standby";
  start_date: string;
  end_date: string;
  reason: string;
  status: "pending" | "approved" | "rejected" | "cancelled";
  created_at: string;
};

interface ScheduleResponse {
  month: string;
  work_orders_per_day: Record<string, number>;
  leave_days: string[];
  standby_days: string[];
  pending_requests: RequestItem[];
}

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

function toDateKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function buildMonthGrid(year: number, month: number): Date[] {
  // month: 0-indexed
  const first = new Date(year, month, 1);
  const startDay = first.getDay(); // 0=Sun
  const days: Date[] = [];
  for (let i = 0; i < startDay; i++) {
    const d = new Date(year, month, 1 - (startDay - i));
    days.push(d);
  }
  const last = new Date(year, month + 1, 0).getDate();
  for (let i = 1; i <= last; i++) {
    days.push(new Date(year, month, i));
  }
  while (days.length % 7 !== 0) {
    const d = days[days.length - 1];
    const next = new Date(d);
    next.setDate(d.getDate() + 1);
    days.push(next);
  }
  return days;
}

const WEEKDAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;

export default function SchedulePage() {
  const router = useRouter();
  const t = useTranslations("pages.account.schedule");
  const tWeek = useTranslations("pages.account.schedule.weekdays");
  const tModal = useTranslations("pages.account.schedule.modal");
  const tStatus = useTranslations("pages.account.schedule.requestStatus");
  const today = new Date();
  const [cursor, setCursor] = useState({
    year: today.getFullYear(),
    month: today.getMonth(),
  });

  const [workOrdersPerDay, setWorkOrdersPerDay] = useState<
    Record<string, number>
  >({});
  const [leaveDays, setLeaveDays] = useState<Set<string>>(new Set());
  const [standbyDays, setStandbyDays] = useState<Set<string>>(new Set());
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [closeToday, setCloseToday] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [modalType, setModalType] = useState<"leave" | "standby" | null>(null);
  const [formStart, setFormStart] = useState("");
  const [formEnd, setFormEnd] = useState("");
  const [formReason, setFormReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const grid = useMemo(
    () => buildMonthGrid(cursor.year, cursor.month),
    [cursor],
  );

  const monthQuery = `${cursor.year}-${String(cursor.month + 1).padStart(2, "0")}`;

  const fetchSchedule = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.get<ScheduleResponse>(
        "/api/v1/technicians/me/schedule",
        { query: { month: monthQuery } },
      );
      setWorkOrdersPerDay(res.work_orders_per_day ?? {});
      setLeaveDays(new Set(res.leave_days ?? []));
      setStandbyDays(new Set(res.standby_days ?? []));
      setRequests(res.pending_requests ?? []);
    } catch (e) {
      setErrorMsg(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, [monthQuery]);

  useEffect(() => {
    fetchSchedule();
  }, [fetchSchedule]);

  function shiftMonth(direction: -1 | 1) {
    setCursor((prev) => {
      const next = new Date(prev.year, prev.month + direction, 1);
      return { year: next.getFullYear(), month: next.getMonth() };
    });
  }

  function openModal(type: "leave" | "standby") {
    setFormStart(toDateKey(today));
    setFormEnd(toDateKey(today));
    setFormReason("");
    setModalType(type);
  }

  async function submitRequest() {
    if (submitting) return;
    if (!formStart || !formEnd || formReason.trim().length < 5 || !modalType)
      return;
    setSubmitting(true);
    try {
      const path =
        modalType === "leave"
          ? "/api/v1/technicians/me/schedule/leave-request"
          : "/api/v1/technicians/me/schedule/standby-request";
      const created = await api.post<RequestItem>(path, {
        start_date: formStart,
        end_date: formEnd,
        reason: formReason.trim(),
      });
      setRequests((prev) => [created, ...prev]);
      setModalType(null);
      setActionMsg(
        t("submitDone", {
          type: modalType === "leave" ? t("leaveTag") : t("standbyTag"),
        }),
      );
      setTimeout(() => setActionMsg(null), 3000);
    } catch (e) {
      setErrorMsg(formatErr(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function cancelRequest(id: string) {
    if (!window.confirm(t("cancelConfirm"))) return;
    try {
      await api.delete(
        `/api/v1/technicians/me/schedule/request/${encodeURIComponent(id)}`,
      );
      setRequests((prev) => prev.filter((r) => r.id !== id));
      setActionMsg(t("cancelDone"));
      setTimeout(() => setActionMsg(null), 2000);
    } catch (e) {
      setErrorMsg(formatErr(e));
    }
  }

  async function toggleCloseToday() {
    const newState = !closeToday;
    try {
      await api.patch("/api/v1/technicians/me/availability", {
        online_state: newState ? "offline" : "available",
      });
      setCloseToday(newState);
      setActionMsg(newState ? t("closeDone") : t("openDone"));
      setTimeout(() => setActionMsg(null), 2000);
    } catch (e) {
      setErrorMsg(formatErr(e));
    }
  }

  const monthLabel = t("monthLabel", {
    year: String(cursor.year),
    month: String(cursor.month + 1),
  });
  const todayKey = toDateKey(today);
  const leaveCount = requests.filter(
    (r) => r.type === "leave" && r.status !== "rejected",
  ).length;
  const standbyCount = requests.filter(
    (r) => r.type === "standby" && r.status !== "rejected",
  ).length;

  return (
    <TechShell>
      {/* schedule_month_header — 自訂返回鈕（返回 /account 而非 my-orders） */}
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[var(--border)] bg-white px-2 py-3">
        <button
          type="button"
          onClick={() => router.push("/account")}
          className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          aria-label={t("back")}
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <span className="text-[15px] font-semibold text-[var(--text-primary)]">
          {t("title")}
        </span>
      </div>

      {actionMsg && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          {actionMsg}
        </div>
      )}

      {errorMsg && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {errorMsg}
        </div>
      )}

      {/* 月份切換 + 配額摘要 */}
      <section className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => shiftMonth(-1)}
            className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            aria-label={t("prevMonth")}
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <span className="text-[15px] font-semibold text-[var(--text-primary)]">
            {monthLabel}
          </span>
          <button
            type="button"
            onClick={() => shiftMonth(1)}
            className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            aria-label={t("nextMonth")}
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          <div className="rounded-md bg-[#FEF3C7] px-2 py-1">
            <span className="block text-[10px] text-[#92400E]">{t("leaveQuota")}</span>
            <span className="text-[16px] font-bold text-[#92400E]">
              {leaveCount}
            </span>
          </div>
          <div className="rounded-md bg-[#DBEAFE] px-2 py-1">
            <span className="block text-[10px] text-[#1E40AF]">{t("standbyQuota")}</span>
            <span className="text-[16px] font-bold text-[#1E40AF]">
              {standbyCount}
            </span>
          </div>
          <div className="rounded-md bg-[#F1F5F9] px-2 py-1">
            <span className="block text-[10px] text-[var(--text-secondary)]">
              {t("monthOrders")}
            </span>
            <span className="text-[16px] font-bold text-[var(--text-primary)]">
              {Object.values(workOrdersPerDay).reduce(
                (sum, n) => sum + (n ?? 0),
                0,
              )}
            </span>
          </div>
        </div>
      </section>

      {/* schedule_calendar_view */}
      <section className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-white p-3 shadow-sm">
        <div className="grid grid-cols-7 gap-1 text-center">
          {WEEKDAY_KEYS.map((w) => (
            <span
              key={w}
              className="text-[11px] font-medium text-[var(--text-secondary)]"
            >
              {tWeek(w)}
            </span>
          ))}
          {grid.map((d) => {
            const key = toDateKey(d);
            const isLeave = leaveDays.has(key);
            const isStandby = standbyDays.has(key);
            const woCount = workOrdersPerDay[key];
            const isCurrentMonth = d.getMonth() === cursor.month;
            const isToday = key === todayKey;
            return (
              <div
                key={key}
                className={`relative flex aspect-square flex-col items-center justify-center rounded text-[12px] ${
                  !isCurrentMonth
                    ? "text-[var(--text-disabled)]"
                    : isToday
                      ? "border border-[var(--primary)] font-bold text-[var(--primary)]"
                      : "text-[var(--text-primary)]"
                } ${
                  isLeave
                    ? "bg-[#FEF3C7]"
                    : isStandby
                      ? "bg-[#DBEAFE]"
                      : ""
                }`}
              >
                <span>{d.getDate()}</span>
                {woCount ? (
                  <span className="absolute right-[2px] top-[2px] rounded-full bg-[var(--primary)] px-[3px] text-[8px] font-bold text-white">
                    {woCount}
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-[var(--border)] pt-2 text-[10px] text-[var(--text-secondary)]">
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded bg-[#FEF3C7]" />
            {t("legend.leave")}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded bg-[#DBEAFE]" />
            {t("legend.standby")}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-[var(--primary)]" />
            {t("legend.orders")}
          </span>
        </div>
      </section>

      {/* close_today_accept_switch */}
      <section className="mx-4 mt-4 flex items-center justify-between rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <div className="flex flex-col">
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            {t("closeToday")}
          </span>
          <span className="text-[11px] text-[var(--text-secondary)]">
            {t("closeTodayHint")}
          </span>
        </div>
        <button
          type="button"
          onClick={toggleCloseToday}
          className="relative h-7 w-12 rounded-full transition"
          style={{
            backgroundColor: closeToday ? "#EF4444" : "#E2E8F0",
          }}
          aria-label={t("closeTodayAria")}
        >
          <span
            className="absolute top-[2px] h-6 w-6 rounded-full bg-white shadow transition-all"
            style={{ left: closeToday ? "22px" : "2px" }}
          />
        </button>
      </section>

      {/* 申請按鈕 */}
      <section className="mx-4 mt-4 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => openModal("leave")}
          className="flex h-12 items-center justify-center gap-1 rounded-lg border border-amber-200 bg-amber-50 text-[14px] font-medium text-amber-800 hover:bg-amber-100"
        >
          <CalendarDays className="h-4 w-4" />
          {t("applyLeave")}
        </button>
        <button
          type="button"
          onClick={() => openModal("standby")}
          className="flex h-12 items-center justify-center gap-1 rounded-lg border border-blue-200 bg-blue-50 text-[14px] font-medium text-blue-800 hover:bg-blue-100"
        >
          <Clock className="h-4 w-4" />
          {t("applyStandby")}
        </button>
      </section>

      {/* pending_requests_list */}
      <section className="mx-4 mt-4 mb-6 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            {t("pending")}
          </span>
          <span className="text-[11px] text-[var(--text-disabled)]">
            {t("pendingCount", {
              count: String(requests.filter((r) => r.status === "pending").length),
            })}
          </span>
        </div>
        {requests.length === 0 ? (
          <p className="py-3 text-center text-[12px] text-[var(--text-disabled)]">
            {t("noPending")}
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {requests.map((r) => (
              <li
                key={r.id}
                className="flex items-start justify-between gap-2 rounded-lg border border-[var(--border)] bg-[#F8FAFC] p-3"
              >
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded px-2 py-[1px] text-[11px] font-semibold ${
                        r.type === "leave"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-blue-100 text-blue-800"
                      }`}
                    >
                      {r.type === "leave" ? t("leaveTag") : t("standbyTag")}
                    </span>
                    <span className="text-[12px] text-[var(--text-secondary)]">
                      {r.start_date} ～ {r.end_date}
                    </span>
                  </div>
                  <span className="text-[12px] text-[var(--text-primary)]">
                    {r.reason}
                  </span>
                  <span className="text-[10px] text-[var(--text-disabled)]">
                    {t("statusPrefix", {
                      label:
                        r.status === "pending"
                          ? tStatus("pending")
                          : r.status === "approved"
                            ? tStatus("approved")
                            : tStatus("rejected"),
                    })}
                  </span>
                </div>
                {r.status === "pending" && (
                  <button
                    type="button"
                    onClick={() => cancelRequest(r.id)}
                    className="flex h-8 w-8 items-center justify-center rounded-md text-red-600 hover:bg-red-50"
                    aria-label={t("cancelAria")}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* leave / standby modal */}
      {modalType && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40"
          onClick={() => !submitting && setModalType(null)}
        >
          <div
            className="w-full max-w-[480px] rounded-t-2xl bg-white p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[16px] font-semibold text-[var(--text-primary)]">
                {modalType === "leave" ? tModal("leaveTitle") : tModal("standbyTitle")}
              </span>
              <button
                type="button"
                onClick={() => setModalType(null)}
                className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <label className="mb-2 flex flex-col gap-1">
              <span className="text-[11px] font-medium text-[var(--text-secondary)]">
                {tModal("startDate")}
              </span>
              <input
                type="date"
                value={formStart}
                onChange={(e) => setFormStart(e.target.value)}
                className="rounded-md border border-[var(--border)] px-3 py-2 text-[14px]"
              />
            </label>

            <label className="mb-2 flex flex-col gap-1">
              <span className="text-[11px] font-medium text-[var(--text-secondary)]">
                {tModal("endDate")}
              </span>
              <input
                type="date"
                value={formEnd}
                onChange={(e) => setFormEnd(e.target.value)}
                className="rounded-md border border-[var(--border)] px-3 py-2 text-[14px]"
              />
            </label>

            <label className="mb-3 flex flex-col gap-1">
              <span className="text-[11px] font-medium text-[var(--text-secondary)]">
                {modalType === "leave" ? tModal("leaveReason") : tModal("standbyNote")}
              </span>
              <textarea
                value={formReason}
                onChange={(e) => setFormReason(e.target.value)}
                rows={3}
                placeholder={
                  modalType === "leave"
                    ? tModal("leaveReasonPlaceholder")
                    : tModal("standbyNotePlaceholder")
                }
                className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
              />
              <span className="text-[10px] text-[var(--text-disabled)]">
                {tModal("minLength", { count: String(formReason.trim().length) })}
              </span>
            </label>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setModalType(null)}
                disabled={submitting}
                className="h-11 flex-1 rounded-lg border border-[var(--border)] text-[14px] font-medium text-[var(--text-primary)] disabled:opacity-50"
              >
                {tModal("cancel")}
              </button>
              <button
                type="button"
                onClick={submitRequest}
                disabled={
                  submitting ||
                  !formStart ||
                  !formEnd ||
                  formReason.trim().length < 5
                }
                className="h-11 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white disabled:opacity-60"
              >
                {submitting ? tModal("submitting") : tModal("submit")}
              </button>
            </div>
          </div>
        </div>
      )}
    </TechShell>
  );
}
