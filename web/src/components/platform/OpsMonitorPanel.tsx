"use client";

// CR-0116 平台維運監控面板。
// registry(monitor_target)管理 + 對所有啟用目標並發探測 /health → 紅綠燈。
// 定位:給非技術者一眼看的「即時」狀態(不存歷史);深度指標/告警走 GCP。
// 前端每 30s 輪詢後端 fan-out(§8-Q7);後端單目標逾時 3s。內部工具 → 文案繁中。
//
// 業主裁決(2026-07-07):儀表板不追蹤平台自己(console 打得開=活著),狀態區只顯示
// **平台級服務**(導流站/師傅 API 等 brand 不屬任何租戶 slug 者);brand=租戶 slug
// 的目標其健康燈移到「租戶管理」頁對應卡片,此處僅留精簡管理列(單一 CRUD 面)。

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Plus, Pencil, Trash2, RefreshCw, BarChart3 } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";

const BASE = "/api/v1/platform/monitor-targets";
const POLL_MS = 30_000;

// CR-0116 A 方案:用量(請求數/CPU/記憶體…)住 GCP Cloud Monitoring,非 /health。
// console 只連過去你建的 GCP Metrics Scope dashboard,不重造。未設 = 不顯示連結。
const GCP_MONITORING_URL = process.env.NEXT_PUBLIC_GCP_MONITORING_URL || "";

type Status = "up" | "degraded" | "down";

interface Target {
  id: string;
  brand: string;
  label: string;
  url: string;
  enabled: boolean;
  sort_order: number;
  note: string | null;
}

interface HealthResult extends Target {
  status: Status;
  http_code: number | null;
  latency_ms: number;
  error: string | null;
}

const STATUS_META: Record<Status, { label: string; dot: string; cls: string }> = {
  up: { label: "正常", dot: "bg-green-500", cls: "text-green-700 bg-green-50 border-green-200" },
  degraded: { label: "降級", dot: "bg-amber-500", cls: "text-amber-700 bg-amber-50 border-amber-200" },
  down: { label: "異常", dot: "bg-red-500", cls: "text-red-700 bg-red-50 border-red-200" },
};

