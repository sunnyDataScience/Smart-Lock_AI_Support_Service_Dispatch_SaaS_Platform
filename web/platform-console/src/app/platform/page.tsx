"use client";

// CR-0114 平台 console 儀表板 + CR-0116 維運監控分頁。
// 分頁:
//   - 概覽:待審計數卡(複用既有 list 端點 status 過濾,零新 API),點卡進審核頁。
//     深連結帶 `?status=`,師傅頁會據此直接落在對應分頁(20260730:原本只到清單
//     的「全部」分頁,且上排統計卡根本不是連結——見 StatCard 註解)。
//   - 維運監控:跨品牌 /health 紅綠燈(monitor_target registry + 並發探測)。
// UAT W6-2:文案接 i18n(platform.dashboard / platform.tenants namespace)。

import { useEffect, useState } from "react";
import Link from "next/link";
import { Building2, UserCheck, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import OpsMonitorPanel from "@/components/platform/OpsMonitorPanel";

interface PlatformMe {
  data: { id: string; display_name: string | null; email: string };
}

type Tab = "overview" | "monitor";

const TABS: { value: Tab; key: string }[] = [
  { value: "overview", key: "tabOverview" },
  { value: "monitor", key: "tabMonitor" },
];

export default function PlatformDashboardPage() {
  const t = useTranslations("platform.dashboard");
  const tc = useTranslations("platform.common");
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
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          {me
            ? t("welcome", { name: me.display_name || me.email })
            : error ?? tc("loading")}
        </p>
      </div>

      {/* 分頁切換 */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map((item) => {
          const active = tab === item.value;
          return (
            <button
              key={item.value}
              type="button"
              onClick={() => setTab(item.value)}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
                active
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {t(item.key)}
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

// 20260702 退場決議 + UAT R2 W3-2:廠商帳號改平台代建(建立即啟用,無待審),
// 「待審發案方」語意收斂為「待審品牌申請」——不再計 vendors pending。
interface Overview {
  brandApps: number;
  techPending: number;
  techActive: number;
  techTotal: number;
  tenants: TenantRow[];
}

// 師傅狀態值。同時用於「算計數」與「組深連結的 ?status=」——兩邊必須是同一個字串,
// 否則卡片顯示 3 件待審、點進去卻篩不到(師傅頁只認 FILTERS 內的值,拼錯會靜默退回全部)。
const TECH_STATUS_PENDING = "pending_approval";
const TECH_STATUS_ACTIVE = "active";

const TENANT_STATUS_CLS: Record<string, string> = {
  active: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)] border-[var(--badge-success-fg)]/25",
  suspended: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)] border-[var(--badge-warn-fg)]/25",
};

function OverviewPanel() {
  const t = useTranslations("platform.dashboard");
  const tc = useTranslations("platform.common");
  const tTenant = useTranslations("platform.tenants");
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [techRes, brandRes, tenantRes] = await Promise.all([
          api.get<{ data: { status?: string }[] }>("/api/v1/platform/technicians"),
          api.get<{ data: unknown[] }>("/api/v1/platform/brand-applications?status=pending"),
          api.get<{ data: TenantRow[] }>("/api/v1/platform/tenants"),
        ]);
        if (cancelled) return;
        const techs = techRes.data ?? [];
        setOv({
          techPending: techs.filter((x) => x.status === TECH_STATUS_PENDING).length,
          techActive: techs.filter((x) => x.status === TECH_STATUS_ACTIVE).length,
          techTotal: techs.length,
          brandApps: brandRes.data?.length ?? 0,
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

  const requestorPending = ov ? ov.brandApps : null;
  const activeTenants = ov ? ov.tenants.filter((x) => x.status === "active").length : null;

  return (
    <div className="flex flex-col gap-6">
      {error && (
        <div className="rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-4 py-3 text-sm text-[var(--badge-danger-fg)]">
          {error}
        </div>
      )}

      {/* 平台總覽統計 */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={t("statActiveTenants")}
          value={activeTenants}
          suffix={ov ? t("statTenantsTotal", { count: ov.tenants.length }) : ""}
          href="/platform/tenants"
        />
        <StatCard
          label={t("statActiveTechs")}
          value={ov?.techActive ?? null}
          suffix={ov ? t("statTechsTotal", { count: ov.techTotal }) : ""}
          href={`/platform/technicians?status=${TECH_STATUS_ACTIVE}`}
        />
        <StatCard
          label={t("statPendingRequestors")}
          value={requestorPending}
          warn
          suffix={t("statUnit")}
          href="/platform/requestors"
        />
        <StatCard
          label={t("statPendingTechs")}
          value={ov?.techPending ?? null}
          warn
          suffix={t("statUnit")}
          href={`/platform/technicians?status=${TECH_STATUS_PENDING}`}
        />
      </div>

      {/* 待辦(點卡進審核頁) */}
      <div className="grid gap-4 sm:grid-cols-2">
        <PendingCard
          href="/platform/requestors"
          icon={Building2}
          title={t("statPendingRequestors")}
          count={requestorPending}
          unit={t("pendingUnit")}
          subtitle={t("pendingRequestorsHint")}
        />
        <PendingCard
          href={`/platform/technicians?status=${TECH_STATUS_PENDING}`}
          icon={UserCheck}
          title={t("statPendingTechs")}
          count={ov ? ov.techPending : null}
          unit={t("pendingUnit")}
          subtitle={t("pendingTechsHint")}
        />
      </div>

      {/* 租戶摘要 */}
      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)]">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
          <p className="text-sm font-semibold text-[var(--text-primary)]">{t("tenantsCardTitle")}</p>
          <Link
            href="/platform/tenants"
            className="inline-flex items-center gap-1 text-xs font-medium text-[var(--primary)] hover:underline"
          >
            {t("manageTenants")}
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>
        {ov === null ? (
          <p className="px-6 py-6 text-sm text-[var(--text-secondary)]">{tc("loading")}</p>
        ) : ov.tenants.length === 0 ? (
          <p className="px-6 py-6 text-sm text-[var(--text-secondary)]">{t("noTenants")}</p>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {ov.tenants.slice(0, 5).map((row) => {
              const cls =
                TENANT_STATUS_CLS[row.status] ??
                "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)] border-[var(--border)]";
              const label =
                row.status === "active" || row.status === "suspended" || row.status === "terminated"
                  ? tTenant(`status.${row.status}`)
                  : row.status;
              return (
                <li key={row.id} className="flex items-center gap-3 px-6 py-3.5">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--primary-subtle,rgba(59,130,246,0.12))] text-sm font-bold text-[var(--primary)]">
                    {(row.company_name || row.slug).slice(0, 1)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                      {row.company_name}
                    </p>
                    <p className="truncate font-mono text-xs text-[var(--text-secondary)]">{row.slug}</p>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}>
                    {label}
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

/** 統計卡。給 href 就整張可點(導到對應清單的對應篩選)。
 *
 * 2026-07-30 業主回報:「待審核師傅」點下去沒反應。原因是這排卡片渲染成純 div,
 * 而它正下方那排待辦卡長得很像、卻是連結——同一個標題出現兩次、只有一張能點,
 * 使用者自然先點上面那張。所以這裡不是「補一個連結」而已,是**這排卡片本來就
 * 該可點**(檔頭註解寫的「點卡進審核頁」原本只有下排做到)。 */
function StatCard({
  label,
  value,
  suffix,
  warn,
  href,
}: {
  label: string;
  value: number | null;
  suffix?: string;
  warn?: boolean;
  href?: string;
}) {
  const highlight = warn && value !== null && value > 0;
  const body = (
    <>
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
    </>
  );
  const base = "rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-5";
  if (!href) return <div className={base}>{body}</div>;
  return (
    <Link
      href={href}
      className={`${base} block transition hover:border-[var(--primary)] hover:shadow-sm`}
    >
      {body}
    </Link>
  );
}

function PendingCard({
  href,
  icon: Icon,
  title,
  count,
  unit,
  subtitle,
}: {
  href: string;
  icon: typeof Building2;
  title: string;
  count: number | null;
  unit: string;
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
        <span className="pb-1 text-xs text-[var(--text-secondary)]">{unit}</span>
      </div>
      <p className="text-xs text-[var(--text-secondary)]">{subtitle}</p>
    </Link>
  );
}
