"use client";

import { Building2, Check, ArrowLeft, Copy, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { PLATFORM_API_BASE_URL } from "@/lib/appMode";

// 品牌/經銷/鎖店「申請導入 SmartLock 平台」公開頁(CR-0114 延伸)。
// 原為 landing(:3002)的 modal，改為 platform 站(:3003)獨立頁，landing 品牌 CTA
// 以絕對 URL 跳轉過來（業主 2026-07-05 要求）。申請=意向書:不收密碼、不建帳號，
// 核准後平台人工開站+聯絡（CR-0114 裁決 2）。POST 平台 API（plain fetch，無登入態）。
// 硬編繁中（對齊 platform console 慣例）。欄位含業界補充（網站/涵蓋地區/規模/品牌/來源）。
//
// 2026-07-18 免 email 自助方案（UAT R2 W3-6 業主裁決,SMTP 暫緩）:
//   - 送出成功畫面顯示「申請編號」（submit 回應 id）+ 複製按鈕，提示保存供日後查詢。
//   - 同頁新增「查詢申請進度」模式（?mode=lookup 可直達）:憑 Email + 申請編號
//     POST /platform/brand-applications:lookup（公開端點,兩者同時精確匹配才回資料,
//     不匹配一律 404 防列舉）→ 顯示審核中/已核准/已駁回（含駁回理由）結果卡。

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

// 申請編號 = 後端 UUID;查詢前先做格式檢查,避免打出必然 404/422 的請求。
const UUID_RE =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

/** 進度查詢回應(:lookup 契約;review_notes 僅 rejected 時回傳) */
type LookupResult = {
  status: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  review_notes?: string | null;
};

// 查詢結果狀態 → 顯示樣式與說明(未知狀態在解析時擋下,顯示 LOOKUP_PARSE_ERROR)
const STATUS_VIEW: Record<string, { label: string; cls: string; desc: string }> = {
  pending: {
    label: "審核中",
    cls: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)]",
    desc: "您的申請正在審核中，審核完成後平台將主動與您聯絡。",
  },
  approved: {
    label: "已核准",
    cls: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)]",
    desc: "您的申請已核准，平台將與您聯繫開通事宜。",
  },
  rejected: {
    label: "已駁回",
    cls: "bg-[var(--badge-danger-bg)] text-[var(--badge-danger-fg)]",
    desc: "很抱歉，本次申請未通過審核。",
  },
};

