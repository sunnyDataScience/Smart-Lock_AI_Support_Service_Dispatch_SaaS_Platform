"use client";

import { Wrench, Check, ChevronLeft, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import BackToHome from "@/components/layout/BackToHome";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { APP_MODE, PEER_PORTAL_URL } from "@/lib/appMode";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

// CR-0115 §8：師傅註冊擴充為 KYC 等級 + 登入/註冊分離。
// 本頁 = 獨立多步驟申請表單（步驟 1 基本 / 2 專業 / 3 撥款與聯絡 / 4 確認）。
// 硬編繁中（對齊 admin/staff 慣例；i18n 列後續輪）。文件上傳步驟待兩階段
// token 上傳後端就緒後再加（本輪先做文字欄位 Tier 1 + Tier 2）。
// 「最小必填」（§8-4）於此表單層強制：姓名/手機/Email/密碼/服務地區/年資/
// 緊急聯絡人+電話/同意條款；敏感 PII 與撥款帳戶選填（核准前可補件）。

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 disabled:opacity-50";

const STEPS = ["基本資料", "專業資格", "撥款與聯絡", "確認送出"] as const;

interface FormState {
  name: string;
  phone: string;
  email: string;
  password: string;
  serviceRegions: string;
  vehicleType: string;
  yearsExperience: string;
  capabilities: string;
  availabilityNote: string;
  bio: string;
  certifications: string;
  emergencyContactName: string;
  emergencyContactPhone: string;
  nationalId: string;
  birthDate: string;
  address: string;
  bankCode: string;
  bankAccount: string;
  taxId: string;
  consent: boolean;
}

const EMPTY: FormState = {
  name: "", phone: "", email: "", password: "", serviceRegions: "",
  vehicleType: "", yearsExperience: "", capabilities: "", availabilityNote: "",
  bio: "", certifications: "", emergencyContactName: "", emergencyContactPhone: "",
  nationalId: "", birthDate: "", address: "", bankCode: "", bankAccount: "",
  taxId: "", consent: false,
};

const splitList = (s: string) =>
  s.split(/[,，、]/).map((v) => v.trim()).filter(Boolean);

const loginHref =
  APP_MODE === "tech" && PEER_PORTAL_URL ? `${PEER_PORTAL_URL}/tech-login` : "/tech-login";

export default function TechRegisterPage() {
  const [step, setStep] = useState(0);
  const [f, setF] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setF((prev) => ({ ...prev, [k]: v }));

  // 各步驟驗證（回傳錯誤 map；空 = 通過）
  function validateStep(s: number): Record<string, string> {
    const e: Record<string, string> = {};
    if (s === 0) {
      if (!f.name.trim()) e.name = "此欄為必填";
      if (!/^09\d{8}$/.test(f.phone)) e.phone = "手機格式：09 開頭共 10 碼";
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email)) e.email = "請輸入正確 Email";
      if (f.password.length < 8) e.password = "密碼至少 8 碼";
      if (splitList(f.serviceRegions).length === 0) e.serviceRegions = "請至少填一個服務地區";
    }
    if (s === 1) {
      const yr = Number(f.yearsExperience);
      if (f.yearsExperience === "" || Number.isNaN(yr) || yr < 0 || yr > 80)
        e.yearsExperience = "請填 0–80 的年資";
    }
    if (s === 2) {
      if (!f.emergencyContactName.trim()) e.emergencyContactName = "此欄為必填";
      if (!/^09\d{8}$/.test(f.emergencyContactPhone))
        e.emergencyContactPhone = "手機格式：09 開頭共 10 碼";
      // 敏感 PII 選填，但填了要合格式
      if (f.nationalId && !/^[A-Z][12]\d{8}$/.test(f.nationalId))
        e.nationalId = "身分證格式：英文字母 + 9 碼數字";
      if (f.bankCode && !/^\d{3,4}$/.test(f.bankCode)) e.bankCode = "銀行代碼 3–4 碼數字";
      if (f.bankAccount && !/^\d{6,16}$/.test(f.bankAccount)) e.bankAccount = "帳號 6–16 碼數字";
      if (f.taxId && !/^\d{8}$/.test(f.taxId)) e.taxId = "統編 8 碼數字";
      if (!f.consent) e.consent = "請勾選同意條款";
    }
    return e;
  }

  function next() {
    const e = validateStep(step);
    setErrors(e);
    if (Object.keys(e).length === 0) setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }
  function prev() {
    setErrors({});
    setStep((s) => Math.max(s - 1, 0));
  }

  // 送出邏輯（非 form submit handler）—— 只由「送出申請」按鈕的 onClick 觸發。
  // 表單本身完全不靠 submit 語意（form onSubmit 一律 preventDefault），杜絕在
  // 中間步驟按 Enter / 按鈕型別誤觸而在確認前就送出的問題。
  async function doSubmit() {
    if (loading) return;
    // 送出前把三個驗證步驟全跑一遍（避免直接跳到確認漏驗）
    const all = { ...validateStep(0), ...validateStep(1), ...validateStep(2) };
    if (Object.keys(all).length > 0) {
      setErrors(all);
      // 跳回第一個有錯的步驟
      if (validateStep(0) && Object.keys(validateStep(0)).length) setStep(0);
      else if (Object.keys(validateStep(1)).length) setStep(1);
      else setStep(2);
      return;
    }
    setLoading(true);
    setSubmitError(null);
    try {
      const certs = splitList(f.certifications).map((c) => ({ cert_name: c }));
      await api.post("/api/v1/technicians/register", {
        name: f.name.trim(),
        phone: f.phone.trim(),
        email: f.email.trim(),
        password: f.password,
        regions: splitList(f.serviceRegions),
        capabilities: splitList(f.capabilities),
        years_experience: Number(f.yearsExperience),
        vehicle_type: f.vehicleType.trim() || undefined,
        availability_note: f.availabilityNote.trim() || undefined,
        bio: f.bio.trim() || undefined,
        certifications: certs.length > 0 ? certs : undefined,
        emergency_contact_name: f.emergencyContactName.trim(),
        emergency_contact_phone: f.emergencyContactPhone.trim(),
        terms_accepted: f.consent,
        national_id: f.nationalId.trim() || undefined,
        birth_date: f.birthDate || undefined,
        address: f.address.trim() || undefined,
        bank_code: f.bankCode.trim() || undefined,
        bank_account: f.bankAccount.trim() || undefined,
        tax_id: f.taxId.trim() || undefined,
      });
      setDone(true);
    } catch (err) {
      setSubmitError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-start justify-center bg-[var(--bg-page)] px-4 py-8 md:items-center">
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>
      <BackToHome className="absolute left-4 top-4" />

      <div className="w-full max-w-[560px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-sm md:p-8">
        <div className="mb-5 flex flex-col items-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <Wrench className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-[var(--text-primary)]">申請成為師傅</h1>
          <p className="text-sm text-[var(--text-secondary)]">填寫資料，送出後待平台審核</p>
        </div>

        {done ? (
          <div className="flex flex-col items-center gap-4 py-6">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-green-100">
              <Check className="h-7 w-7 text-green-600" />
            </div>
            <p className="text-center text-sm text-[var(--text-primary)]">
              申請已送出！您的帳號待平台審核通過後即可登入。
            </p>
            <Link
              href={loginHref}
              className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]"
            >
              前往登入
            </Link>
          </div>
        ) : (
          <>
            <Stepper step={step} />

            <form onSubmit={(e) => e.preventDefault()} className="mt-5 flex flex-col gap-4">
              {step === 0 && <StepBasic f={f} set={set} errors={errors} />}
              {step === 1 && <StepPro f={f} set={set} errors={errors} />}
              {step === 2 && <StepSensitive f={f} set={set} errors={errors} />}
              {step === 3 && <StepConfirm f={f} />}

              {submitError && (
                <div
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                >
                  {submitError}
                </div>
              )}

              <div className="mt-1 flex items-center justify-between gap-3">
                {step > 0 ? (
                  <button
                    type="button"
                    onClick={prev}
                    className="flex items-center gap-1 rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                  >
                    <ChevronLeft className="h-4 w-4" /> 上一步
                  </button>
                ) : (
                  <Link
                    href={loginHref}
                    className="text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  >
                    ← 返回登入
                  </Link>
                )}

                {step < STEPS.length - 1 ? (
                  <button
                    type="button"
                    onClick={next}
                    className="rounded-lg bg-[var(--primary)] px-5 py-2 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]"
                  >
                    下一步
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={doSubmit}
                    disabled={loading}
                    className="rounded-lg bg-[var(--primary)] px-5 py-2 text-sm font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-60"
                  >
                    {loading ? "送出中…" : "送出申請"}
                  </button>
                )}
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

function Stepper({ step }: { step: number }) {
  return (
    <div className="flex items-center">
      {STEPS.map((label, i) => {
        const active = i === step;
        const past = i < step;
        return (
          <div key={label} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-full text-[13px] font-semibold ${
                  active
                    ? "bg-[var(--primary)] text-white"
                    : past
                      ? "bg-green-100 text-green-600"
                      : "bg-[var(--surface-strong)] text-[var(--text-secondary)]"
                }`}
              >
                {past ? <Check className="h-4 w-4" /> : i + 1}
              </span>
              <span
                className={`whitespace-nowrap text-[11px] ${
                  active ? "font-semibold text-[var(--text-primary)]" : "text-[var(--text-secondary)]"
                }`}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <span
                className={`mx-1 mb-4 h-px flex-1 ${past ? "bg-green-300" : "bg-[var(--border)]"}`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

type StepProps = {
  f: FormState;
  set: <K extends keyof FormState>(k: K, v: FormState[K]) => void;
  errors: Record<string, string>;
};

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
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-[13px] font-medium text-[var(--text-primary)]">
        {label}
        {required ? <span className="text-red-500"> *</span> : <span className="text-[var(--text-disabled)]">（選填）</span>}
      </span>
      {children}
      {hint && !error && <span className="text-xs text-[var(--text-secondary)]">{hint}</span>}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </label>
  );
}

function StepBasic({ f, set, errors }: StepProps) {
  return (
    <>
      <Field label="姓名" required error={errors.name}>
        <input value={f.name} onChange={(e) => set("name", e.target.value)} className={inputCls} />
      </Field>
      <Field label="手機號碼" required error={errors.phone}>
        <input value={f.phone} onChange={(e) => set("phone", e.target.value)} placeholder="09xxxxxxxx" className={inputCls} />
      </Field>
      <Field label="Email" required error={errors.email}>
        <input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} className={inputCls} />
      </Field>
      <Field label="密碼" required hint="至少 8 碼" error={errors.password}>
        <input type="password" value={f.password} onChange={(e) => set("password", e.target.value)} className={inputCls} />
      </Field>
      <Field label="服務地區" required hint="逗號分隔，例：台北市、新北市" error={errors.serviceRegions}>
        <input value={f.serviceRegions} onChange={(e) => set("serviceRegions", e.target.value)} placeholder="台北市、新北市" className={inputCls} />
      </Field>
      <Field label="交通工具" hint="例：機車 / 汽車 / 貨車">
        <input value={f.vehicleType} onChange={(e) => set("vehicleType", e.target.value)} placeholder="機車" className={inputCls} />
      </Field>
    </>
  );
}

function StepPro({ f, set, errors }: StepProps) {
  return (
    <>
      <Field label="從業年資（年）" required error={errors.yearsExperience}>
        <input type="number" min={0} max={80} value={f.yearsExperience} onChange={(e) => set("yearsExperience", e.target.value)} className={inputCls} />
      </Field>
      <Field label="可服務品牌" hint="逗號分隔，例：Yale、Dormakaba、Kaadas">
        <input value={f.capabilities} onChange={(e) => set("capabilities", e.target.value)} placeholder="Yale、Dormakaba" className={inputCls} />
      </Field>
      <Field label="可服務時段" hint="例：全職・平日假日皆可">
        <input value={f.availabilityNote} onChange={(e) => set("availabilityNote", e.target.value)} className={inputCls} />
      </Field>
      <Field label="專業證照" hint="逗號分隔證照名稱，例：室內配線技術士乙級">
        <input value={f.certifications} onChange={(e) => set("certifications", e.target.value)} className={inputCls} />
      </Field>
      <Field label="自我介紹" hint="簡述經驗與專長，會顯示給派工方">
        <textarea
          value={f.bio}
          onChange={(e) => set("bio", e.target.value)}
          rows={3}
          maxLength={1000}
          className={`${inputCls} h-auto resize-y py-2`}
        />
      </Field>
    </>
  );
}

function StepSensitive({ f, set, errors }: StepProps) {
  return (
    <>
      <Field label="緊急聯絡人" required error={errors.emergencyContactName}>
        <input value={f.emergencyContactName} onChange={(e) => set("emergencyContactName", e.target.value)} className={inputCls} />
      </Field>
      <Field label="緊急聯絡人電話" required error={errors.emergencyContactPhone}>
        <input value={f.emergencyContactPhone} onChange={(e) => set("emergencyContactPhone", e.target.value)} placeholder="09xxxxxxxx" className={inputCls} />
      </Field>

      <div className="flex items-start gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2.5">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[var(--primary)]" />
        <p className="text-xs text-[var(--text-secondary)]">
          以下為敏感資料，加密保存、僅供平台審核與撥款；可先略過，於核准前補件。
        </p>
      </div>

      <Field label="身分證字號" hint="加密保存" error={errors.nationalId}>
        <input value={f.nationalId} onChange={(e) => set("nationalId", e.target.value.toUpperCase())} placeholder="A123456789" className={inputCls} />
      </Field>
      <Field label="生日">
        <input type="date" value={f.birthDate} onChange={(e) => set("birthDate", e.target.value)} className={inputCls} />
      </Field>
      <Field label="通訊地址">
        <input value={f.address} onChange={(e) => set("address", e.target.value)} className={inputCls} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="銀行代碼" hint="例：822" error={errors.bankCode}>
          <input value={f.bankCode} onChange={(e) => set("bankCode", e.target.value)} placeholder="822" className={inputCls} />
        </Field>
        <Field label="撥款帳號" hint="加密保存" error={errors.bankAccount}>
          <input value={f.bankAccount} onChange={(e) => set("bankAccount", e.target.value)} className={inputCls} />
        </Field>
      </div>
      <Field label="統一編號" hint="有工作室者填" error={errors.taxId}>
        <input value={f.taxId} onChange={(e) => set("taxId", e.target.value)} placeholder="8 碼數字" className={inputCls} />
      </Field>

      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={f.consent}
          onChange={(e) => set("consent", e.target.checked)}
          className="mt-0.5 h-4 w-4"
        />
        <span className="text-[13px] text-[var(--text-primary)]">
          我已閱讀並同意服務條款、隱私權政策，並授權平台進行背景查核。
          {errors.consent && <span className="block text-xs text-red-600">{errors.consent}</span>}
        </span>
      </label>
    </>
  );
}

function StepConfirm({ f }: { f: FormState }) {
  const rows: [string, string][] = [
    ["姓名", f.name],
    ["手機", f.phone],
    ["Email", f.email],
    ["服務地區", f.serviceRegions],
    ["交通工具", f.vehicleType],
    ["年資", f.yearsExperience ? `${f.yearsExperience} 年` : ""],
    ["可服務品牌", f.capabilities],
    ["可服務時段", f.availabilityNote],
    ["證照", f.certifications],
    ["緊急聯絡人", f.emergencyContactName ? `${f.emergencyContactName} / ${f.emergencyContactPhone}` : ""],
    ["身分證字號", f.nationalId ? maskTail(f.nationalId, 3) : ""],
    ["撥款帳號", f.bankAccount ? `${f.bankCode ? f.bankCode + " " : ""}${maskTail(f.bankAccount, 4)}` : ""],
    ["統一編號", f.taxId],
  ];
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-[var(--text-secondary)]">請確認以下資料後送出：</p>
      <dl className="divide-y divide-[var(--border)] rounded-lg border border-[var(--border)]">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-start justify-between gap-3 px-3 py-2">
            <dt className="text-[12px] text-[var(--text-secondary)]">{label}</dt>
            <dd className={`text-right text-[13px] ${value ? "text-[var(--text-primary)]" : "text-[var(--text-disabled)]"}`}>
              {value || "未填"}
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-[var(--text-disabled)]">
        身分證與撥款帳號僅顯示末碼，完整資料加密保存。
      </p>
    </div>
  );
}

function maskTail(v: string, visible: number): string {
  const s = v.trim();
  if (s.length <= visible) return s;
  return "•".repeat(s.length - visible) + s.slice(-visible);
}
