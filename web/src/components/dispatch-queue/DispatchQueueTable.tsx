"use client";

import Link from "next/link";
import { ChevronRight, Ellipsis } from "lucide-react";
import type { components } from "@/types/api.generated";

type DispatchLog = components["schemas"]["DispatchLog"];

interface Props {
  items: DispatchLog[];
  loading?: boolean;
}

const attemptBadge: Record<
  number,
  { label: string; bg: string; text: string }
> = {
  1: { label: "第 1 次", bg: "#DBEAFE", text: "#2563EB" },
  2: { label: "第 2 次", bg: "#FEF3C7", text: "#D97706" },
  3: { label: "第 3 次", bg: "#FEE2E2", text: "#DC2626" },
};

const TECH_PALETTE = ["#2563EB", "#8B5CF6", "#10B981", "#F59E0B", "#6366F1", "#EC4899"];

function techColor(name: string | null | undefined): string {
  if (!name) return "#94A3B8";
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) & 0xffffffff;
  return TECH_PALETTE[Math.abs(hash) % TECH_PALETTE.length];
}

function scoreColor(score: number | null | undefined): string {
  if (score == null) return "#94A3B8";
  if (score >= 80) return "#10B981";
  if (score >= 60) return "#3B82F6";
  if (score >= 40) return "#F59E0B";
  return "#EF4444";
}

