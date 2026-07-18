"use client";

import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus, Tag, Trash2, X } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// CR-0110(20260702 會議裁決簡化版):報價主檔三類目 CRUD。
// 一品牌一 DB → 單庫 code 唯一,無 per-tenant 複合鍵;軟刪;編輯後 is_mock=FALSE。

interface Service {
  service_code: string;
  category: string;
  service_name: string;
  service_type: string;
  unit: string;
  internal_base_cost?: string | null;
  suggested_customer_price: string | null;
  decision_status: string;
  is_mock: boolean;
}
interface Material {
  material_code: string;
  category: string;
  material_name: string;
  unit: string;
  internal_cost?: string | null;
  suggested_price: string | null;
  decision_status: string;
}
interface Surcharge {
  rule_code: string;
  rule_type: string;
  rule_name: string;
  amount: string | null;
  value_text: string | null;
  decision_status: string;
}
interface Catalog {
  services: Service[];
  materials: Material[];
  surcharges: Surcharge[];
  cost_visible: boolean;
  note: string;
}

// 服務類型中文標籤（DB service_catalog.service_type 現存值；編輯仍存原始碼，僅顯示翻譯）
const SERVICE_TYPE_LABEL: Record<string, string> = {
  repair: "維修",
  replacement: "更換",
  removal: "拆除",
  inspection: "檢測",
  emergency: "緊急救援",
  destruction: "破壞開啟",
  dispatch: "出勤",
  install: "安裝",
};

// 編輯 modal 的欄位描述(依類目)
type FieldDef = { key: string; label: string; type: "text" | "number"; required?: boolean };

const SERVICE_FIELDS: FieldDef[] = [
  { key: "service_name", label: "服務名稱", type: "text", required: true },
  { key: "service_type", label: "服務類型", type: "text" },
  { key: "category", label: "分類", type: "text" },
  { key: "unit", label: "單位", type: "text" },
  { key: "internal_base_cost", label: "內部成本", type: "number" },
  { key: "suggested_customer_price", label: "建議客價", type: "number" },
];
const MATERIAL_FIELDS: FieldDef[] = [
  { key: "material_name", label: "材料名稱", type: "text", required: true },
  { key: "category", label: "分類", type: "text" },
  { key: "unit", label: "單位", type: "text" },
  { key: "internal_cost", label: "內部成本", type: "number" },
  { key: "suggested_price", label: "建議售價", type: "number" },
];
const SURCHARGE_FIELDS: FieldDef[] = [
  { key: "rule_name", label: "規則名稱", type: "text", required: true },
  { key: "rule_type", label: "規則類型", type: "text" },
  { key: "condition_note", label: "條件說明", type: "text" },
  { key: "amount", label: "金額", type: "number" },
  { key: "value_text", label: "值(文字)", type: "text" },
];

const SEGMENT_META = {
  services: { fields: SERVICE_FIELDS, codeKey: "service_code", title: "服務" },
  materials: { fields: MATERIAL_FIELDS, codeKey: "material_code", title: "材料" },
  surcharges: { fields: SURCHARGE_FIELDS, codeKey: "rule_code", title: "加價規則" },
} as const;

type Segment = keyof typeof SEGMENT_META;

function price(v?: string | null): string {
  if (v == null) return "—";
  return `NT$ ${Math.round(parseFloat(v)).toLocaleString()}`;
}

// UAT P3 內部術語外洩：seed 內少數規則值為英文工程備註，顯示層轉為使用者中文
// （資料層正規化屬另案；此處僅收斂已知字串，未知值原樣顯示）
function friendlyValueText(v: string | null): string | null {
  if (!v) return v;
  if (v.includes("50% from the final quote")) {
    return "最終報價金額之 50%（計算方式待確認）";
  }
  return v;
}

