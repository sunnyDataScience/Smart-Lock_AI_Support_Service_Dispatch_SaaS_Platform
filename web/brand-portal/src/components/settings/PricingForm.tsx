"use client";

import { useEffect, useMemo, useState } from "react";
import { Calculator, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api, auth, tenantPath, getCurrentSession } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useLocale, useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type PricingRule = components["schemas"]["PricingRule"];
type PricingRulePage = components["schemas"]["PricingRulePage"];
type PricingSurcharge = components["schemas"]["PricingSurcharge"];
type PricingRuleEnvelope = components["schemas"]["PricingRuleEnvelope"];
type PricingRuleCreateRequest = components["schemas"]["PricingRuleCreateRequest"];
type PricingRuleUpdateRequest = components["schemas"]["PricingRuleUpdateRequest"];
type PricingCalculateRequest = components["schemas"]["PricingCalculateRequest"];
type PricingCalculateResponse = components["schemas"]["PricingCalculateResponse"];
type LockType = PricingRule["lock_type"];
type Difficulty = PricingRule["difficulty"];

const LOCK_TYPE_VALUES: LockType[] = ["digital_deadbolt", "smart_lock", "padlock", "other"];
const DIFFICULTY_VALUES: Difficulty[] = ["simple", "moderate", "complex"];

const difficultyColor: Record<
  Difficulty,
  { textColor: string; bgColor: string }
> = {
  simple: { textColor: "#16A34A", bgColor: "#DCFCE7" },
  moderate: { textColor: "#B45309", bgColor: "#FEF3C7" },
  complex: { textColor: "#B91C1C", bgColor: "#FEE2E2" },
};

