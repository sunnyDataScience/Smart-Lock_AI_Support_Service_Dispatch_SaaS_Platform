"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Plus, Trash2, AlertCircle, CheckCircle2 } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SubflowHeader from "@/components/tech/SubflowHeader";

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
      // 後端 API 待補：POST /api/v1/work-orders/{id}/scope-change
      // body: { reason, items: [{ name, unit_price, quantity }], total_estimate }
      // MVP：模擬 1.2 秒延遲後成功
      await new Promise((r) => setTimeout(r, 1200));
      setSubmitOk(true);
      setTimeout(() => router.push(`/my-orders/${id}`), 1500);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <TechShell>
      <SubflowHeader workOrderId={id} title="範圍變更申請" />

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          範圍變更已送出，等候客戶核准
        </div>
      )}

      <div className="m-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800">
        <AlertCircle className="mr-1 inline h-3 w-3" />
        後端 `/scope-change` API 待補，目前為前端表單預覽
      </div>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          變更事由
        </span>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          placeholder="例：客戶現場確認需追加更換 2 個鎖芯..."
          className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
        />
        <span className="text-[10px] text-[var(--text-disabled)]">
          至少 10 字（{reason.trim().length}/10）
        </span>
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            追加工項
          </span>
          <button
            type="button"
            onClick={() => setItems((prev) => [...prev, newItem()])}
            className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-[12px] text-[var(--primary)] hover:bg-[#EFF6FF]"
          >
            <Plus className="h-3 w-3" />
            新增
          </button>
        </div>

        {items.map((it, idx) => (
          <div
            key={it.id}
            className="flex flex-col gap-2 rounded-lg border border-[var(--border)] bg-[#F8FAFC] p-3"
          >
            <div className="flex items-start gap-2">
              <input
                type="text"
                value={it.name}
                onChange={(e) => updateItem(idx, { name: e.target.value })}
                placeholder="工項名稱"
                className="flex-1 rounded-md border border-[var(--border)] bg-white px-2 py-1 text-[13px]"
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
                <span className="text-[var(--text-secondary)]">單價</span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={it.unit_price}
                  onChange={(e) =>
                    updateItem(idx, { unit_price: e.target.value })
                  }
                  placeholder="$"
                  className="w-full rounded-md border border-[var(--border)] bg-white px-2 py-1"
                />
              </label>
              <label className="flex w-24 items-center gap-1">
                <span className="text-[var(--text-secondary)]">數量</span>
                <input
                  type="number"
                  min={1}
                  value={it.quantity}
                  onChange={(e) =>
                    updateItem(idx, { quantity: parseInt(e.target.value) || 0 })
                  }
                  className="w-full rounded-md border border-[var(--border)] bg-white px-2 py-1"
                />
              </label>
            </div>
            <div className="text-right text-[12px] text-[var(--text-secondary)]">
              小計：${(parseFloat(it.unit_price) || 0) * (it.quantity || 0)}
            </div>
          </div>
        ))}
      </section>

      <section className="mx-4 mt-4 rounded-xl border border-[var(--primary)] bg-[#EFF6FF] p-4">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-semibold text-[var(--primary)]">
            追加總額
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
          取消
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit}
          className="h-12 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white disabled:opacity-60"
        >
          {submitting ? "送出中…" : "送出申請"}
        </button>
      </div>
    </TechShell>
  );
}
