"use client";

// 平台 console — 廠商帳號管理 panel(「發案方審核」頁的分頁之一)。
// 20260702 退場決議 + UAT R2 W3-2:廠商「自助註冊」收掉,帳號改由平台代建。
// 本 panel 從「審核」改為「帳號管理」:
//   - 清單沿用 GET /api/v1/platform/vendors(listPlatformVendors)
//   - 「建立廠商帳號」→ POST /api/v1/platform/vendors(建立即 active,不走待審)
//   - 核准/拒絕動作與自助註冊文案已移除;status 標籤保留全值域
//     (歷史資料仍可能帶 pending_approval / rejected)
// 型別未重生前對新端點採防禦性呼叫(本地 interface,不依賴 api.generated.ts)。

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useToast } from "@/components/ui/Toast";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type VendorStatus = "pending_approval" | "active" | "suspended" | "rejected";

interface Vendor {
  id: string;
  vendor_type: string;
  name: string;
  company_name: string | null;
  phone: string;
  email: string;
  address: string | null;
  status: VendorStatus;
  created_at: string | null;
}

const STATUS_CLS: Record<VendorStatus, string> = {
  pending_approval: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)] border-[var(--badge-warn-fg)]/25",
  active: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)] border-[var(--badge-success-fg)]/25",
  suspended: "bg-[var(--badge-danger-bg)] text-[var(--badge-danger-fg)] border-[var(--badge-danger-fg)]/25",
  rejected: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)] border-[var(--border)]",
};

// 自助註冊退場後不再有「待審」工作流 → 篩選只留 全部/已啟用/已停權;
// 預設「全部」(帳號皆平台代建,無待辦語意)。
const FILTERS: (VendorStatus | "")[] = ["", "active", "suspended"];

