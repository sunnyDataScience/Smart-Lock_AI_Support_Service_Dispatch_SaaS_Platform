"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Calendar,
  ClipboardList,
  CircleAlert,
  DollarSign,
  MessageSquare,
  Pencil,
  Phone,
  Star,
  Wallet,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { statusGroupOf } from "@/components/work-orders/WorkOrdersTable";
import { api, resolveTenantId } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useLocale, useTranslations } from "@/components/i18n/LocaleProvider";

interface RecentOrder {
  id: string;
  status: string;
  address: string | null;
  brand: string | null;
  model: string | null;
  priority: string | null;
  estimated_price: number | null;
  created_at: string | null;
  completed_at: string | null;
}

interface RecentConversation {
  id: string;
  status: string;
  channel: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface CustomerDetail {
  id: string;
  display_name: string;
  line_user_id: string | null;
  phone: string | null;
  address: string | null;
  last_active_at: string | null;
  total_conversations: number;
  total_orders: number;
  last_service_at: string | null;
  created_at: string;
  history: {
    work_order_status_breakdown: Record<string, number>;
    avg_completion_minutes: number | null;
    avg_rating: number | null;
    rated_count: number;
    dispute_count: number;
    refund_count: number;
    refund_total: number;
    recent_orders: RecentOrder[];
    recent_conversations: RecentConversation[];
  };
}

function formatTwd(n: number | null | undefined): string {
  if (n == null) return "—";
  return `NT$ ${Math.round(n).toLocaleString("en-US")}`;
}

export default function CustomerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const t = useTranslations("admin.customers.detail");
  // UAT P2-10：工單狀態 label 與派工管理統一 —— 共用 statusGroupOf +
  // status.workOrderGroup 字典（原本本頁自建 待派工/已確認 等字典，兩處不一致）
  const tGroup = useTranslations("status.workOrderGroup");
  const tKpi = useTranslations("admin.customers.detail.kpi");
  const tCols = useTranslations("admin.customers.detail.ordersCols");
  const tConvStatus = useTranslations("admin.customers.detail.convStatus");
  const tConvChannel = useTranslations("admin.customers.detail.convChannel");
  const { locale } = useLocale();
  const formatDateTime = (iso?: string | null): string => {
    if (!iso) return "—";
    return new Date(iso).toLocaleString(locale, { hour12: false });
  };
  const statusLabel = (status: string): string => tGroup(statusGroupOf(status));
  // 對話 status / channel label（i18n；未知值回退原始值）。
  const convStatusLabel = (s: string): string => {
    const known: Record<string, string> = {
      active: tConvStatus("active"),
      escalated: tConvStatus("escalated"),
      closed: tConvStatus("closed"),
    };
    return known[s] ?? s;
  };
  const convChannelLabel = (c: string): string => {
    const known: Record<string, string> = {
      line: tConvChannel("line"),
      web: tConvChannel("web"),
      phone: tConvChannel("phone"),
    };
    return known[c] ?? c;
  };
  const [data, setData] = useState<CustomerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        // CR-0002-α：遷移至 tenant-scoped v2 端點
        const tenantId = resolveTenantId();
        const res = await api.get<CustomerDetail>(
          `/tenants/${encodeURIComponent(tenantId)}/customers/${encodeURIComponent(id)}`,
        );
        if (!cancelled) setData(res);
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
  }, [id]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <div className="flex items-center gap-2">
            <Link
              href="/admin/customers"
              className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              aria-label={t("back")}
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {t("breadcrumb")}
            </span>
          </div>
          {data && (
            <Link
              href={`/admin/customers/${id}/edit`}
              className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-[7px] text-[13px] text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
            >
              <Pencil className="h-3.5 w-3.5" />
              {t("edit")}
            </Link>
          )}
        </div>

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-[13px] text-red-700">
            {error}
          </div>
        )}

        {loading && !data ? (
          <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
            {t("loading")}
          </div>
        ) : !data ? (
          <div className="m-8 text-[14px] text-[var(--text-secondary)]">
            {t("notFound")}
          </div>
        ) : (
          <main className="flex-1 overflow-auto px-8 py-6">
            <div className="grid grid-cols-3 gap-6">
              {/* 左欄：profile */}
              <section className="col-span-1 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5 shadow-sm">
                <div className="mb-4 flex items-center gap-3">
                  <div
                    className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--primary)]/10 text-[20px] font-bold text-[var(--primary)]"
                  >
                    {data.display_name.slice(0, 1).toUpperCase()}
                  </div>
                  <div>
                    <h2 className="text-[18px] font-bold text-[var(--text-primary)]">
                      {data.display_name}
                    </h2>
                    <span className="font-mono text-[11px] text-[var(--text-disabled)]">
                      #{data.id.slice(0, 8)}
                    </span>
                  </div>
                </div>
                <div className="flex flex-col gap-2 text-[13px]">
                  <div className="flex items-center gap-2">
                    <Phone className="h-3 w-3 text-[var(--text-secondary)]" />
                    <span className="text-[var(--text-primary)]">
                      {data.phone || "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-secondary)]">{t("addressLabel")}</span>
                    <span className="text-[var(--text-primary)]">
                      {data.address || "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-secondary)]">
                      {t("lineIdLabel")}
                    </span>
                    <span className="font-mono text-[11px] text-[var(--text-secondary)]">
                      {data.line_user_id
                        ? data.line_user_id.slice(0, 14) + "…"
                        : "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-secondary)]">
                      {t("createdLabel")}
                    </span>
                    <span className="text-[var(--text-primary)]">
                      {formatDateTime(data.created_at)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-secondary)]">
                      {t("lastActiveLabel")}
                    </span>
                    <span className="text-[var(--text-primary)]">
                      {formatDateTime(data.last_active_at)}
                    </span>
                  </div>
                </div>
              </section>

              {/* 中右欄：統計卡 + 歷史 */}
              <div className="col-span-2 flex flex-col gap-6">
                <section className="grid grid-cols-4 gap-3">
                  <KpiCard
                    icon={ClipboardList}
                    label={tKpi("totalOrders")}
                    value={data.total_orders}
                    color="var(--primary)"
                  />
                  <KpiCard
                    icon={MessageSquare}
                    label={tKpi("totalConversations")}
                    value={data.total_conversations}
                    color="var(--info)"
                  />
                  <KpiCard
                    icon={Star}
                    label={tKpi("avgRating")}
                    value={
                      data.history.avg_rating != null
                        ? data.history.avg_rating.toFixed(2)
                        : "—"
                    }
                    sub={
                      data.history.rated_count > 0
                        ? tKpi("rated", { count: String(data.history.rated_count) })
                        : tKpi("noRating")
                    }
                    color="var(--accent-hover)"
                  />
                  <KpiCard
                    icon={CircleAlert}
                    label={tKpi("disputeCount")}
                    value={data.history.dispute_count}
                    color={
                      data.history.dispute_count > 0
                        ? "var(--error)"
                        : "var(--text-secondary)"
                    }
                  />
                </section>

                <section className="grid grid-cols-3 gap-3">
                  <KpiCard
                    icon={Calendar}
                    label={tKpi("avgCompletion")}
                    value={
                      data.history.avg_completion_minutes != null
                        ? tKpi("minutes", { min: String(Math.round(data.history.avg_completion_minutes)) })
                        : "—"
                    }
                    color="var(--info)"
                  />
                  <KpiCard
                    icon={Wallet}
                    label={tKpi("refundCount")}
                    value={data.history.refund_count}
                    color={
                      data.history.refund_count > 0
                        ? "var(--error)"
                        : "var(--text-secondary)"
                    }
                  />
                  <KpiCard
                    icon={DollarSign}
                    label={tKpi("refundTotal")}
                    value={formatTwd(data.history.refund_total)}
                    color={
                      data.history.refund_total > 0
                        ? "var(--error)"
                        : "var(--text-secondary)"
                    }
                  />
                </section>

                {/* 工單狀態分布 */}
                {Object.keys(data.history.work_order_status_breakdown).length >
                  0 && (
                  <section className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
                    <h3 className="mb-3 text-[14px] font-semibold text-[var(--text-primary)]">
                      {t("statusBreakdown")}
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {/* UAT P2-10：原始狀態先折成派工管理的狀態群組再加總，
                          避免同群組（如 completed/confirmed）拆成兩顆同名籤 */}
                      {Object.entries(
                        Object.entries(
                          data.history.work_order_status_breakdown,
                        ).reduce<Record<string, number>>((acc, [status, count]) => {
                          const label = statusLabel(status);
                          return { ...acc, [label]: (acc[label] ?? 0) + count };
                        }, {}),
                      ).map(([label, count]) => (
                        <span
                          key={label}
                          className="rounded-md bg-[#F1F5F9] px-3 py-1 text-[12px] text-[var(--text-secondary)]"
                        >
                          {t("statusValue", { label })}
                          <strong className="text-[var(--text-primary)]">
                            {count}
                          </strong>
                        </span>
                      ))}
                    </div>
                  </section>
                )}

                {/* 最近工單 */}
                <section className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
                  <h3 className="mb-3 text-[14px] font-semibold text-[var(--text-primary)]">
                    {t("recentOrders", { count: String(data.history.recent_orders.length) })}
                  </h3>
                  {data.history.recent_orders.length === 0 ? (
                    <p className="py-4 text-center text-[12px] text-[var(--text-disabled)]">
                      {t("noOrders")}
                    </p>
                  ) : (
                    <table className="w-full text-[12px]">
                      <thead className="bg-[#F8FAFC] text-left text-[11px] text-[var(--text-secondary)]">
                        <tr>
                          <th className="px-2 py-2">{tCols("id")}</th>
                          <th className="px-2 py-2">{tCols("brandModel")}</th>
                          <th className="px-2 py-2">{tCols("status")}</th>
                          <th className="px-2 py-2 text-right">{tCols("estimate")}</th>
                          <th className="px-2 py-2">{tCols("createdAt")}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]">
                        {data.history.recent_orders.map((wo) => (
                          <tr
                            key={wo.id}
                            className="hover:bg-[#F8FAFC]"
                          >
                            <td className="px-2 py-2">
                              <Link
                                href={`/work-orders/${wo.id}`}
                                className="font-mono text-[var(--primary)] hover:underline"
                              >
                                #{wo.id.slice(0, 8)}
                              </Link>
                            </td>
                            <td className="px-2 py-2 text-[var(--text-primary)]">
                              {wo.brand} {wo.model}
                            </td>
                            <td className="px-2 py-2">
                              <span className="rounded bg-[#F1F5F9] px-2 py-[1px] text-[11px]">
                                {statusLabel(wo.status)}
                              </span>
                            </td>
                            <td className="px-2 py-2 text-right">
                              {formatTwd(wo.estimated_price)}
                            </td>
                            <td className="px-2 py-2 text-[var(--text-secondary)]">
                              {formatDateTime(wo.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </section>

                {/* 最近對話 */}
                <section className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
                  <h3 className="mb-3 text-[14px] font-semibold text-[var(--text-primary)]">
                    {t("recentConversations", { count: String(data.history.recent_conversations.length) })}
                  </h3>
                  {data.history.recent_conversations.length === 0 ? (
                    <p className="py-4 text-center text-[12px] text-[var(--text-disabled)]">
                      {t("noConversations")}
                    </p>
                  ) : (
                    <ul className="divide-y divide-[var(--border)]">
                      {data.history.recent_conversations.map((conv) => (
                        <li key={conv.id} className="py-2">
                          <div className="flex items-center justify-between">
                            <Link
                              href={`/conversations/${conv.id}`}
                              className="font-mono text-[12px] text-[var(--primary)] hover:underline"
                            >
                              #{conv.id.slice(0, 8)}
                            </Link>
                            <span className="text-[11px] text-[var(--text-disabled)]">
                              {formatDateTime(conv.updated_at)}
                            </span>
                          </div>
                          <div className="mt-1 flex gap-2 text-[11px] text-[var(--text-secondary)]">
                            <span className="rounded bg-[#F1F5F9] px-2 py-[1px]">
                              {convStatusLabel(conv.status)}
                            </span>
                            {conv.channel && (
                              <span className="rounded bg-[#F1F5F9] px-2 py-[1px]">
                                {convChannelLabel(conv.channel)}
                              </span>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>
            </div>
          </main>
        )}
      </div>
    </div>
  );
}

interface KpiCardProps {
  icon: React.ComponentType<{
    className?: string;
    style?: React.CSSProperties;
  }>;
  label: string;
  value: number | string;
  sub?: string;
  color?: string;
}

function KpiCard({ icon: Icon, label, value, sub, color = "var(--primary)" }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-3 shadow-sm">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4" style={{ color }} />
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {label}
        </span>
      </div>
      <div className="mt-1 text-[20px] font-bold" style={{ color }}>
        {value}
      </div>
      {sub && (
        <div className="text-[10px] text-[var(--text-disabled)]">{sub}</div>
      )}
    </div>
  );
}