export default function QuoteCatalogPage() {
  const t = useTranslations("admin.quoteCatalog");
  const [cat, setCat] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  // modal 狀態:segment + code(null=新增)+ 初始值
  const [editing, setEditing] = useState<{
    segment: Segment;
    code: string | null;
    initial: Record<string, unknown>;
  } | null>(null);

  const fetchCatalog = useCallback(async () => {
    try {
      const res = await api.get<Catalog>(tenantPath("/quote-catalog"));
      setCat(res);
    } catch (e) {
      setError(friendlyError(e));
    }
  }, []);

  useEffect(() => {
    fetchCatalog();
  }, [fetchCatalog]);

  async function handleDelete(segment: Segment, code: string) {
    if (!window.confirm(`確定刪除 ${code}?(軟刪,可由工程端復原)`)) return;
    setError(null);
    try {
      await api.delete(tenantPath(`/quote-catalog/${segment}/${encodeURIComponent(code)}`));
      cacheInvalidate("GET:");
      await fetchCatalog();
    } catch (e) {
      setError(friendlyError(e));
    }
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <Tag className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          {!cat ? (
            <p className="text-sm text-[var(--text-secondary)]">{t("loading")}</p>
          ) : (
            <div className="flex flex-col gap-8">
              {/* 服務 */}
              <Section
                title={t("services", { n: cat.services.length })}
                onAdd={() => setEditing({ segment: "services", code: null, initial: {} })}
              >
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("code")}</th>
                      <th className="px-3 py-2 text-left">{t("name")}</th>
                      <th className="px-3 py-2 text-left">{t("type")}</th>
                      {cat.cost_visible && <th className="px-3 py-2 text-right">{t("cost")}</th>}
                      <th className="px-3 py-2 text-right">{t("custPrice")}</th>
                      <th className="w-[90px] px-3 py-2 text-right">{t("actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cat.services.map((s) => (
                      <tr key={s.service_code} className="border-t border-[var(--border)]">
                        <td className="px-3 py-2 font-mono text-[12px] text-[var(--text-secondary)]">{s.service_code}</td>
                        <td className="px-3 py-2 text-[var(--text-primary)]">{s.service_name}</td>
                        <td className="px-3 py-2 text-[var(--text-secondary)]">{SERVICE_TYPE_LABEL[s.service_type] ?? s.service_type}</td>
                        {cat.cost_visible && <td className="px-3 py-2 text-right font-mono text-[var(--text-disabled)]">{price(s.internal_base_cost)}</td>}
                        <td className="px-3 py-2 text-right font-mono font-medium text-[var(--text-primary)]">{price(s.suggested_customer_price)}</td>
                        <RowActions
                          onEdit={() =>
                            setEditing({
                              segment: "services",
                              code: s.service_code,
                              initial: {
                                service_name: s.service_name,
                                service_type: s.service_type,
                                category: s.category,
                                unit: s.unit,
                                internal_base_cost: s.internal_base_cost,
                                suggested_customer_price: s.suggested_customer_price,
                              },
                            })
                          }
                          onDelete={() => handleDelete("services", s.service_code)}
                        />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Section>

              {/* 材料 */}
              <Section
                title={t("materials", { n: cat.materials.length })}
                onAdd={() => setEditing({ segment: "materials", code: null, initial: {} })}
              >
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("code")}</th>
                      <th className="px-3 py-2 text-left">{t("name")}</th>
                      {cat.cost_visible && <th className="px-3 py-2 text-right">{t("cost")}</th>}
                      <th className="px-3 py-2 text-right">{t("custPrice")}</th>
                      <th className="w-[90px] px-3 py-2 text-right">{t("actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cat.materials.map((m) => (
                      <tr key={m.material_code} className="border-t border-[var(--border)]">
                        <td className="px-3 py-2 font-mono text-[12px] text-[var(--text-secondary)]">{m.material_code}</td>
                        <td className="px-3 py-2 text-[var(--text-primary)]">{m.material_name}</td>
                        {cat.cost_visible && <td className="px-3 py-2 text-right font-mono text-[var(--text-disabled)]">{price(m.internal_cost)}</td>}
                        <td className="px-3 py-2 text-right font-mono font-medium text-[var(--text-primary)]">{price(m.suggested_price)}</td>
                        <RowActions
                          onEdit={() =>
                            setEditing({
                              segment: "materials",
                              code: m.material_code,
                              initial: {
                                material_name: m.material_name,
                                category: m.category,
                                unit: m.unit,
                                internal_cost: m.internal_cost,
                                suggested_price: m.suggested_price,
                              },
                            })
                          }
                          onDelete={() => handleDelete("materials", m.material_code)}
                        />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Section>

              {/* 加價/取消費規則 */}
              <Section
                title={t("surcharges", { n: cat.surcharges.length })}
                onAdd={() => setEditing({ segment: "surcharges", code: null, initial: {} })}
              >
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("ruleType")}</th>
                      <th className="px-3 py-2 text-left">{t("name")}</th>
                      <th className="px-3 py-2 text-left">{t("value")}</th>
                      <th className="px-3 py-2 text-left">{t("status")}</th>
                      <th className="w-[90px] px-3 py-2 text-right">{t("actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cat.surcharges.map((r) => (
                      <tr key={r.rule_code} className="border-t border-[var(--border)]">
                        <td className="px-3 py-2 text-[var(--text-secondary)]">{r.rule_type}</td>
                        <td className="px-3 py-2 text-[var(--text-primary)]">{r.rule_name}</td>
                        <td className="px-3 py-2 font-mono text-[var(--text-primary)]">{r.amount != null ? price(r.amount) : friendlyValueText(r.value_text)}</td>
                        <td className="px-3 py-2">
                          <span className={`rounded px-2 py-[2px] text-[11px] ${["已知規格", "已確認"].includes(r.decision_status) ? "bg-[#DCFCE7] text-[#15803D]" : "bg-[#FEF3C7] text-[#92400E]"}`}>
                            {r.decision_status}
                          </span>
                        </td>
                        <RowActions
                          onEdit={() =>
                            setEditing({
                              segment: "surcharges",
                              code: r.rule_code,
                              initial: {
                                rule_name: r.rule_name,
                                rule_type: r.rule_type,
                                amount: r.amount,
                                value_text: r.value_text,
                              },
                            })
                          }
                          onDelete={() => handleDelete("surcharges", r.rule_code)}
                        />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Section>

              {/* UAT P3 內部術語外洩：後端 note 為工程備註（esales mock 等），不對使用者顯示 */}
              <p className="text-[12px] text-[var(--text-disabled)]">
                標示「待決策」的項目代表正式價格尚未由品牌方核定，報價時請以最新核定值為準。
              </p>
            </div>
          )}
        </div>
      </div>

      {editing && (
        <EditModal
          segment={editing.segment}
          code={editing.code}
          initial={editing.initial}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            cacheInvalidate("GET:");
            await fetchCatalog();
          }}
        />
      )}
    </div>
  );
}

function RowActions({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <td className="px-3 py-2 text-right">
      <div className="flex justify-end gap-1">
        <button
          type="button"
          onClick={onEdit}
          title="編輯"
          className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)] hover:text-[var(--primary)]"
        >
          <Pencil className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          title="刪除"
          className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)] hover:text-red-600"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </td>
  );
}