export default function VendorsPanel() {
  const { toast } = useToast();
  const t = useTranslations("platform.vendors");
  const tc = useTranslations("platform.common");
  const tf = useTranslations("platform.fields");
  const tt = useTranslations("platform.requestors.type");
  const [filter, setFilter] = useState<string>("");
  const [items, setItems] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = filter ? `?status=${filter}` : "";
      const res = await api.get<{ items: Vendor[] }>(`/api/v1/platform/vendors${qs}`);
      setItems(res.items ?? []);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="text-sm text-[var(--text-secondary)]">{t("intro")}</p>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="flex shrink-0 items-center gap-1.5 rounded-lg bg-[var(--primary)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />
          {t("create")}
        </button>
      </div>

      <div className="flex gap-2">
        {FILTERS.map((value) => (
          <button
            key={value || "all"}
            type="button"
            onClick={() => setFilter(value)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              filter === value
                ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
            }`}
          >
            {value === "" ? tc("all") : t(`status.${value}`)}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-4 py-3 text-sm text-[var(--badge-danger-fg)]">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">{tc("loading")}</p>
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          {t("empty")}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((v) => (
            <div
              key={v.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-base font-semibold text-[var(--text-primary)]">
                      {v.company_name || v.name}
                    </span>
                    <span className="rounded-md border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                      {["brand", "locksmith", "distributor"].includes(v.vendor_type)
                        ? tt(v.vendor_type)
                        : v.vendor_type}
                    </span>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_CLS[v.status] ?? STATUS_CLS.rejected}`}>
                      {t(`status.${v.status}`)}
                    </span>
                  </div>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
                    <span>{tf("contact")}{tc("colon")}{v.name}</span>
                    <span>{tf("phone")}{tc("colon")}{v.phone || "—"}</span>
                    <span>{tf("email")}{tc("colon")}{v.email || "—"}</span>
                    {v.address && (
                      <span className="sm:col-span-2">{tf("address")}{tc("colon")}{v.address}</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {createOpen && (
        <CreateVendorModal
          onClose={() => setCreateOpen(false)}
          onCreated={(displayName) => {
            setCreateOpen(false);
            toast({ title: t("createDone", { name: displayName }), variant: "success" });
            load();
          }}
        />
      )}
    </div>
  );
}

// ── 建立廠商帳號 Modal ───────────────────────────────────────────────────────
// 欄位與 inline 驗證對齊後端契約(POST /api/v1/platform/vendors,復用
// register_vendor 驗證規則):統編 8 碼數字、電話 09 開頭 10 碼、密碼 ≥8 碼。

interface CreateForm {
  name: string;
  company_name: string;
  tax_id: string;
  phone: string;
  email: string;
  password: string;
}

type FieldKey = keyof CreateForm;

const EMPTY_FORM: CreateForm = {
  name: "",
  company_name: "",
  tax_id: "",
  phone: "",
  email: "",
  password: "",
};

function CreateVendorModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (displayName: string) => void;
}) {
  const t = useTranslations("platform.vendors");
  const tc = useTranslations("platform.common");
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<FieldKey, string>>>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  function setField(key: FieldKey, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
    // 使用者修改欄位時清掉該欄位錯誤(inline 驗證回饋)
    setFieldErrors((errs) => (errs[key] ? { ...errs, [key]: undefined } : errs));
  }

  function validate(f: CreateForm): Partial<Record<FieldKey, string>> {
    const errs: Partial<Record<FieldKey, string>> = {};
    if (!f.name.trim()) errs.name = t("nameRequired");
    if (!f.company_name.trim()) errs.company_name = t("companyRequired");
    if (!/^\d{8}$/.test(f.tax_id.trim())) errs.tax_id = t("taxIdInvalid");
    if (!/^09\d{8}$/.test(f.phone.trim())) errs.phone = t("phoneInvalid");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.trim())) errs.email = t("emailInvalid");
    if (f.password.length < 8) errs.password = t("passwordTooShort");
    return errs;
  }

  async function submit() {
    const errs = validate(form);
    if (Object.values(errs).some(Boolean)) {
      setFieldErrors(errs);
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await api.post("/api/v1/platform/vendors", {
        name: form.name.trim(),
        company_name: form.company_name.trim(),
        tax_id: form.tax_id.trim(),
        phone: form.phone.trim(),
        email: form.email.trim(),
        password: form.password,
      });
      onCreated(form.company_name.trim() || form.name.trim());
    } catch (e) {
      setMsg(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-lg">
        <h2 className="text-lg font-bold text-[var(--text-primary)]">{t("createTitle")}</h2>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">{t("createHint")}</p>

        <div className="mt-4 flex flex-col gap-3">
          <FormField
            label={t("fieldName")}
            value={form.name}
            error={fieldErrors.name}
            onChange={(v) => setField("name", v)}
          />
          <FormField
            label={t("fieldCompany")}
            value={form.company_name}
            error={fieldErrors.company_name}
            onChange={(v) => setField("company_name", v)}
          />
          <div className="flex gap-3">
            <FormField
              label={t("fieldTaxId")}
              value={form.tax_id}
              error={fieldErrors.tax_id}
              onChange={(v) => setField("tax_id", v)}
              placeholder={t("taxIdPlaceholder")}
              className="flex-1"
            />
            <FormField
              label={t("fieldPhone")}
              value={form.phone}
              error={fieldErrors.phone}
              onChange={(v) => setField("phone", v)}
              placeholder={t("phonePlaceholder")}
              className="flex-1"
            />
          </div>
          <FormField
            label={t("fieldEmail")}
            value={form.email}
            error={fieldErrors.email}
            onChange={(v) => setField("email", v)}
            type="email"
          />
          <FormField
            label={t("fieldPassword")}
            value={form.password}
            error={fieldErrors.password}
            onChange={(v) => setField("password", v)}
            placeholder={t("passwordPlaceholder")}
            type="password"
          />
        </div>

        {msg && <p className="mt-3 text-[13px] text-[var(--status-danger)]">{msg}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
          >
            {tc("cancel")}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={busy}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {busy ? t("creating") : t("createSubmit")}
          </button>
        </div>
      </div>
    </div>
  );
}

function FormField({
  label,
  value,
  error,
  onChange,
  placeholder,
  type = "text",
  className = "",
}: {
  label: string;
  value: string;
  error?: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  className?: string;
}) {
  return (
    <label className={`flex flex-col gap-1 text-sm ${className}`}>
      <span className="text-[var(--text-secondary)]">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`rounded-lg border bg-[var(--bg-page)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)] ${
          error ? "border-[var(--status-danger)]" : "border-[var(--border)]"
        }`}
      />
      {error && <span className="text-xs text-[var(--status-danger)]">{error}</span>}
    </label>
  );
}
