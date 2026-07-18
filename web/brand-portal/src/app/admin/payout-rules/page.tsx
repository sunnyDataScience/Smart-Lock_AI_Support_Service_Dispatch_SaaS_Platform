"use client";

import { useCallback, useEffect, useState } from "react";
import { Banknote, Pencil, Plus, Trash2, X } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { formatTwd } from "@/lib/format";

// UAT W1-6（業主裁決）：拆帳規則由純唯讀改為完整 CRUD——新增/編輯/停用，
// 比照 /admin/quote-catalog 頁 UI pattern；生效日可編（原 seed 缺值恆「—」）。
// 寫入權限＝後端 OPS_ROLES（admin/operations_manager），與 cost_visible 同集合，
// 故以 cost_visible 作為編輯 UI 顯示 gate。每次寫入後端硬性留審計。

interface PayoutRule {
  rule_id: string;
  service_code: string;
  service_name: string | null;
  level_id: string;
  base_payout?: string | number | null;
  night_surcharge_pct: string | number | null;
  urgent_surcharge_pct: string | number | null;
  currency: string | null;
  effective_date: string | null;
  expiry_date: string | null;
  decision_status: string | null;
  is_mock: boolean;
}
interface Resp {
  data: PayoutRule[];
  cost_visible: boolean;
  note: string;
}

// UAT P2-12：拆帳規則狀態中文化（DB technician_payout_rule.decision_status：
// draft / draft_review / accepted，migration 045 + 082）
const DECISION_STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  draft_review: "覆核中",
  accepted: "已確認",
};

const LEVEL_OPTIONS = ["LV-A", "LV-B", "LV-C"];

function pct(v: string | number | null): string {
  if (v == null) return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return "—";
  return `${Math.round(n * 100)}%`;
}
// UAT W1-5：幣別統一走共用 formatTwd（NT$ 整數格式）；cur 欄位（如 "TWD"）不再直出
function money(v: string | number | null | undefined): string {
  if (v == null) return "—";
  return formatTwd(v);
}

interface Draft {
  rule_id: string;
  service_code: string;
  service_name: string;
  level_id: string;
  base_payout: string;
  night_surcharge_pct: string;
  urgent_surcharge_pct: string;
  effective_date: string;
  expiry_date: string;
}

const EMPTY_DRAFT: Draft = {
  rule_id: "",
  service_code: "",
  service_name: "",
  level_id: "LV-A",
  base_payout: "",
  night_surcharge_pct: "",
  urgent_surcharge_pct: "",
  effective_date: "",
  expiry_date: "",
};

/** 前端 inline 驗證（與後端 service 層同規則：必填 / base ≥ 0 / 比例 0~1 / 生效 ≤ 失效） */
function validateDraft(d: Draft, isCreate: boolean): string | null {
  if (isCreate && !d.rule_id.trim()) return "規則代碼為必填";
  if (isCreate && d.rule_id.trim().length > 60) return "規則代碼長度上限 60";
  if (!d.service_code.trim()) return "服務代碼為必填";
  if (!d.level_id.trim()) return "技師級別為必填";
  if (!d.base_payout.trim()) return "基本拆帳為必填";
  const base = Number(d.base_payout);
  if (Number.isNaN(base) || base < 0) return "基本拆帳必須為 ≥ 0 的數字";
  for (const [label, raw] of [
    ["夜間加成率", d.night_surcharge_pct],
    ["急件加成率", d.urgent_surcharge_pct],
  ] as const) {
    if (!raw.trim()) continue;
    const n = Number(raw);
    if (Number.isNaN(n) || n < 0 || n > 1) return `${label}必須為 0~1 之間的比例（例 0.2 = 20%）`;
  }
  if (d.effective_date && d.expiry_date && d.effective_date > d.expiry_date) {
    return "生效日不可晚於失效日";
  }
  return null;
}