function formatRelativeRemaining(createdIso: string | null | undefined, timeoutSec: number | null | undefined): {
  label: string;
  cls: string;
} {
  if (!createdIso || !timeoutSec) return { label: "—", cls: "text-[var(--text-secondary)]" };
  const created = new Date(createdIso).getTime();
  const deadline = created + timeoutSec * 1000;
  const remainingMs = deadline - Date.now();
  if (remainingMs < 0) {
    const overdueMin = Math.round(-remainingMs / 60000);
    return { label: `已逾時 ${overdueMin}min`, cls: "text-[#DC2626] font-bold" };
  }
  const totalSec = Math.floor(remainingMs / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  const label = `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  if (totalSec <= 120) return { label, cls: "text-[#D97706] font-medium" };
  return { label, cls: "text-[var(--text-primary)] font-medium" };
}

function formatCreatedAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${m}-${day} ${hh}:${mm}`;
}

interface AggregatedRow {
  log: DispatchLog;
  attempt: number;
  isStuck: boolean;
}

function aggregate(items: DispatchLog[]): AggregatedRow[] {
  const buckets = new Map<string, DispatchLog[]>();
  for (const log of items) {
    if (!log.work_order_id) continue;
    const arr = buckets.get(log.work_order_id) ?? [];
    arr.push(log);
    buckets.set(log.work_order_id, arr);
  }
  const rows: AggregatedRow[] = [];
  for (const logs of buckets.values()) {
    const sorted = [...logs].sort((a, b) =>
      (a.created_at ?? "").localeCompare(b.created_at ?? ""),
    );
    const assigns = sorted.filter((l) => l.action === "assign");
    const latest = sorted[sorted.length - 1];
    if (!latest) continue;
    const attempt = Math.max(1, Math.min(3, assigns.length || 1));
    const isStuck =
      latest.action === "timeout" ||
      latest.action === "reject" ||
      (latest.action === "assign" && attempt >= 3);
    rows.push({ log: latest, attempt, isStuck });
  }
  rows.sort((a, b) =>
    (b.log.created_at ?? "").localeCompare(a.log.created_at ?? ""),
  );
  return rows;
}

const columns = [
  { label: "", width: "w-10" },
  { label: "工單編號", width: "w-[140px]" },
  { label: "派工次數", width: "w-20" },
  { label: "當前技師", width: "w-[140px]" },
  { label: "媒合分數", width: "w-[120px]" },
  { label: "拒單原因 / 備註", width: "flex-1" },
  { label: "剩餘時間", width: "w-[100px]" },
  { label: "建立時間", width: "w-[130px]" },
  { label: "操作", width: "w-20" },
];

export default function DispatchQueueTable({ items, loading }: Props) {
  const rows = aggregate(items);

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
        <div className="flex items-center bg-[#F8FAFC] px-4 py-3">
          {columns.map((col, idx) => (
            <span
              key={col.label || `col-${idx}`}
              className={`${col.width} shrink-0 text-xs font-semibold text-[var(--text-secondary)]`}
            >
              {col.label}
            </span>
          ))}
        </div>

        {loading && rows.length === 0 && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            載入中…
          </div>
        )}
        {!loading && rows.length === 0 && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            目前沒有派工歷程
          </div>
        )}

        {rows.map(({ log, attempt, isStuck }) => {
          const badge = attemptBadge[attempt];
          const color = scoreColor(log.match_score);
          const score = log.match_score ?? null;
          const barWidth = score != null ? Math.round((score / 100) * 60) : 0;
          const techName = log.technician_name ?? "未指派";
          const reasonText =
            log.rejection_reason ?? log.notes ?? (log.action === "accept" ? "技師已接受" : "—");
          const remaining =
            log.action === "assign"
              ? formatRelativeRemaining(log.created_at, log.timeout_seconds)
              : { label: "—", cls: "text-[var(--text-secondary)]" };

          return (
            <div
              key={log.id}
              className={`flex items-center border-t border-[var(--border)] px-4 py-3 hover:bg-[#EFF6FF] ${
                isStuck ? "border-l-4 border-l-[#EF4444] bg-[#FEF2F2]" : ""
              }`}
            >
              <div className="flex w-10 shrink-0 items-center justify-center">
                <ChevronRight className="h-4 w-4 text-[var(--text-secondary)]" />
              </div>

              <Link
                href={`/work-orders/${log.work_order_id}`}
                className="w-[140px] shrink-0 truncate font-mono text-[12px] font-medium text-[var(--primary)]"
                title={log.work_order_id}
              >
                {log.work_order_id?.slice(0, 8) ?? "—"}
              </Link>

              <div className="flex w-20 shrink-0 items-center">
                <span
                  className="rounded px-2 py-[2px] text-xs font-semibold"
                  style={{ backgroundColor: badge.bg, color: badge.text }}
                >
                  {badge.label}
                </span>
              </div>

              <div className="flex w-[140px] shrink-0 items-center gap-2">
                <div
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
                  style={{ backgroundColor: techColor(log.technician_name) }}
                >
                  {techName[0] ?? "?"}
                </div>
                <span className="truncate text-[13px] text-[var(--text-primary)]">
                  {techName}
                </span>
              </div>

              <div className="flex w-[120px] shrink-0 items-center gap-2">
                {score != null ? (
                  <>
                    <div className="h-[6px] w-[60px] overflow-hidden rounded-full bg-[#E2E8F0]">
                      <div
                        className="h-full rounded-full"
                        style={{ width: barWidth, backgroundColor: color }}
                      />
                    </div>
                    <span
                      className="text-[13px] font-semibold"
                      style={{ color }}
                    >
                      {Math.round(score)}
                    </span>
                  </>
                ) : (
                  <span className="text-[13px] text-[var(--text-disabled)]">—</span>
                )}
              </div>

              <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--text-secondary)]">
                {reasonText}
              </span>

              <span
                className={`w-[100px] shrink-0 text-[13px] ${remaining.cls}`}
              >
                {remaining.label}
              </span>

              <span className="w-[130px] shrink-0 text-[13px] text-[var(--text-secondary)]">
                {formatCreatedAt(log.created_at)}
              </span>

              <div className="flex w-20 shrink-0 items-center">
                {isStuck ? (
                  <button
                    disabled
                    title="即將推出"
                    className="cursor-not-allowed rounded-md bg-[var(--primary)] px-3 py-1 text-xs font-semibold text-white opacity-60"
                  >
                    介入
                  </button>
                ) : (
                  <button
                    disabled
                    title="即將推出"
                    className="flex h-8 w-8 cursor-not-allowed items-center justify-center rounded-md opacity-60"
                  >
                    <Ellipsis className="h-5 w-5 text-[var(--text-secondary)]" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between px-4">
        <span className="text-[13px] text-[var(--text-secondary)]">
          顯示 {rows.length} 筆活躍工單（共 {items.length} 條派工事件）
        </span>
      </div>
    </div>
  );
}
