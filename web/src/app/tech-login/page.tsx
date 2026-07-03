"use client";

import { Wrench } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import BackToHome from "@/components/layout/BackToHome";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, loginTechnician } from "@/lib/api";
import { APP_MODE, PEER_PORTAL_URL } from "@/lib/appMode";
import { friendlyError } from "@/lib/apiError";
import { LOCK_BRANDS_HINT } from "@/lib/constants/brands";

// 20260702 會議決議 2:UI 入口濃縮為兩條、登入與註冊同框(仿 Google)。
// 本頁 = 接案方入口「鎖匠師傅」:登入 tab(手機/Email)+ 註冊 tab(原 /register
// 技師表單搬入;註冊後 pending_approval,核准前不可登入 → 顯示待核准訊息)。
// 2026-06-19:已移除 DesktopMobileGuard,桌面/手機皆可直接登入。

type Tab = "login" | "register";

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

export default function TechLoginPage() {
  const t = useTranslations("techPortal.techLogin");
  const tR = useTranslations("register");
  const [tab, setTab] = useState<Tab>("login");

  // ?tab=register 深連結。window.location 讀取,避免 useSearchParams Suspense 需求。
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
            <Wrench className="h-6 w-6 text-white" />
          </div>
          <div className="flex flex-col items-center gap-1">
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {t("brandName")}
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">{t("subtitle")}</p>
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
          <TechLoginForm t={t} />
        ) : (
          <TechRegisterForm tR={tR} onToLogin={() => setTab("login")} />
        )}

        <div className="mt-5 border-t border-[var(--border)] pt-4 text-center">
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

function TechRegisterForm({
  tR,
  onToLogin,
}: {
  tR: (k: string, vars?: Record<string, string | number>) => string;
  onToLogin: () => void;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [serviceRegions, setServiceRegions] = useState("");
  const [capabilities, setCapabilities] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      // 逗號(,/，/、)分隔 → 陣列(與後台 CreateTechnicianModal 同慣例)
      const splitList = (s: string) =>
        s.split(/[,，、]/).map((v) => v.trim()).filter(Boolean);
      const caps = splitList(capabilities);
      await api.post("/api/v1/technicians/register", {
        name: name.trim(),
        phone: phone.trim(),
        email: email.trim(),
        password,
        regions: splitList(serviceRegions),
        capabilities: caps.length > 0 ? caps : undefined,
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
        <span className="text-[var(--text-secondary)]">{tR("name")}</span>
        <input value={name} onChange={(e) => setName(e.target.value)} required className={inputCls} />
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
        <span className="text-[var(--text-secondary)]">{tR("serviceRegions")}</span>
        <input
          value={serviceRegions}
          onChange={(e) => setServiceRegions(e.target.value)}
          required
          placeholder="台北市、新北市"
          className={inputCls}
        />
        <span className="text-xs text-[var(--text-secondary)]">{tR("serviceRegionsHint")}</span>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("capabilities")}</span>
        <input
          value={capabilities}
          onChange={(e) => setCapabilities(e.target.value)}
          placeholder={LOCK_BRANDS_HINT}
          className={inputCls}
        />
        <span className="text-xs text-[var(--text-secondary)]">{tR("capabilitiesHint")}</span>
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
