"use client";

// CR-0118 平台 console — 租戶管理 panel(「租戶管理」頁)。
// 列出已開站租戶 registry(核准品牌申請時自動登錄);生命週期為**平台層標示**:
// 停用/恢復只翻 registry 狀態,實際停站/重啟走維運(gcloud / 各品牌後台)。
// 業主裁決(2026-07-07):租戶相關的服務監控(monitor_target.brand=租戶 slug)
// 健康燈顯示在此頁對應卡片(30s 輪詢);目標登記/維護仍在儀表板→維運監控。
// 內部工具,文案直接繁中(不入 i18n 兩 locale)。

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { cacheInvalidate } from "@shared/lib/cache";

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

const PROBE_META: Record<ProbeStatus, { label: string; dot: string; cls: string }> = {
  up: { label: "正常", dot: "bg-green-500", cls: "text-green-700 bg-green-50 border-green-200" },
  degraded: { label: "降級", dot: "bg-amber-500", cls: "text-amber-700 bg-amber-50 border-amber-200" },
  down: { label: "異常", dot: "bg-red-500", cls: "text-red-700 bg-red-50 border-red-200" },
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

const FILTERS: { value: Filter; label: string }[] = [
  { value: "active", label: "營運中" },
  { value: "suspended", label: "已停用" },
  { value: "all", label: "全部" },
];

const STATUS_LABEL: Record<Status, string> = {
  active: "營運中",
  suspended: "已停用",
  terminated: "已終止",
};

const STATUS_CLS: Record<Status, string> = {
  active: "bg-green-50 text-green-700 border-green-200",
  suspended: "bg-amber-50 text-amber-700 border-amber-200",
  terminated: "bg-gray-100 text-gray-600 border-gray-200",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("zh-TW", { hour12: false });
}

export default function TenantsPanel() {
  const [filter, setFilter] = useState<Filter>("active");
  const [rows, setRows] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [healthByBrand, setHealthByBrand] = useState<Record<string, HealthResult[]>>({});
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

  async function transition(t: Tenant, action: "suspend" | "reactivate") {
    const verb = action === "suspend" ? "停用" : "恢復";
    const extra =
      action === "suspend"
        ? "\n\n注意:此操作僅在平台標示為已停用,實際停站(關閉該品牌服務)需另行以維運流程處理。"
        : "";
    if (!window.confirm(`確定要${verb}租戶「${t.company_name}」?${extra}`)) return;
    setBusyId(t.id);
    try {
      await api.post(`/api/v1/platform/tenants/${t.id}:${action}`, {});
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到舊清單
      await load();
    } catch (err) {
      window.alert(friendlyError(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[var(--text-secondary)]">
        已開站的品牌租戶名冊(核准品牌申請時自動登錄)。停用/恢復為
        <span className="font-medium text-[var(--text-primary)]">平台層標示</span>
        ;實際停站或重啟該品牌服務,請走維運流程(gcloud / 各品牌後台)。
      </p>

      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFilter(f.value)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              filter === f.value
                ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          目前沒有{filter === "all" ? "" : STATUS_LABEL[filter as Status]}租戶
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {rows.map((t) => (
            <div
              key={t.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-base font-semibold text-[var(--text-primary)]">
                      {t.company_name}
                    </span>
                    <span className="rounded-md bg-[var(--bg-page)] px-2 py-0.5 font-mono text-xs text-[var(--text-secondary)]">
                      {t.slug}
                    </span>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_CLS[t.status]}`}>
                      {STATUS_LABEL[t.status]}
                    </span>
                  </div>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
                    {t.contact_name && <span>聯絡人：{t.contact_name}</span>}
                    {t.contact_phone && <span>電話：{t.contact_phone}</span>}
                    {t.contact_email && <span className="truncate">Email：{t.contact_email}</span>}
                    <span>開站於：{fmtDate(t.created_at)}</span>
                    {t.status === "suspended" && t.status_changed_at && (
                      <span className="sm:col-span-2 text-amber-700">
                        停用於：{fmtDate(t.status_changed_at)}
                      </span>
                    )}
                  </div>
                  {(healthByBrand[t.slug] ?? []).length > 0 && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-[var(--text-secondary)]">服務狀態：</span>
                      {(healthByBrand[t.slug] ?? []).map((h) => {
                        const meta = PROBE_META[h.status];
                        return (
                          <span
                            key={h.id}
                            title={`HTTP ${h.http_code ?? "—"} · ${h.latency_ms}ms`}
                            className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium ${meta.cls}`}
                          >
                            <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
                            {h.label}　{meta.label}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  {t.deploy_note && (
                    <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--bg-page)] p-3 font-mono text-xs leading-relaxed text-[var(--text-secondary)]">
                      {t.deploy_note}
                    </pre>
                  )}
                </div>
                <div className="flex gap-2">
                  {t.status === "active" && (
                    <button
                      type="button"
                      disabled={busyId === t.id}
                      onClick={() => transition(t, "suspend")}
                      className="rounded-lg border border-amber-300 px-3 py-1.5 text-sm font-medium text-amber-700 transition hover:bg-amber-50 disabled:opacity-50"
                    >
                      {busyId === t.id ? "處理中…" : "停用"}
                    </button>
                  )}
                  {t.status === "suspended" && (
                    <button
                      type="button"
                      disabled={busyId === t.id}
                      onClick={() => transition(t, "reactivate")}
                      className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                    >
                      {busyId === t.id ? "處理中…" : "恢復"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
