"use client";

// CR-0114 平台 console 儀表板 + CR-0116 維運監控分頁。
// 分頁:
//   - 概覽:待審計數卡(複用既有 list 端點 status 過濾,零新 API),點卡進審核頁。
//   - 維運監控:跨品牌 /health 紅綠燈(monitor_target registry + 並發探測)。

import { useEffect, useState } from "react";
import Link from "next/link";
import { Building2, UserCheck, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import OpsMonitorPanel from "@/components/platform/OpsMonitorPanel";

interface PlatformMe {
  data: { id: string; display_name: string | null; email: string };
}

type Tab = "overview" | "monitor";

const TABS: { value: Tab; label: string }[] = [
  { value: "overview", label: "概覽" },
  { value: "monitor", label: "維運監控" },
];

export default function PlatformDashboardPage() {
  const [me, setMe] = useState<PlatformMe["data"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    let cancelled = false;
    api
      .get<PlatformMe>("/api/v1/platform/me")
      .then((res) => {
        if (!cancelled) setMe(res.data);
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">儀表板</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          {me ? `${me.display_name || me.email}，歡迎回來。` : error ?? "載入中…"}
        </p>
      </div>

      {/* 分頁切換 */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map((t) => {
          const active = tab === t.value;
          return (
            <button
              key={t.value}
              type="button"
              onClick={() => setTab(t.value)}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
                active
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "overview" ? <OverviewPanel /> : <OpsMonitorPanel />}
    </div>
  );
}

// ── 概覽:平台總覽統計 + 待審 + 租戶摘要(零新 API,複用既有 list 端點)────────

interface TenantRow {
  id: string;
  slug: string;
  company_name: string;
  status: string;
  created_at?: string | null;
}

interface Overview {
  brandApps: number;
  vendors: number;
  techPending: number;
  techActive: number;
  techTotal: number;
  tenants: TenantRow[];
}

const TENANT_STATUS_META: Record<string, { label: string; cls: string }> = {
  active: { label: "營運中", cls: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)] border-[var(--badge-success-fg)]/25" },
  suspended: { label: "已停用", cls: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)] border-[var(--badge-warn-fg)]/25" },
};

function OverviewPanel() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [techRes, brandRes, vendorRes, tenantRes] = await Promise.all([
          api.get<{ data: { status?: string }[] }>("/api/v1/platform/technicians"),
          api.get<{ data: unknown[] }>("/api/v1/platform/brand-applications?status=pending"),
          api.get<{ items: unknown[] }>("/api/v1/platform/vendors?status=pending_approval"),
          api.get<{ data: TenantRow[] }>("/api/v1/platform/tenants"),
        ]);
        if (cancelled) return;
        const techs = techRes.data ?? [];
        setOv({
          techPending: techs.filter((t) => t.status === "pending_approval").length,
          techActive: techs.filter((t) => t.status === "active").length,
          techTotal: techs.length,
          brandApps: brandRes.data?.length ?? 0,
          vendors: vendorRes.items?.length ?? 0,
          tenants: tenantRes.data ?? [],
        });
      } catch (err) {
        if (!cancelled) setError(friendlyError(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const requestorPending = ov ? ov.brandApps + ov.vendors : null;
  const activeTenants = ov ? ov.tenants.filter((t) => t.status === "active").length : null;

  return (
    <div className="flex flex-col gap-6">
      {error && (
        <div className="rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-4 py-3 text-sm text-[var(--badge-danger-fg)]">
          {error}
        </div>
      )}

      {/* 平台總覽統計 */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="營運中租戶" value={activeTenants} suffix={ov ? `／共 ${ov.tenants.length} 個品牌` : ""} />
        <StatCard label="啟用中師傅" value={ov?.techActive ?? null} suffix={ov ? `／共 ${ov.techTotal} 位` : ""} />
        <StatCard label="待審發案方" value={requestorPending} warn suffix="件" />
        <StatCard label="待審師傅" value={ov?.techPending ?? null} warn suffix="件" />
      </div>

      {/* 待辦(點卡進審核頁) */}
      <div className="grid gap-4 sm:grid-cols-2">
        <PendingCard
          href="/platform/requestors"
          icon={Building2}
          title="待審發案方"
          count={requestorPending}
          subtitle={
            ov
              ? `品牌申請 ${ov.brandApps}　·　廠商帳號 ${ov.vendors}`
              : "品牌／經銷／鎖店的平台導入申請與帳號審核"
          }
        />
        <PendingCard
          href="/platform/technicians"
          icon={UserCheck}
          title="待審師傅"
          count={ov ? ov.techPending : null}
          subtitle="鎖匠師傅的註冊審核與生命週期管理"
        />
      </div>

      {/* 租戶摘要 */}
      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)]">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
          <p className="text-sm font-semibold text-[var(--text-primary)]">品牌租戶</p>
          <Link
            href="/platform/tenants"
            className="inline-flex items-center gap-1 text-xs font-medium text-[var(--primary)] hover:underline"
          >
            管理租戶與 License
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>
        {ov === null ? (
          <p className="px-6 py-6 text-sm text-[var(--text-secondary)]">載入中…</p>
        ) : ov.tenants.length === 0 ? (
          <p className="px-6 py-6 text-sm text-[var(--text-secondary)]">尚無已開站租戶。</p>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {ov.tenants.slice(0, 5).map((t) => {
              const meta = TENANT_STATUS_META[t.status] ?? {
                label: t.status,
                cls: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)] border-[var(--border)]",
              };
              return (
                <li key={t.id} className="flex items-center gap-3 px-6 py-3.5">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--primary-subtle,rgba(59,130,246,0.12))] text-sm font-bold text-[var(--primary)]">
                    {(t.company_name || t.slug).slice(0, 1)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                      {t.company_name}
                    </p>
                    <p className="truncate font-mono text-xs text-[var(--text-secondary)]">{t.slug}</p>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-medium ${meta.cls}`}>
                    {meta.label}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  suffix,
  warn,
}: {
  label: string;
  value: number | null;
  suffix?: string;
  warn?: boolean;
}) {
  const highlight = warn && value !== null && value > 0;
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-5">
      <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span
          className={`text-3xl font-bold leading-none tabular-nums ${
            highlight ? "text-[var(--badge-warn-fg)]" : "text-[var(--text-primary)]"
          }`}
        >
          {value === null ? "—" : value}
        </span>
        {suffix && <span className="text-xs text-[var(--text-secondary)]">{suffix}</span>}
      </div>
    </div>
  );
}

function PendingCard({
  href,
  icon: Icon,
  title,
  count,
  subtitle,
}: {
  href: string;
  icon: typeof Building2;
  title: string;
  count: number | null;
  subtitle: string;
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col gap-4 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 transition hover:border-[var(--primary)] hover:shadow-sm"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--primary-subtle,rgba(59,130,246,0.12))]">
            <Icon className="h-5 w-5 text-[var(--primary)]" aria-hidden />
          </div>
          <p className="text-sm font-semibold text-[var(--text-primary)]">{title}</p>
        </div>
        <ArrowRight
          className="h-4 w-4 text-[var(--text-secondary)] transition group-hover:translate-x-0.5 group-hover:text-[var(--primary)]"
          aria-hidden
        />
      </div>
      <div className="flex items-end gap-2">
        <span className="text-4xl font-bold leading-none text-[var(--text-primary)]">
          {count === null ? "—" : count}
        </span>
        <span className="pb-1 text-xs text-[var(--text-secondary)]">件待審核</span>
      </div>
      <p className="text-xs text-[var(--text-secondary)]">{subtitle}</p>
    </Link>
  );
}
