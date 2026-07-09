"use client";

import { useMemo } from "react";
import { MapPin, X } from "lucide-react";
import Link from "next/link";
import type { components } from "@/types/api.generated";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_TONE,
  URGENCY_TONE,
  type StatusGroup,
} from "@/components/work-orders/WorkOrdersTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type WorkOrder = components["schemas"]["WorkOrder"];
type Urgency = components["schemas"]["Urgency"];

interface Props {
  items: WorkOrder[];
  selectedItem: WorkOrder | null;
  onClose: () => void;
}

interface DistrictBucket {
  district: string;
  count: number;
  pending: number;
  inProgress: number;
  done: number;
}

function bucketByDistrict(
  items: WorkOrder[],
  noDistrictLabel: string,
): DistrictBucket[] {
  const map = new Map<string, DistrictBucket>();
  for (const item of items) {
    const key = item.district || noDistrictLabel;
    const group = STATUS_GROUP_MAP[item.status];
    const bucket = map.get(key) ?? {
      district: key,
      count: 0,
      pending: 0,
      inProgress: 0,
      done: 0,
    };
    bucket.count += 1;
    if (group === "pending" || group === "dispatched") bucket.pending += 1;
    else if (group === "in_progress") bucket.inProgress += 1;
    else if (group === "done") bucket.done += 1;
    map.set(key, bucket);
  }
  return [...map.values()].sort((a, b) => b.count - a.count);
}

function shortId(id: string): string {
  return id.slice(0, 8);
}

export default function MapView({ items, selectedItem, onClose }: Props) {
  const t = useTranslations("components.workOrders.mapView");
  const tGroup = useTranslations("status.workOrderGroup");
  const tUrgency = useTranslations("urgency");

  const groupLabels: Record<StatusGroup, string> = useMemo(
    () => ({
      pending: tGroup("pending"),
      dispatched: tGroup("dispatched"),
      in_progress: tGroup("in_progress"),
      done: tGroup("done"),
      cancelled: tGroup("cancelled"),
    }),
    [tGroup],
  );

  const urgencyBaseLabels: Record<Urgency, string> = useMemo(
    () => ({
      low: tUrgency("low"),
      medium: tUrgency("medium"),
      high: tUrgency("high"),
    }),
    [tUrgency],
  );

  const noDistrictLabel = t("noDistrict");
  const buckets = bucketByDistrict(items, noDistrictLabel);

  return (
    <div className="relative flex flex-1 flex-col gap-4 bg-[var(--bg-page)] p-6">
      <div className="rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
        {t("notice")}
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        <div className="flex w-[260px] flex-shrink-0 flex-col rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
          <div className="flex items-center gap-2 border-b border-[var(--border)] px-4 py-3">
            <MapPin className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              {t("districtTitle")}
            </span>
          </div>
          <div className="flex flex-1 flex-col overflow-auto">
            {buckets.length === 0 ? (
              <div className="flex h-[120px] items-center justify-center text-[12px] text-[var(--text-secondary)]">
                {t("noData")}
              </div>
            ) : (
              buckets.map((b) => (
                <div
                  key={b.district}
                  className="flex flex-col gap-1 border-b border-[var(--border)] px-4 py-3 last:border-b-0"
                >
                  <div className="flex items-center justify-between">
                    <span
                      className="truncate text-[13px] font-medium text-[var(--text-primary)]"
                      title={b.district}
                    >
                      {b.district || noDistrictLabel}
                    </span>
                    <span className="rounded bg-[#1E293B] px-2 py-[2px] text-[11px] font-bold text-white">
                      {b.count}
                    </span>
                  </div>
                  <div className="flex gap-2 text-[10px]">
                    <span style={{ color: "#6366F1" }}>
                      {t("bucketPending", { count: b.pending })}
                    </span>
                    <span style={{ color: "#3B82F6" }}>
                      {t("bucketInProgress", { count: b.inProgress })}
                    </span>
                    <span style={{ color: "#10B981" }}>
                      {t("bucketDone", { count: b.done })}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="relative flex flex-1 items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-gradient-to-br from-[#E2E8F0] to-[#CBD5E1] p-6">
          {selectedItem ? (
            <div className="absolute left-6 top-6 flex w-[320px] flex-col gap-3 rounded-xl bg-[var(--bg-surface)] p-4 shadow-xl">
              <div className="flex items-center justify-between">
                <span
                  className="font-mono text-[13px] font-semibold text-[var(--text-primary)]"
                  title={selectedItem.id}
                >
                  {shortId(selectedItem.id)}
                </span>
                <button
                  onClick={onClose}
                  className="rounded p-1 hover:bg-[var(--bg-page)]"
                >
                  <X className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
                </button>
              </div>

              <div className="flex items-center gap-2">
                {(() => {
                  const group = STATUS_GROUP_MAP[selectedItem.status];
                  const tone = STATUS_GROUP_TONE[group];
                  return (
                    <span
                      className="rounded-full px-[10px] py-[2px] text-[11px] font-medium"
                      style={{ color: tone.color, backgroundColor: tone.bg }}
                    >
                      {groupLabels[group]}
                    </span>
                  );
                })()}
                {(() => {
                  const u = URGENCY_TONE[selectedItem.urgency];
                  return (
                    <span
                      className="rounded px-2 py-[2px] text-[11px] font-medium"
                      style={{ color: u.color, backgroundColor: u.bg }}
                    >
                      {t("urgency", { label: urgencyBaseLabels[selectedItem.urgency] })}
                    </span>
                  );
                })()}
              </div>

              <div className="h-px w-full bg-[var(--border)]" />

              <div className="flex flex-col gap-[6px]">
                <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                  {selectedItem.brand || "—"} {selectedItem.model || ""}
                </span>
                <span className="text-[12px] text-[var(--text-secondary)]">
                  {selectedItem.district || "—"}
                </span>
                <span
                  className="text-[12px] text-[var(--text-secondary)]"
                  title={selectedItem.address}
                >
                  {selectedItem.address || "—"}
                </span>
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {selectedItem.technician_id
                      ? t("techTag", { id: selectedItem.technician_id.slice(0, 4) })
                      : t("unassigned")}
                  </span>
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {selectedItem.scheduled_time
                      ? t("scheduled", {
                          time: new Date(selectedItem.scheduled_time).toLocaleString("zh-TW", {
                            hour12: false,
                          }),
                        })
                      : t("unscheduled")}
                  </span>
                </div>
              </div>

              <div className="h-px w-full bg-[var(--border)]" />

              <div className="flex items-center justify-between">
                <button
                  disabled
                  title={t("comingSoon")}
                  className="flex h-[34px] cursor-not-allowed items-center gap-[6px] rounded-lg bg-[#CBD5E1] px-4 opacity-70"
                >
                  <span className="text-[13px] font-semibold text-white">
                    {t("assignTech")}
                  </span>
                </button>
                <Link
                  href={`/work-orders/${selectedItem.id}`}
                  className="text-[13px] font-medium text-[var(--primary)] hover:underline"
                >
                  {t("viewDetail")}
                </Link>
              </div>
            </div>
          ) : (
            <div className="text-center">
              <MapPin className="mx-auto h-10 w-10 text-[var(--text-disabled)]" />
              <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
                {t("hint")}
              </p>
              <p className="mt-1 text-[11px] text-[var(--text-disabled)]">
                {t("hintSub")}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
