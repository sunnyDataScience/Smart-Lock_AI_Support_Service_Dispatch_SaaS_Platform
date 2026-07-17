"use client";

// CR-0169 師傅 LINE 推播 — 平台官方號綁定卡(帳號頁)。
// 流程:產生 6 位綁定碼(TTL 10 分)→ 加平台官方號好友 → LINE 輸入碼 → webhook 綁定。
// 已綁:顯示遮蔽尾碼+搶單池新單推播開關(HD-3=b)+解綁。

import { useCallback, useEffect, useState } from "react";
import { MessageCircle, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";

interface Binding {
  bound: boolean;
  line_user_id_masked: string | null;
  notify_pool_new: boolean;
  platform_line_configured: boolean;
}

export default function LineBindCard() {
  const t = useTranslations("pages.account.lineBind");
  const [binding, setBinding] = useState<Binding | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get<{ data: Binding }>("/api/v1/technicians/me/line-binding");
      setBinding(res.data);
      setError(null);
    } catch (e) {
      setError(friendlyError(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function issueCode() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ data: { code: string } }>(
        "/api/v1/technicians/me/line-bind-code",
        {},
      );
      setCode(res.data.code);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  async function togglePool() {
    if (!binding) return;
    setBusy(true);
    try {
      const res = await api.patch<{ data: Binding }>(
        "/api/v1/technicians/me/line-binding",
        { notify_pool_new: !binding.notify_pool_new },
      );
      setBinding(res.data);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  async function unbind() {
    if (typeof window !== "undefined" && !window.confirm(t("unbindConfirm"))) return;
    setBusy(true);
    try {
      await api.delete("/api/v1/technicians/me/line-binding");
      setCode(null);
      await load();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
      <div className="mb-2 flex items-center gap-2">
        <MessageCircle className="h-4 w-4 text-[#06C755]" aria-hidden />
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
          {t("title")}
        </span>
      </div>
      <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">{t("desc")}</p>

      {error && (
        <p className="mt-2 rounded-lg bg-red-50 px-2 py-1.5 text-[11px] text-red-700">{error}</p>
      )}

      {binding && !binding.platform_line_configured && (
        <p className="mt-2 rounded-lg bg-amber-50 px-2 py-1.5 text-[11px] text-amber-700">
          {t("notConfigured")}
        </p>
      )}

      {binding?.bound ? (
        <div className="mt-3 flex flex-col gap-3">
          <div className="flex items-center justify-between rounded-xl bg-emerald-50 px-3 py-2">
            <span className="text-[12px] font-medium text-emerald-700">
              {t("boundAs", { masked: binding.line_user_id_masked ?? "" })}
            </span>
            <button
              type="button"
              onClick={unbind}
              disabled={busy}
              className="text-[11px] text-[var(--text-disabled)] underline disabled:opacity-50"
            >
              {t("unbind")}
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-[12px] text-[var(--text-primary)]">{t("poolToggleLabel")}</span>
              <span className="text-[10px] text-[var(--text-disabled)]">{t("poolToggleHint")}</span>
            </div>
            <button
              type="button"
              onClick={togglePool}
              disabled={busy}
              className="relative h-7 w-12 rounded-full transition disabled:opacity-50"
              style={{ backgroundColor: binding.notify_pool_new ? "#10B981" : "#D1D5DB" }}
              aria-label={t("poolToggleLabel")}
            >
              <span
                className="absolute top-[2px] h-6 w-6 rounded-full bg-white shadow transition-all"
                style={{ left: binding.notify_pool_new ? "22px" : "2px" }}
              />
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-col gap-2">
          {code ? (
            <div className="rounded-xl border border-dashed border-[var(--border)] p-3 text-center">
              <p className="text-[11px] text-[var(--text-secondary)]">{t("codeLabel")}</p>
              <p className="my-1 font-mono text-[28px] font-bold tracking-[0.3em] text-[var(--text-primary)]">
                {code}
              </p>
              <p className="text-[10px] leading-relaxed text-[var(--text-disabled)]">
                {t("codeHint")}
              </p>
            </div>
          ) : null}
          <button
            type="button"
            onClick={issueCode}
            disabled={busy}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-[#06C755] px-4 py-2.5 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} aria-hidden />
            {code ? t("regenBtn") : t("bindBtn")}
          </button>
        </div>
      )}
    </section>
  );
}
