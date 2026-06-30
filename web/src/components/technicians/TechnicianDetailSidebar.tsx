"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import PenaltyBonusLog from "@/components/technicians/PenaltyBonusLog";
import { formatRelative } from "@/lib/format";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_TONE,
  type StatusGroup,
} from "@/components/work-orders/WorkOrdersTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];
type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];

const ACTIVE_STATUSES: ReadonlySet<WorkOrderStatus> = new Set([
  "accepted",
  "scheduled",
  "dispatching",
  "assigned",
  "en_route",
  "arrived",
  "in_progress",
]);

interface Props {
  technicianId?: string;
  /** CR-0104：技師真實在線狀態（online_state），由 admin 詳情頁傳入，供 AvailabilityCard 顯示真值 */
  availability?: string;
}

/* CR-0104：在線狀態顯示對照（值域對齊後端 online_state CHECK / TechnicianAvailability enum）。
   與主頁 header 徽章標籤一致。 */
const AVAILABILITY_DISPLAY: Record<string, { label: string; color: string; dot: string }> = {
  available: { label: "可用", color: "#059669", dot: "#059669" },
  busy: { label: "外出中", color: "#1E40AF", dot: "#1E40AF" },
  offline: { label: "離線", color: "var(--text-secondary)", dot: "var(--text-disabled)" },
  on_leave: { label: "休假中", color: "#92400E", dot: "#92400E" },
  circuit_breaker_open: { label: "暫停派工", color: "#991B1B", dot: "#991B1B" },
};

// CR-0106 佣金月結回應（固定工資制；對齊 technician_commission_service）
interface CommissionLine {
  service_code: string;
  service_name: string;
  quantity: number;
  unit_payout: number;
  line_total: number;
  mapped: boolean;
}
interface CommissionSummary {
  year: number;
  month: number;
  level: string;
  completed_orders: number;
  gross_amount: number;
  deduction_total: number;
  net_amount: number;
  currency: string;
  lines: CommissionLine[];
  unmapped_count: number;
  notes: { surcharge_applied: boolean; deductions_wired: boolean; rate_source: string };
}

function ntd(n: number): string {
  return `NT$ ${Math.round(n).toLocaleString("en-US")}`;
}

export default function TechnicianDetailSidebar({ technicianId, availability }: Props) {
  return (
    <aside className="w-[360px] flex-shrink-0 flex flex-col gap-4 bg-[#F1F5F9] p-4 overflow-y-auto h-full">
      <AvailabilityCard availability={availability} />
      <ActiveOrdersCard technicianId={technicianId} />
      <CommissionSummaryCard technicianId={technicianId} />
      <PenaltyBonusLog technicianId={technicianId} />
    </aside>
  );
}

function CardWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="w-full rounded-xl p-4 flex flex-col gap-3"
      style={{
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border)",
        boxShadow: "0 1px 4px rgba(15, 23, 42, 0.05)",
      }}
    >
      {children}
    </div>
  );
}

function CardTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3
      className="text-base font-semibold"
      style={{ color: "var(--text-primary)" }}
    >
      {children}
    </h3>
  );
}

function AvailabilityCard({ availability }: { availability?: string }) {
  const t = useTranslations("components.technicians.detailSidebar");
  // CR-0104：讀真實 online_state（取代原本永遠在線的假 toggle）。無值退回 offline。
  const disp = AVAILABILITY_DISPLAY[availability ?? "offline"] ?? AVAILABILITY_DISPLAY.offline;
  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>{t("availabilityTitle")}</CardTitle>
      </div>
      <div className="flex items-center gap-2.5">
        <span className="w-3.5 h-3.5 rounded-full" style={{ backgroundColor: disp.dot }} />
        <span className="text-sm font-semibold" style={{ color: disp.color }}>
          {disp.label}
        </span>
      </div>
      <p className="text-[11px]" style={{ color: "var(--text-disabled)" }}>
        在線狀態由技師端 App 切換；管理後台僅檢視。
      </p>
    </CardWrapper>
  );
}