export default function PayoutRulesPage() {
  const [resp, setResp] = useState<Resp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ ruleId: string | null; draft: Draft } | null>(null);

  const fetchRules = useCallback(async () => {
    try {
      const res = await api.get<Resp>(tenantPath("/payout-rules"));
      setResp(res);
    } catch (e) {
      setError(friendlyError(e));
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  function showToast(msg: string) {
    setToast(msg);
    window.setTimeout(() => setToast(null), 3000);
  }

  function startCreate() {
    setEditing({ ruleId: null, draft: { ...EMPTY_DRAFT } });
  }

  function startEdit(r: PayoutRule) {
    setEditing({
      ruleId: r.rule_id,
      draft: {
        rule_id: r.rule_id,
        service_code: r.service_code ?? "",
        service_name: r.service_name ?? "",
        level_id: r.level_id ?? "LV-A",
        base_payout: r.base_payout != null ? String(r.base_payout) : "",
        night_surcharge_pct: r.night_surcharge_pct != null ? String(r.night_surcharge_pct) : "",
        urgent_surcharge_pct: r.urgent_surcharge_pct != null ? String(r.urgent_surcharge_pct) : "",
        effective_date: r.effective_date?.slice(0, 10) ?? "",
        expiry_date: r.expiry_date?.slice(0, 10) ?? "",
      },
    });
  }

  async function handleDisable(r: PayoutRule) {
    if (!window.confirm(`確定停用拆帳規則 ${r.rule_id}？停用後不再參與拆帳計算（可由工程端復原）。`)) {
      return;
    }
    setError(null);
    try {
      await api.delete(tenantPath(`/payout-rules/${encodeURIComponent(r.rule_id)}`));
      showToast(`已停用 ${r.rule_id}`);
      await fetchRules();
    } catch (e) {
      setError(friendlyError(e));
    }
  }

  const canEdit = !!resp?.cost_visible; // OPS_ROLES 同集合（見檔頭註解）

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <Banknote className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">師傅拆帳規則</h1>
          {resp?.data?.some((r) => r.is_mock) && (
            <span className="rounded bg-[#FEF3C7] px-2 py-[2px] text-[11px] text-[#92400E]">示意資料</span>
          )}
          {canEdit && (
            <button
              type="button"
              onClick={startCreate}
              className="ml-auto flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-[6px] text-[13px] font-medium text-[var(--primary)] hover:bg-[var(--primary-light)]"
            >
              <Plus className="h-4 w-4" />
              新增規則
            </button>
          )}
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {toast && (
            <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {toast}
            </div>
          )}
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          )}
          {!resp ? (
            <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
          ) : resp.data.length === 0 ? (
            <p className="text-sm text-[var(--text-disabled)]">尚無拆帳規則</p>
          ) : (
            <>
              <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">服務代碼</th>
                      <th className="px-3 py-2 text-left">服務名稱</th>
                      <th className="px-3 py-2 text-left">等級</th>
                      {resp.cost_visible && <th className="px-3 py-2 text-right">基本拆帳</th>}
                      <th className="px-3 py-2 text-right">夜間加成</th>
                      <th className="px-3 py-2 text-right">急件加成</th>
                      <th className="px-3 py-2 text-left">生效日</th>
                      <th className="px-3 py-2 text-left">狀態</th>
                      {canEdit && <th className="w-[90px] px-3 py-2 text-right">操作</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {resp.data.map((r) => (
                      <tr key={r.rule_id} className="border-t border-[var(--border)]">
                        <td className="px-3 py-2 font-mono text-[12px] text-[var(--text-secondary)]">{r.service_code}</td>
                        <td className="px-3 py-2 text-[var(--text-primary)]">{r.service_name}</td>
                        <td className="px-3 py-2 text-[var(--text-secondary)]">{r.level_id}</td>
                        {resp.cost_visible && (
                          <td className="px-3 py-2 text-right font-mono font-medium text-[var(--text-primary)]">
                            {money(r.base_payout)}
                          </td>
                        )}
                        <td className="px-3 py-2 text-right">{pct(r.night_surcharge_pct)}</td>
                        <td className="px-3 py-2 text-right">{pct(r.urgent_surcharge_pct)}</td>
                        <td className="px-3 py-2 text-[var(--text-secondary)]">{r.effective_date?.slice(0, 10) || "—"}</td>
                        <td className="px-3 py-2">
                          <span className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] text-[var(--text-secondary)]">
                            {r.decision_status
                              ? DECISION_STATUS_LABEL[r.decision_status] ?? r.decision_status
                              : "—"}
                          </span>
                        </td>
                        {canEdit && (
                          <td className="px-3 py-2 text-right">
                            <div className="flex justify-end gap-1">
                              <button
                                type="button"
                                onClick={() => startEdit(r)}
                                title="編輯"
                                className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)] hover:text-[var(--primary)]"
                              >
                                <Pencil className="h-4 w-4" />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDisable(r)}
                                title="停用"
                                className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)] hover:text-red-600"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!resp.cost_visible && (
                <p className="mt-2 text-[11px] text-[var(--text-disabled)]">基本拆帳金額僅後台財務角色可見。</p>
              )}
              {/* UAT W1-6：頁面已開放 CRUD——原「純唯讀、正式值尚待確認」說明移除 */}
              {canEdit && (
                <p className="mt-2 text-[12px] text-[var(--text-disabled)]">
                  新增或編輯後即為正式生效值（狀態自動轉「已確認」）；停用為軟刪、所有變更皆留審計紀錄。
                </p>
              )}
            </>
          )}
        </div>
      </div>

      {editing && (
        <EditModal
          ruleId={editing.ruleId}
          initial={editing.draft}
          onClose={() => setEditing(null)}
          onSaved={async (msg) => {
            setEditing(null);
            showToast(msg);
            await fetchRules();
          }}
        />
      )}
    </div>
  );
}

