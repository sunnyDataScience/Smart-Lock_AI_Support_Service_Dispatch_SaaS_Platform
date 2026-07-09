"use client";

import { KeyRound } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { requestPasswordReset } from "@/lib/api";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// CR-0025 / ADR-0114 — 自助忘記密碼 step 1：輸入 email → 寄重設連結。
// 後端一律回 200（枚舉防護），故成功畫面固定顯示「若帳號存在已寄出」。
export default function ForgotPasswordPage() {
  const t = useTranslations("passwordReset");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    try {
      await requestPasswordReset(email.trim());
    } catch {
      // 枚舉防護：不論成敗都顯示同一訊息，不洩漏帳號是否存在
    } finally {
      setSent(true);
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4">
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>

      <div className="w-full max-w-[400px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <KeyRound className="h-6 w-6 text-white" />
          </div>
          <div className="flex flex-col items-center gap-1 text-center">
            <h1 className="text-xl font-bold text-[var(--text-primary)]">{t("requestTitle")}</h1>
            <p className="text-sm text-[var(--text-secondary)]">{t("requestSubtitle")}</p>
          </div>
        </div>

        {sent ? (
          <div className="flex flex-col gap-4">
            <div
              role="status"
              className="rounded-lg border border-[var(--border)] bg-[var(--surface-subtle)] px-4 py-3 text-sm text-[var(--text-primary)]"
            >
              {t("requestSent")}
            </div>
            <Link
              href="/login"
              className="text-center text-sm font-medium text-[var(--primary)] hover:underline"
            >
              {t("backToLogin")}
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <label htmlFor="reset-email" className="flex flex-col gap-[6px]">
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">{t("emailLabel")}</span>
              <input
                id="reset-email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50"
                placeholder={t("emailPlaceholder")}
              />
            </label>

            <button
              type="submit"
              disabled={loading || !email}
              className="h-10 rounded-lg bg-[var(--primary)] text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 disabled:opacity-50"
            >
              {loading ? t("requestSubmitting") : t("requestSubmit")}
            </button>

            <Link
              href="/login"
              className="text-center text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--primary)] hover:underline"
            >
              {t("backToLogin")}
            </Link>
          </form>
        )}
      </div>
    </div>
  );
}
