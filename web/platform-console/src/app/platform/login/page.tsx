"use client";

// CR-0114 平台管理員登入(Lock AI 內部自用)。
// 打 /api/v1/platform/auth/login(平台庫帳號池,與品牌/師傅登入完全隔離);
// token role=platform_admin,AuthGuard/rolePolicy 只放行 /platform 頁群。
// UAT W6-2:登入前頁也要能切語言——右上補 LocaleToggle(與 console 殼頂欄同機制),
// 文案接 platform.login namespace。

import { ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { loginPlatformAdmin } from "@/lib/api";
import { friendlyLoginError } from "@/lib/apiError";
import IdleLogoutNotice from "@/components/auth/IdleLogoutNotice";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

export default function PlatformLoginPage() {
  const router = useRouter();
  const t = useTranslations("platform.login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginPlatformAdmin(email.trim(), password);
      router.replace("/platform");
    } catch (err) {
      setError(friendlyLoginError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4 py-8">
      {/* 登入前無 console 殼頂欄,LocaleToggle 固定右上(同 tech-portal 登入頁) */}
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>

      <div className="w-full max-w-[400px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <ShieldCheck className="h-6 w-6 text-white" aria-hidden />
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

        <IdleLogoutNotice />

        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-[var(--text-primary)]">{t("emailLabel")}</span>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputCls}
              disabled={loading}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-[var(--text-primary)]">{t("passwordLabel")}</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputCls}
              disabled={loading}
            />
          </label>

          {error && (
            <p role="alert" className="rounded-lg bg-[var(--danger-subtle,rgba(239,68,68,0.1))] px-3 py-2 text-sm text-[var(--danger,#dc2626)]">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || !email || password.length < 8}
            className="h-10 rounded-lg bg-[var(--primary)] text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {loading ? t("submitting") : t("submit")}
          </button>

          {/* CR-0166 D8：SSO 三站複製——OIDC 授權碼流（2.1.1-R3，複製自 brand-portal）。
              NEXT_PUBLIC_CASDOOR_ENDPOINT 配置時顯示；redirect_uri client 端組。 */}
          {process.env.NEXT_PUBLIC_CASDOOR_ENDPOINT && (
            <button
              type="button"
              onClick={() => {
                const ep = (process.env.NEXT_PUBLIC_CASDOOR_ENDPOINT ?? "").replace(/\/$/, "");
                const cid = process.env.NEXT_PUBLIC_CASDOOR_CLIENT_ID ?? "smartlock-portal-client";
                const uri = encodeURIComponent(`${window.location.origin}/auth/callback`);
                window.location.href = `${ep}/login/oauth/authorize?client_id=${encodeURIComponent(cid)}&response_type=code&redirect_uri=${uri}&scope=read&state=smartlock`;
              }}
              className="h-10 rounded-lg border border-[var(--border)] text-sm font-medium text-[var(--text-primary)] transition hover:bg-[var(--bg-page)]"
            >
              {t("sso")}
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
