"use client";

import { FormEvent, useState } from "react";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";

// 品牌員工帳號申請表單(CR-0114 R5,裁決 4)—— 品牌自家員工於登入頁自助申請,
// POST /tenants/{tid}/staff-applications(公開端點,tenantId 取自 path;前端以
// tenantPath 帶入本部署品牌租戶,與 X-Tenant-ID header 一致)。送出後 pending,
// 待品牌 Admin 於「員工帳號管理」審核並**指派角色**(申請階段不選角色、不建 users)。
//
// 與舊 VendorRegisterForm 的差異:那是廠商/品牌自助「註冊帳號」(vendor_type +
// 公司/統編),本表單只收員工基本資料(姓名/Email/電話/密碼),角色由 Admin 指派。

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

export default function StaffRegisterForm({
  onDone,
  doneActionLabel,
}: {
  /** 成功畫面的次要動作(登入頁 = 切回登入 tab) */
  onDone: () => void;
  doneActionLabel: string;
}) {
  const t = useTranslations("staffApply");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      // tenantPath → /tenants/{tid}/staff-applications;tid 取自 auth.getTenantId()
      // (公開頁未登入 → FALLBACK_TENANT_ID = 本部署品牌租戶)。
      await api.post(tenantPath("/staff-applications"), {
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim() || undefined,
        password,
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
          {t("success")}
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
      <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
        {t("intro")}
      </p>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{t("name")}</span>
        <input value={name} onChange={(e) => setName(e.target.value)} required className={inputCls} />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{t("email")}</span>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className={inputCls}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{t("phone")}</span>
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          pattern="09\d{8}"
          placeholder="09xxxxxxxx"
          className={inputCls}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--text-secondary)]">{t("password")}</span>
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

      <button
        type="submit"
        disabled={loading}
        className="mt-2 h-10 rounded-lg bg-[var(--primary)] text-sm font-semibold text-white disabled:opacity-60"
      >
        {loading ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
