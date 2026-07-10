"use client";

import { Building2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, getCurrentSession, login, loginVendor } from "@/lib/api";
import StaffRegisterForm from "@/components/auth/StaffRegisterForm";
import { APP_MODE, PEER_PORTAL_URL } from "@/lib/appMode";
import { friendlyError } from "@/lib/apiError";
import { fallbackRouteForRole } from "@/lib/rolePolicy";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import BackToHome from "@/components/layout/BackToHome";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 20260702 會議決議 2:UI 入口濃縮為兩條、登入與註冊同框(仿 Google)。
// 本頁 = 派案方入口「品牌 / 經銷 / 鎖店」:
//   - 登入 tab:單一表單同時涵蓋後台管理角色(loginAdmin)與廠商帳號(loginVendor)
//     —— 先試 admin,401 才退試 vendor(非 401 如鎖定/停用直接顯示,不重試),
//     成功後依角色導向(fallbackRouteForRole:vendor→/vendor、其他→/dashboard)。
//   - 註冊 tab:品牌員工帳號申請(CR-0114 R5 裁決 4;StaffRegisterForm →
//     POST /tenants/{tid}/staff-applications,pending 待品牌 Admin 審核並指派角色;
//     舊 VendorRegisterForm 廠商自助註冊已退場,品牌導入改走 landing → platform)。
// /vendor-login 與 /register 保留 redirect 到新入口,不破壞既有連結。

type Tab = "login" | "register";

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

export default function BrandEntryPage() {
  const t = useTranslations("login");
  const tR = useTranslations("register");
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("login");

  // ?tab=register 深連結(來自 /register redirect)。用 window.location 讀,
  // 避免 useSearchParams 的 Suspense 邊界需求。
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("tab") === "register") {
      setTab("register");
    }
  }, []);

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4 py-8">
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>
      <BackToHome className="absolute left-4 top-4" />

      <div className="w-full max-w-[440px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <Building2 className="h-6 w-6 text-white" />
          </div>
          <div className="flex flex-col items-center gap-1">
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {t("entryTitle")}
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">{t("entrySubtitle")}</p>
          </div>
        </div>

        {/* 登入/註冊同框切換(仿 Google) */}
        <div className="mb-5 flex rounded-lg border border-[var(--border)] p-1">
          {(["login", "register"] as Tab[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setTab(k)}
              className={`flex-1 rounded-md py-2 text-sm font-semibold transition ${
                tab === k
                  ? "bg-[var(--primary)] text-white"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {k === "login" ? t("tabLogin") : t("tabRegister")}
            </button>
          ))}
        </div>

        {tab === "login" ? (
          <BrandLoginForm t={t} onDone={(dest) => router.replace(dest)} />
        ) : (
          <StaffRegisterForm onDone={() => setTab("login")} doneActionLabel={tR("toLogin")} />
        )}

        <div className="mt-5 border-t border-[var(--border)] pt-4 text-center">
          <Link
            href={
              APP_MODE === "dispatch" && PEER_PORTAL_URL
                ? `${PEER_PORTAL_URL}/tech-login`
                : "/tech-login"
            }
            className="text-[13px] font-medium text-[var(--primary)] hover:underline"
          >
            {t("techEntryLink")}
          </Link>
        </div>

        {/* TODO: remove dev hint before prod */}
        <p className="mt-4 text-center text-xs text-[var(--text-disabled)]">
          {t("devHint")}
        </p>
      </div>
    </div>
  );
}

function BrandLoginForm({
  t,
  onDone,
}: {
  t: (k: string, vars?: Record<string, string | number>) => string;
  onDone: (dest: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      // 派案方單一表單:先試後台角色,查無帳號(401)才退試廠商帳號。
      // 非 401(登入鎖定 429 / 帳號停用 403)直接顯示,不重試以免混淆訊息。
      try {
        await login(email.trim(), password);
      } catch (e1) {
        if (!(e1 instanceof ApiError && e1.status === 401)) throw e1;
        await loginVendor(email.trim(), password);
      }
      onDone(fallbackRouteForRole(getCurrentSession()?.role ?? null));
    } catch (e) {
      setError(friendlyError(e));
      setLoading(false);
    }
  }

  return (
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
          className={inputCls}
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

      {/* CR-0146 OIDC 授權碼流(2.1.1-R2):NEXT_PUBLIC_CASDOOR_ENDPOINT 配置時顯示。
          redirect_uri 須於 client 端組(SSR 無 window → 空值 bug,E2E 抓到) */}
      {process.env.NEXT_PUBLIC_CASDOOR_ENDPOINT && (
        <button
          type="button"
          onClick={() => {
            const ep = (process.env.NEXT_PUBLIC_CASDOOR_ENDPOINT ?? "").replace(/\/$/, "");
            const cid = process.env.NEXT_PUBLIC_CASDOOR_CLIENT_ID ?? "smartlock-portal-client";
            const uri = encodeURIComponent(`${window.location.origin}/auth/callback`);
            window.location.href = `${ep}/login/oauth/authorize?client_id=${encodeURIComponent(cid)}&response_type=code&redirect_uri=${uri}&scope=read&state=smartlock`;
          }}
          className="flex h-10 items-center justify-center rounded-lg border border-[var(--border)] text-sm font-medium text-[var(--text-primary)] transition hover:bg-[var(--bg-page)]"
        >
          以單一登入(SSO)繼續
        </button>
      )}
    </form>
  );
}
