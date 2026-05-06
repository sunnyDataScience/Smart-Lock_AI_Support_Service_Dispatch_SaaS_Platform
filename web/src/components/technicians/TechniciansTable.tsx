"use client";

import { Star, Ellipsis } from "lucide-react";
import Link from "next/link";
import type { components } from "@/types/api.generated";

type Technician = components["schemas"]["Technician"];
type Availability = Technician["availability"];

interface Props {
  items: Technician[];
  loading?: boolean;
}

interface AvailabilityStyle {
  label: string;
  textColor: string;
  bgColor: string;
}

const AVAILABILITY_STYLE: Record<Availability, AvailabilityStyle> = {
  available: { label: "可用", textColor: "#065F46", bgColor: "#D1FAE5" },
  busy: { label: "外出中", textColor: "#1E40AF", bgColor: "#DBEAFE" },
  offline: { label: "離線", textColor: "var(--text-secondary)", bgColor: "var(--bg-page)" },
  on_leave: { label: "休假中", textColor: "#92400E", bgColor: "#FEF3C7" },
  circuit_breaker_open: { label: "暫停派工", textColor: "#991B1B", bgColor: "#FEE2E2" },
};

const BRAND_STYLE: Record<string, { textColor: string; bgColor: string }> = {
  Yale: { textColor: "#92400E", bgColor: "#FEF3C7" },
  Chatlock: { textColor: "#3730A3", bgColor: "#E0E7FF" },
  美樂: { textColor: "#065F46", bgColor: "#D1FAE5" },
  "Mi-La": { textColor: "#065F46", bgColor: "#D1FAE5" },
  Dormakaba: { textColor: "#1E40AF", bgColor: "#DBEAFE" },
};

const FALLBACK_BRAND = { textColor: "var(--text-secondary)", bgColor: "var(--bg-page)" };

const AVATAR_PALETTE = ["#DBEAFE", "#FEF3C7", "#FCE7F3", "#E0E7FF", "#D1FAE5", "#FEE2E2", "#F3E8FF", "#FFEDD5"];

function avatarColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length];
}

const columns = [
  { label: "", width: "w-[52px] shrink-0" },
  { label: "技師", width: "w-[200px] shrink-0" },
  { label: "專長品牌", width: "w-[180px] shrink-0" },
  { label: "服務區域", width: "w-[180px] shrink-0" },
  { label: "評分", width: "w-[80px] shrink-0" },
  { label: "狀態", width: "w-[100px] shrink-0" },
  { label: "完成工單", width: "w-[100px] shrink-0" },
  { label: "操作", width: "flex-1 min-w-0" },
];

export default function TechniciansTable({ items, loading }: Props) {
  return (
    <div className="flex min-w-0 flex-1 flex-col bg-[var(--bg-surface)]">
      {/* Header Row */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-8">
        <div className="flex w-[52px] shrink-0 items-center">
          <div className="h-[18px] w-[18px] rounded border-[1.5px] border-[var(--border)]" />
        </div>
        {columns.slice(1).map((col) => (
          <div key={col.label} className={`flex items-center ${col.width}`}>
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {/* Body */}
      {loading && items.length === 0 ? (
        <div className="flex min-w-0 flex-1 items-center justify-center py-12 text-sm text-[var(--text-secondary)]">
          載入中…
        </div>
      ) : items.length === 0 ? (
        <div className="flex min-w-0 flex-1 items-center justify-center py-12 text-sm text-[var(--text-secondary)]">
          目前沒有技師
        </div>
      ) : (
        items.map((t) => {
          const status = AVAILABILITY_STYLE[t.availability] ?? AVAILABILITY_STYLE.available;
          const brands = (t.skills ?? []).slice(0, 3);
          const region = (t.service_areas ?? []).slice(0, 2).join("、") || "—";
          return (
            <div
              key={t.id}
              className="flex h-[60px] items-center border-b border-[var(--border)] px-8"
            >
              {/* Checkbox */}
              <div className="flex w-[52px] shrink-0 items-center">
                <div className="h-[18px] w-[18px] rounded border-[1.5px] border-[var(--border)]" />
              </div>

              {/* Tech info */}
              <div className="flex w-[200px] shrink-0 items-center gap-[10px]">
                <div
                  className="h-9 w-9 flex-shrink-0 rounded-full"
                  style={{ backgroundColor: avatarColor(t.id) }}
                />
                <div className="flex flex-col gap-[2px]">
                  <Link
                    href={`/technicians/${t.id}`}
                    className="text-[14px] font-medium text-[var(--text-primary)] hover:underline"
                  >
                    {t.name}
                  </Link>
                  <span className="font-['IBM_Plex_Mono'] text-[11px] text-[var(--text-secondary)]">
                    {t.phone}
                  </span>
                </div>
              </div>

              {/* Brands */}
              <div className="flex w-[180px] shrink-0 flex-wrap items-center gap-1">
                {brands.length > 0 ? (
                  brands.map((b) => {
                    const style = BRAND_STYLE[b] ?? FALLBACK_BRAND;
                    return (
                      <span
                        key={b}
                        className="rounded px-2 py-[2px] text-[11px] font-medium"
                        style={{ color: style.textColor, backgroundColor: style.bgColor }}
                      >
                        {b}
                      </span>
                    );
                  })
                ) : (
                  <span className="text-[11px] text-[var(--text-disabled)]">—</span>
                )}
              </div>

              {/* Region */}
              <div className="flex w-[180px] shrink-0 items-center">
                <span className="text-[13px] text-[var(--text-primary)]">
                  {region}
                </span>
              </div>

              {/* Rating */}
              <div className="flex w-[80px] shrink-0 items-center gap-1">
                <Star className="h-[14px] w-[14px] fill-[var(--accent)] text-[var(--accent)]" />
                <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                  {t.rating.toFixed(1)}
                </span>
              </div>

              {/* Status */}
              <div className="flex w-[100px] shrink-0 items-center">
                <span
                  className="rounded-full px-[10px] py-[3px] text-[12px] font-medium"
                  style={{ color: status.textColor, backgroundColor: status.bgColor }}
                >
                  {status.label}
                </span>
              </div>

              {/* Completed Orders */}
              <div className="flex w-[100px] shrink-0 items-center">
                <span className="text-[14px] font-semibold text-[var(--primary)]">
                  {t.completed_orders_count ?? 0}
                </span>
              </div>

              {/* Actions */}
              <div className="flex min-w-0 flex-1 items-center">
                <Ellipsis className="h-5 w-5 text-[var(--text-secondary)]" />
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