// 查詢結果解讀失敗時的顯性錯誤訊息（UAT R3-1:原 fallback「已受理」會把
// 駁回/未知狀態誤導成受理中,改為明講解讀失敗請重試）
const LOOKUP_PARSE_ERROR = "無法解讀查詢結果，請稍後再試。";

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

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
  // 送出成功後的申請編號(defensive:後端回 {data:{id,status}} 信封,取不到就不顯示編號區塊)
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  // 頁面模式:apply=申請表單(含成功畫面)/ lookup=查詢申請進度
  const [mode, setMode] = useState<"apply" | "lookup">("apply");
  const [lookupEmail, setLookupEmail] = useState("");
  const [lookupId, setLookupId] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupFieldErrors, setLookupFieldErrors] = useState<Record<string, string>>({});
  const [lookupResult, setLookupResult] = useState<LookupResult | null>(null);

  // ?mode=lookup 直達查詢(landing 入口用)。避免 useSearchParams 需 Suspense,
  // 純 client 頁直接讀 window.location。
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mode") === "lookup") setMode("lookup");
  }, []);

  function goBack() {
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else window.location.assign("/platform/login");
  }

  async function copyApplicationId() {
    if (!applicationId) return;
    try {
      await navigator.clipboard.writeText(applicationId);
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 2000);
    } catch {
      setCopyState("failed");
    }
  }

  /** 切到查詢模式;剛送出成功時帶入 Email 與申請編號方便直接查 */
  function openLookup(prefill: boolean) {
    if (prefill) {
      setLookupEmail(email.trim());
      setLookupId(applicationId ?? "");
    }
    setLookupResult(null);
    setLookupError(null);
    setLookupFieldErrors({});
    setMode("lookup");
  }

  async function onLookupSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    const em = lookupEmail.trim();
    if (!em) errs.lookup_email = "請輸入申請時填寫的 Email";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em)) errs.lookup_email = "Email 格式不正確";
    const id = lookupId.trim();
    if (!id) errs.lookup_id = "請輸入申請編號";
    else if (!UUID_RE.test(id)) errs.lookup_id = "申請編號格式不正確（送出申請時顯示的編號）";
    setLookupFieldErrors(errs);
    if (Object.keys(errs).length > 0) {
      setLookupError(null);
      setLookupResult(null);
      return;
    }
    setLookupError(null);
    setLookupResult(null);
    setLookupLoading(true);
    try {
      const res = await fetch(
        `${PLATFORM_API_BASE_URL}/api/v1/platform/brand-applications:lookup`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: em, application_id: id }),
        },
      );
      if (!res.ok) {
        // 契約:不匹配一律 404 generic(防列舉),不細分是哪個欄位錯。
        if (res.status === 404) {
          setLookupError("查無資料，請確認 Email 與申請編號是否正確。");
        } else if (res.status === 429) {
          setLookupError("查詢過於頻繁，請稍後再試。");
        } else {
          setLookupError("查詢失敗，請稍後再試。");
        }
        return;
      }
      // 契約:200 回信封 {data:{status,submitted_at,reviewed_at,review_notes}}
      // （UAT R3-1:原本把整個信封當扁平物件塞進 state → status 恆 undefined
      // 永遠走 fallback「已受理」）。data 缺漏或 status 非已知值 → 顯性錯誤,
      // 不再默默顯示誤導性的受理中文案。
      let body: { data?: LookupResult | null } | null = null;
      try {
        body = await res.json();
      } catch {
        /* 非 JSON 回應 → 走下方解讀失敗訊息 */
      }
      const data = body?.data;
      if (data && typeof data.status === "string" && STATUS_VIEW[data.status]) {
        setLookupResult(data);
      } else {
        setLookupError(LOOKUP_PARSE_ERROR);
      }
    } catch {
      setLookupError("查詢失敗，請確認網路後再試。");
    } finally {
      setLookupLoading(false);
    }
  }

  // 欄位有錯時輸入框標紅。用 important modifier（Tailwind v4 後綴 !）蓋掉 inputCls
  // 的預設 border 色（兩個同名 utility 並存時勝負取決於產出 CSS 順序，不加 ! 不保證紅框生效）。
  const errCls = (key: string) =>
    fieldErrors[key]
      ? " border-[var(--status-danger)]! focus:border-[var(--status-danger)]!"
      : "";

  const lookupErrCls = (key: string) =>
    lookupFieldErrors[key]
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
      // 201 回信封 {data:{id,status}};data.id=申請編號,供免 email 查詢進度
      // （UAT R3-1:原本讀頂層 created?.id 恆 undefined → 編號區塊被 defensive
      // 隱藏,申請人拿不到編號）。防禦性讀取:解析失敗不擋成功畫面,只是不顯示
      // 編號區塊。
      let created: { data?: { id?: unknown } | null } | null = null;
      try {
        created = await res.json();
      } catch {
        /* 非 JSON 回應 → 略過編號顯示 */
      }
      const createdId = created?.data?.id;
      setApplicationId(
        typeof createdId === "string" && createdId ? createdId : null,
      );
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
          {mode === "lookup" ? (
            <>
              <h1 className="text-xl font-bold text-[var(--text-primary)]">查詢申請進度</h1>
              <p className="max-w-[440px] text-sm text-[var(--text-secondary)]">
                輸入申請時填寫的 Email 與送出後取得的申請編號，即可查詢審核進度。
              </p>
            </>
          ) : (
            <>
              <h1 className="text-xl font-bold text-[var(--text-primary)]">申請導入 SmartLock 平台</h1>
              <p className="max-w-[440px] text-sm text-[var(--text-secondary)]">
                品牌商、經銷商、鎖店皆可申請。送出基本資料後，平台將審核並與您聯絡協助開站與教育訓練。
              </p>
              {!done && (
                <button
                  type="button"
                  onClick={() => openLookup(false)}
                  className="mt-1 inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--primary)] underline-offset-4 transition hover:underline"
                >
                  <Search className="h-3.5 w-3.5" aria-hidden />
                  已送出申請？查詢審核進度
                </button>
              )}
            </>
          )}
        </div>

        {mode === "lookup" ? (
          <div className="flex flex-col gap-4">
            <form onSubmit={onLookupSubmit} noValidate className="flex flex-col gap-4">
              {lookupError && (
                <div
                  role="alert"
                  className="rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-3 py-2 text-sm text-[var(--badge-danger-fg)]"
                >
                  {lookupError}
                </div>
              )}
              <Field label="Email" required hint="申請時填寫的聯絡 Email" error={lookupFieldErrors.lookup_email}>
                <input
                  type="email"
                  value={lookupEmail}
                  onChange={(e) => setLookupEmail(e.target.value)}
                  aria-invalid={!!lookupFieldErrors.lookup_email || undefined}
                  className={inputCls + lookupErrCls("lookup_email")}
                />
              </Field>
              <Field
                label="申請編號"
                required
                hint="申請送出成功時顯示的編號"
                error={lookupFieldErrors.lookup_id}
              >
                <input
                  value={lookupId}
                  onChange={(e) => setLookupId(e.target.value)}
                  placeholder="例：123e4567-e89b-12d3-a456-426614174000"
                  aria-invalid={!!lookupFieldErrors.lookup_id || undefined}
                  className={inputCls + lookupErrCls("lookup_id")}
                />
              </Field>
              <button
                type="submit"
                disabled={lookupLoading}
                className="h-11 rounded-lg bg-[var(--primary)] text-sm font-semibold text-white transition hover:bg-[var(--primary-hover)] disabled:opacity-60"
              >
                {lookupLoading ? "查詢中…" : "查詢進度"}
              </button>
            </form>

            {lookupResult && (() => {
              // set 時已驗證 status ∈ STATUS_VIEW;此為防禦保底(未知狀態不渲染
              // 誤導卡,由 LOOKUP_PARSE_ERROR 訊息負責告知)
              const view = STATUS_VIEW[lookupResult.status];
              if (!view) return null;
              return (
                <div
                  role="status"
                  className="rounded-xl border border-[var(--border)] bg-[var(--bg-page)] p-4"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${view.cls}`}
                    >
                      {view.label}
                    </span>
                    <span className="text-[12px] text-[var(--text-disabled)]">
                      送出於 {formatDateTime(lookupResult.submitted_at)}
                      {lookupResult.reviewed_at
                        ? `・審核於 ${formatDateTime(lookupResult.reviewed_at)}`
                        : ""}
                    </span>
                  </div>
                  <p className="mt-2.5 text-sm leading-relaxed text-[var(--text-primary)]">
                    {view.desc}
                  </p>
                  {lookupResult.status === "rejected" && lookupResult.review_notes && (
                    <div className="mt-2.5 rounded-lg bg-[var(--bg-surface)] px-3 py-2">
                      <p className="text-[12px] font-medium text-[var(--text-secondary)]">駁回理由</p>
                      <p className="mt-0.5 whitespace-pre-wrap text-sm text-[var(--text-primary)]">
                        {lookupResult.review_notes}
                      </p>
                    </div>
                  )}
                </div>
              );
            })()}

            <button
              type="button"
              onClick={() => setMode("apply")}
              className="inline-flex items-center justify-center gap-1 text-[13px] font-medium text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
              返回申請表單
            </button>
          </div>
        ) : done ? (
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--badge-success-bg)]">
              <Check className="h-7 w-7 text-[var(--badge-success-fg)]" />
            </div>
            <p className="max-w-[400px] text-center text-sm text-[var(--text-primary)]">
              申請已送出！平台審核後將盡快與您聯絡。感謝您有意加入 SmartLock。
            </p>
            {applicationId && (
              <div className="w-full max-w-[440px] rounded-xl border border-[var(--border)] bg-[var(--bg-page)] p-4 text-left">
                <p className="text-[13px] font-medium text-[var(--text-secondary)]">申請編號</p>
                <div className="mt-1.5 flex items-center gap-2">
                  <code className="min-w-0 flex-1 break-all rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-[13px] text-[var(--text-primary)]">
                    {applicationId}
                  </code>
                  <button
                    type="button"
                    onClick={copyApplicationId}
                    className="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg border border-[var(--border)] px-2.5 text-[12px] font-medium text-[var(--text-secondary)] transition hover:border-[var(--border-focus)] hover:text-[var(--text-primary)]"
                  >
                    {copyState === "copied" ? (
                      <Check className="h-3.5 w-3.5" aria-hidden />
                    ) : (
                      <Copy className="h-3.5 w-3.5" aria-hidden />
                    )}
                    {copyState === "copied" ? "已複製" : "複製"}
                  </button>
                </div>
                {copyState === "failed" && (
                  <p className="mt-1.5 text-xs text-[var(--status-danger)]">
                    複製失敗，請手動選取編號複製。
                  </p>
                )}
                <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
                  請保存此編號：之後可憑 Email＋申請編號隨時查詢審核進度。
                </p>
              </div>
            )}
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={() => openLookup(true)}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--text-primary)] transition hover:border-[var(--border-focus)]"
              >
                <Search className="h-4 w-4" aria-hidden />
                查詢申請進度
              </button>
              <button
                type="button"
                onClick={goBack}
                className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]"
              >
                返回上一頁
              </button>
            </div>
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
