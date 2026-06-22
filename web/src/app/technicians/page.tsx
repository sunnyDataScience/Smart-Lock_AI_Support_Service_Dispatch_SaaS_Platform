"use client";

import { useMemo, useState } from "react";
import { Search, ChevronDown, Wrench, Plus } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import TechniciansTable from "@/components/technicians/TechniciansTable";
import { ApiError, api, getCurrentSession } from "@/lib/api";
import { cacheInvalidate } from "@/lib/cache";
import { useToast } from "@/components/ui/Toast";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";
import CreateTechnicianModal from "@/components/admin/CreateTechnicianModal";

type Technician = components["schemas"]["Technician"];

function formatTechnicianError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

const PAGE_SIZE = 20;

// Stable keys for filter labels — resolved per-render via i18n
const FILTER_DROPDOWN_KEYS = [
  "status",
  "brandSpecialty",
  "serviceArea",
  "rating",
] as const;

export default function TechniciansPage() {
  const t = useTranslations("pages.technicians");
  const tFilters = useTranslations("pages.technicians.filters");
  const { toast } = useToast();

  // CR-0002-α：遷移至 tenant-scoped v2 端點
  const session = getCurrentSession();
  const tenantId = session?.tenantId ?? "00000000-0000-0000-0000-000000000001";

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [capabilityFilter, setCapabilityFilter] = useState<string>("");
  const [regionFilter, setRegionFilter] = useState<string>("");
  const [ratingMinFilter, setRatingMinFilter] = useState<string>("");
  const [keyword, setKeyword] = useState<string>("");
  const [createOpen, setCreateOpen] = useState(false);
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    if (statusFilter) p.set("status", statusFilter);
    if (capabilityFilter) p.set("capability", capabilityFilter);
    if (regionFilter) p.set("service_region", regionFilter);
    if (ratingMinFilter) p.set("rating_min", ratingMinFilter);
    if (keyword.trim()) p.set("keyword", keyword.trim());
    const qs = p.toString();
    return qs ? `?${qs}` : "";
  }, [statusFilter, capabilityFilter, regionFilter, ratingMinFilter, keyword]);

  const { items, cursor, hasMore, loading, error, loadMore, refresh } = usePaginatedFetch<Technician>({
    path: `/tenants/${encodeURIComponent(tenantId)}/technicians${queryString}`,
    pageSize: PAGE_SIZE,
    formatError: formatTechnicianError,
  });

  // 核准 pending_approval 技師（onboarding → active）→ 之後才可被派工
  async function handleApprove(tech: Technician) {
    const initiator = session?.userId ?? "";
    if (!initiator) {
      toast({ variant: "error", title: t("approveFailed"), description: "缺少操作者身分（請重新登入）" });
      return;
    }
    setApprovingId(tech.id);
    try {
      await api.post(
        `/tenants/${encodeURIComponent(tenantId)}/technicians/${tech.id}:onboard-approve`,
        {},
        { headers: { "X-Initiator": initiator } },
      );
      toast({ variant: "success", title: t("approveSuccess", { name: tech.name }) });
      cacheInvalidate("GET:"); // 清 30s GET 快取，讓 refresh 取到更新後狀態
      refresh();
    } catch (e) {
      toast({ variant: "error", title: t("approveFailed"), description: formatTechnicianError(e) });
    } finally {
      setApprovingId(null);
    }
  }

  // 從 items 抽 distinct capabilities + service areas
  const { capabilityOptions, regionOptions } = useMemo(() => {
    const caps = new Set<string>();
    const regs = new Set<string>();
    items.forEach((tech: any) => {
      (tech.skills ?? []).forEach((s: string) => caps.add(s));
      (tech.service_areas ?? []).forEach((r: string) => regs.add(r));
    });
    return {
      capabilityOptions: Array.from(caps).sort(),
      regionOptions: Array.from(regs).sort(),
    };
  }, [items]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* Page Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <div className="flex items-center gap-3">
            <Wrench className="h-6 w-6 text-[var(--primary)]" />
            <div className="flex flex-col gap-[2px]">
              <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
                {t("title")}
              </h1>
            </div>
            <span className="ml-1 flex items-center rounded-xl bg-[#DBEAFE] px-3 py-1 text-xs font-semibold text-[var(--primary)]">
              {loading && items.length === 0
                ? t("loadingBadge")
                : hasMore
                  ? t("techCountMore", { count: items.length })
                  : t("techCount", { count: items.length })}
            </span>
          </div>

          <button
            onClick={() => setCreateOpen(true)}
            className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-5 py-[10px] hover:opacity-90"
          >
            <Plus className="h-4 w-4 text-white" />
            <span className="text-sm font-semibold text-white">{t("addTechnician")}</span>
          </button>
        </div>

        {/* Filter Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-3">
          <div className="flex h-[38px] w-[280px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3">
            <Search className="h-4 w-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="flex-1 bg-transparent text-[13px] outline-none"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-[38px] rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("status")}</option>
            <option value="pending_approval">待審核</option>
            <option value="active">在職</option>
            <option value="suspended">停權</option>
            <option value="terminated">終止</option>
            <option value="inactive">離職</option>
          </select>

          <select
            value={capabilityFilter}
            onChange={(e) => setCapabilityFilter(e.target.value)}
            className="h-[38px] rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("brandSpecialty")}</option>
            {capabilityOptions.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          <select
            value={regionFilter}
            onChange={(e) => setRegionFilter(e.target.value)}
            className="h-[38px] rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("serviceArea")}</option>
            {regionOptions.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>

          <select
            value={ratingMinFilter}
            onChange={(e) => setRatingMinFilter(e.target.value)}
            className="h-[38px] rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("rating")}</option>
            <option value="3.0">≥ 3.0</option>
            <option value="4.0">≥ 4.0</option>
            <option value="4.5">≥ 4.5</option>
          </select>
        </div>

        {/* Table Area */}
        <main className="flex flex-1 flex-col gap-4 overflow-auto bg-[var(--bg-page)]">
          {error && (
            <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {t("loadFailed", { error })}
            </div>
          )}

          <TechniciansTable
            items={items}
            loading={loading}
            onApprove={handleApprove}
            approvingId={approvingId}
          />

          {hasMore && items.length > 0 && (
            <div className="flex justify-center pb-6">
              <button
                disabled={loading}
                onClick={loadMore}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? t("loadingMore") : t("loadMore")}
              </button>
            </div>
          )}
        </main>
      </div>

      <CreateTechnicianModal
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSuccess={() => {
          setCreateOpen(false);
          refresh();
        }}
      />
    </div>
  );
}
