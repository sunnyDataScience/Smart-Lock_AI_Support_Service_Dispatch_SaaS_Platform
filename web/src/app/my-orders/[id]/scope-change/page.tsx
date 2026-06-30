"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Plus, Trash2, CheckCircle2 } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SubflowHeader from "@/components/tech/SubflowHeader";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

interface ScopeItem {
  id: string;
  name: string;
  unit_price: string;
  quantity: number;
}

function newItem(): ScopeItem {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    name: "",
    unit_price: "",
    quantity: 1,
  };
}

export default function ScopeChangePage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();
  const t = useTranslations("techPortal.scopeChange");
  const tCommon = useTranslations("techPortal.common");

  const [reason, setReason] = useState("");
  const [items, setItems] = useState<ScopeItem[]>([newItem()]);
  const [submitting, setSubmitting] = useState(false);
  const [submitOk, setSubmitOk] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function updateItem(idx: number, patch: Partial<ScopeItem>) {
    setItems((prev) =>
      prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)),
    );
  }

  function removeItem(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }

  const total = items.reduce((sum, it) => {
    const price = parseFloat(it.unit_price) || 0;
    return sum + price * (it.quantity || 0);
  }, 0);

  const canSubmit =
    reason.trim().length >= 10 &&
    items.length > 0 &&
    items.every(
      (it) =>
        it.name.trim().length > 0 &&
        parseFloat(it.unit_price) > 0 &&
        it.quantity > 0,
    ) &&
    !submitting;

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(id)}/scope-change`),
        {
          reason: reason.trim(),
          items: items.map((it) => ({
            name: it.name.trim(),
            unit_price: it.unit_price.trim(),
            quantity: it.quantity,
          })),
          total_estimate: total > 0 ? total.toFixed(2) : undefined,
        },
      );
      setSubmitOk(true);
      setTimeout(() => router.push(`/my-orders/${id}`), 1500);
    } catch (e) {
      setSubmitError(
        friendlyError(e),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <TechShell>
      <SubflowHeader workOrderId={id} title={t("title")} />

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          {t("successSubmitted")}
        </div>
      )}

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("reasonLabel")}
        </span>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          placeholder={t("reasonPlaceholder")}
          className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
        />
        <span className="text-[10px] text-[var(--text-disabled)]">
          {t("reasonHint", { count: reason.trim().length })}
        </span>
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            {t("itemsLabel")}
          </span>
          <button
            type="button"
            onClick={() => setItems((prev) => [...prev, newItem()])}
            className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-[12px] text-[var(--primary)] hover:bg-[var(--primary-light)]"
          >
            <Plus className="h-3 w-3" />
            {t("addItem")}
          </button>
        </div>

        {items.map((it, idx) => (
          <div
            key={it.id}
            className="flex flex-col gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] p-3"
          >
            <div className="flex items-start gap-2">
              <input
                type="text"
                value={it.name}
                onChange={(e) => updateItem(idx, { name: e.target.value })}
                placeholder={t("itemNamePlaceholder")}
                className="flex-1 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1 text-[13px]"
              />
              {items.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeItem(idx)}
                  className="flex h-8 w-8 items-center justify-center rounded-md text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              )}
            </div>
            <div className="flex items-center gap-2 text-[12px]">
              <label className="flex flex-1 items-center gap-1">
                <span className="text-[var(--text-secondary)]">{t("unitPriceLabel")}</span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={it.unit_price}
                  onChange={(e) =>
                    updateItem(idx, { unit_price: e.target.value })
                  }
                  placeholder={t("unitPricePlaceholder")}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1"
                />
              </label>
              <label className="flex w-24 items-center gap-1">
                <span className="text-[var(--text-secondary)]">{t("quantityLabel")}</span>
                <input
                  type="number"
                  min={1}
                  value={it.quantity}
                  onChange={(e) =>
                    updateItem(idx, { quantity: parseInt(e.target.value) || 0 })
                  }
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1"
                />
              </label>
            </div>
            <div className="text-right text-[12px] text-[var(--text-secondary)]">
              {t("subtotal", {
                amount: (parseFloat(it.unit_price) || 0) * (it.quantity || 0),
              })}
            </div>
          </div>
        ))}
      </section>

      <section className="mx-4 mt-4 rounded-xl border border-[var(--primary)] bg-[var(--primary-light)] p-4">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-semibold text-[var(--primary)]">
            {t("totalLabel")}
          </span>
          <span className="text-[20px] font-bold text-[var(--primary)]">
            ${total.toFixed(0)}
          </span>
        </div>
      </section>

      {submitError && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {submitError}
        </div>
      )}

      <div className="mt-4 flex gap-2 px-4 pb-4">
        <button
          type="button"
          onClick={() => router.push(`/my-orders/${id}`)}
          className="h-12 flex-1 rounded-lg border border-[var(--border)] text-[14px] font-medium text-[var(--text-primary)]"
        >
          {tCommon("cancel")}
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit}
          className="h-12 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white disabled:opacity-60"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </div>
    </TechShell>
  );
}
