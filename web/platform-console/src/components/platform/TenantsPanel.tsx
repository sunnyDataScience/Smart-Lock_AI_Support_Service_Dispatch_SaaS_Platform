"use client";

// CR-0118 平台 console — 租戶管理 panel(「租戶管理」頁)。
// 列出已開站租戶 registry(核准品牌申請時自動登錄);生命週期為**平台層標示**:
// 停用/恢復只翻 registry 狀態,實際停站/重啟走維運(gcloud / 各品牌後台)。
// 業主裁決(2026-07-07):租戶相關的服務監控(monitor_target.brand=租戶 slug)
// 健康燈顯示在此頁對應卡片(30s 輪詢);目標登記/維護仍在儀表板→維運監控。
// UAT W6-2:文案接 i18n(platform.tenants / platform.monitor namespace)。

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";
import LicenseModal from "@/components/platform/LicenseModal";
import { useActionDialog } from "@/components/ui/ActionDialog";
import { useToast } from "@/components/ui/Toast";
import { useLocale, useTranslations } from "@/components/i18n/LocaleProvider";

type Status = "active" | "suspended" | "terminated";

type ProbeStatus = "up" | "degraded" | "down";

interface HealthResult {
  id: string;
  brand: string;
  label: string;
  status: ProbeStatus;
  http_code: number | null;
  latency_ms: number;
}

const PROBE_CLS: Record<ProbeStatus, { dot: string; cls: string }> = {
  up: { dot: "bg-[var(--status-success)]", cls: "text-[var(--badge-success-fg)] bg-[var(--badge-success-bg)] border-[var(--badge-success-fg)]/25" },
  degraded: { dot: "bg-[var(--status-warning)]", cls: "text-[var(--badge-warn-fg)] bg-[var(--badge-warn-bg)] border-[var(--badge-warn-fg)]/25" },
  down: { dot: "bg-[var(--status-danger)]", cls: "text-[var(--badge-danger-fg)] bg-[var(--badge-danger-bg)] border-[var(--badge-danger-fg)]/25" },
};

const HEALTH_POLL_MS = 30_000;

interface Tenant {
  id: string;
  slug: string;
  company_name: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  status: Status;
  plan: string | null;
  application_id: string | null;
  deploy_note: string | null;
  status_changed_at: string | null;
  status_changed_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

type Filter = Status | "all";

const FILTERS: Filter[] = ["active", "suspended", "all"];

const STATUS_CLS: Record<Status, string> = {
  active: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)] border-[var(--badge-success-fg)]/25",
  suspended: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)] border-[var(--badge-warn-fg)]/25",
  terminated: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)] border-[var(--border)]",
};

function fmtDate(iso: string | null, dateLocale: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString(dateLocale, { hour12: false });
}

