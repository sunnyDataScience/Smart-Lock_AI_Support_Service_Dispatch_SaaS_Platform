"use client";

import { useCallback, useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Plus, Trash2, X } from "lucide-react";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";

/* CR-0107：師傅獎懲明細（真資料）。取代前端寫死 4 筆 mock。
   業主裁決「後台手動登錄 + 自動帶取消罰」（Q121 師傅扣款須主管拍板，不腦補自動規則）：
   - 手動：admin/主管登錄實際獎金/扣款（可刪）。
   - 自動帶入：取消失約扣款（BR-CANCEL-007，read-only，標「自動」）。 */

interface PBEntry {
  id: string;
  entry_type: "bonus" | "penalty";
  title: string;
  reason: string | null;
  amount: number;
  occurred_date: string | null;
  source: "manual" | "cancellation";
  source_work_order_id: string | null;
  editable: boolean;
}

interface PBForm {
  entry_type: "bonus" | "penalty";
  title: string;
  amount: string;
  occurred_date: string;
  reason: string;
}

const EMPTY_FORM: PBForm = {
  entry_type: "bonus",
  title: "",
  amount: "",
  occurred_date: "",
  reason: "",
};

function ntd(n: number): string {
  return `NT$ ${Math.round(n).toLocaleString("en-US")}`;
}

export default function PenaltyBonusLog({ technicianId }: { technicianId?: string }) {
  const [entries, setEntries] = useState<PBEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<PBForm>(EMPTY_FORM);
  const [formMsg, setFormMsg] = useState<string | null>(null);

  const basePath = technicianId
    ? tenantPath(`/technicians/${technicianId}/penalty-bonus`)
    : null;

  const load = useCallback(async () => {
    if (!basePath) return;
    setError(null);
    try {
      const res = await api.get<{ data: PBEntry[] }>(basePath);
      setEntries(res.data ?? []);
    } catch (e) {
      setError(friendlyError(e));
    }
  }, [basePath]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      await load();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  function openNew() {
    setForm(EMPTY_FORM);
    setFormMsg(null);
    setModalOpen(true);
  }

  async function handleSave() {
    if (!basePath) return;
    if (!form.title.trim()) {
      setFormMsg("事由為必填");
      return;
    }
    if (!form.amount || Number(form.amount) < 0) {
      setFormMsg("金額需為非負數");
      return;
    }
    if (!form.occurred_date) {
      setFormMsg("日期為必填");
      return;
    }
    setBusy(true);
    setFormMsg(null);
    try {
      await api.post(basePath, {
        entry_type: form.entry_type,
        title: form.title.trim(),
        amount: Number(form.amount),
        occurred_date: form.occurred_date,
        reason: form.reason.trim() || null,
      });
      cacheInvalidate("GET:");
      setModalOpen(false);
      await load();
    } catch (e) {
      setFormMsg(`儲存失敗：${friendlyError(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(entry: PBEntry) {
    if (!basePath) return;
    if (!window.confirm(`確定刪除「${entry.title}」？`)) return;
    setBusy(true);
    try {
      await api.delete(`${basePath}/${encodeURIComponent(entry.id)}`);
      cacheInvalidate("GET:");
      await load();
    } catch (e) {
      setError(`刪除失敗：${friendlyError(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="w-full rounded-xl p-4 flex flex-col gap-3"
      style={{
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border)",
        boxShadow: "0 1px 4px rgba(15, 23, 42, 0.05)",
      }}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          獎懲紀錄
        </h3>
        <button
          onClick={openNew}
          disabled={busy || !technicianId}
          className="flex items-center gap-1 rounded border px-2 py-0.5 text-xs disabled:opacity-50"
          style={{ borderColor: "var(--primary)", color: "var(--primary)" }}
        >
          <Plus size={12} />
          新增
        </button>
      </div>

      {error && (
        <span className="text-[12px]" style={{ color: "var(--error)" }}>
          {error}
        </span>
      )}

      {loading ? (
        <span className="text-xs" style={{ color: "var(--text-disabled)" }}>載入中…</span>
      ) : entries.length === 0 ? (
        <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
          尚無獎懲紀錄。取消失約扣款會自動帶入；其他獎懲由主管「新增」登錄。
        </span>
      ) : (
        <div className="flex flex-col gap-2.5 w-full">
          {entries.map((entry) => {
            const isBonus = entry.entry_type === "bonus";
            return (
              <div key={entry.id} className="flex items-center gap-2 w-full">
                <span
                  className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0"
                  style={{
                    backgroundColor: isBonus ? "#D1FAE5" : "#FEE2E2",
                    color: isBonus ? "#059669" : "var(--error)",
                  }}
                >
                  {isBonus ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate" style={{ color: "var(--text-primary)" }}>
                    {entry.title}
                    {entry.source === "cancellation" && (
                      <span
                        className="ml-1 text-[10px] rounded px-1 py-0.5"
                        style={{ backgroundColor: "#F1F5F9", color: "var(--text-disabled)" }}
                      >
                        自動
                      </span>
                    )}
                  </p>
                  <p className="text-[11px]" style={{ color: "var(--text-disabled)" }}>
                    {entry.occurred_date ?? "—"}
                  </p>
                </div>
                <span
                  className="text-xs font-semibold flex-shrink-0"
                  style={{ color: isBonus ? "#059669" : "var(--error)" }}
                >
                  {isBonus ? "+" : "-"}{ntd(entry.amount)}
                </span>
                {entry.editable && (
                  <button
                    onClick={() => handleDelete(entry)}
                    disabled={busy}
                    aria-label="刪除"
                    className="flex-shrink-0 disabled:opacity-50"
                    style={{ color: "var(--text-disabled)" }}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg bg-[var(--bg-surface)] p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[16px] font-semibold text-[var(--text-primary)]">登錄獎懲</h3>
              <button onClick={() => setModalOpen(false)} aria-label="關閉" className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex flex-col gap-3">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">類型</span>
                <select
                  value={form.entry_type}
                  onChange={(e) => setForm((f) => ({ ...f, entry_type: e.target.value as "bonus" | "penalty" }))}
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                >
                  <option value="bonus">獎金</option>
                  <option value="penalty">扣款</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">事由 *</span>
                <input
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="高評價獎金 / 遲到扣款"
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                />
              </label>
              <div className="flex gap-3">
                <label className="flex flex-1 flex-col gap-1 text-sm">
                  <span className="text-[var(--text-secondary)]">金額 *</span>
                  <input
                    type="number"
                    min="0"
                    value={form.amount}
                    onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                    placeholder="200"
                    className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                  />
                </label>
                <label className="flex flex-1 flex-col gap-1 text-sm">
                  <span className="text-[var(--text-secondary)]">日期 *</span>
                  <input
                    type="date"
                    value={form.occurred_date}
                    onChange={(e) => setForm((f) => ({ ...f, occurred_date: e.target.value }))}
                    className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                  />
                </label>
              </div>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">說明（選填）</span>
                <input
                  value={form.reason}
                  onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                />
              </label>
            </div>
            {formMsg && <p className="mt-3 text-[13px] text-red-600">{formMsg}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => setModalOpen(false)} disabled={busy} className="rounded border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50">
                取消
              </button>
              <button onClick={handleSave} disabled={busy} className="rounded bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
                {busy ? "儲存中…" : "儲存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
