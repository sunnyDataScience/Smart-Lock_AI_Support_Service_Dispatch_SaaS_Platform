"use client";

// CR-0166 R3 平台 console — 租戶 License / 模組開通管理 modal。
// 平台管理員設定訂閱級距、開通附加模組（refinery/studio/compiler）、License 到期日。
// 內部工具，文案直接繁中。

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

const PLAN_TIERS = ["free", "standard", "pro", "enterprise"] as const;
// core 恆有、不可取消；其餘為 License 附加模組
const OPTIONAL_MODULES: { key: string; label: string }[] = [
  { key: "refinery", label: "知識精煉（refinery）" },
  { key: "studio", label: "設定工作室（studio）" },
  { key: "compiler", label: "Onboarding 編譯器（compiler）" },
];

interface License {
  tenant_id: string;
  plan_tier: string;
  entitled_modules: string[];
  license_expires_at: string | null;
  is_expired: boolean;
}

interface Props {
  tenantId: string;
  tenantName: string;
  onClose: () => void;
  onSaved?: () => void;
}

export default function LicenseModal({ tenantId, tenantName, onClose, onSaved }: Props) {
  const [lic, setLic] = useState<License | null>(null);
  const [tier, setTier] = useState<string>("standard");
  const [modules, setModules] = useState<Set<string>>(new Set(["core"]));
  const [expires, setExpires] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ data: License }>(
        `/api/v1/platform/tenants/${tenantId}/license`,
      );
      const d = res.data;
      setLic(d);
      setTier(d.plan_tier);
      setModules(new Set(d.entitled_modules));
      setExpires(d.license_expires_at ? d.license_expires_at.slice(0, 10) : "");
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  function toggle(key: string) {
    setModules((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      next.add("core"); // core 恆保留
      return next;
    });
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api.put(`/api/v1/platform/tenants/${tenantId}/license`, {
        plan_tier: tier,
        entitled_modules: Array.from(modules).filter((m) => m !== "core"),
        license_expires_at: expires ? `${expires}T23:59:59+08:00` : null,
      });
      onSaved?.();
      onClose();
    } catch (e) {
      setError(friendlyError(e));
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-[var(--text-primary)]">
          License 管理
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">{tenantName}</p>

        {error && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="py-10 text-center text-sm text-[var(--text-secondary)]">載入中…</div>
        ) : (
          <div className="mt-4 flex flex-col gap-4">
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-[var(--text-primary)]">訂閱級距</span>
              <select
                value={tier}
                onChange={(e) => setTier(e.target.value)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2"
              >
                {PLAN_TIERS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </label>

            <div className="flex flex-col gap-2 text-sm">
              <span className="font-medium text-[var(--text-primary)]">開通模組</span>
              <label className="flex items-center gap-2 text-[var(--text-secondary)]">
                <input type="checkbox" checked disabled /> core（核心，恆開通）
              </label>
              {OPTIONAL_MODULES.map((m) => (
                <label key={m.key} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={modules.has(m.key)}
                    onChange={() => toggle(m.key)}
                  />
                  {m.label}
                </label>
              ))}
            </div>

            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-[var(--text-primary)]">
                License 到期日（留空＝無期限）
              </span>
              <input
                type="date"
                value={expires}
                onChange={(e) => setExpires(e.target.value)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2"
              />
              {lic?.is_expired && (
                <span className="text-xs text-red-600">目前 License 已過期，僅 core 可用</span>
              )}
            </label>
          </div>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving || loading}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {saving ? "儲存中…" : "儲存"}
          </button>
        </div>
      </div>
    </div>
  );
}
