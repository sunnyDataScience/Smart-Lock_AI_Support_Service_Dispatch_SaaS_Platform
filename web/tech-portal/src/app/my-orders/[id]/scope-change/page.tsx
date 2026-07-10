"use client";

// CR-0144/ADR-027:現場報價修正(requote command)——技師只提交項目異動草稿,
// **不含金額**(零定價權;金額由品牌定價引擎+小編審核決定,經客戶確認生效)。
// 本頁原為 scope-change 自填單價流,與 ADR-027 相悖,2026-07-10 原地改造。

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Plus, Send, Trash2 } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

interface DiffItem {
  id: string;
  item: string;
  quantity: number;
  note: string;
}

function newItem(): DiffItem {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    item: "",
    quantity: 1,
    note: "",
  };
}

const REASON_OPTIONS = [
  { value: "scope_add", label: "現場追加項目(如加購鎖芯、耗材)" },
  { value: "scope_change", label: "作業範圍變更(與原報價不符)" },
  { value: "estimate_error", label: "原估價有誤(需重新估價)" },
];

export default function RequotePage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();
  const [reason, setReason] = useState("scope_add");
  const [items, setItems] = useState<DiffItem[]>([newItem()]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  function updateItem(idx: number, patch: Partial<DiffItem>) {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  }

  async function submit() {
    const diffs = items
      .filter((it) => it.item.trim())
      .map(({ item, quantity, note }) => ({ item: item.trim(), quantity, note: note.trim() }));
    if (diffs.length === 0) {
      setError("請至少填寫一個異動項目");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(id)}/requote-requests`),
        { reason, item_diffs: diffs },
      );
      setDone(true);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <TechShell>
      <div className="mx-auto max-w-md px-4 py-6">
        {done ? (
          <div className="py-8 text-center">
            <CheckCircle2 className="mx-auto mb-3 h-12 w-12 text-[#15803D]" />
            <h1 className="mb-2 text-lg font-bold text-[var(--text-primary)]">修正請求已送出</h1>
            <p className="mb-6 text-sm leading-relaxed text-[var(--text-secondary)]">
              品牌後台將重新估價並經客戶確認,結果會通知您。
              價格由品牌端計算,無需您填寫。
            </p>
            <button
              onClick={() => router.push(`/my-orders/${id}`)}
              className="rounded-lg bg-[var(--primary)] px-6 py-2 text-sm font-semibold text-white"
            >
              回工單
            </button>
          </div>
        ) : (
          <>
            <button
              onClick={() => router.back()}
              className="mb-4 inline-flex items-center gap-1 text-sm text-[var(--text-secondary)]"
            >
              <ArrowLeft className="h-4 w-4" /> 返回
            </button>
            <h1 className="mb-1 text-lg font-bold text-[var(--text-primary)]">現場報價修正</h1>
            <p className="mb-5 text-[12.5px] leading-relaxed text-[var(--text-secondary)]">
              只需回報「異動了什麼」——<strong>不必也不能填價格</strong>,
              金額由品牌端定價並經客戶確認後生效(產生新版報價)。
            </p>

            <label className="mb-1 block text-[12px] font-semibold text-[var(--text-secondary)]">事由</label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mb-4 w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
            >
              {REASON_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            <label className="mb-1 block text-[12px] font-semibold text-[var(--text-secondary)]">
              異動項目(不含金額)
            </label>
            {items.map((it, idx) => (
              <div key={it.id} className="mb-2 rounded-lg border border-[var(--border)] p-3">
                <div className="mb-2 flex gap-2">
                  <input
                    value={it.item}
                    onChange={(e) => updateItem(idx, { item: e.target.value })}
                    placeholder="項目/料件名稱,如:鎖芯更換"
                    className="min-w-0 flex-1 rounded-md border border-[var(--border)] px-3 py-2 text-sm"
                  />
                  <input
                    type="number"
                    min={1}
                    value={it.quantity}
                    onChange={(e) =>
                      updateItem(idx, { quantity: Math.max(1, Number(e.target.value) || 1) })
                    }
                    className="w-16 rounded-md border border-[var(--border)] px-2 py-2 text-center text-sm"
                  />
                  {items.length > 1 && (
                    <button
                      onClick={() => setItems((prev) => prev.filter((_, i) => i !== idx))}
                      aria-label="移除項目"
                      className="text-[var(--text-disabled)]"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <input
                  value={it.note}
                  onChange={(e) => updateItem(idx, { note: e.target.value })}
                  placeholder="備註(選填,如:客戶要求升級)"
                  className="w-full rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
                />
              </div>
            ))}
            <button
              onClick={() => setItems((prev) => [...prev, newItem()])}
              className="mb-5 inline-flex items-center gap-1 text-sm font-semibold text-[var(--primary)]"
            >
              <Plus className="h-4 w-4" /> 新增項目
            </button>

            {error && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              onClick={submit}
              disabled={busy}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--primary)] py-3 text-sm font-bold text-white disabled:opacity-50"
            >
              <Send className="h-4 w-4" /> {busy ? "送出中…" : "送出修正請求"}
            </button>
            <p className="mt-3 text-center text-[11.5px] text-[var(--text-disabled)]">
              限進行中的工單且僅限本單指派技師;同一工單同時只能有一筆進行中的修正。
            </p>
          </>
        )}
      </div>
    </TechShell>
  );
}
