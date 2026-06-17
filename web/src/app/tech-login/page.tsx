"use client";

import { Wrench } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import DesktopMobileGuard from "@/components/tech/DesktopMobileGuard";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, loginTechnician } from "@/lib/api";

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
      router.replace("/pool");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
      setLoading(false);
    }
  }

  return (
    <DesktopMobileGuard>
    <div
      className="flex min-h-screen w-full justify-center"
      style={{
        background:
          "linear-gradient(180deg, #2563EB 0%, #1E40AF 60%, #F8FAFC 60%)",
      }}
    >
      <div className="flex min-h-screen w-full max-w-[480px] flex-col bg-transparent px-6 pt-[env(safe-area-inset-top,0)]">
        {/* brand_header_mobile */}
        <header className="mt-12 flex flex-col items-center gap-2 text-white">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/20 backdrop-blur">
            <Wrench className="h-7 w-7 text-white" />
          </div>
          <h1 className="mt-1 text-[20px] font-bold">{t("brandName")}</h1>
          <p className="text-[14px] opacity-90">{t("subtitle")}</p>
        </header>

        {/* tech_login_form */}
        <main className="mt-10 flex-1">
          <form
            onSubmit={onSubmit}
            className="flex flex-col gap-4 rounded-2xl bg-white p-6 shadow-2xl"
          >
            <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
              {t("title")}
            </h2>

            <label className="flex flex-col gap-[6px]">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                {t("identifierLabel")}
              </span>
              <input
                type="text"
                inputMode="email"
                autoComplete="username"
                required
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                className="h-12 rounded-lg border border-[var(--border)] px-3 text-[15px] focus:border-[var(--primary)] focus:outline-none"
                placeholder={t("identifierPlaceholder")}
              />
            </label>

            <label className="flex flex-col gap-[6px]">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                {t("passwordLabel")}
              </span>
              <input
                type="password"
                autoComplete="current-password"
                required
                minLength={4}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-12 rounded-lg border border-[var(--border)] px-3 text-[15px] focus:border-[var(--primary)] focus:outline-none"
                placeholder={t("passwordPlaceholder")}
              />
            </label>

            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !identifier || !password}
              className="mt-2 h-12 rounded-lg bg-[var(--primary)] text-[15px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-60"
            >
              {loading ? t("submitting") : t("submit")}
            </button>

            <div className="mt-2 flex items-center justify-between text-[12px]">
              {/* CR-0025：自助忘記密碼上線後改回可點連結 → /forgot-password（email 重設）。 */}
              <Link href="/forgot-password" className="text-[var(--primary)] hover:underline">
                {t("forgotPassword")}
              </Link>
              <Link href="/login" className="text-[var(--primary)] hover:underline">
                {t("adminLink")}
              </Link>
            </div>
          </form>
        </main>

        {/* mobile_footer */}
        <footer className="my-6 text-center text-[11px] text-[var(--text-disabled)]">
          {t("footerVersion")}
        </footer>
      </div>
    </div>
    </DesktopMobileGuard>
  );
}
