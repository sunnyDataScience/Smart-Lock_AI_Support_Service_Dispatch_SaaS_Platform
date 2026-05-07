"use client";

/**
 * CustomerForm — 客戶 admin 新增 / 編輯共用表單
 *
 * 對應 E7x §4.2 FE UI 缺口 — 客戶主檔新增/編輯。
 *
 * 欄位驗證（前端）：
 *   - name (display_name)：required，去頭尾空白後不可為空
 *   - phone：required，台灣手機 09 開頭 10 碼（09xx-xxx-xxx 或 09xxxxxxxx）
 *   - email：optional，若填則需符合基本 email 格式
 *   - address：optional，自由文字
 *
 * API 串接：
 *   - mode="create" → POST /api/v1/customers (operationId: createCustomer)
 *   - mode="edit"   → PATCH /api/v1/customers/{id} (operationId: updateCustomer)
 *
 * 型別來源：components["schemas"]["CustomerCreateRequest" | "CustomerUpdateRequest"]
 *   由 OpenAPI spec → openapi-typescript regen（於 BE PR #43 merge 後同步）。
 */

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type CustomerCreateRequest = components["schemas"]["CustomerCreateRequest"];
type CustomerUpdateRequest = components["schemas"]["CustomerUpdateRequest"];

export interface CustomerFormInitial {
  display_name?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
}

export interface CustomerFormProps {
  mode: "create" | "edit";
  /** edit mode 必填 */
  customerId?: string;
  /** edit mode 預填 */
  initial?: CustomerFormInitial;
  /** 成功後導頁；預設 create → 列表 / edit → 詳情 */
  redirectTo?: string;
}

// 台灣手機：0 開頭，第 2 碼 9，後面 8 碼數字。允許 - 或空白分隔；驗證時去除。
const PHONE_REGEX = /^09\d{8}$/;
// 寬鬆 email，符合表單常見驗證（後端再做嚴格驗證）。
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function normalizePhone(raw: string): string {
  return raw.replace(/[\s-]/g, "");
}

interface FieldErrors {
  display_name?: string;
  phone?: string;
  email?: string;
}

export function CustomerForm({
  mode,
  customerId,
  initial,
  redirectTo,
}: CustomerFormProps) {
  const router = useRouter();

  const [displayName, setDisplayName] = useState(initial?.display_name ?? "");
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [address, setAddress] = useState(initial?.address ?? "");

  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  // 當 initial prop 變動（e.g. edit 頁 fetch 完成才注入），同步 state
  useEffect(() => {
    if (initial) {
      setDisplayName(initial.display_name ?? "");
      setPhone(initial.phone ?? "");
      setEmail(initial.email ?? "");
      setAddress(initial.address ?? "");
    }
  }, [initial]);

  function validate(): boolean {
    const errors: FieldErrors = {};

    if (!displayName.trim()) {
      errors.display_name = "客戶名稱必填";
    }

    const normPhone = normalizePhone(phone);
    if (!normPhone) {
      errors.phone = "電話必填";
    } else if (!PHONE_REGEX.test(normPhone)) {
      errors.phone = "請輸入有效的台灣手機（09xx-xxx-xxx）";
    }

    const trimmedEmail = email.trim();
    if (trimmedEmail && !EMAIL_REGEX.test(trimmedEmail)) {
      errors.email = "Email 格式不正確";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setServerError(null);

    if (!validate()) return;

    const basePayload = {
      display_name: displayName.trim(),
      phone: normalizePhone(phone),
      ...(email.trim() ? { email: email.trim() } : {}),
      ...(address.trim() ? { address: address.trim() } : {}),
    };

    setSubmitting(true);
    try {
      if (mode === "create") {
        const payload: CustomerCreateRequest = basePayload;
        const res = await api.post<{ data: { id: string } }>(
          "/api/v1/customers",
          payload,
        );
        const newId = res.data?.id;
        router.replace(redirectTo ?? (newId ? `/admin/customers/${newId}` : "/admin/customers"));
      } else {
        if (!customerId) throw new Error("缺少客戶 ID（edit mode）");
        const payload: CustomerUpdateRequest = basePayload;
        await api.patch(
          `/api/v1/customers/${encodeURIComponent(customerId)}`,
          payload,
        );
        router.replace(redirectTo ?? `/admin/customers/${customerId}`);
      }
    } catch (e) {
      setServerError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
      setSubmitting(false);
    }
  }

  const cancelHref =
    mode === "edit" && customerId
      ? `/admin/customers/${customerId}`
      : "/admin/customers";

  return (
    <form
      onSubmit={onSubmit}
      className="mx-auto flex max-w-2xl flex-col gap-5 px-6 py-8"
      noValidate
    >
      <Link
        href={cancelHref}
        className="flex w-fit items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--primary)]"
      >
        <ChevronLeft className="h-4 w-4" />
        取消
      </Link>

      <h1 className="text-[20px] font-semibold text-[var(--text-primary)]">
        {mode === "create" ? "新增客戶" : "編輯客戶"}
      </h1>

      {serverError && (
        <div
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-[13px] text-red-700"
        >
          {serverError}
        </div>
      )}

      <Field
        label="客戶名稱"
        required
        error={fieldErrors.display_name}
        htmlFor="customer-display-name"
      >
        <input
          id="customer-display-name"
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          maxLength={120}
          autoComplete="name"
          className="w-full rounded-md border border-[var(--border)] px-3 py-2 text-[14px] focus:border-[var(--primary)] focus:outline-none"
        />
      </Field>

      <Field
        label="電話"
        required
        error={fieldErrors.phone}
        hint="台灣手機格式（例：0912-345-678）"
        htmlFor="customer-phone"
      >
        <input
          id="customer-phone"
          type="tel"
          inputMode="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          maxLength={20}
          autoComplete="tel"
          placeholder="0912345678"
          className="w-full rounded-md border border-[var(--border)] px-3 py-2 text-[14px] focus:border-[var(--primary)] focus:outline-none"
        />
      </Field>

      <Field
        label="Email"
        error={fieldErrors.email}
        htmlFor="customer-email"
      >
        <input
          id="customer-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          maxLength={254}
          autoComplete="email"
          placeholder="optional"
          className="w-full rounded-md border border-[var(--border)] px-3 py-2 text-[14px] focus:border-[var(--primary)] focus:outline-none"
        />
      </Field>

      <Field label="地址" htmlFor="customer-address">
        <textarea
          id="customer-address"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          maxLength={500}
          rows={3}
          autoComplete="street-address"
          className="w-full resize-y rounded-md border border-[var(--border)] px-3 py-2 text-[14px] focus:border-[var(--primary)] focus:outline-none"
        />
      </Field>

      <div className="flex items-center justify-end gap-3 pt-2">
        <Link
          href={cancelHref}
          className="rounded-md border border-[var(--border)] px-4 py-2 text-[13px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
        >
          取消
        </Link>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting
            ? mode === "create"
              ? "建立中…"
              : "儲存中…"
            : mode === "create"
              ? "建立客戶"
              : "儲存變更"}
        </button>
      </div>
    </form>
  );
}

interface FieldProps {
  label: string;
  htmlFor: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}

function Field({ label, htmlFor, required, hint, error, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-[13px] font-medium text-[var(--text-primary)]"
      >
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
      {children}
      {hint && !error && (
        <span className="text-[11px] text-[var(--text-disabled)]">{hint}</span>
      )}
      {error && (
        <span role="alert" className="text-[11px] text-red-600">
          {error}
        </span>
      )}
    </div>
  );
}

export default CustomerForm;
