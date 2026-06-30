"use client";

import { Store } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ApiError, loginVendor } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import BackToHome from "@/components/layout/BackToHome";
import { useTranslations } from "@/components/i18n/LocaleProvider";

export default function VendorLoginPage() {
  const t = useTranslations("vendorLogin");
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginVendor(email.trim(), password);
      // CR-0029：導向廠商專區（原導 /dashboard 會被 rolePolicy 擋住）
      router.replace("/vendor");
    } catch (err) {
      if (err instanceof ApiError) setError(friendlyError(err));
      else if (err instanceof Error) setError(err.message);
      else setError(String(err));
      setLoading(false);
    }
  }

  const inputCls =
    "w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)]";

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4">
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>
      <BackToHome className="absolute left-4 top-4" />

      <div className="w-full max-w-[400px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <Store className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
          <p className="text-sm text-[var(--text-secondary)]">{t("subtitle")}</p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">{t("email")}</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className={inputCls} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">{t("password")}</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className={inputCls} />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="mt-2 rounded-lg bg-[var(--primary)] py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {loading ? t("submitting") : t("submit")}
          </button>

          <div className="flex justify-between text-[13px]">
            <Link href="/forgot-password" className="font-medium text-[var(--primary)] hover:underline">
              {t("forgotPassword")}
            </Link>
            <Link href="/register" className="font-medium text-[var(--primary)] hover:underline">
              {t("registerLink")}
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
