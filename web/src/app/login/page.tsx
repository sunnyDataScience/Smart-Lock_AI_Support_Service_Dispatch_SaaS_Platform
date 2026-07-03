"use client";

import { Building2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, api, getCurrentSession, login, loginVendor } from "@/lib/api";
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
//   - 註冊 tab:廠商自助註冊(原 /register 廠商表單搬入;技師註冊在 /tech-login)。
// /vendor-login 與 /register 保留 redirect 到新入口,不破壞既有連結。

type VendorType = "brand" | "locksmith" | "distributor";
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
          <VendorRegisterForm tR={tR} onToLogin={() => setTab("login")} />
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
    </form>
  );
}

function VendorRegisterForm({
  tR,
  onToLogin,
}: {
  tR: (k: string, vars?: Record<string, string | number>) => string;
  onToLogin: () => void;
}) {
  const [vendorType, setVendorType] = useState<VendorType>("brand");
  const [name, setName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [address, setAddress] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/api/v1/vendors/register", {
        vendor_type: vendorType,
        name: name.trim(),
        company_name: companyName.trim(),
        tax_id: taxId.trim(),
        phone: phone.trim(),
        email: email.trim(),
        password,
        address: address.trim() || undefined,
      });
      setDone(true);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="flex flex-col items-center gap-4">
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-center text-sm text-green-700">
          {tR("successPending")}
        </div>
        <button
          type="button"
          onClick={onToLogin}
          className="text-sm font-medium text-[var(--primary)] hover:underline"
        >
          {tR("toLogin")}
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("vendorType")}</span>
        <select
          value={vendorType}
          onChange={(e) => setVendorType(e.target.value as VendorType)}
          className={inputCls}
        >
          <option value="brand">{tR("vtBrand")}</option>
          <option value="locksmith">{tR("vtLocksmith")}</option>
          <option value="distributor">{tR("vtDistributor")}</option>
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("contactName")}</span>
        <input value={name} onChange={(e) => setName(e.target.value)} required className={inputCls} />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("companyName")}</span>
        <input
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          required
          className={inputCls}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("taxId")}</span>
        <input
          value={taxId}
          onChange={(e) => setTaxId(e.target.value)}
          required
          pattern="\d{8}"
          inputMode="numeric"
          placeholder="12345678"
          className={inputCls}
        />
        <span className="text-xs text-[var(--text-secondary)]">{tR("taxIdHint")}</span>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("phone")}</span>
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          required
          pattern="09\d{8}"
          placeholder="09xxxxxxxx"
          className={inputCls}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("email")}</span>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className={inputCls} />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("password")}</span>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          maxLength={72}
          className={inputCls}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("address")}</span>
        <input value={address} onChange={(e) => setAddress(e.target.value)} className={inputCls} />
      </label>

      <button
        type="submit"
        disabled={loading}
        className="mt-2 h-10 rounded-lg bg-[var(--primary)] text-sm font-semibold text-white disabled:opacity-60"
      >
        {loading ? tR("submitting") : tR("submit")}
      </button>
    </form>
  );
}
