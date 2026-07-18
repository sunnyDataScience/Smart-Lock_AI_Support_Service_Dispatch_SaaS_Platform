"use client";

import { Building2, Check, ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { PLATFORM_API_BASE_URL } from "@/lib/appMode";

// 品牌/經銷/鎖店「申請導入 SmartLock 平台」公開頁(CR-0114 延伸)。
// 原為 landing(:3002)的 modal，改為 platform 站(:3003)獨立頁，landing 品牌 CTA
// 以絕對 URL 跳轉過來（業主 2026-07-05 要求）。申請=意向書:不收密碼、不建帳號，
// 核准後平台人工開站+聯絡（CR-0114 裁決 2）。POST 平台 API（plain fetch，無登入態）。
// 硬編繁中（對齊 platform console 慣例）。欄位含業界補充（網站/涵蓋地區/規模/品牌/來源）。

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

type AppType = "brand" | "locksmith" | "distributor";

const VOLUME_OPTIONS = ["未定", "50 以下", "50–200", "200–500", "500 以上"];
const REFERRAL_OPTIONS = ["Google 搜尋", "朋友介紹", "社群媒體", "業務接洽", "展會/活動", "其他"];

// 422 field 級 details（body.email 等）→ 對應欄位下方的繁中訊息。
// key = API snake_case 欄位名（details[].field 去掉 "body." 前綴）；
// 訊息對齊後端 BrandApplicationBody 的驗證規則，查無對應時用泛訊息。
const FIELD_MESSAGES: Record<string, string> = {
  application_type: "申請類型無效，請重新選擇",
  company_name: "請輸入公司名稱（150 字內）",
  contact_name: "請輸入聯絡人姓名（150 字內）",
  tax_id: "統一編號需為 8 碼數字",
  phone: "聯絡電話需為 09 開頭共 10 碼數字",
  email: "Email 格式不正確",
  address: "公司地址過長（500 字內）",
  website: "公司網站網址過長（255 字內）",
  coverage_regions: "服務涵蓋地區過長（500 字內）",
  store_count: "門市／據點數需為 0–100000 的整數",
  expected_monthly_orders: "預估月工單量格式不正確",
  main_brands: "主營品牌／產品過長（500 字內）",
  referral_source: "來源選項格式不正確",
  notes: "備註過長（1000 字內）",
};

export default function BrandApplyPage() {
  const router = useRouter();
  const [applicationType, setApplicationType] = useState<AppType>("brand");
  const [companyName, setCompanyName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [website, setWebsite] = useState("");
  const [contactName, setContactName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [coverageRegions, setCoverageRegions] = useState("");
  const [storeCount, setStoreCount] = useState("");
  const [expectedMonthlyOrders, setExpectedMonthlyOrders] = useState("");
  const [mainBrands, setMainBrands] = useState("");
  const [referralSource, setReferralSource] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [done, setDone] = useState(false);

  function goBack() {
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else window.location.assign("/platform/login");
  }

  // 欄位有錯時輸入框標紅。用 important modifier（Tailwind v4 後綴 !）蓋掉 inputCls
  // 的預設 border 色（兩個同名 utility 並存時勝負取決於產出 CSS 順序，不加 ! 不保證紅框生效）。
  const errCls = (key: string) =>
    fieldErrors[key]
      ? " border-[var(--status-danger)]! focus:border-[var(--status-danger)]!"
      : "";

  // submit 時全欄檢查一次（取代原生氣泡驗證；規則對齊後端 BrandApplicationBody）
  function validateAll(): Record<string, string> {
    const errs: Record<string, string> = {};
    if (!companyName.trim()) errs.company_name = "請輸入公司名稱";
    if (!/^\d{8}$/.test(taxId.trim())) errs.tax_id = "統一編號需為 8 碼數字";
    if (!contactName.trim()) errs.contact_name = "請輸入聯絡人姓名";
    if (!/^09\d{8}$/.test(phone.trim())) errs.phone = "聯絡電話需為 09 開頭共 10 碼數字";
    const em = email.trim();
    if (!em) errs.email = "請輸入 Email";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em)) errs.email = "Email 格式不正確";
    return errs;
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const clientErrs = validateAll();
    setFieldErrors(clientErrs);
    if (Object.keys(clientErrs).length > 0) {
      setError("輸入的資料有誤，請檢查標紅欄位後再送出。");
      return;
    }
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
            website: website.trim() || undefined,
            coverage_regions: coverageRegions.trim() || undefined,
            store_count: storeCount.trim() ? Number(storeCount) : undefined,
            expected_monthly_orders:
              expectedMonthlyOrders && expectedMonthlyOrders !== "未定"
                ? expectedMonthlyOrders
                : undefined,
            main_brands: mainBrands.trim() || undefined,
            referral_source: referralSource.trim() || undefined,
            notes: notes.trim() || undefined,
          }),
        },
      );
      if (!res.ok) {
        let body: {
          message?: string;
          detail?: string;
          details?: { field?: string; issue?: string }[];
        } | null = null;
        try {
          body = await res.json();
        } catch {
          /* 非 JSON 回應 → 走下方泛訊息 */
        }
        // 422 帶 field 級 details（RFC7807 superset，field = "body.email" 等）
        // → 解析後 inline 顯示在對應欄位下方，不再丟英文泛訊息。
        if (res.status === 422 && Array.isArray(body?.details) && body.details.length > 0) {
          const serverErrs: Record<string, string> = {};
          body.details.forEach((d) => {
            const key = (d.field ?? "").replace(/^body\./, "");
            if (key) serverErrs[key] = FIELD_MESSAGES[key] ?? "此欄位格式不正確，請修正後再送出";
          });
          setFieldErrors(serverErrs);
          setError("輸入的資料有誤，請檢查標紅欄位後再送出。");
          return;
        }
        // 後端 message 已是繁中（業務刻意寫給使用者）才直接顯示；
        // 英文 message 不露出，改依狀態碼給繁中泛訊息（對齊 apiError.ts 慣例）。
        const backendMsg = body?.message || body?.detail;
        if (backendMsg && /[一-鿿]/.test(backendMsg)) setError(backendMsg);
        else if (res.status === 429) setError("申請送出過於頻繁，請稍後再試");
        else setError("送出失敗，請稍後再試");
        return;
      }
      setDone(true);
    } catch {
      setError("送出失敗，請確認網路後再試");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-start justify-center bg-[var(--bg-page)] px-4 py-8 md:items-center">
      <button
        type="button"
        onClick={goBack}
        className="absolute left-4 top-4 inline-flex items-center gap-1 text-[13px] font-medium text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
      >
        <ArrowLeft className="h-4 w-4" />
        返回上一頁
      </button>

      <div className="w-full max-w-[600px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-sm md:p-8">
        <div className="mb-5 flex flex-col items-center gap-2 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <Building2 className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-[var(--text-primary)]">申請導入 SmartLock 平台</h1>
          <p className="max-w-[440px] text-sm text-[var(--text-secondary)]">
            品牌商、經銷商、鎖店皆可申請。送出基本資料後，平台將審核並與您聯絡協助開站與教育訓練。
          </p>
        </div>

        {done ? (
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--badge-success-bg)]">
              <Check className="h-7 w-7 text-[var(--badge-success-fg)]" />
            </div>
            <p className="max-w-[400px] text-center text-sm text-[var(--text-primary)]">
              申請已送出！平台審核後將盡快與您聯絡。感謝您有意加入 SmartLock。
            </p>
            <button
              type="button"
              onClick={goBack}
              className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]"
            >
              返回上一頁
            </button>
          </div>
        ) : (
          // noValidate：改用 submit 時全欄 inline 驗證，不依賴原生氣泡（一次只提示一欄且樣式不可控）
          <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
            {error && (
              <div
                role="alert"
                className="rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-3 py-2 text-sm text-[var(--badge-danger-fg)]"
              >
                {error}
              </div>
            )}

            <Section title="申請類型">
              <Field label="您的身分" required error={fieldErrors.application_type}>
                <select
                  value={applicationType}
                  onChange={(e) => setApplicationType(e.target.value as AppType)}
                  className={inputCls + errCls("application_type")}
                >
                  <option value="brand">品牌商</option>
                  <option value="locksmith">鎖店</option>
                  <option value="distributor">經銷商</option>
                </select>
              </Field>
            </Section>

            <Section title="公司資料">
              <Field label="公司名稱" required error={fieldErrors.company_name}>
                <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} aria-invalid={!!fieldErrors.company_name || undefined} className={inputCls + errCls("company_name")} />
              </Field>
              <Field label="統一編號" required hint="8 碼數字，用於開立發票與對帳" error={fieldErrors.tax_id}>
                <input value={taxId} onChange={(e) => setTaxId(e.target.value)} inputMode="numeric" placeholder="12345678" aria-invalid={!!fieldErrors.tax_id || undefined} className={inputCls + errCls("tax_id")} />
              </Field>
              <Field label="公司網站" error={fieldErrors.website}>
                <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://" aria-invalid={!!fieldErrors.website || undefined} className={inputCls + errCls("website")} />
              </Field>
            </Section>

            <Section title="聯絡資訊">
              <Field label="聯絡人" required error={fieldErrors.contact_name}>
                <input value={contactName} onChange={(e) => setContactName(e.target.value)} aria-invalid={!!fieldErrors.contact_name || undefined} className={inputCls + errCls("contact_name")} />
              </Field>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="聯絡電話" required error={fieldErrors.phone}>
                  <input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="numeric" placeholder="09xxxxxxxx" aria-invalid={!!fieldErrors.phone || undefined} className={inputCls + errCls("phone")} />
                </Field>
                <Field label="Email" required error={fieldErrors.email}>
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} aria-invalid={!!fieldErrors.email || undefined} className={inputCls + errCls("email")} />
                </Field>
              </div>
              <Field label="公司地址" error={fieldErrors.address}>
                <input value={address} onChange={(e) => setAddress(e.target.value)} aria-invalid={!!fieldErrors.address || undefined} className={inputCls + errCls("address")} />
              </Field>
            </Section>

            <Section title="營運概況" subtitle="協助平台評估與媒合（選填）">
              <Field label="服務涵蓋地區" hint="逗號分隔，例：台北市、新北市（派工媒合用）" error={fieldErrors.coverage_regions}>
                <input value={coverageRegions} onChange={(e) => setCoverageRegions(e.target.value)} placeholder="台北市、新北市" aria-invalid={!!fieldErrors.coverage_regions || undefined} className={inputCls + errCls("coverage_regions")} />
              </Field>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="門市 / 據點數" error={fieldErrors.store_count}>
                  <input type="number" min={0} value={storeCount} onChange={(e) => setStoreCount(e.target.value)} aria-invalid={!!fieldErrors.store_count || undefined} className={inputCls + errCls("store_count")} />
                </Field>
                <Field label="預估月工單量" error={fieldErrors.expected_monthly_orders}>
                  <select value={expectedMonthlyOrders} onChange={(e) => setExpectedMonthlyOrders(e.target.value)} className={inputCls + errCls("expected_monthly_orders")}>
                    <option value="">請選擇</option>
                    {VOLUME_OPTIONS.map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field label="主營品牌 / 產品" hint="例：Yale、Dormakaba、Kaadas" error={fieldErrors.main_brands}>
                <input value={mainBrands} onChange={(e) => setMainBrands(e.target.value)} aria-invalid={!!fieldErrors.main_brands || undefined} className={inputCls + errCls("main_brands")} />
              </Field>
              <Field label="如何得知 SmartLock" error={fieldErrors.referral_source}>
                <select value={referralSource} onChange={(e) => setReferralSource(e.target.value)} className={inputCls + errCls("referral_source")}>
                  <option value="">請選擇</option>
                  {REFERRAL_OPTIONS.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              </Field>
            </Section>

            <Section title="需求說明">
              <Field label="備註" error={fieldErrors.notes}>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  maxLength={1000}
                  rows={3}
                  aria-invalid={!!fieldErrors.notes || undefined}
                  className={`${inputCls + errCls("notes")} h-auto resize-y py-2`}
                  placeholder="想導入的情境、期待的協助等（選填）"
                />
              </Field>
            </Section>

            <button
              type="submit"
              disabled={loading}
              className="h-11 rounded-lg bg-[var(--primary)] text-sm font-semibold text-white transition hover:bg-[var(--primary-hover)] disabled:opacity-60"
            >
              {loading ? "送出中…" : "送出申請"}
            </button>
            <p className="text-center text-xs text-[var(--text-disabled)]">
              送出即表示同意平台就本申請與您聯絡。申請不會建立任何帳號。
            </p>
          </form>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline gap-2 border-b border-[var(--border)] pb-1.5">
        <h2 className="text-[13px] font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
          {title}
        </h2>
        {subtitle && <span className="text-[11px] text-[var(--text-disabled)]">{subtitle}</span>}
      </div>
      {children}
    </section>
  );
}

function Field({
  label,
  required,
  hint,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  /** 欄位級驗證錯誤（client 檢查或 API 422 details）→ 欄位下方紅字 */
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-[13px] font-medium text-[var(--text-primary)]">
        {label}
        {required ? <span className="text-[var(--status-danger)]"> *</span> : <span className="text-[var(--text-disabled)]">（選填）</span>}
      </span>
      {children}
      {error && (
        <span role="alert" className="text-xs text-[var(--status-danger)]">
          {error}
        </span>
      )}
      {hint && !error && <span className="text-xs text-[var(--text-secondary)]">{hint}</span>}
    </label>
  );
}
