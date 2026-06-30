"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ApiError, login } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import BackToHome from "@/components/layout/BackToHome";
import { useTranslations } from "@/components/i18n/LocaleProvider";

export default function LoginPage() {
  const t = useTranslations("login");
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email.trim(), password);
      router.replace("/dashboard");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(friendlyError(e));
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError(String(e));
      }
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4">
      {/* 登入前語系切換 — 公開頁面也應允許切，否則 zh-TW 預設不會的英文用戶看不懂表單
       * 位置：右上角 absolute，不擠壓登入卡片視覺中心 */}
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>
      <BackToHome className="absolute left-4 top-4" />

      <div className="w-full max-w-[400px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <Lock className="h-6 w-6 text-white" />
          </div>
          <div className="flex flex-col items-center gap-1">
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {t("title")}
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">
              {t("subtitle")}
            </p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <label htmlFor="login-email" className="flex flex-col gap-[6px]">
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              {t("emailLabel")}
            </span>
            <input
              id="login-email"
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

          <label htmlFor="login-password" className="flex flex-col gap-[6px]">
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              {t("passwordLabel")}
            </span>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50"
              placeholder={t("passwordPlaceholder")}
            />
          </label>

          {error && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="h-10 rounded-lg bg-[var(--primary)] text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 disabled:opacity-50"
          >
            {loading ? t("submitting") : t("submit")}
          </button>

          <Link
            href="/forgot-password"
            className="text-center text-[13px] font-medium text-[var(--primary)] hover:underline"
          >
            {t("forgotPassword")}
          </Link>
          <Link
            href="/register"
            className="text-center text-[13px] font-medium text-[var(--primary)] hover:underline"
          >
            {t("registerLink")}
          </Link>
        </form>

        {/* TODO: remove dev hint before prod */}
        <p className="mt-6 text-center text-xs text-[var(--text-disabled)]">
          {t("devHint")}
        </p>
      </div>
    </div>
  );
}
