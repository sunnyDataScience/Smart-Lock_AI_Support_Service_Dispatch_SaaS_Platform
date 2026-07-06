"use client";

// CR-0114 平台 console 儀表板。
// 骨架期(R1)兩張卡是靜態佔位;R2/R3 審核頁落地後,此頁接上真實待審計數 +
// 卡片可點進對應審核頁(發案方審核 / 師傅管理)。計數直接複用既有 list 端點
// 的 status 過濾(不新增 API):
//   - 待審發案方 = brand-applications(pending) + vendors(pending_approval)
//   - 待審師傅   = technicians(pending_approval)

import { useEffect, useState } from "react";
import Link from "next/link";
import { Building2, UserCheck, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

interface PlatformMe {
  data: { id: string; display_name: string | null; email: string };
}

interface Counts {
  brandApps: number;
  vendors: number;
  technicians: number;
}

export default function PlatformDashboardPage() {
  const [me, setMe] = useState<PlatformMe["data"] | null>(null);
  const [counts, setCounts] = useState<Counts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [meRes, techRes, brandRes, vendorRes] = await Promise.all([
          api.get<PlatformMe>("/api/v1/platform/me"),
          api.get<{ data: unknown[] }>(
            "/api/v1/platform/technicians?status=pending_approval",
          ),
          api.get<{ data: unknown[] }>(
            "/api/v1/platform/brand-applications?status=pending",
          ),
          api.get<{ items: unknown[] }>(
            "/api/v1/platform/vendors?status=pending_approval",
          ),
        ]);
        if (cancelled) return;
        setMe(meRes.data);
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

  const requestorPending =
    counts !== null ? counts.brandApps + counts.vendors : null;
  const techPending = counts !== null ? counts.technicians : null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">儀表板</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          {me ? `${me.display_name || me.email}，歡迎回來。` : error ?? "載入中…"}
        </p>
      </div>

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
