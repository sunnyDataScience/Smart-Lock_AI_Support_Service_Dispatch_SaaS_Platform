"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, KeyRound } from "lucide-react";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { auth, changePassword, logout } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

/**
 * ChangePasswordSection — 帳戶頁「修改密碼」區塊（UAT W4-7）。
 *
 * 後端 POST /api/v1/auth/change-password 與型別本就存在，純前端缺入口。
 * 表單：目前密碼＋新密碼＋確認新密碼，inline 驗證（長度/一致/不得同舊密碼）。
 * 成功後（A3 會踢舊 session）顯示「請重新登入」提示，短暫停留後主動登出並導
 * /tech-login —— 與其等舊 token 半路 401,不如主動引導體驗較好。
 */

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

// 成功提示停留時間（ms）：讓使用者讀完「請重新登入」再導頁
const REDIRECT_DELAY_MS = 1800;

export default function ChangePasswordSection() {
  const router = useRouter();
  const t = useTranslations("pages.account.changePassword");

  const [open, setOpen] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  function validate(): string | null {
    if (newPw.length < 8) return t("tooShort");
    if (newPw !== confirmPw) return t("mismatch");
    if (newPw === currentPw) return t("sameAsCurrent");
    return null;
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const invalid = validate();
    if (invalid) {
      setError(invalid);
      return;
    }
    setLoading(true);
    try {
      await changePassword(currentPw, newPw);
      setDone(true);
      // A3：改密碼後舊 session 已被踢，主動登出（失敗也清本地 token）並導登入頁
      window.setTimeout(async () => {
        try {
          await logout();
        } catch {
          auth.clear();
        } finally {
          router.replace("/tech-login");
        }
      }, REDIRECT_DELAY_MS);
    } catch (err) {
      setError(friendlyError(err));
      setLoading(false);
    }
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--bg-page)]"
      >
        <div className="flex items-center gap-3">
          <KeyRound className="h-4 w-4 text-[var(--text-secondary)]" />
          <span className="text-[14px] font-medium text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 text-[var(--text-disabled)]" />
        ) : (
          <ChevronRight className="h-4 w-4 text-[var(--text-disabled)]" />
        )}
      </button>

      {open && (
        <div className="border-t border-[var(--border)] px-4 py-4">
          {done ? (
            <div
              role="status"
              className="rounded-lg border border-[var(--border)] bg-[var(--surface-subtle)] px-4 py-3 text-sm text-[var(--text-primary)]"
            >
              {t("success")}
            </div>
          ) : (
            <form onSubmit={onSubmit} className="flex flex-col gap-3">
              <label htmlFor="current-password" className="flex flex-col gap-[6px]">
                <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                  {t("currentLabel")}
                </span>
                <input
                  id="current-password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={currentPw}
                  onChange={(e) => setCurrentPw(e.target.value)}
                  disabled={loading}
                  className={inputCls}
                />
              </label>

              <label htmlFor="change-new-password" className="flex flex-col gap-[6px]">
                <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                  {t("newLabel")}
                </span>
                <input
                  id="change-new-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  disabled={loading}
                  className={inputCls}
                  placeholder={t("newPlaceholder")}
                />
              </label>

              <label htmlFor="change-confirm-password" className="flex flex-col gap-[6px]">
                <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                  {t("confirmLabel")}
                </span>
                <input
                  id="change-confirm-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  disabled={loading}
                  className={inputCls}
                  placeholder={t("newPlaceholder")}
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
                disabled={loading || !currentPw || !newPw || !confirmPw}
                className="h-10 rounded-lg bg-[var(--primary)] text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 disabled:opacity-50"
              >
                {loading ? t("submitting") : t("submit")}
              </button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}