export default function OpsMonitorPanel() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [tenantSlugs, setTenantSlugs] = useState<Set<string>>(new Set());
  const [health, setHealth] = useState<Record<string, HealthResult>>({});
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [edit, setEdit] = useState<Target | "new" | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadRegistry = useCallback(async () => {
    try {
      const res = await api.get<{ data: Target[] }>(BASE);
      setTargets(res.data ?? []);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // 租戶 slug 名冊:brand=slug 的目標其狀態顯示於租戶管理頁,此處只留管理列。
  // 取不到名冊時 fail-soft 為空集合(全部目標照舊顯示狀態,不擋監控主功能)。
  const loadTenantSlugs = useCallback(async () => {
    try {
      const res = await api.get<{ data: { slug: string }[] }>("/api/v1/platform/tenants");
      setTenantSlugs(new Set((res.data ?? []).map((t) => t.slug)));
    } catch {
      setTenantSlugs(new Set());
    }
  }, []);

  const probe = useCallback(async () => {
    setProbing(true);
    try {
      const res = await api.get<{ data: HealthResult[]; checked_at: string }>(`${BASE}/health`);
      const map: Record<string, HealthResult> = {};
      (res.data ?? []).forEach((r) => {
        map[r.id] = r;
      });
      setHealth(map);
      setCheckedAt(res.checked_at ?? null);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setProbing(false);
    }
  }, []);

  useEffect(() => {
    loadRegistry();
    loadTenantSlugs();
    probe();
    pollRef.current = setInterval(probe, POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadRegistry, loadTenantSlugs, probe]);

  async function removeTarget(t: Target) {
    if (!window.confirm(`確定刪除監控目標「${t.brand} / ${t.label}」？`)) return;
    try {
      await api.delete(`${BASE}/${encodeURIComponent(t.id)}`);
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 registry 讀到含此目標的舊清單
      await loadRegistry();
      await probe();
    } catch (e) {
      window.alert(friendlyError(e));
    }
  }

  // 依 brand 分組,再切平台級(顯示狀態)/租戶級(僅管理列,狀態在租戶管理頁)
  const { platformGroups, tenantGroups } = useMemo(() => {
    const g = new Map<string, Target[]>();
    targets.forEach((t) => {
      const arr = g.get(t.brand) ?? [];
      arr.push(t);
      g.set(t.brand, arr);
    });
    const all = Array.from(g.entries());
    return {
      platformGroups: all.filter(([brand]) => !tenantSlugs.has(brand)),
      tenantGroups: all.filter(([brand]) => tenantSlugs.has(brand)),
    };
  }, [targets, tenantSlugs]);

  // 摘要只計此頁顯示狀態的平台級目標(租戶級健康燈在租戶管理頁,不重複計)
  const summary = useMemo(() => {
    const platformIds = new Set(platformGroups.flatMap(([, items]) => items.map((t) => t.id)));
    const vals = Object.values(health).filter((v) => platformIds.has(v.id));
    return {
      up: vals.filter((v) => v.status === "up").length,
      degraded: vals.filter((v) => v.status === "degraded").length,
      down: vals.filter((v) => v.status === "down").length,
    };
  }, [health, platformGroups]);

  return (
    <div className="flex flex-col gap-4">
      {/* 工具列 */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-sm text-[var(--text-secondary)]">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-green-500" /> {summary.up} 正常
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-amber-500" /> {summary.degraded} 降級
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-red-500" /> {summary.down} 異常
          </span>
          {checkedAt && (
            <span className="text-xs">
              最後檢查 {checkedAt.slice(11, 19)}（每 30 秒自動更新）
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {GCP_MONITORING_URL && (
            <a
              href={GCP_MONITORING_URL}
              target="_blank"
              rel="noopener noreferrer"
              title="用量指標（請求數／CPU／記憶體）在 GCP Cloud Monitoring"
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
            >
              <BarChart3 className="h-3.5 w-3.5" aria-hidden />
              詳細用量 ↗
            </a>
          )}
          <button
            type="button"
            onClick={probe}
            disabled={probing}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${probing ? "animate-spin" : ""}`} aria-hidden />
            立即檢查
          </button>
          <button
            type="button"
            onClick={() => setEdit("new")}
            className="flex items-center gap-1.5 rounded-lg bg-[var(--primary)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90"
          >
            <Plus className="h-4 w-4" aria-hidden />
            新增目標
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
      ) : targets.length === 0 ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          尚無監控目標。點「新增目標」登記各品牌服務的 health URL。
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          {platformGroups.map(([brand, items]) => (
            <section
              key={brand}
              className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
            >
              <h3 className="mb-3 text-sm font-bold text-[var(--text-primary)]">{brand}</h3>
              <div className="flex flex-col divide-y divide-[var(--border)]">
                {items.map((t) => {
                  const h = health[t.id];
                  const meta = h ? STATUS_META[h.status] : null;
                  return (
                    <div key={t.id} className="flex items-center gap-3 py-3">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium ${
                          t.enabled
                            ? meta?.cls ?? "text-[var(--text-secondary)] bg-[var(--bg-page)] border-[var(--border)]"
                            : "text-[var(--text-secondary)] bg-[var(--bg-page)] border-[var(--border)]"
                        }`}
                      >
                        <span
                          className={`h-2 w-2 rounded-full ${
                            !t.enabled ? "bg-gray-300" : meta?.dot ?? "bg-gray-300 animate-pulse"
                          }`}
                        />
                        {!t.enabled ? "停用" : meta?.label ?? "檢查中"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-[var(--text-primary)]">{t.label}</span>
                          {h && t.enabled && (
                            <span className="text-xs text-[var(--text-secondary)]">
                              {h.http_code ?? "—"}　{h.latency_ms}ms
                            </span>
                          )}
                        </div>
                        <div className="truncate text-xs text-[var(--text-secondary)]">
                          {t.url}
                          {t.note ? `　·　${t.note}` : ""}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setEdit(t)}
                        aria-label="編輯"
                        className="text-[var(--text-secondary)] hover:text-[var(--primary)]"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeTarget(t)}
                        aria-label="刪除"
                        className="text-[var(--text-secondary)] hover:text-red-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}

          {tenantGroups.length > 0 && (
            <section className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--bg-surface)] p-5">
              <h3 className="text-sm font-bold text-[var(--text-primary)]">租戶品牌監控目標</h3>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                健康狀態顯示於「租戶管理」頁對應租戶卡片;此處僅供登記與維護(品牌代號=租戶 slug)。
              </p>
              <div className="mt-2 flex flex-col divide-y divide-[var(--border)]">
                {tenantGroups.flatMap(([brand, items]) =>
                  items.map((t) => (
                    <div key={t.id} className="flex items-center gap-3 py-2.5">
                      <span className="rounded-md bg-[var(--bg-page)] px-2 py-0.5 font-mono text-xs text-[var(--text-secondary)]">
                        {brand}
                      </span>
                      <div className="min-w-0 flex-1">
                        <span className="text-sm font-medium text-[var(--text-primary)]">{t.label}</span>
                        <span className="ml-2 truncate text-xs text-[var(--text-secondary)]">
                          {t.url}
                          {!t.enabled ? "　·　已停用" : ""}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setEdit(t)}
                        aria-label="編輯"
                        className="text-[var(--text-secondary)] hover:text-[var(--primary)]"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeTarget(t)}
                        aria-label="刪除"
                        className="text-[var(--text-secondary)] hover:text-red-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )),
                )}
              </div>
            </section>
          )}
        </div>
      )}

      {edit !== null && (
        <TargetModal
          target={edit === "new" ? null : edit}
          onClose={() => setEdit(null)}
          onSaved={() => {
            setEdit(null);
            loadRegistry();
            probe();
          }}
        />
      )}
    </div>
  );
}

