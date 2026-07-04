"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 品牌/經銷/鎖店(派案方)自助申請表單 —— POST /api/v1/vendors/register,
// 送出後 pending 待後台「廠商審核」核准(半自動化導入,對齊 20260702 會議 §三)。
// 從 login/page.tsx 抽出共用:登入頁「註冊」tab 與 landing 一頁式的「申請導入」
// modal 都用這份(CR-0112 後兩處入口共存)。

export type VendorType = "brand" | "locksmith" | "distributor";

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

export default function VendorRegisterForm({
  onDone,
  doneActionLabel,
}: {
  /** 成功畫面的次要動作(登入頁=切回登入 tab;landing modal=關閉) */
  onDone: () => void;
  doneActionLabel: string;
}) {
  const tR = useTranslations("register");
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
          onClick={onDone}
          className="text-sm font-medium text-[var(--primary)] hover:underline"
        >
          {doneActionLabel}
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
