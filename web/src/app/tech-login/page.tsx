"use client";

import { Wrench } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import BackToHome from "@/components/layout/BackToHome";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { loginTechnician } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

// 2026-06-19：移除 DesktopMobileGuard（原桌面顯示「請使用手機開啟」太不便）+ 藍漸層手機版型，
// 改為與 vendor-login / login 一致的置中卡片，桌面/手機皆可直接登入。
// 技師工作頁（/pool 等）本就無 guard，故此頁解鎖後整條技師流程桌面可用。
export default function TechLoginPage() {
  const router = useRouter();
  const t = useTranslations("techPortal.techLogin");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginTechnician(identifier.trim(), password);
      router.replace("/home");
    } catch (e) {
      setError(
        friendlyError(e),
      );
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4">
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>
      <BackToHome className="absolute left-4 top-4" />

      <div className="w-full max-w-[400px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <Wrench className="h-6 w-6 text-white" />
          </div>
          <div className="flex flex-col items-center gap-1">
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {t("brandName")}
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">{t("subtitle")}</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-[6px]">
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              {t("identifierLabel")}
            </span>
            <input
              type="text"
              inputMode="email"
              autoComplete="username"
              required
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              disabled={loading}
              className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50"
              placeholder={t("identifierPlaceholder")}
            />
          </label>

          <label className="flex flex-col gap-[6px]">
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              {t("passwordLabel")}
            </span>
            <input
              type="password"
              autoComplete="current-password"
              required
              minLength={8}
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
            disabled={loading || !identifier || !password}
            className="h-10 rounded-lg bg-[var(--primary)] text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 disabled:opacity-50"
          >
            {loading ? t("submitting") : t("submit")}
          </button>

          <div className="flex items-center justify-between text-[13px]">
            <Link
              href="/forgot-password"
              className="font-medium text-[var(--primary)] hover:underline"
            >
              {t("forgotPassword")}
            </Link>
            <Link
              href="/login"
              className="font-medium text-[var(--primary)] hover:underline"
            >
              {t("adminLink")}
            </Link>
          </div>
          <Link
            href="/register"
            className="text-center text-[13px] font-medium text-[var(--primary)] hover:underline"
          >
            {t("registerLink")}
          </Link>
        </form>

        <p className="mt-6 text-center text-xs text-[var(--text-disabled)]">
          {t("footerVersion")}
        </p>
      </div>
    </div>
  );
}
