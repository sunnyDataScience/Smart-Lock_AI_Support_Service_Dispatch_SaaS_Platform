"use client";

import { FormEvent, useState } from "react";
import { PLATFORM_API_BASE_URL } from "@/lib/appMode";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 品牌/經銷/鎖店「成為品牌」平台申請表單(CR-0114 R2,landing 品牌 CTA 專用)。
// 與舊 VendorRegisterForm 的關鍵差異:申請是**意向書** ——
//   - 不收密碼、不建帳號(核准後由平台人工開站+聯絡;裁決 2)
//   - POST 平台 API /api/v1/platform/brand-applications(非品牌 api 的
//     /vendors/register),資料進平台庫由 platform console 審核
// 用 plain fetch 而非 lib/api client:api client 綁品牌 API base 與品牌 auth
// header,此表單是無登入態的跨服務公開請求。

export type ApplicationType = "brand" | "locksmith" | "distributor";

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

export default function BrandApplyForm({
  onDone,
  doneActionLabel,
}: {
  /** 成功畫面的次要動作(landing modal=關閉) */
  onDone: () => void;
  doneActionLabel: string;
}) {
  const tR = useTranslations("register");
  const tL = useTranslations("landing");
  const [applicationType, setApplicationType] = useState<ApplicationType>("brand");
  const [contactName, setContactName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(
        `${PLATFORM_API_BASE_URL}/api/v1/platform/brand-applications`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            application_type: applicationType,
            company_name: companyName.trim(),
            contact_name: contactName.trim(),
            tax_id: taxId.trim(),
            phone: phone.trim(),
            email: email.trim(),
            address: address.trim() || undefined,
            notes: notes.trim() || undefined,
          }),
        },
      );
      if (!res.ok) {
        // 後端錯誤信封(RFC7807/legacy 皆有 message);409 去重/429 限流訊息直接顯示
        let msg = tL("applyError");
        try {
          const body = (await res.json()) as { message?: string; detail?: string };
          msg = body.message || body.detail || msg;
        } catch {
          // 非 JSON 回應 → 用預設訊息
        }
        setError(msg);
        return;
      }
      setDone(true);
    } catch {
      setError(tL("applyError"));
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="flex flex-col items-center gap-4">
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-center text-sm text-green-700">
          {tL("applySuccess")}
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
          value={applicationType}
          onChange={(e) => setApplicationType(e.target.value as ApplicationType)}
          className={inputCls}
        >
          <option value="brand">{tR("vtBrand")}</option>
          <option value="locksmith">{tR("vtLocksmith")}</option>
          <option value="distributor">{tR("vtDistributor")}</option>
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("contactName")}</span>
        <input
          value={contactName}
          onChange={(e) => setContactName(e.target.value)}
          required
          className={inputCls}
        />
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
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className={inputCls}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tR("address")}</span>
        <input value={address} onChange={(e) => setAddress(e.target.value)} className={inputCls} />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{tL("applyNotes")}</span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          maxLength={1000}
          rows={3}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1"
        />
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
