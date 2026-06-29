"use client";

import { useMemo, useState } from "react";
import {
  Search,
  UserPlus,
  Users,
  ShieldAlert,
  Clock,
  ChevronDown,
  Eye,
  Pencil,
  X,
  Lock,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, resolveTenantId } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import { LOCK_BRANDS } from "@/lib/constants/brands";
import type { components } from "@/types/api.generated";

type Customer = components["schemas"]["Customer"];
type Technician = components["schemas"]["Technician"];

function formatCustomerError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

const PAGE_LIMIT = 20;

function maskLineId(line: string | null | undefined): string {
  if (!line) return "—";
  if (line.length <= 10) return line;
  return `${line.slice(0, 5)}****${line.slice(-4)}`;
}

function avatarChar(c: Customer): string {
  if (c.display_name) return c.display_name[0];
  if (c.phone) return c.phone[0];
  return c.id[0].toUpperCase();
}

function formatDateOnly(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

const COLUMN_KEYS = [
  { key: "customer", width: "w-[220px]" },
  { key: "lineId", width: "w-[150px]" },
  { key: "address", width: "w-[260px]" },
  { key: "conversations", width: "w-[80px]" },
  { key: "orders", width: "w-[80px]" },
  { key: "lastService", width: "w-[120px]" },
  { key: "lastActive", width: "w-[120px]" },
  { key: "actions", width: "w-[60px]" },
] as const;

export default function CustomersPage() {
  const t = useTranslations("admin.customers.list");
  const [searchQuery, setSearchQuery] = useState("");
  const [riskFilter, setRiskFilter] = useState<string>("");
  const [brandFilter, setBrandFilter] = useState<string>("");
  const [warrantyFilter, setWarrantyFilter] = useState<string>("");
  const [preferredTechFilter, setPreferredTechFilter] = useState<string>("");

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    if (riskFilter) p.set("risk_level", riskFilter);
    if (brandFilter) p.set("device_brand", brandFilter);
    if (warrantyFilter) p.set("warranty_status", warrantyFilter);
    if (preferredTechFilter) p.set("preferred_technician_id", preferredTechFilter);
    const qs = p.toString();
    return qs ? `?${qs}` : "";
  }, [riskFilter, brandFilter, warrantyFilter, preferredTechFilter]);

  // CR-0002-α：遷移至 tenant-scoped v2 端點
  const tenantId = resolveTenantId();

  const {
    items,
    hasMore,
    loadingInitial,
    loadingMore,
    loading,
    error,
    loadMore,
    refresh,
  } = usePaginatedFetch<Customer>({
    path: `/tenants/${encodeURIComponent(tenantId)}/customers${queryString}`,
    pageSize: PAGE_LIMIT,
    formatError: formatCustomerError,
  });

  // 偏好技師篩選下拉資料 — 取本租戶技師清單（取代手打 UUID）
  const { items: technicians } = usePaginatedFetch<Technician>({
    path: `/tenants/${encodeURIComponent(tenantId)}/technicians`,
    pageSize: 100,
  });

  const filtered = searchQuery
    ? items.filter((c) => {
        const q = searchQuery.toLowerCase();
        return (
          (c.display_name ?? "").toLowerCase().includes(q) ||
          (c.phone ?? "").toLowerCase().includes(q) ||
          (c.line_user_id ?? "").toLowerCase().includes(q) ||
          (c.address ?? "").toLowerCase().includes(q)
        );
      })
    : items;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* 捲動容器須為 block（非 flex column）：flex column 的子層預設 flex-shrink:1，
            內容超高時會被壓縮塞進視窗（表格被壓扁 + overflow-hidden 裁切）導致捲軸失效。
            改 space-y-5 讓子層自然堆疊、溢出觸發 overflow-auto 捲動（對齊 quotes 頁模式）。*/}
        <div className="flex-1 space-y-5 overflow-auto pl-14 pr-4 py-6 md:px-8">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
                {t("title")}
              </h1>
              <span className="flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-[2px] text-xs text-[var(--primary)]">
                <Lock className="h-3 w-3" />
                {t("tenantTag")}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex w-80 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
                <Search className="h-4 w-4 text-[var(--text-disabled)]" />
                <input
                  type="text"
                  placeholder={t("searchPlaceholder")}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 bg-transparent text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery("")}>
                    <X className="h-4 w-4 text-[var(--text-disabled)]" />
                  </button>
                )}
              </div>
              <button
                onClick={refresh}
                disabled={loading}
                title={t("refresh")}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${
                    loading ? "animate-spin" : ""
                  }`}
                />
              </button>
              <Link
                href="/admin/customers/new"
                className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 hover:opacity-90"
              >
                <UserPlus className="h-4 w-4 text-white" />
                <span className="text-[13px] font-medium text-white">
                  {t("addCustomer")}
                </span>
              </Link>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Summary Stats — mock with banner */}
          <div className="grid grid-cols-4 gap-4">
            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
                <Users className="h-5 w-5 text-[var(--primary)]" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  {t("stats.pageTotal")}
                </span>
                <span className="text-xl font-bold text-[var(--text-primary)]">
                  {items.length}
                  {hasMore && "+"}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 opacity-60">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50">
                <Users className="h-5 w-5 text-green-600" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  {t("stats.active")}
                </span>
                <span className="text-xl font-bold text-[var(--text-disabled)]">
                  —
                </span>
                <span className="text-[11px] text-[var(--text-disabled)]">
                  {t("stats.activeNote")}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 opacity-60">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50">
                <ShieldAlert className="h-5 w-5 text-red-400" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  {t("stats.highRisk")}
                </span>
                <span className="text-xl font-bold text-[var(--text-disabled)]">
                  —
                </span>
                <span className="text-[11px] text-[var(--text-disabled)]">
                  {t("stats.highRiskNote")}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 opacity-60">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50">
                <Clock className="h-5 w-5 text-amber-400" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  {t("stats.warrantyExpiring")}
                </span>
                <span className="text-xl font-bold text-[var(--text-disabled)]">
                  —
                </span>
                <span className="text-[11px] text-[var(--text-disabled)]">
                  {t("stats.warrantyNote")}
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4">
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="rounded-lg border border-[var(--border)] px-3 py-[7px] text-[13px] text-[var(--text-primary)] outline-none"
            >
              <option value="">{t("filterChips.risk")}</option>
              <option value="low">{t("filterChips.riskOptions.low")}</option>
              <option value="medium">{t("filterChips.riskOptions.medium")}</option>
              <option value="high">{t("filterChips.riskOptions.high")}</option>
              <option value="critical">
                {t("filterChips.riskOptions.critical")}
              </option>
            </select>

            <select
              value={brandFilter}
              onChange={(e) => setBrandFilter(e.target.value)}
              className="rounded-lg border border-[var(--border)] px-3 py-[7px] text-[13px] text-[var(--text-primary)] outline-none"
            >
              <option value="">{t("filterChips.brand")}</option>
              {LOCK_BRANDS.map((b) => (
                <option key={b.value} value={b.value}>
                  {b.label}
                </option>
              ))}
              <option value="Other">{t("filterChips.brandOther")}</option>
            </select>

            <select
              value={warrantyFilter}
              onChange={(e) => setWarrantyFilter(e.target.value)}
              className="rounded-lg border border-[var(--border)] px-3 py-[7px] text-[13px] text-[var(--text-primary)] outline-none"
            >
              <option value="">{t("filterChips.warranty")}</option>
              <option value="active">
                {t("filterChips.warrantyOptions.active")}
              </option>
              <option value="expired">
                {t("filterChips.warrantyOptions.expired")}
              </option>
              <option value="none">
                {t("filterChips.warrantyOptions.none")}
              </option>
            </select>

            <select
              value={preferredTechFilter}
              onChange={(e) => setPreferredTechFilter(e.target.value)}
              className="rounded-lg border border-[var(--border)] px-3 py-[7px] text-[13px] text-[var(--text-primary)] outline-none w-[220px]"
            >
              <option value="">{t("filterChips.preferredTechAll")}</option>
              {technicians.map((tech) => (
                <option key={tech.id} value={tech.id}>
                  {tech.name}
                  {tech.phone ? `（${tech.phone}）` : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Data Table */}
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center bg-[#F8FAFC] px-4 py-3">
              {COLUMN_KEYS.map((col) => (
                <div key={col.key} className={col.width}>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.key === "actions" ? "" : t(`cols.${col.key}`)}
                  </span>
                </div>
              ))}
            </div>

            {loadingInitial ? (
              <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
                {t("loading")}
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
                {searchQuery ? t("emptyFilter") : t("empty")}
              </div>
            ) : (
              filtered.map((c) => (
                <div
                  key={c.id}
                  className="group flex items-center border-t border-[var(--border)] px-4 py-3 transition-colors hover:bg-blue-50"
                >
                  <div className="flex w-[220px] items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#DBEAFE] text-xs font-semibold text-[var(--primary)]">
                      {avatarChar(c)}
                    </div>
                    <div className="flex flex-col">
                      <span
                        className="truncate text-[13px] font-medium text-[var(--text-primary)]"
                        title={c.display_name}
                      >
                        {c.display_name}
                      </span>
                      <span className="text-[11px] text-[var(--text-secondary)]">
                        {c.phone ?? "—"}
                      </span>
                    </div>
                  </div>

                  <div className="w-[150px]">
                    <span
                      className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-secondary)]"
                      title={c.line_user_id ?? undefined}
                    >
                      {maskLineId(c.line_user_id)}
                    </span>
                  </div>

                  <div className="w-[260px]">
                    <span
                      className="block truncate text-[13px] text-[var(--text-primary)]"
                      title={c.address ?? ""}
                    >
                      {c.address ?? "—"}
                    </span>
                  </div>

                  <div className="w-[80px]">
                    <span className="text-[13px] text-[var(--text-primary)]">
                      {c.total_conversations}
                    </span>
                  </div>

                  <div className="w-[80px]">
                    <span className="text-[13px] text-[var(--text-primary)]">
                      {c.total_orders}
                    </span>
                  </div>

                  <div className="w-[120px]">
                    <span className="text-[13px] text-[var(--text-secondary)]">
                      {formatDateOnly(c.last_service_at)}
                    </span>
                  </div>

                  <div className="w-[120px]">
                    <span
                      className="text-[13px] text-[var(--text-secondary)]"
                      title={c.last_active_at ?? ""}
                    >
                      {c.last_active_at ? formatRelative(c.last_active_at) : "—"}
                    </span>
                  </div>

                  <div className="flex w-[60px] items-center gap-1">
                    <Link
                      href={`/admin/customers/${c.id}`}
                      title={t("viewDetail")}
                      className="rounded-md p-1 opacity-0 transition-opacity hover:bg-[var(--bg-page)] group-hover:opacity-80"
                    >
                      <Eye className="h-4 w-4 text-[var(--text-secondary)]" />
                    </Link>
                    <Link
                      href={`/admin/customers/${c.id}/edit`}
                      title={t("editCustomer")}
                      className="rounded-md p-1 opacity-0 transition-opacity hover:bg-[var(--bg-page)] group-hover:opacity-80"
                    >
                      <Pencil className="h-4 w-4 text-[var(--text-secondary)]" />
                    </Link>
                  </div>
                </div>
              ))
            )}

            {hasMore && filtered.length > 0 && (
              <div className="flex items-center justify-center border-t border-[var(--border)] px-4 py-3">
                <button
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="rounded-lg border border-[var(--border)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loadingMore ? t("loadingMore") : t("loadMore")}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