function EditModal({
  segment,
  code,
  initial,
  onClose,
  onSaved,
}: {
  segment: Segment;
  code: string | null;
  initial: Record<string, unknown>;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const meta = SEGMENT_META[segment];
  const isCreate = code == null;
  const [newCode, setNewCode] = useState("");
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      meta.fields.map((f) => [f.key, initial[f.key] != null ? String(initial[f.key]) : ""]),
    ),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {};
      for (const f of meta.fields) {
        const raw = values[f.key]?.trim();
        if (!raw) continue;
        body[f.key] = f.type === "number" ? Number(raw) : raw;
      }
      if (isCreate) {
        await api.post(tenantPath(`/quote-catalog/${segment}`), { code: newCode.trim(), ...body });
      } else {
        await api.patch(tenantPath(`/quote-catalog/${segment}/${encodeURIComponent(code)}`), body);
      }
      await onSaved();
    } catch (err) {
      setError(friendlyError(err));
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-[420px] rounded-xl bg-[var(--bg-surface)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            {isCreate ? `新增${meta.title}` : `編輯${meta.title} ${code}`}
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
              <span className="text-[var(--text-secondary)]">代碼 *</span>
              <input
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
                required
                maxLength={40}
                placeholder="例:SVC-CUSTOM-001"
                className="h-9 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 font-mono text-sm"
              />
            </label>
          )}
          {meta.fields.map((f) => (
            <label key={f.key} className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">
                {f.label}
                {f.required ? " *" : ""}
              </span>
              <input
                type={f.type === "number" ? "number" : "text"}
                min={f.type === "number" ? 0 : undefined}
                step={f.type === "number" ? "0.01" : undefined}
                value={values[f.key] ?? ""}
                onChange={(e) => setValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                required={!!f.required}
                className="h-9 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm"
              />
            </label>
          ))}

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

function Section({
  title,
  onAdd,
  children,
}: {
  title: string;
  onAdd: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">{title}</h2>
        <button
          type="button"
          onClick={onAdd}
          className="flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-[6px] text-[13px] font-medium text-[var(--primary)] hover:bg-[var(--primary-light)]"
        >
          <Plus className="h-4 w-4" />
          新增
        </button>
      </div>
      <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">{children}</div>
    </section>
  );
}
