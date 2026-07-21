"use client";

import { BellRing, Camera, Wallet, Wrench } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { loginTechnician } from "@/lib/api";
import { APP_MODE, PEER_PORTAL_URL } from "@/lib/appMode";
import { friendlyLoginError } from "@/lib/apiError";
import IdleLogoutNotice from "@/components/auth/IdleLogoutNotice";

// 本頁 = 師傅登入入口。CR-0115：登入與註冊分離 —— 註冊由此頁的 tab 改為連到
// 獨立多步驟頁 /tech-register（欄位擴為 KYC 等級、單卡塞不下）。
// 2026-06-19:已移除 DesktopMobileGuard,桌面/手機皆可直接登入。
//
// 2026-07-10 版面比照品牌後台登入頁改左右分欄:`/` 一律導 /tech-login,
// 本頁即師傅站首頁 —— 左側資訊面板(lg 以上,深 teal 漸層)、右側登入表單;
// BackToHome 移除(無上一頁可回)。

const inputCls =
  "h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

// 註冊頁位置：tech build 站內 /tech-register；dispatch（配 PEER）指對方 tech portal。
const registerHref =
  APP_MODE === "dispatch" && PEER_PORTAL_URL
    ? `${PEER_PORTAL_URL}/tech-register`
    : "/tech-register";

export default function TechLoginPage() {
  const t = useTranslations("techPortal.techLogin");

  const features = [
    { icon: BellRing, title: t("heroFeature1Title"), desc: t("heroFeature1Desc") },
    { icon: Camera, title: t("heroFeature2Title"), desc: t("heroFeature2Desc") },
    { icon: Wallet, title: t("heroFeature3Title"), desc: t("heroFeature3Desc") },
  ];

  return (
    <div className="tech-soft flex min-h-dvh bg-[var(--bg-surface)]">
      {/* 左:資訊面板(lg 以上顯示;固定深 teal 漸層,雙主題皆成立) */}
      <aside className="relative hidden w-[52%] flex-col justify-between overflow-hidden bg-gradient-to-br from-[#04211E] via-[#0B3F39] to-[#0F766E] p-12 text-white lg:flex xl:p-16">
        {/* 裝飾光暈(純視覺,不佔互動) */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-[#14B8A6]/20 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-40 -left-24 h-[28rem] w-[28rem] rounded-full bg-[#5EEAD4]/10 blur-3xl"
        />

        <div className="relative flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/20">
            <Wrench className="h-6 w-6 text-white" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold tracking-wide">{t("brandName")}</span>
            <span className="text-xs text-white/60">{t("subtitle")}</span>
          </div>
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
                  <Icon className="h-5 w-5 text-[#5EEAD4]" />
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

      {/* 右:登入表單 */}
      <main className="relative flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <div className="absolute right-4 top-4">
          <LocaleToggle />
        </div>

        <div className="w-full max-w-[400px]">
          {/* 行動版精簡品牌列(左面板隱藏時的替代) */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--primary)]">
              <Wrench className="h-5 w-5 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="text-base font-bold leading-tight text-[var(--text-primary)]">
                {t("brandName")}
              </span>
              <span className="text-xs text-[var(--text-secondary)]">{t("subtitle")}</span>
            </div>
          </div>

          <div className="mb-6 flex flex-col gap-1">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {t("subtitle")}
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">{t("entrySubtitle")}</p>
          </div>

          <IdleLogoutNotice />

          <TechLoginForm t={t} />

          {/* CR-0115：註冊分離 —— 連到獨立多步驟申請頁 */}
          <div className="mt-6 rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-3 text-center">
            <span className="text-[13px] text-[var(--text-secondary)]">{t("noAccount")} </span>
            <Link
              href={registerHref}
              className="text-[13px] font-semibold text-[var(--primary)] hover:underline"
            >
              {t("applyLink")}
            </Link>
          </div>
        </div>
      </main>
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
      setError(friendlyLoginError(e));
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      {/* CR-0177 S2：SSO 為**主要**登入路徑（置頂 + 主要樣式）；密碼登入降為 break-glass
          緊急備援（後端 S4 留稽核 break_glass_local_login）。未配置 Casdoor 則版面不變。 */}
      {process.env.NEXT_PUBLIC_CASDOOR_ENDPOINT && (
        <>
          <button
            type="button"
            onClick={() => {
              const ep = (process.env.NEXT_PUBLIC_CASDOOR_ENDPOINT ?? "").replace(/\/$/, "");
              const cid = process.env.NEXT_PUBLIC_CASDOOR_CLIENT_ID ?? "smartlock-portal-client";
              const uri = encodeURIComponent(`${window.location.origin}/auth/callback`);
              window.location.href = `${ep}/login/oauth/authorize?client_id=${encodeURIComponent(cid)}&response_type=code&redirect_uri=${uri}&scope=read&state=smartlock`;
            }}
            className="flex h-11 items-center justify-center rounded-full bg-[var(--primary)] text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2"
          >
            以單一登入（SSO）繼續
          </button>
          <div className="flex items-center gap-3 text-[12px] text-[var(--text-primary)] opacity-70">
            <span className="h-px flex-1 bg-[var(--border)]" />
            <span>或使用密碼登入（緊急備援）</span>
            <span className="h-px flex-1 bg-[var(--border)]" />
          </div>
        </>
      )}

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
          className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {/* CR-0177 S2：SSO 已配置時密碼登入為備援 → 次要樣式（未配置則維持主要樣式） */}
      <button
        type="submit"
        disabled={loading || !identifier || !password}
        className={
          process.env.NEXT_PUBLIC_CASDOOR_ENDPOINT
            ? "flex h-11 items-center justify-center rounded-full border border-[var(--border)] text-sm font-medium text-[var(--text-primary)] transition hover:bg-[var(--bg-page)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 disabled:opacity-50"
            : "h-11 rounded-full bg-[var(--primary)] text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 disabled:opacity-50"
        }
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