function ActiveOrdersCard({ technicianId }: { technicianId?: string }) {
  const t = useTranslations("components.technicians.detailSidebar");
  const tGroup = useTranslations("status.workOrderGroup");

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

  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!technicianId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setOrders([]);
    (async () => {
      try {
        const res = await api.get<WorkOrderPage>(tenantPath("/work-orders"), {
          query: { technician_id: technicianId, limit: 20 },
        });
        if (cancelled) return;
        const items = (res.items ?? []) as WorkOrder[];
        setOrders(items.filter((o) => ACTIVE_STATUSES.has(o.status)));
      } catch (e) {
        if (cancelled) return;
        setError(
          friendlyError(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [technicianId]);

  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>{t("activeOrdersTitle")}</CardTitle>
        {orders.length > 0 && (
          <span
            className="text-xs font-semibold rounded-full px-2 py-0.5 text-white"
            style={{ backgroundColor: "var(--primary)" }}
          >
            {orders.length}
          </span>
        )}
      </div>

      {error && (
        <span className="text-[12px]" style={{ color: "var(--error)" }}>
          {t("loadFailed", { error })}
        </span>
      )}

      {!error && loading && orders.length === 0 && (
        <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
          {t("querying")}
        </span>
      )}

      {!error && !loading && orders.length === 0 && (
        <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
          {t("noActive")}
        </span>
      )}

      {orders.length > 0 && (
        <div className="flex flex-col gap-2 w-full">
          {orders.map((order) => {
            const group = STATUS_GROUP_MAP[order.status];
            const tone = STATUS_GROUP_TONE[group];
            const shortId = order.id.slice(0, 8);
            const device = [order.brand, order.model].filter(Boolean).join(" ") || "—";
            const location = order.district || order.address || "—";
            return (
              <div
                key={order.id}
                className="w-full rounded-lg p-3 flex flex-col gap-1.5"
                style={{ border: "1px solid var(--border)" }}
              >
                <div className="flex items-center justify-between">
                  <Link
                    href={`/work-orders/${order.id}`}
                    className="font-mono text-xs font-semibold hover:underline"
                    style={{ color: "var(--primary)" }}
                    title={order.id}
                  >
                    {shortId}
                  </Link>
                  <span
                    className="text-[11px] font-medium rounded px-1.5 py-0.5"
                    style={{ backgroundColor: tone.bg, color: tone.color }}
                  >
                    {groupLabels[group]}
                  </span>
                </div>
                <p
                  className="text-[13px]"
                  style={{ color: "var(--text-primary)" }}
                >
                  {device} — {location}
                </p>
                <p
                  className="text-[11px]"
                  style={{ color: "var(--text-disabled)" }}
                >
                  {t("createdAt", { time: formatRelative(order.created_at) })}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </CardWrapper>
  );
}

// CR-0106：佣金月結（固定工資制）。讀真實 completed WO × payout_rule，取代抽成制 mock。
function CommissionSummaryCard({ technicianId }: { technicianId?: string }) {
  const [summary, setSummary] = useState<CommissionSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!technicianId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await api.get<{ data: CommissionSummary }>(
          tenantPath(`/technicians/${technicianId}/commission-summary`),
        );
        if (!cancelled) setSummary(res.data ?? null);
      } catch (e) {
        if (!cancelled)
          setError(
            friendlyError(e),
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [technicianId]);

  const hasData = summary && (summary.gross_amount > 0 || summary.lines.length > 0);

  return (
    <CardWrapper>
      <div className="flex items-center justify-between">
        <CardTitle>佣金摘要</CardTitle>
        {summary && (
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
            {summary.year}年{summary.month}月 · {summary.level} 級
          </span>
        )}
      </div>

      {error && (
        <span className="text-[12px]" style={{ color: "var(--error)" }}>
          載入失敗：{error}
        </span>
      )}
      {!error && loading && !summary && (
        <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
          計算中…
        </span>
      )}

      {summary && (
        <>
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            本月工資（{summary.completed_orders} 張完工單）
          </p>
          <p className="text-[28px] font-bold" style={{ color: "#059669" }}>
            {ntd(summary.gross_amount)}
          </p>

          {hasData ? (
            <div className="flex flex-col gap-1.5 w-full">
              {summary.lines.map((ln) => (
                <div key={ln.service_code} className="flex items-center justify-between w-full">
                  <span className="text-xs truncate" style={{ color: "var(--text-secondary)" }}>
                    {ln.service_name} ×{ln.quantity}
                    {!ln.mapped && (
                      <span style={{ color: "var(--error)" }}>（無費率）</span>
                    )}
                  </span>
                  <span className="text-xs" style={{ color: "var(--text-primary)" }}>
                    {ntd(ln.line_total)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
              {summary.completed_orders > 0
                ? "完工單尚無可計酬的服務明細（明細未帶服務代碼）。"
                : "本月尚無已完工工單，有工單完工後自動計算。"}
            </span>
          )}

          <div className="w-full h-px" style={{ backgroundColor: "var(--border)" }} />
          <div className="flex items-center justify-between w-full">
            <span className="text-[13px] font-semibold" style={{ color: "var(--text-primary)" }}>
              應付金額
            </span>
            <span className="text-sm font-semibold" style={{ color: "#D97706" }}>
              {ntd(summary.net_amount)}
            </span>
          </div>
          <p className="text-[11px]" style={{ color: "var(--text-disabled)" }}>
            固定工資制（業主核准費率）。夜間/急件加成與扣項（車馬/平台費等）待結算模組接入。
          </p>
        </>
      )}
    </CardWrapper>
  );
}