function EditModal({
  ruleId,
  initial,
  onClose,
  onSaved,
}: {
  ruleId: string | null; // null = 新增
  initial: Draft;
  onClose: () => void;
  onSaved: (msg: string) => Promise<void>;
}) {
  const isCreate = ruleId == null;
  const [draft, setDraft] = useState<Draft>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof Draft>(key: K, value: string) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const invalid = validateDraft(draft, isCreate);
    if (invalid) {
      setError(invalid);
      return;
    }
    setBusy(true);
    setError(null);
    const body: Record<string, unknown> = {
      service_code: draft.service_code.trim(),
      level_id: draft.level_id.trim(),
      base_payout: Number(draft.base_payout),
    };
    if (draft.service_name.trim()) body.service_name = draft.service_name.trim();
    if (draft.night_surcharge_pct.trim()) body.night_surcharge_pct = Number(draft.night_surcharge_pct);
    if (draft.urgent_surcharge_pct.trim()) body.urgent_surcharge_pct = Number(draft.urgent_surcharge_pct);
    if (draft.effective_date) body.effective_date = draft.effective_date;
    if (draft.expiry_date) body.expiry_date = draft.expiry_date;
    try {
      if (isCreate) {
        await api.post(tenantPath("/payout-rules"), { rule_id: draft.rule_id.trim(), ...body });
        await onSaved(`已新增拆帳規則 ${draft.rule_id.trim()}`);
      } else {
        await api.patch(tenantPath(`/payout-rules/${encodeURIComponent(ruleId)}`), body);
        await onSaved(`已更新拆帳規則 ${ruleId}`);
      }
    } catch (err) {
      setError(friendlyError(err));
      setBusy(false);
    }
  }

  const inputCls =
    "h-9 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-[460px] overflow-auto rounded-xl bg-[var(--bg-surface)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            {isCreate ? "新增拆帳規則" : `編輯拆帳規則 ${ruleId}`}
          </h2>
          <button type="button" onClick={onClose} className="rounded p-1 hover:bg-[var(--bg-page)]">
            <X className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>
        </div>

        {error && (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          {isCreate && (
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">規則代碼 *</span>
              <input
                value={draft.rule_id}
                onChange={(e) => set("rule_id", e.target.value)}
                required
                maxLength={60}
                placeholder="例：PAY-SVC-RES-001-A"
                className={`${inputCls} font-mono`}
              />
            </label>
          )}
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">服務代碼 *</span>
            <input
              value={draft.service_code}
              onChange={(e) => set("service_code", e.target.value)}
              required
              maxLength={40}
              placeholder="例：SVC-RES-001"
              className={`${inputCls} font-mono`}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">服務名稱</span>
            <input
              value={draft.service_name}
              onChange={(e) => set("service_name", e.target.value)}
              maxLength={120}
              className={inputCls}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">技師級別 *</span>
            <select
              value={draft.level_id}
              onChange={(e) => set("level_id", e.target.value)}
              className={inputCls}
            >
              {LEVEL_OPTIONS.map((lv) => (
                <option key={lv} value={lv}>
                  {lv}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">基本拆帳（內部成本）*</span>
            <input
              type="number"
              min={0}
              step="0.01"
              value={draft.base_payout}
              onChange={(e) => set("base_payout", e.target.value)}
              required
              className={inputCls}
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">夜間加成率（0~1）</span>
              <input
                type="number"
                min={0}
                max={1}
                step="0.01"
                value={draft.night_surcharge_pct}
                onChange={(e) => set("night_surcharge_pct", e.target.value)}
                placeholder="0.2"
                className={inputCls}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">急件加成率（0~1）</span>
              <input
                type="number"
                min={0}
                max={1}
                step="0.01"
                value={draft.urgent_surcharge_pct}
                onChange={(e) => set("urgent_surcharge_pct", e.target.value)}
                placeholder="0.15"
                className={inputCls}
              />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">生效日</span>
              <input
                type="date"
                value={draft.effective_date}
                onChange={(e) => set("effective_date", e.target.value)}
                className={inputCls}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">失效日</span>
              <input
                type="date"
                value={draft.expiry_date}
                onChange={(e) => set("expiry_date", e.target.value)}
                className={inputCls}
              />
            </label>
          </div>

          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="h-9 rounded-lg border border-[var(--border)] px-4 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={busy}
              className="h-9 rounded-lg bg-[var(--primary)] px-4 text-sm font-semibold text-white disabled:opacity-60"
            >
              {busy ? "儲存中…" : "儲存"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
