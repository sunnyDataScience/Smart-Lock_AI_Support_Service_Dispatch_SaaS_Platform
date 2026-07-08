"use client";

// CR-0114 平台 console 儀表板 + CR-0116 維運監控分頁。
// 分頁:
//   - 概覽:待審計數卡(複用既有 list 端點 status 過濾,零新 API),點卡進審核頁。
//   - 維運監控:跨品牌 /health 紅綠燈(monitor_target registry + 並發探測)。

import { useEffect, useState } from "react";
import Link from "next/link";
import { Building2, UserCheck, ArrowRight } from "lucide-react";
import { api } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
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

// ── 概覽:待審計數卡 ──────────────────────────────────────────────────────────

interface Counts {
  brandApps: number;
  vendors: number;
  technicians: number;
}

function OverviewPanel() {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [techRes, brandRes, vendorRes] = await Promise.all([
          api.get<{ data: unknown[] }>("/api/v1/platform/technicians?status=pending_approval"),
          api.get<{ data: unknown[] }>("/api/v1/platform/brand-applications?status=pending"),
          api.get<{ items: unknown[] }>("/api/v1/platform/vendors?status=pending_approval"),
        ]);
        if (cancelled) return;
        setCounts({
          technicians: techRes.data?.length ?? 0,
          brandApps: brandRes.data?.length ?? 0,
          vendors: vendorRes.items?.length ?? 0,
        });
      } catch (err) {
        if (!cancelled) setError(friendlyError(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const requestorPending = counts !== null ? counts.brandApps + counts.vendors : null;
  const techPending = counts !== null ? counts.technicians : null;

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <PendingCard
          href="/platform/requestors"
          icon={Building2}
          title="待審發案方"
          count={requestorPending}
          subtitle={
            counts
              ? `品牌申請 ${counts.brandApps}　·　廠商帳號 ${counts.vendors}`
              : "品牌／經銷／鎖店的平台導入申請與帳號審核"
          }
        />
        <PendingCard
          href="/platform/technicians"
          icon={UserCheck}
          title="待審師傅"
          count={techPending}
          subtitle="鎖匠師傅的註冊審核與生命週期管理"
        />
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