function TargetModal({
  target,
  onClose,
  onSaved,
}: {
  target: Target | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    brand: target?.brand ?? "",
    label: target?.label ?? "",
    url: target?.url ?? "",
    note: target?.note ?? "",
    enabled: target?.enabled ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function save() {
    if (!form.brand.trim() || !form.label.trim() || !form.url.trim()) {
      setMsg("品牌、服務標籤、health URL 皆為必填");
      return;
    }
    setBusy(true);
    setMsg(null);
    const payload = {
      brand: form.brand.trim(),
      label: form.label.trim(),
      url: form.url.trim(),
      note: form.note.trim() || null,
      enabled: form.enabled,
    };
    try {
      if (target) {
        await api.patch(`${BASE}/${encodeURIComponent(target.id)}`, payload);
      } else {
        await api.post(BASE, payload);
      }
      cacheInvalidate("GET:"); // 新增/編輯目標後立即反映（清 30s GET 舊快取）
      onSaved();
    } catch (e) {
      setMsg(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-bold text-[var(--text-primary)]">
          {target ? "編輯監控目標" : "新增監控目標"}
        </h2>
        <div className="flex flex-col gap-3">
          <Field label="品牌 / 分組 *" value={form.brand} onChange={(v) => setForm((f) => ({ ...f, brand: v }))} placeholder="locksmart" />
          <Field label="服務標籤 *" value={form.label} onChange={(v) => setForm((f) => ({ ...f, label: v }))} placeholder="派工 API" />
          <Field label="Health URL *" value={form.url} onChange={(v) => setForm((f) => ({ ...f, url: v }))} placeholder="https://xxx.run.app/health" />
          <Field label="備註（選填）" value={form.note} onChange={(v) => setForm((f) => ({ ...f, note: v }))} placeholder="正式環境主派工服務" />
          <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))}
              className="h-4 w-4"
            />
            啟用探測
          </label>
        </div>
        {msg && <p className="mt-3 text-[13px] text-red-600">{msg}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={save}
            disabled={busy}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "儲存中…" : "儲存"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)]"
      />
    </label>
  );
}
