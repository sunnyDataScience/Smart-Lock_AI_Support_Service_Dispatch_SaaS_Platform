"use client";

import { Wrench } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import BackToHome from "@/components/layout/BackToHome";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { loginTechnician } from "@/lib/api";
import { APP_MODE, PEER_PORTAL_URL } from "@/lib/appMode";
import { friendlyError } from "@/lib/apiError";

// 本頁 = 師傅登入入口。CR-0115：登入與註冊分離 —— 註冊由此頁的 tab 改為連到
// 獨立多步驟頁 /tech-register（欄位擴為 KYC 等級、單卡塞不下）。
// 2026-06-19:已移除 DesktopMobileGuard,桌面/手機皆可直接登入。

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

// 註冊頁位置：tech build 站內 /tech-register；dispatch（配 PEER）指對方 tech portal。
const registerHref =
  APP_MODE === "dispatch" && PEER_PORTAL_URL
    ? `${PEER_PORTAL_URL}/tech-register`
    : "/tech-register";

export default function TechLoginPage() {
  const t = useTranslations("techPortal.techLogin");

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4 py-8">
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>
      <BackToHome className="absolute left-4 top-4" />

      <div className="w-full max-w-[440px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-sm">
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

        <TechLoginForm t={t} />

        {/* CR-0115：註冊分離 —— 連到獨立多步驟申請頁 */}
        <div className="mt-5 rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-3 text-center">
          <span className="text-[13px] text-[var(--text-secondary)]">{t("noAccount")} </span>
          <Link
            href={registerHref}
            className="text-[13px] font-semibold text-[var(--primary)] hover:underline"
          >
            {t("applyLink")}
          </Link>
        </div>

        <div className="mt-4 border-t border-[var(--border)] pt-4 text-center">
          <Link
            href={
              APP_MODE === "tech" && PEER_PORTAL_URL
                ? `${PEER_PORTAL_URL}/login`
                : "/login"
            }
            className="text-[13px] font-medium text-[var(--primary)] hover:underline"
          >
            {t("brandEntryLink")}
          </Link>
        </div>

        <p className="mt-4 text-center text-xs text-[var(--text-disabled)]">
          {t("footerVersion")}
        </p>
      </div>
    </div>
  );
}

function TechLoginForm({
  t,
}: {
  t: (k: string, vars?: Record<string, string | number>) => string;
}) {
  const router = useRouter();
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
      setError(friendlyError(e));
      setLoading(false);
    }
  }

  return (
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
          className={inputCls}
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
          className={inputCls}
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

      <Link
        href="/forgot-password"
        className="text-center text-[13px] font-medium text-[var(--primary)] hover:underline"
      >
        {t("forgotPassword")}
      </Link>
    </form>
  );
}
