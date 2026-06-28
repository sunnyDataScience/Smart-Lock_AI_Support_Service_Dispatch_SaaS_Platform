"use client";

import { UserPlus } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { LOCK_BRANDS_HINT } from "@/lib/constants/brands";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import BackToHome from "@/components/layout/BackToHome";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type RoleTab = "technician" | "vendor";
type VendorType = "brand" | "locksmith" | "distributor";

export default function RegisterPage() {
  const t = useTranslations("register");
  const [tab, setTab] = useState<RoleTab>("technician");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // technician-only（派工媒合依據：服務地區 + 可服務品牌）
  const [serviceRegions, setServiceRegions] = useState("");
  const [capabilities, setCapabilities] = useState("");
  // vendor-only
  const [vendorType, setVendorType] = useState<VendorType>("brand");
  const [companyName, setCompanyName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [address, setAddress] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // 依註冊身分導向正確登入頁（技師→/tech-login，廠商→/vendor-login；非管理員 /login）
  const loginHref = tab === "vendor" ? "/vendor-login" : "/tech-login";

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (tab === "technician") {
        // 逗號（,/，/、）分隔 → 陣列（與後台 CreateTechnicianModal 同慣例）
        const splitList = (s: string) =>
          s.split(/[,，、]/).map((v) => v.trim()).filter(Boolean);
        const regions = splitList(serviceRegions);
        const caps = splitList(capabilities);
        await api.post("/api/v1/technicians/register", {
          name: name.trim(),
          phone: phone.trim(),
          email: email.trim(),
          password,
          regions,
          capabilities: caps.length > 0 ? caps : undefined,
        });
      } else {
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
      }
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError) setError(`${err.errorCode} (${err.status})：${err.message}`);
      else if (err instanceof Error) setError(err.message);
      else setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  const inputCls =
    "w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)]";

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4 py-8">
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>
      <BackToHome className="absolute left-4 top-4" />

      <div className="w-full max-w-[440px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <UserPlus className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
          <p className="text-sm text-[var(--text-secondary)]">{t("subtitle")}</p>
        </div>

        {done ? (
          <div className="flex flex-col items-center gap-4">
            <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-center text-sm text-green-700">
              {t("successPending")}
            </div>
            <Link href={loginHref} className="text-sm font-medium text-[var(--primary)] hover:underline">
              {t("toLogin")}
            </Link>
          </div>
        ) : (
          <>
            {/* 角色切換 */}
            <div className="mb-5 flex rounded-lg border border-[var(--border)] p-1">
              {(["technician", "vendor"] as RoleTab[]).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setTab(r)}
                  className={`flex-1 rounded-md py-2 text-sm font-semibold ${
                    tab === r
                      ? "bg-[var(--primary)] text-white"
                      : "text-[var(--text-secondary)]"
                  }`}
                >
                  {r === "technician" ? t("tabTechnician") : t("tabVendor")}
                </button>
              ))}
            </div>

            {error && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <form onSubmit={onSubmit} className="flex flex-col gap-3">
              {tab === "vendor" && (
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-[var(--text-secondary)]">{t("vendorType")}</span>
                  <select
                    value={vendorType}
                    onChange={(e) => setVendorType(e.target.value as VendorType)}
                    className={inputCls}
                  >
                    <option value="brand">{t("vtBrand")}</option>
                    <option value="locksmith">{t("vtLocksmith")}</option>
                    <option value="distributor">{t("vtDistributor")}</option>
                  </select>
                </label>
              )}

              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">
                  {tab === "vendor" ? t("contactName") : t("name")}
                </span>
                <input value={name} onChange={(e) => setName(e.target.value)} required className={inputCls} />
              </label>

              {tab === "vendor" && (
                <>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-[var(--text-secondary)]">{t("companyName")}</span>
                    <input
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      required
                      className={inputCls}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-[var(--text-secondary)]">{t("taxId")}</span>
                    <input
                      value={taxId}
                      onChange={(e) => setTaxId(e.target.value)}
                      required
                      pattern="\d{8}"
                      inputMode="numeric"
                      placeholder="12345678"
                      className={inputCls}
                    />
                    <span className="text-xs text-[var(--text-secondary)]">{t("taxIdHint")}</span>
                  </label>
                </>
              )}

              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">{t("phone")}</span>
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
                <span className="text-[var(--text-secondary)]">{t("email")}</span>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className={inputCls} />
              </label>

              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">{t("password")}</span>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} maxLength={72} className={inputCls} />
              </label>

              {tab === "technician" && (
                <>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-[var(--text-secondary)]">{t("serviceRegions")}</span>
                    <input
                      value={serviceRegions}
                      onChange={(e) => setServiceRegions(e.target.value)}
                      required
                      placeholder="台北市、新北市"
                      className={inputCls}
                    />
                    <span className="text-xs text-[var(--text-secondary)]">{t("serviceRegionsHint")}</span>
                  </label>

                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-[var(--text-secondary)]">{t("capabilities")}</span>
                    <input
                      value={capabilities}
                      onChange={(e) => setCapabilities(e.target.value)}
                      placeholder={LOCK_BRANDS_HINT}
                      className={inputCls}
                    />
                    <span className="text-xs text-[var(--text-secondary)]">{t("capabilitiesHint")}</span>
                  </label>
                </>
              )}

              {tab === "vendor" && (
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-[var(--text-secondary)]">{t("address")}</span>
                  <input value={address} onChange={(e) => setAddress(e.target.value)} className={inputCls} />
                </label>
              )}

              <button
                type="submit"
                disabled={loading}
                className="mt-2 rounded-lg bg-[var(--primary)] py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {loading ? t("submitting") : t("submit")}
              </button>
            </form>

            <p className="mt-4 text-center text-sm text-[var(--text-secondary)]">
              {t("haveAccount")}{" "}
              <Link href={loginHref} className="font-medium text-[var(--primary)] hover:underline">
                {t("toLogin")}
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
