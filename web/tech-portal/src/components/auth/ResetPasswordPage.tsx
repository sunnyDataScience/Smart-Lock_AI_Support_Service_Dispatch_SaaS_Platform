"use client";

import { KeyRound } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { ApiError, confirmPasswordReset } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// CR-0025 / ADR-0114 — 自助忘記密碼 step 2：?token=... + 新密碼 → confirm。
function ResetPasswordInner() {
  const t = useTranslations("passwordReset");
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError(t("tooShort"));
      return;
    }
    if (password !== confirmPw) {
      setError(t("mismatch"));
      return;
    }
    setLoading(true);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
    } catch (e) {
      if (e instanceof ApiError && (e.errorCode === "RESET_TOKEN_INVALID" || e.errorCode === "RESET_TOKEN_EXPIRED")) {
        setError(t("expiredOrUsed"));
      } else if (e instanceof ApiError) {
        setError(friendlyError(e));
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
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
            <h1 className="text-xl font-bold text-[var(--text-primary)]">{t("confirmTitle")}</h1>
            <p className="text-sm text-[var(--text-secondary)]">{t("confirmSubtitle")}</p>
          </div>
        </div>

        {!token ? (
          <div className="flex flex-col gap-4">
            <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {t("missingToken")}
            </div>
            <Link href="/forgot-password" className="text-center text-sm font-medium text-[var(--primary)] hover:underline">
              {t("requestTitle")}
            </Link>
          </div>
        ) : done ? (
          <div className="flex flex-col gap-4">
            <div role="status" className="rounded-lg border border-[var(--border)] bg-[var(--surface-subtle)] px-4 py-3 text-sm text-[var(--text-primary)]">
              {t("confirmSuccess")}
            </div>
            {/* UAT W4-4：師傅站登入頁是 /tech-login（/login 不存在 → 404） */}
            <Link href="/tech-login" className="text-center text-sm font-medium text-[var(--primary)] hover:underline">
              {t("goLogin")}
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <label htmlFor="new-password" className="flex flex-col gap-[6px]">
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">{t("newPasswordLabel")}</span>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50"
                placeholder={t("newPasswordPlaceholder")}
              />
            </label>

            <label htmlFor="confirm-password" className="flex flex-col gap-[6px]">
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">{t("confirmPasswordLabel")}</span>
              <input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                disabled={loading}
                className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50"
                placeholder={t("newPasswordPlaceholder")}
              />
            </label>

            {error && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !password || !confirmPw}
              className="h-10 rounded-lg bg-[var(--primary)] text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 disabled:opacity-50"
            >
              {loading ? t("confirmSubmitting") : t("confirmSubmit")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordInner />
    </Suspense>
  );
}