export default function TenantsPanel() {
  const actionDialog = useActionDialog();
  const { toast } = useToast();
  const { locale } = useLocale();
  const t = useTranslations("platform.tenants");
  const tc = useTranslations("platform.common");
  const tf = useTranslations("platform.fields");
  const tm = useTranslations("platform.monitor");
  const dateLocale = locale === "en" ? "en-US" : "zh-TW";
  const [filter, setFilter] = useState<Filter>("active");
  const [rows, setRows] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [healthByBrand, setHealthByBrand] = useState<Record<string, HealthResult[]>>({});
  // CR-0166 R3:License 管理 modal 目標租戶
  const [licenseTenant, setLicenseTenant] = useState<Tenant | null>(null);
  const healthPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = filter === "all" ? "" : `?status=${filter}`;
      const res = await api.get<{ data: Tenant[] }>(`/api/v1/platform/tenants${qs}`);
      setRows(res.data);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  // 租戶服務健康燈:同一 fan-out 端點,依 brand(=租戶 slug)歸戶到卡片。
  // fail-soft:探測失敗不影響名冊主功能(卡片只是不顯示健康列)。
  const probeHealth = useCallback(async () => {
    try {
      const res = await api.get<{ data: HealthResult[] }>(
        "/api/v1/platform/monitor-targets/health",
      );
      const map: Record<string, HealthResult[]> = {};
      (res.data ?? []).forEach((r) => {
        (map[r.brand] = map[r.brand] ?? []).push(r);
      });
      setHealthByBrand(map);
    } catch {
      /* fail-soft */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    probeHealth();
    healthPollRef.current = setInterval(probeHealth, HEALTH_POLL_MS);
    return () => {
      if (healthPollRef.current) clearInterval(healthPollRef.current);
    };
  }, [probeHealth]);

  async function transition(tenant: Tenant, action: "suspend" | "reactivate") {
    const verb = t(`action.${action}`);
    const confirmed = await actionDialog.open({
      title: t("actionDialogTitle", { action: verb, name: tenant.company_name }),
      description: action === "suspend" ? t("suspendDesc") : t("reactivateDesc"),
      danger: action === "suspend",
      confirmLabel: verb,
    });
    if (confirmed === null) return;
    setBusyId(tenant.id);
    try {
      await api.post(`/api/v1/platform/tenants/${tenant.id}:${action}`, {});
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到舊清單
      await load();
      toast({ title: t("actionDone", { action: verb, name: tenant.company_name }), variant: "success" });
    } catch (err) {
      toast({
        title: t("actionFailed", { action: verb }),
        description: friendlyError(err),
        variant: "error",
      });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-[var(--text-secondary)]">
        {t("hintBefore")}
        <span className="font-medium text-[var(--text-primary)]">{t("hintStrong")}</span>
        {t("hintAfter")}
      </p>

      <div className="flex gap-2">
        {FILTERS.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilter(value)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              filter === value
                ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
            }`}
          >
            {value === "all" ? tc("all") : t(`status.${value}`)}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-4 py-3 text-sm text-[var(--badge-danger-fg)]">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">{tc("loading")}</p>
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          {filter === "all"
            ? t("emptyAll")
            : t("emptyFiltered", { status: t(`status.${filter}`) })}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {rows.map((tenant) => (
            <div
              key={tenant.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-base font-semibold text-[var(--text-primary)]">
                      {tenant.company_name}
                    </span>
                    <span className="rounded-md bg-[var(--bg-page)] px-2 py-0.5 font-mono text-xs text-[var(--text-secondary)]">
                      {tenant.slug}
                    </span>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_CLS[tenant.status]}`}>
                      {t(`status.${tenant.status}`)}
                    </span>
                  </div>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
                    {tenant.contact_name && (
                      <span>{tf("contact")}{tc("colon")}{tenant.contact_name}</span>
                    )}
                    {tenant.contact_phone && (
                      <span>{tf("phone")}{tc("colon")}{tenant.contact_phone}</span>
                    )}
                    {tenant.contact_email && (
                      <span className="truncate">{tf("email")}{tc("colon")}{tenant.contact_email}</span>
                    )}
                    <span>{t("createdAt")}{tc("colon")}{fmtDate(tenant.created_at, dateLocale)}</span>
                    {tenant.status === "suspended" && tenant.status_changed_at && (
                      <span className="sm:col-span-2 text-[var(--badge-warn-fg)]">
                        {t("suspendedAt")}{tc("colon")}{fmtDate(tenant.status_changed_at, dateLocale)}
                      </span>
                    )}
                  </div>
                  {(healthByBrand[tenant.slug] ?? []).length > 0 && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-[var(--text-secondary)]">
                        {t("serviceStatus")}{tc("colon")}
                      </span>
                      {(healthByBrand[tenant.slug] ?? []).map((h) => {
                        const meta = PROBE_CLS[h.status];
                        return (
                          <span
                            key={h.id}
                            title={`HTTP ${h.http_code ?? "—"} · ${h.latency_ms}ms`}
                            className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium ${meta.cls}`}
                          >
                            <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
                            {h.label}　{tm(`status.${h.status}`)}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  {tenant.deploy_note && (
                    <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--bg-page)] p-3 font-mono text-xs leading-relaxed text-[var(--text-secondary)]">
                      {tenant.deploy_note}
                    </pre>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setLicenseTenant(tenant)}
                    className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)]"
                  >
                    License
                  </button>
                  {tenant.status === "active" && (
                    <button
                      type="button"
                      disabled={busyId === tenant.id}
                      onClick={() => transition(tenant, "suspend")}
                      className="rounded-lg border border-[var(--badge-warn-fg)]/35 px-3 py-1.5 text-sm font-medium text-[var(--badge-warn-fg)] transition hover:bg-[var(--badge-warn-bg)] disabled:opacity-50"
                    >
                      {busyId === tenant.id ? tc("processing") : t("action.suspend")}
                    </button>
                  )}
                  {tenant.status === "suspended" && (
                    <button
                      type="button"
                      disabled={busyId === tenant.id}
                      onClick={() => transition(tenant, "reactivate")}
                      className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                    >
                      {busyId === tenant.id ? tc("processing") : t("action.reactivate")}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {licenseTenant && (
        <LicenseModal
          tenantId={licenseTenant.id}
          tenantName={licenseTenant.company_name}
          onClose={() => setLicenseTenant(null)}
          onSaved={load}
        />
      )}
    </div>
  );
}