function formatTwd(amount: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

const DECIMAL_RE = /^\d+(\.\d{1,2})?$/;

export default function PricingForm() {
  const t = useTranslations("components.settings.pricingForm");
  const tLock = useTranslations("components.settings.pricingForm.lockTypes");
  const tDiff = useTranslations("components.settings.pricingForm.difficulties");
  const { locale } = useLocale();
  const lockTypeLabel = useMemo<Record<LockType, string>>(
    () => Object.fromEntries(LOCK_TYPE_VALUES.map((v) => [v, tLock(v)])) as Record<LockType, string>,
    [tLock],
  );
  const difficultyLabel = useMemo<Record<Difficulty, string>>(
    () => Object.fromEntries(DIFFICULTY_VALUES.map((v) => [v, tDiff(v)])) as Record<Difficulty, string>,
    [tDiff],
  );

  const [items, setItems] = useState<PricingRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const [editorMode, setEditorMode] = useState<"create" | "edit" | null>(null);
  const [editorRule, setEditorRule] = useState<PricingRule | null>(null);
  const [editorPending, setEditorPending] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [calcOpen, setCalcOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<PricingRulePage>(
        tenantPath("/pricing/rules"),
        { query: { limit: 50 } },
      );
      setItems(res.items ?? []);
      setUpdatedAt(new Date());
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const openCreate = () => {
    setEditorRule(null);
    setEditorError(null);
    setEditorMode("create");
  };

  const openEdit = (rule: PricingRule) => {
    setEditorRule(rule);
    setEditorError(null);
    setEditorMode("edit");
  };

  const closeEditor = () => {
    if (editorPending) return;
    setEditorMode(null);
    setEditorRule(null);
    setEditorError(null);
  };

  const handleCreate = async (req: PricingRuleCreateRequest) => {
    setEditorPending(true);
    setEditorError(null);
    try {
      const res = await api.post<PricingRuleEnvelope>(
        tenantPath("/pricing/rules"),
        req,
        { headers: { "X-Initiator": getCurrentSession()?.userId ?? "" } },
      );
      const created = res.data;
      if (created) {
        setItems((prev) => [created, ...prev]);
        setToast(t("createdToast", { brand: created.brand, lockType: lockTypeLabel[created.lock_type] }));
      }
      setEditorMode(null);
      setEditorRule(null);
    } catch (e) {
      setEditorError(
        friendlyError(e),
      );
    } finally {
      setEditorPending(false);
    }
  };

  const handleUpdate = async (
    rule: PricingRule,
    req: PricingRuleUpdateRequest,
  ) => {
    setEditorPending(true);
    setEditorError(null);
    try {
      const res = await api.put<PricingRuleEnvelope>(
        tenantPath(`/pricing/rules/${encodeURIComponent(rule.id)}`),
        req,
        { headers: { "X-Initiator": getCurrentSession()?.userId ?? "" } },
      );
      const updated = res.data;
      if (updated) {
        setItems((prev) =>
          prev.map((r) => (r.id === updated.id ? updated : r)),
        );
        setToast(t("updatedToast", { brand: updated.brand, lockType: lockTypeLabel[updated.lock_type] }));
      }
      setEditorMode(null);
      setEditorRule(null);
    } catch (e) {
      setEditorError(
        friendlyError(e),
      );
    } finally {
      setEditorPending(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-[var(--text-primary)]">
            {t("title")}
          </span>
          <button
            onClick={fetchRules}
            disabled={loading}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
            title={t("refresh")}
          >
            <RefreshCw
              className={`h-[14px] w-[14px] text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
            />
          </button>
          <span
            className="flex items-center gap-[6px] rounded-full px-3 py-1 text-xs font-medium"
            style={{
              backgroundColor: error ? "#FEE2E2" : "#DCFCE7",
              color: error ? "#B91C1C" : "#15803D",
            }}
          >
            <span
              className="h-[6px] w-[6px] rounded-full"
              style={{ backgroundColor: error ? "#DC2626" : "#22C55E" }}
            />
            {error ? t("connection.fail") : t("connection.ok")}
          </span>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          {updatedAt
            ? t("lastUpdated", { time: updatedAt.toLocaleTimeString(locale, { hour12: false }) })
            : t("subtitle")}
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <span className="text-[13px] text-[var(--text-secondary)]">
          {t("intro")}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCalcOpen(true)}
            className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-[13px] font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-page)]"
          >
            <Calculator className="h-4 w-4" />
            {t("calc")}
          </button>
          <button
            onClick={openCreate}
            className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            {t("create")}
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-[var(--border)]">
        {/* Table Header */}
        <div className="flex items-center bg-[#F8FAFC] px-4 py-3">
          <div className="w-[140px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {t("cols.brand")}
            </span>
          </div>
          <div className="w-[180px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {t("cols.lockType")}
            </span>
          </div>
          <div className="w-[110px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {t("cols.difficulty")}
            </span>
          </div>
          <div className="flex w-[140px] justify-end">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {t("cols.basePrice")}
            </span>
          </div>
          <div className="flex flex-1 justify-center">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {t("cols.surcharges")}
            </span>
          </div>
          <div className="w-[80px]" />
        </div>

        {/* Loading / Empty */}
        {loading && items.length === 0 && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            {t("loading")}
          </div>
        )}
        {!loading && items.length === 0 && !error && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            {t("empty")}
          </div>
        )}

        {/* Data Rows */}
        {items.map((rule) => {
          const diffColor = difficultyColor[rule.difficulty] ?? { textColor: "#64748B", bgColor: "#F1F5F9" };
          const surcharges = rule.surcharges ?? [];
          return (
            <div
              key={rule.id}
              className="flex items-start border-t border-[var(--border)] px-4 py-3"
            >
              <div className="w-[140px]">
                <span className="text-[13px] font-medium text-[var(--text-primary)]">
                  {rule.brand}
                </span>
              </div>
              <div className="w-[180px]">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  {lockTypeLabel[rule.lock_type] ?? rule.lock_type}
                </span>
              </div>
              <div className="w-[110px]">
                <span
                  className="rounded-md px-2 py-1 text-xs font-semibold"
                  style={{
                    color: diffColor.textColor,
                    backgroundColor: diffColor.bgColor,
                  }}
                >
                  {difficultyLabel[rule.difficulty] ?? rule.difficulty}
                </span>
              </div>
              <div className="flex w-[140px] justify-end">
                <span className="font-['IBM_Plex_Mono'] text-[13px] font-semibold text-[var(--text-primary)]">
                  {formatTwd(rule.base_price)}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-1 pl-4">
                {surcharges.length === 0 && (
                  <span className="text-[12px] text-[var(--text-disabled)]">
                    {t("noSurcharge")}
                  </span>
                )}
                {surcharges.map((s, idx) => (
                  <div
                    key={`${rule.id}-${idx}`}
                    className="flex items-center gap-2 text-[12px]"
                  >
                    <span className="font-medium text-[var(--text-primary)]">
                      {s.name}
                    </span>
                    {s.condition && (
                      <span className="text-[var(--text-secondary)]">
                        ({s.condition})
                      </span>
                    )}
                    <span className="font-['IBM_Plex_Mono'] font-semibold text-[var(--primary)]">
                      +{formatTwd(s.amount)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex w-[80px] justify-end">
                <button
                  onClick={() => openEdit(rule)}
                  title={t("edit")}
                  className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)]"
                >
                  <Pencil className="h-4 w-4 text-[var(--text-secondary)]" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {editorMode && (
        <PricingRuleEditor
          mode={editorMode}
          rule={editorRule}
          pending={editorPending}
          error={editorError}
          onCancel={closeEditor}
          onSubmitCreate={handleCreate}
          onSubmitUpdate={(req) => editorRule && handleUpdate(editorRule, req)}
        />
      )}

      {calcOpen && (
        <PricingCalculator
          rules={items}
          onClose={() => setCalcOpen(false)}
        />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}

type SurchargeDraft = {
  name: string;
  condition: string;
  amount: string;
};

function PricingRuleEditor({
  mode,
  rule,
  pending,
  error,
  onCancel,
  onSubmitCreate,
  onSubmitUpdate,
}: {
  mode: "create" | "edit";
  rule: PricingRule | null;
  pending: boolean;
  error: string | null;
  onCancel: () => void;
  onSubmitCreate: (req: PricingRuleCreateRequest) => void;
  onSubmitUpdate: (req: PricingRuleUpdateRequest) => void;
}) {
  const t = useTranslations("components.settings.pricingForm.editor");
  const tLock = useTranslations("components.settings.pricingForm.lockTypes");
  const tDiff = useTranslations("components.settings.pricingForm.difficulties");
  const initial = rule;
  const [brand, setBrand] = useState(initial?.brand ?? "");
  const [lockType, setLockType] = useState<LockType>(
    initial?.lock_type ?? "digital_deadbolt",
  );
  const [difficulty, setDifficulty] = useState<Difficulty>(
    initial?.difficulty ?? "simple",
  );
  const [basePrice, setBasePrice] = useState<string>(initial?.base_price ?? "");
  const [surcharges, setSurcharges] = useState<SurchargeDraft[]>(
    (initial?.surcharges ?? []).map((s: PricingSurcharge) => ({
      name: s.name,
      condition: s.condition ?? "",
      amount: s.amount,
    })),
  );

  const isEdit = mode === "edit";

  const validate = (): string | null => {
    if (!isEdit && !brand.trim()) return t("errors.brandRequired");
    if (basePrice && !DECIMAL_RE.test(basePrice))
      return t("errors.basePriceFormat");
    for (let i = 0; i < surcharges.length; i++) {
      const s = surcharges[i];
      if (!s.name.trim()) return t("errors.surchargeName", { n: String(i + 1) });
      if (!s.amount || !DECIMAL_RE.test(s.amount))
        return t("errors.surchargeAmount", { n: String(i + 1) });
    }
    return null;
  };

  const buildSurchargesPayload = (): PricingSurcharge[] =>
    surcharges.map((s) => {
      const item: PricingSurcharge = {
        name: s.name.trim(),
        amount: s.amount,
      };
      if (s.condition.trim()) item.condition = s.condition.trim();
      return item;
    });

  const handleSubmit = () => {
    const localErr = validate();
    if (localErr) {
      // Surface as part of error display via parent? Use a local alert via toast
      alert(localErr);
      return;
    }
    if (isEdit) {
      const req: PricingRuleUpdateRequest = {};
      if (basePrice && basePrice !== initial?.base_price)
        req.base_price = basePrice;
      const newSurcharges = buildSurchargesPayload();
      const oldSurcharges = (initial?.surcharges ?? []).map(
        (s: PricingSurcharge) => ({
          name: s.name,
          condition: s.condition ?? "",
          amount: s.amount,
        }),
      );
      const surchargesChanged =
        JSON.stringify(
          newSurcharges.map((s) => ({
            name: s.name,
            condition: s.condition ?? "",
            amount: s.amount,
          })),
        ) !== JSON.stringify(oldSurcharges);
      if (surchargesChanged) req.surcharges = newSurcharges;
      if (Object.keys(req).length === 0) {
        alert(t("errors.noChange"));
        return;
      }
      onSubmitUpdate(req);
    } else {
      if (!basePrice) {
        alert(t("errors.basePriceRequired"));
        return;
      }
      const req: PricingRuleCreateRequest = {
        brand: brand.trim(),
        lock_type: lockType,
        difficulty,
        base_price: basePrice,
      };
      const sc = buildSurchargesPayload();
      if (sc.length > 0) req.surcharges = sc;
      onSubmitCreate(req);
    }
  };

  const addSurcharge = () =>
    setSurcharges((prev) => [...prev, { name: "", condition: "", amount: "" }]);

  const updateSurcharge = (
    idx: number,
    field: keyof SurchargeDraft,
    value: string,
  ) =>
    setSurcharges((prev) =>
      prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)),
    );

  const removeSurcharge = (idx: number) =>
    setSurcharges((prev) => prev.filter((_, i) => i !== idx));

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-[560px] max-h-[90vh] overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center gap-2">
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {isEdit ? t("editTitle") : t("createTitle")}
          </span>
        </div>

        <div className="flex flex-col gap-4">
          <Field label={t("fields.brand")} required>
            <input
              type="text"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              disabled={isEdit || pending}
              maxLength={100}
              placeholder={t("fields.brandPlaceholder")}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:bg-[var(--bg-page)] disabled:opacity-70"
            />
            {isEdit && (
              <span className="mt-1 text-[11px] text-[var(--text-disabled)]">
                {t("fields.brandLockedHint")}
              </span>
            )}
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label={t("fields.lockType")} required>
              <select
                value={lockType}
                onChange={(e) => setLockType(e.target.value as LockType)}
                disabled={isEdit || pending}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:bg-[var(--bg-page)] disabled:opacity-70"
              >
                {LOCK_TYPE_VALUES.map((value) => (
                  <option key={value} value={value}>
                    {tLock(value)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("fields.difficulty")} required>
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                disabled={isEdit || pending}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:bg-[var(--bg-page)] disabled:opacity-70"
              >
                {DIFFICULTY_VALUES.map((value) => (
                  <option key={value} value={value}>
                    {tDiff(value)}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label={t("fields.basePrice")} required>
            <input
              type="text"
              value={basePrice}
              onChange={(e) => setBasePrice(e.target.value)}
              disabled={pending}
              inputMode="decimal"
              placeholder={t("fields.basePricePlaceholder")}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
            />
          </Field>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                {t("fields.surcharges")}
              </span>
              <button
                onClick={addSurcharge}
                disabled={pending}
                type="button"
                className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1 text-[12px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                <Plus className="h-3 w-3" />
                {t("fields.addSurcharge")}
              </button>
            </div>
            {surcharges.length === 0 && (
              <span className="text-[12px] text-[var(--text-disabled)]">
                {t("fields.noSurchargeYet")}
              </span>
            )}
            {surcharges.map((s, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <input
                  type="text"
                  value={s.name}
                  onChange={(e) => updateSurcharge(idx, "name", e.target.value)}
                  disabled={pending}
                  maxLength={100}
                  placeholder={t("fields.surchargeName")}
                  className="w-[120px] rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-[6px] text-[12px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
                />
                <input
                  type="text"
                  value={s.condition}
                  onChange={(e) =>
                    updateSurcharge(idx, "condition", e.target.value)
                  }
                  disabled={pending}
                  maxLength={200}
                  placeholder={t("fields.surchargeCondition")}
                  className="flex-1 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-[6px] text-[12px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
                />
                <input
                  type="text"
                  value={s.amount}
                  onChange={(e) =>
                    updateSurcharge(idx, "amount", e.target.value)
                  }
                  disabled={pending}
                  inputMode="decimal"
                  placeholder={t("fields.surchargeAmount")}
                  className="w-[90px] rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-[6px] text-[12px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
                />
                <button
                  onClick={() => removeSurcharge(idx)}
                  disabled={pending}
                  type="button"
                  title={t("fields.remove")}
                  className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-red-50 disabled:opacity-50"
                >
                  <Trash2 className="h-3 w-3 text-[var(--status-danger)]" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            type="button"
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            onClick={handleSubmit}
            disabled={pending}
            type="button"
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("saving") : isEdit ? t("update") : t("create")}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[12px] font-medium text-[var(--text-secondary)]">
        {label}
        {required && <span className="ml-[2px] text-[var(--status-danger)]">*</span>}
      </span>
      {children}
    </div>
  );
}

function PricingCalculator({
  rules,
  onClose,
}: {
  rules: PricingRule[];
  onClose: () => void;
}) {
  const t = useTranslations("components.settings.pricingForm.calculator");
  const tLock = useTranslations("components.settings.pricingForm.lockTypes");
  const tDiff = useTranslations("components.settings.pricingForm.difficulties");
  const brandSuggestions = Array.from(
    new Set(rules.map((r) => r.brand).filter(Boolean)),
  );
  const [brand, setBrand] = useState<string>(brandSuggestions[0] ?? "");
  const [lockType, setLockType] = useState<LockType>("digital_deadbolt");
  const [difficulty, setDifficulty] = useState<Difficulty>("simple");
  const [isEmergency, setIsEmergency] = useState(false);
  const [isNight, setIsNight] = useState(false);
  const [additionalText, setAdditionalText] = useState("");

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PricingCalculateResponse | null>(null);

  const calculate = async () => {
    if (!brand.trim()) {
      setError(t("errBrandRequired"));
      return;
    }
    const items = additionalText
      .split(/[,，、\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    const req: PricingCalculateRequest = {
      brand: brand.trim(),
      lock_type: lockType,
      difficulty,
      is_emergency: isEmergency,
      is_night_service: isNight,
      additional_items: items.length > 0 ? items : undefined,
    };
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const tenantId = auth.getTenantId();
      const res = await api.post<PricingCalculateResponse>(
        `/tenants/${tenantId}/pricing/calculate`,
        req,
      );
      setResult(res);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={onClose}
    >
      <div
        className="flex w-full max-w-[560px] flex-col gap-4 rounded-xl bg-[var(--bg-surface)] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <span className="text-lg font-bold text-[var(--text-primary)]">
            {t("title")}
          </span>
          <button
            onClick={onClose}
            className="text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            {t("close")}
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label={t("brand")} required>
            <input
              list="pricing-calc-brand-list"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
              placeholder={t("brandPlaceholder")}
            />
            <datalist id="pricing-calc-brand-list">
              {brandSuggestions.map((b) => (
                <option key={b} value={b} />
              ))}
            </datalist>
          </Field>
          <Field label={t("lockType")} required>
            <select
              value={lockType}
              onChange={(e) => setLockType(e.target.value as LockType)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
            >
              {LOCK_TYPE_VALUES.map((value) => (
                <option key={value} value={value}>
                  {tLock(value)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("difficulty")} required>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as Difficulty)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
            >
              {DIFFICULTY_VALUES.map((value) => (
                <option key={value} value={value}>
                  {tDiff(value)}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex flex-col justify-center gap-2">
            <label className="flex items-center gap-2 text-[13px] text-[var(--text-primary)]">
              <input
                type="checkbox"
                checked={isEmergency}
                onChange={(e) => setIsEmergency(e.target.checked)}
              />
              {t("isEmergency")}
            </label>
            <label className="flex items-center gap-2 text-[13px] text-[var(--text-primary)]">
              <input
                type="checkbox"
                checked={isNight}
                onChange={(e) => setIsNight(e.target.checked)}
              />
              {t("isNight")}
            </label>
          </div>
        </div>

        <Field label={t("additional")}>
          <textarea
            value={additionalText}
            onChange={(e) => setAdditionalText(e.target.value)}
            rows={2}
            className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
            placeholder={t("additionalPlaceholder")}
          />
        </Field>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {error}
          </div>
        )}

        {result && (
          <div className="flex flex-col gap-2 rounded-lg border border-[var(--border)] bg-[#F8FAFC] p-4">
            <div className="flex items-center justify-between text-[13px]">
              <span className="text-[var(--text-secondary)]">{t("basePrice")}</span>
              <span className="font-['IBM_Plex_Mono'] font-semibold text-[var(--text-primary)]">
                {formatTwd(result.base_price)}
              </span>
            </div>
            {(result.surcharges ?? []).map((s, idx) => (
              <div
                key={`calc-sur-${idx}`}
                className="flex items-center justify-between text-[13px]"
              >
                <span className="text-[var(--text-secondary)]">
                  + {s.name}
                  {s.condition && (
                    <span className="text-[var(--text-disabled)]">
                      （{s.condition}）
                    </span>
                  )}
                </span>
                <span className="font-['IBM_Plex_Mono'] font-semibold text-[var(--primary)]">
                  +{formatTwd(s.amount)}
                </span>
              </div>
            ))}
            {(result.surcharges ?? []).length === 0 && (
              <div className="text-[12px] text-[var(--text-disabled)]">
                {t("noSurcharges")}
              </div>
            )}
            <div className="mt-1 flex items-center justify-between border-t border-[var(--border)] pt-2 text-[14px]">
              <span className="font-semibold text-[var(--text-primary)]">
                {t("totalLabel", { currency: result.currency ?? "TWD" })}
              </span>
              <span className="font-['IBM_Plex_Mono'] text-lg font-bold text-[var(--primary)]">
                {formatTwd(result.total)}
              </span>
            </div>
          </div>
        )}

        <div className="flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            disabled={pending}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-[13px] font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("close")}
          </button>
          <button
            onClick={calculate}
            disabled={pending}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {pending ? t("calculating") : t("calc")}
          </button>
        </div>
      </div>
    </div>
  );
}
