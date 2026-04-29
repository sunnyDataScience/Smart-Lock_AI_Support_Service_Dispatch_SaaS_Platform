"use client";

import { useEffect, useState } from "react";
import { Calculator, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { ApiError, api } from "@/lib/api";
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

const LOCK_TYPE_OPTIONS: { value: LockType; label: string }[] = [
  { value: "digital_deadbolt", label: "電子鎖（Deadbolt）" },
  { value: "smart_lock", label: "智慧鎖（Smart Lock）" },
  { value: "padlock", label: "掛鎖" },
  { value: "other", label: "其他" },
];

const DIFFICULTY_OPTIONS: { value: Difficulty; label: string }[] = [
  { value: "simple", label: "簡單" },
  { value: "moderate", label: "中等" },
  { value: "complex", label: "困難" },
];

const lockTypeLabel: Record<LockType, string> = Object.fromEntries(
  LOCK_TYPE_OPTIONS.map((o) => [o.value, o.label]),
) as Record<LockType, string>;

const difficultyLabel: Record<Difficulty, string> = Object.fromEntries(
  DIFFICULTY_OPTIONS.map((o) => [o.value, o.label]),
) as Record<Difficulty, string>;

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
        "/api/v1/pricing/rules?limit=50",
      );
      setItems(res.items ?? []);
      setUpdatedAt(new Date());
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
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
        "/api/v1/pricing/rules",
        req,
      );
      const created = res.data;
      if (created) {
        setItems((prev) => [created, ...prev]);
        setToast(`已建立規則：${created.brand} / ${lockTypeLabel[created.lock_type]}`);
      }
      setEditorMode(null);
      setEditorRule(null);
    } catch (e) {
      setEditorError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
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
        `/api/v1/pricing/rules/${encodeURIComponent(rule.id)}`,
        req,
      );
      const updated = res.data;
      if (updated) {
        setItems((prev) =>
          prev.map((r) => (r.id === updated.id ? updated : r)),
        );
        setToast(`已更新規則：${updated.brand} / ${lockTypeLabel[updated.lock_type]}`);
      }
      setEditorMode(null);
      setEditorRule(null);
    } catch (e) {
      setEditorError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
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
            報價規則 V2.0
          </span>
          <button
            onClick={fetchRules}
            disabled={loading}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
            title="重新整理"
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
            {error ? "連線失敗" : "已連線"}
          </span>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          {updatedAt
            ? `最後更新：${updatedAt.toLocaleTimeString("zh-TW", { hour12: false })}`
            : "管理依品牌、鎖型、難度的基礎報價"}
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
          列表為 listPricingRules 即時資料（已過濾停用規則），可即時新增與編輯。
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCalcOpen(true)}
            className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-[13px] font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-page)]"
          >
            <Calculator className="h-4 w-4" />
            試算報價
          </button>
          <button
            onClick={openCreate}
            className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            新增規則
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-[var(--border)]">
        {/* Table Header */}
        <div className="flex items-center bg-[#F8FAFC] px-4 py-3">
          <div className="w-[140px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              品牌
            </span>
          </div>
          <div className="w-[180px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              鎖型
            </span>
          </div>
          <div className="w-[110px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              難度
            </span>
          </div>
          <div className="flex w-[140px] justify-end">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              基礎價
            </span>
          </div>
          <div className="flex flex-1 justify-center">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              加價條件
            </span>
          </div>
          <div className="w-[80px]" />
        </div>

        {/* Loading / Empty */}
        {loading && items.length === 0 && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            載入中…
          </div>
        )}
        {!loading && items.length === 0 && !error && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            尚無計價規則
          </div>
        )}

        {/* Data Rows */}
        {items.map((rule) => {
          const diffColor = difficultyColor[rule.difficulty];
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
                    無加價條件
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
                  title="編輯規則"
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
    if (!isEdit && !brand.trim()) return "請填寫品牌";
    if (basePrice && !DECIMAL_RE.test(basePrice))
      return "基礎價格式：1200 或 1200.50";
    for (let i = 0; i < surcharges.length; i++) {
      const s = surcharges[i];
      if (!s.name.trim()) return `加價條件 #${i + 1}：請填寫名稱`;
      if (!s.amount || !DECIMAL_RE.test(s.amount))
        return `加價條件 #${i + 1}：金額需為數字（如 500.00）`;
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
        alert("沒有任何變更");
        return;
      }
      onSubmitUpdate(req);
    } else {
      if (!basePrice) {
        alert("請填寫基礎價");
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
            {isEdit ? "編輯計價規則" : "新增計價規則"}
          </span>
        </div>

        <div className="flex flex-col gap-4">
          <Field label="品牌" required>
            <input
              type="text"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              disabled={isEdit || pending}
              maxLength={100}
              placeholder="例：Yale"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:bg-[var(--bg-page)] disabled:opacity-70"
            />
            {isEdit && (
              <span className="mt-1 text-[11px] text-[var(--text-disabled)]">
                建立後不可變更
              </span>
            )}
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="鎖型" required>
              <select
                value={lockType}
                onChange={(e) => setLockType(e.target.value as LockType)}
                disabled={isEdit || pending}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:bg-[var(--bg-page)] disabled:opacity-70"
              >
                {LOCK_TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="難度" required>
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                disabled={isEdit || pending}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:bg-[var(--bg-page)] disabled:opacity-70"
              >
                {DIFFICULTY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="基礎價（NT$）" required>
            <input
              type="text"
              value={basePrice}
              onChange={(e) => setBasePrice(e.target.value)}
              disabled={pending}
              inputMode="decimal"
              placeholder="例：1200.00"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
            />
          </Field>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                加價條件（選填）
              </span>
              <button
                onClick={addSurcharge}
                disabled={pending}
                type="button"
                className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1 text-[12px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                <Plus className="h-3 w-3" />
                新增加價
              </button>
            </div>
            {surcharges.length === 0 && (
              <span className="text-[12px] text-[var(--text-disabled)]">
                尚未設定加價條件
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
                  placeholder="名稱（夜間服務）"
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
                  placeholder="條件（22:00–06:00）"
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
                  placeholder="金額"
                  className="w-[90px] rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-[6px] text-[12px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70"
                />
                <button
                  onClick={() => removeSurcharge(idx)}
                  disabled={pending}
                  type="button"
                  title="移除"
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
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={pending}
            type="button"
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "儲存中…" : isEdit ? "確認更新" : "確認建立"}
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
      setError("請填寫品牌");
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
      const res = await api.post<PricingCalculateResponse>(
        "/api/v1/pricing/calculate",
        req,
      );
      setResult(res);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
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
            試算報價
          </span>
          <button
            onClick={onClose}
            className="text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            關閉
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="品牌" required>
            <input
              list="pricing-calc-brand-list"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
              placeholder="輸入品牌"
            />
            <datalist id="pricing-calc-brand-list">
              {brandSuggestions.map((b) => (
                <option key={b} value={b} />
              ))}
            </datalist>
          </Field>
          <Field label="鎖型" required>
            <select
              value={lockType}
              onChange={(e) => setLockType(e.target.value as LockType)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
            >
              {LOCK_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="難度" required>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as Difficulty)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
            >
              {DIFFICULTY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
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
              緊急加成
            </label>
            <label className="flex items-center gap-2 text-[13px] text-[var(--text-primary)]">
              <input
                type="checkbox"
                checked={isNight}
                onChange={(e) => setIsNight(e.target.checked)}
              />
              夜間服務
            </label>
          </div>
        </div>

        <Field label="額外項目（用逗號或換行分隔，例：陽台, 二樓）">
          <textarea
            value={additionalText}
            onChange={(e) => setAdditionalText(e.target.value)}
            rows={2}
            className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
            placeholder="陽台, 二樓"
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
              <span className="text-[var(--text-secondary)]">基礎價</span>
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
                無套用任何加成
              </div>
            )}
            <div className="mt-1 flex items-center justify-between border-t border-[var(--border)] pt-2 text-[14px]">
              <span className="font-semibold text-[var(--text-primary)]">
                總額（{result.currency ?? "TWD"}）
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
            關閉
          </button>
          <button
            onClick={calculate}
            disabled={pending}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {pending ? "計算中…" : "試算"}
          </button>
        </div>
      </div>
    </div>
  );
}
