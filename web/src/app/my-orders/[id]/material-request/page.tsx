"use client";

import { useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Plus, Trash2, CheckCircle2, Package } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SubflowHeader from "@/components/tech/SubflowHeader";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

interface MissingItem {
  id: string;
  brand: string;
  model: string;
  quantity: number;
}

function newItem(): MissingItem {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    brand: "",
    model: "",
    quantity: 1,
  };
}

type UrgencyValue = "now" | "today" | "tomorrow";
const URGENCY_VALUES: UrgencyValue[] = ["now", "today", "tomorrow"];

export default function MaterialRequestPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();
  const t = useTranslations("techPortal.materialRequest");
  const tUrg = useTranslations("techPortal.materialRequest.urgencies");
  const tCommon = useTranslations("techPortal.common");

  const urgencies = useMemo(
    () => URGENCY_VALUES.map((v) => ({ value: v, label: tUrg(v) })),
    [tUrg],
  );

  const [items, setItems] = useState<MissingItem[]>([newItem()]);
  const [urgency, setUrgency] = useState<UrgencyValue>("today");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitOk, setSubmitOk] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function updateItem(idx: number, patch: Partial<MissingItem>) {
    setItems((prev) =>
      prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)),
    );
  }

  const canSubmit =
    items.length > 0 &&
    items.every(
      (it) =>
        it.brand.trim() && it.model.trim() && it.quantity > 0,
    ) &&
    !submitting;

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(id)}/material-request`),
        {
          items: items.map((it) => ({
            brand: it.brand.trim(),
            model: it.model.trim(),
            quantity: it.quantity,
          })),
          urgency,
          note: note.trim() || undefined,
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

      {submitError && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {submitError}
        </div>
      )}

      <section className="mx-4 mt-4 flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            {t("listTitle")}
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
              <Package className="mt-2 h-4 w-4 flex-shrink-0 text-[var(--text-secondary)]" />
              <div className="flex flex-1 flex-col gap-2">
                <input
                  type="text"
                  value={it.brand}
                  onChange={(e) =>
                    updateItem(idx, { brand: e.target.value })
                  }
                  placeholder={t("brandPlaceholder")}
                  className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1 text-[13px]"
                />
                <input
                  type="text"
                  value={it.model}
                  onChange={(e) =>
                    updateItem(idx, { model: e.target.value })
                  }
                  placeholder={t("modelPlaceholder")}
                  className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1 text-[13px]"
                />
                <label className="flex items-center gap-1 text-[12px]">
                  <span className="text-[var(--text-secondary)]">{t("quantityLabel")}</span>
                  <input
                    type="number"
                    min={1}
                    value={it.quantity}
                    onChange={(e) =>
                      updateItem(idx, {
                        quantity: parseInt(e.target.value) || 0,
                      })
                    }
                    className="w-20 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1"
                  />
                </label>
              </div>
              {items.length > 1 && (
                <button
                  type="button"
                  onClick={() =>
                    setItems((prev) => prev.filter((_, i) => i !== idx))
                  }
                  className="flex h-8 w-8 items-center justify-center rounded-md text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>
        ))}
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("urgencyLabel")}
        </span>
        <div className="flex flex-col gap-2">
          {urgencies.map((u) => (
            <label
              key={u.value}
              className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-[13px] ${
                urgency === u.value
                  ? "border-[var(--primary)] bg-[var(--primary-light)]"
                  : "border-[var(--border)] bg-[var(--bg-surface)]"
              }`}
            >
              <input
                type="radio"
                checked={urgency === u.value}
                onChange={() => setUrgency(u.value)}
                className="h-4 w-4 accent-[var(--primary)]"
              />
              {u.label}
            </label>
          ))}
        </div>
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("noteLabel")}
        </span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          placeholder={t("notePlaceholder")}
          className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
        />
      </section>

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
