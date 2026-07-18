"use client";

// CR-0166 R3 平台 console — 租戶 License / 模組開通管理 modal。
// 平台管理員設定訂閱級距、開通附加模組（refinery/studio/compiler）、License 到期日。
// UAT W6-2:文案接 i18n(platform.license namespace)。

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";

const PLAN_TIERS = ["free", "standard", "pro", "enterprise"] as const;
// core 恆有、不可取消；其餘為 License 附加模組
const OPTIONAL_MODULES = ["refinery", "studio", "compiler"] as const;

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
  const t = useTranslations("platform.license");
  const tc = useTranslations("platform.common");
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
          {t("title")}
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">{tenantName}</p>

        {error && (
          <div className="mt-3 rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-3 py-2 text-sm text-[var(--badge-danger-fg)]">
            {error}
          </div>
        )}

        {loading ? (
          <div className="py-10 text-center text-sm text-[var(--text-secondary)]">{tc("loading")}</div>
        ) : (
          <div className="mt-4 flex flex-col gap-4">
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-[var(--text-primary)]">{t("planTier")}</span>
              <select
                value={tier}
                onChange={(e) => setTier(e.target.value)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2"
              >
                {PLAN_TIERS.map((p) => (
                  <option key={p} value={p}>{t(`plan.${p}`)}</option>
                ))}
              </select>
            </label>

            <div className="flex flex-col gap-2 text-sm">
              <span className="font-medium text-[var(--text-primary)]">{t("modules")}</span>
              <label className="flex items-center gap-2 text-[var(--text-secondary)]">
                <input type="checkbox" checked disabled /> {t("coreModule")}
              </label>
              {OPTIONAL_MODULES.map((m) => (
                <label key={m} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={modules.has(m)}
                    onChange={() => toggle(m)}
                  />
                  {t(`module.${m}`)}
                </label>
              ))}
            </div>

            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-[var(--text-primary)]">
                {t("expiresLabel")}
              </span>
              <input
                type="date"
                value={expires}
                onChange={(e) => setExpires(e.target.value)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2"
              />
              {lic?.is_expired && (
                <span className="text-xs text-[var(--status-danger)]">{t("expiredHint")}</span>
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
            {tc("cancel")}
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving || loading}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {saving ? tc("saving") : tc("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
