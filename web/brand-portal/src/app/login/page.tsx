"use client";

import { Bot, Building2, ClipboardList, Receipt } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, getCurrentSession, login, loginVendor } from "@/lib/api";
import StaffRegisterForm from "@/components/auth/StaffRegisterForm";
import IdleLogoutNotice from "@/components/auth/IdleLogoutNotice";
import { APP_MODE, PEER_PORTAL_URL } from "@/lib/appMode";
import { friendlyLoginError } from "@/lib/apiError";
import { fallbackRouteForRole } from "@/lib/rolePolicy";
import LocaleToggle from "@/components/i18n/LocaleToggle";
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
//
// 2026-07-10 版面改為左右分欄:`/` 已一律導 /login(3000 不渲染 landing),
// 本頁即品牌後台首頁 —— 左側品牌資訊面板(lg 以上)、右側登入表單;
// BackToHome 移除(無上一頁可回)。

type Tab = "login" | "register";

const inputCls =
  "h-11 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

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

  const features = [
    { icon: Bot, title: t("heroFeature1Title"), desc: t("heroFeature1Desc") },
    { icon: ClipboardList, title: t("heroFeature2Title"), desc: t("heroFeature2Desc") },
    { icon: Receipt, title: t("heroFeature3Title"), desc: t("heroFeature3Desc") },
  ];

  return (
    <div className="flex min-h-dvh bg-[var(--bg-surface)]">
      {/* 左:品牌資訊面板(lg 以上顯示;固定深藍漸層,雙主題皆成立) */}
      <aside className="relative hidden w-[52%] flex-col justify-between overflow-hidden bg-gradient-to-br from-[#0B1220] via-[#132B66] to-[#1D4ED8] p-12 text-white lg:flex xl:p-16">
        {/* 裝飾光暈(純視覺,不佔互動) */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-[#3B82F6]/20 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-40 -left-24 h-[28rem] w-[28rem] rounded-full bg-[#60A5FA]/10 blur-3xl"
        />

        <div className="relative flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/20">
            <Building2 className="h-6 w-6 text-white" />
          </div>
          <span className="text-lg font-bold tracking-wide">{t("heroBrand")}</span>
        </div>

        <div className="relative max-w-[30rem]">
          <h2 className="text-3xl font-bold leading-snug xl:text-4xl [text-wrap:balance]">
            {t("heroTitle")}
          </h2>
          <p className="mt-4 text-[15px] leading-relaxed text-white/75">
            {t("heroSubtitle")}
          </p>

          <ul className="mt-10 flex flex-col gap-6">
            {features.map(({ icon: Icon, title, desc }) => (
              <li key={title} className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/15">
                  <Icon className="h-5 w-5 text-[#93C5FD]" />
                </div>
                <div>
                  <p className="text-[15px] font-semibold">{title}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-white/65">{desc}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-white/45">{t("heroFootnote")}</p>
      </aside>

      {/* 右:登入/註冊 */}
      <main className="relative flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <div className="absolute right-4 top-4">
          <LocaleToggle />
        </div>

        <div className="w-full max-w-[400px]">
          {/* 行動版精簡品牌列(左面板隱藏時的替代) */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--primary)]">
              <Building2 className="h-5 w-5 text-white" />
            </div>
            <span className="text-base font-bold text-[var(--text-primary)]">
              {t("heroBrand")}
            </span>
          </div>

          <div className="mb-6 flex flex-col gap-1">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {t("entryTitle")}
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">{t("entrySubtitle")}</p>
          </div>

          <IdleLogoutNotice />

          {/* 登入/註冊同框切換(仿 Google) */}
          <div className="mb-6 flex rounded-lg border border-[var(--border)] p-1">
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

          <div className="mt-6 border-t border-[var(--border)] pt-4 text-center">
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
      </main>
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
      setError(friendlyLoginError(e));
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
        className="h-11 rounded-lg bg-[var(--primary)] text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 disabled:opacity-50"
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
          className="flex h-11 items-center justify-center rounded-lg border border-[var(--border)] text-sm font-medium text-[var(--text-primary)] transition hover:bg-[var(--bg-page)]"
        >
          以單一登入(SSO)繼續
        </button>
      )}
    </form>
  );
}
