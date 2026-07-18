"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ClipboardList,
  Pencil,
  Check,
  X,
  ShieldCheck,
  PenLine,
} from "lucide-react";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { TranslateFn } from "@/lib/translate";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];

/**
 * DispatchOrderView — 標準化派工單 6 模組視圖（CR-0091）。
 *
 * 依「電子鎖安裝與維修派工單整合分析報告.pdf」6 大模組組織既有 work_orders 欄位，
 * 模組 1/2/3/5 的標準化欄位可內嵌編輯（PATCH /work-orders/{id}/fields，CR-0026/0043/0047
 * 缺的編輯 UI），模組 4 免責同意串 admin 唯讀 GET，模組 5 計費沿用 quote-items，
 * 模組 6 簽認顯示狀態。UAT W6-1：label 全數接 i18n
 * （namespace: components.workOrders.dispatchOrder）。
 */

// i18n namespace（本檔所有 label 的字典位置）
const NS = "components.workOrders.dispatchOrder";

// enum 值域（label 由 i18n enums.* 解析；此處只留合法值供 <select> 產生選項）
const ENUM_VALUES: Record<string, string[]> = {
  serviceCategory: ["install", "warranty_in", "warranty_out", "repair"],
  warrantyStatus: ["in_warranty", "out_warranty", "not_applicable"],
  rainExposure: ["indoor", "outdoor_covered", "outdoor_exposed"],
  paymentMethod: ["cash", "bank_transfer", "credit_card", "line_pay"],
  doorType: ["iron", "wood", "steel", "other"],
};

type FieldType = "text" | "select" | "date" | "bool" | "number";
interface FieldDef {
  key: string; // WorkOrderFieldsPatchRequest 欄位（label = t(`fields.${key}`)）
  type: FieldType;
  enumKey?: keyof typeof ENUM_VALUES & string;
  suffix?: string;
}

// 可編輯欄位（嚴格對齊後端 WorkOrderFieldsPatchRequest 白名單）
const M1_FIELDS: FieldDef[] = [
  { key: "customer_name", type: "text" },
  { key: "customer_phone", type: "text" },
  { key: "customer_address", type: "text" },
];
const M2_FIELDS: FieldDef[] = [
  { key: "brand", type: "text" },
  { key: "model", type: "text" },
  { key: "serial_number", type: "text" },
  { key: "dealer", type: "text" },
  { key: "install_date", type: "date" },
  { key: "purchase_date", type: "date" },
  { key: "rain_exposure", type: "select", enumKey: "rainExposure" },
  { key: "door_type", type: "select", enumKey: "doorType" },
  { key: "door_thickness", type: "text", suffix: "mm" },
  { key: "is_interior_door", type: "bool" },
];
const M3_FIELDS: FieldDef[] = [
  { key: "service_category", type: "select", enumKey: "serviceCategory" },
  // UAT N2：派工前置閘要求問題類型——由唯讀（問題卡帶入）改為可編輯，
  // 缺欄單（含手建卡急件）才有路補齊過閘（後端 PATCH 白名單同步開放）
  { key: "problem_type", type: "text" },
  { key: "warranty_status", type: "select", enumKey: "warrantyStatus" },
];
const M5_FIELDS: FieldDef[] = [
  { key: "payment_method", type: "select", enumKey: "paymentMethod" },
  { key: "invoice_no", type: "text" },
  { key: "special_door_surcharge", type: "bool" },
];

const ALL_EDITABLE = [...M1_FIELDS, ...M2_FIELDS, ...M3_FIELDS, ...M5_FIELDS];

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  return v.slice(0, 10);
}
function fmtPrice(v?: string | null): string {
  if (v == null) return "—";
  const n = parseFloat(v);
  return Number.isNaN(n) ? "—" : `NT$ ${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
/** enum 值 → i18n label；字典缺該值時 fallback 原始碼（translate 缺 key 會回傳 path） */
function enumLabel(t: TranslateFn, enumKey: string, raw: string): string {
  const path = `enums.${enumKey}.${raw}`;
  const v = t(path);
  return v.endsWith(path) ? raw : v;
}
function displayValue(order: WorkOrder, f: FieldDef, t: TranslateFn): string {
  const raw = (order as Record<string, unknown>)[f.key];
  if (f.type === "bool") return raw ? t("boolYes") : t("boolNo");
  if (raw == null || raw === "") return "—";
  if (f.type === "date") return fmtDate(String(raw));
  if (f.enumKey) return enumLabel(t, f.enumKey, String(raw));
  return `${raw}${f.suffix ? ` ${f.suffix}` : ""}`;
}

interface Props {
  order: WorkOrder | null;
  onUpdated: (wo: WorkOrder) => void;
}

export default function DispatchOrderView({ order, onUpdated }: Props) {
  const t = useTranslations(NS);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = useCallback(() => {
    if (!order) return;
    const d: Record<string, unknown> = {};
    for (const f of ALL_EDITABLE) d[f.key] = (order as Record<string, unknown>)[f.key] ?? "";
    setDraft(d);
    setError(null);
    setEditing(true);
  }, [order]);

  const save = useCallback(async () => {
    if (!order) return;
    // 只送有變動的欄位（patch exclude_unset 語意）
    const body: Record<string, unknown> = {};
    for (const f of ALL_EDITABLE) {
      const orig = (order as Record<string, unknown>)[f.key] ?? (f.type === "bool" ? false : "");
      let next = draft[f.key];
      if (f.type === "bool") next = !!next;
      if (next === "") next = null;
      const origNorm = orig === "" ? null : orig;
      if (JSON.stringify(next) !== JSON.stringify(origNorm)) body[f.key] = next;
    }
    if (Object.keys(body).length === 0) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await api.patch<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(order.id)}/fields`),
        body,
      );
      if (res.data) onUpdated(res.data);
      setEditing(false);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setSaving(false);
    }
  }, [order, draft, onUpdated]);

  if (!order) return null;

  return (
    <div className="mx-8 my-4 flex flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-[var(--primary)]" />
          <h2 className="text-[17px] font-bold text-[var(--text-primary)]">{t("title")}</h2>
          <span className="text-[12px] text-[var(--text-secondary)]">{t("subtitle")}</span>
        </div>
        {!editing ? (
          <button
            onClick={startEdit}
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--primary)] px-3 py-1.5 text-[13px] font-semibold text-[var(--primary)] hover:bg-[var(--primary-light)]"
          >
            <Pencil className="h-4 w-4" /> {t("editFields")}
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50"
            >
              <Check className="h-4 w-4" /> {saving ? t("saving") : t("save")}
            </button>
            <button
              onClick={() => setEditing(false)}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 text-[13px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              <X className="h-4 w-4" /> {t("cancel")}
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}

      <ModuleSection n={1} title={t("modules.m1")}>
        <FieldGrid order={order} fields={M1_FIELDS} editing={editing} draft={draft} setDraft={setDraft} />
        <ReadOnlyRow label={t("readonly.scheduledDate")} value={fmtDate(order.scheduled_time)} hint={t("readonly.scheduledHint")} />
      </ModuleSection>

      <ModuleSection n={2} title={t("modules.m2")}>
        <FieldGrid order={order} fields={M2_FIELDS} editing={editing} draft={draft} setDraft={setDraft} />
      </ModuleSection>

      <ModuleSection n={3} title={t("modules.m3")}>
        <FieldGrid order={order} fields={M3_FIELDS} editing={editing} draft={draft} setDraft={setDraft} />
        <ReadOnlyRow
          label={t("readonly.warrantyExpiry")}
          value={fmtDate(order.warranty_expiry_date)}
          hint={t("readonly.warrantyExpiryHint")}
        />
        <ReadOnlyRow
          label={t("readonly.completionStatus")}
          value={order.completion_status ? enumLabel(t, "completionStatus", order.completion_status) : "—"}
          hint={t("readonly.completionHint")}
        />
        {order.status_reason && <ReadOnlyRow label={t("readonly.statusReason")} value={order.status_reason} />}
      </ModuleSection>

      <ModuleSection n={4} title={t("modules.m4")}>
        <ConsentPanel workOrderId={order.id} />
      </ModuleSection>

      <ModuleSection n={5} title={t("modules.m5")}>
        <FieldGrid order={order} fields={M5_FIELDS} editing={editing} draft={draft} setDraft={setDraft} />
        <BillingPanel workOrderId={order.id} finalAmount={order.customer_final_amount} />
      </ModuleSection>

      <ModuleSection n={6} title={t("modules.m6")}>
        <SignaturePanel order={order} />
      </ModuleSection>
    </div>
  );
}

function ModuleSection({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    // UAT W6-3：模組卡底色改 semantic token（原硬編碼 #FBFCFE 淺色，
    // 深色模式下文字 token 翻亮 → 白底近白字對比 1.04:1 不可讀）
    <section className="flex flex-col gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] p-4">
      <h3 className="flex items-center gap-2 text-[14px] font-semibold text-[var(--text-primary)]">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--primary)] text-[11px] font-bold text-white">
          {n}
        </span>
        {title}
      </h3>
      <div className="flex flex-col gap-2 pl-7">{children}</div>
    </section>
  );
}

function FieldGrid({
  order,
  fields,
  editing,
  draft,
  setDraft,
}: {
  order: WorkOrder;
  fields: FieldDef[];
  editing: boolean;
  draft: Record<string, unknown>;
  setDraft: (updater: (prev: Record<string, unknown>) => Record<string, unknown>) => void;
}) {
  const t = useTranslations(NS);
  return (
    <div className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
      {fields.map((f) => (
        <div key={f.key} className="flex items-center justify-between gap-3">
          <span className="text-[13px] text-[var(--text-secondary)]">{t(`fields.${f.key}`)}</span>
          {editing ? (
            <FieldInput f={f} value={draft[f.key]} onChange={(v) => setDraft((p) => ({ ...p, [f.key]: v }))} />
          ) : (
            <span className="text-right text-[13px] font-medium text-[var(--text-primary)]">
              {displayValue(order, f, t)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function FieldInput({ f, value, onChange }: { f: FieldDef; value: unknown; onChange: (v: unknown) => void }) {
  const t = useTranslations(NS);
  // bg/text 用 semantic token：深色模式下不繼承淺色卡底（UAT W6-3）
  const cls =
    "w-[180px] rounded border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1 text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none";
  if (f.type === "bool") {
    return (
      <input
        type="checkbox"
        checked={!!value}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4"
      />
    );
  }
  if (f.type === "select" && f.enumKey) {
    return (
      <select value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} className={cls}>
        <option value="">—</option>
        {ENUM_VALUES[f.enumKey].map((v) => (
          <option key={v} value={v}>
            {enumLabel(t, f.enumKey!, v)}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      type={f.type === "date" ? "date" : "text"}
      value={String(value ?? "").slice(0, f.type === "date" ? 10 : undefined)}
      onChange={(e) => onChange(e.target.value)}
      className={cls}
    />
  );
}

function ReadOnlyRow({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[13px] text-[var(--text-secondary)]">
        {label}
        {hint && <span className="ml-1 text-[11px] text-[var(--text-disabled)]">{hint}</span>}
      </span>
      <span className="text-right text-[13px] font-medium text-[var(--text-primary)]">{value}</span>
    </div>
  );
}

// ── 模組 4：免責同意（admin 唯讀 GET，CR-0091）──
interface ConsentItem {
  consent_type: string;
  title: string;
  accepted: boolean;
  accepted_at?: string | null;
}
function ConsentPanel({ workOrderId }: { workOrderId: string }) {
  const t = useTranslations(NS);
  const [items, setItems] = useState<ConsentItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ consents: ConsentItem[] }>(
          tenantPath(`/work-orders/${encodeURIComponent(workOrderId)}/consents`),
        );
        if (!cancelled) setItems(res.consents ?? []);
      } catch (e) {
        if (!cancelled) setError(friendlyError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workOrderId]);

  if (error) return <span className="text-[12px] text-[var(--text-disabled)]">{error}</span>;
  if (!items) return <span className="text-[13px] text-[var(--text-secondary)]">{t("consent.loading")}</span>;

  return (
    <div className="flex flex-col gap-2">
      {items.map((c) => {
        const label = t(`consent.labels.${c.consent_type}`);
        return (
          <div key={c.consent_type} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-1.5 text-[13px] text-[var(--text-secondary)]">
              <ShieldCheck className="h-4 w-4 text-[var(--text-disabled)]" />
              {label.endsWith(`consent.labels.${c.consent_type}`) ? c.title : label}
            </span>
            {c.accepted ? (
              <span className="rounded bg-[#DCFCE7] px-2 py-[2px] text-[12px] font-medium text-[#15803D]">
                {t("consent.accepted")}
                {c.accepted_at ? ` · ${fmtDate(c.accepted_at)}` : ""}
              </span>
            ) : (
              <span className="rounded bg-[#FEF3C7] px-2 py-[2px] text-[12px] text-[#92400E]">{t("consent.awaitingSign")}</span>
            )}
          </div>
        );
      })}
      <span className="text-[11px] text-[var(--text-disabled)]">{t("consent.note")}</span>
    </div>
  );
}

// ── 模組 5：計費明細（沿用 quote-items）──
interface QuoteLine {
  id: string;
  item_name: string;
  quantity: number;
  customer_price: string | null;
}
function BillingPanel({ workOrderId, finalAmount }: { workOrderId: string; finalAmount?: string | null }) {
  const t = useTranslations(NS);
  const [items, setItems] = useState<QuoteLine[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ items: QuoteLine[] }>(
          tenantPath(`/work-orders/${encodeURIComponent(workOrderId)}/quote-items`),
        );
        if (!cancelled) setItems(res.items ?? []);
      } catch (e) {
        if (!cancelled) setError(friendlyError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workOrderId]);

  return (
    <div className="mt-1 flex flex-col gap-1.5 border-t border-[var(--border)] pt-2">
      <span className="text-[12px] font-semibold text-[var(--text-secondary)]">{t("billing.title")}</span>
      {error ? (
        <span className="text-[12px] text-[var(--text-disabled)]">{error}</span>
      ) : !items ? (
        <span className="text-[13px] text-[var(--text-secondary)]">{t("billing.loading")}</span>
      ) : items.length === 0 ? (
        <span className="text-[13px] text-[var(--text-disabled)]">{t("billing.empty")}</span>
      ) : (
        items.map((it) => (
          <div key={it.id} className="flex items-center justify-between text-[13px]">
            <span className="text-[var(--text-secondary)]">
              {it.item_name} ×{it.quantity}
            </span>
            <span className="font-mono font-medium text-[var(--text-primary)]">{fmtPrice(it.customer_price)}</span>
          </div>
        ))
      )}
      <div className="flex items-center justify-between border-t border-[var(--border)] pt-1.5">
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">{t("billing.total")}</span>
        <span className="font-mono text-[14px] font-bold text-[var(--text-primary)]">{fmtPrice(finalAmount)}</span>
      </div>
    </div>
  );
}

// ── 模組 6：雙方簽認（狀態顯示；簽名動作走頁面既有簽名鈕）──
function SignaturePanel({ order }: { order: WorkOrder }) {
  const t = useTranslations(NS);
  const signed = ["completed", "confirmed", "closed"].includes(order.status ?? "");
  const customerConfirmed = ["confirmed", "closed"].includes(order.status ?? "");
  const row = (label: string, done: boolean) => (
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-1.5 text-[13px] text-[var(--text-secondary)]">
        <PenLine className="h-4 w-4 text-[var(--text-disabled)]" />
        {label}
      </span>
      <span
        className={
          done
            ? "rounded bg-[#DCFCE7] px-2 py-[2px] text-[12px] font-medium text-[#15803D]"
            : // 前景/背景成對硬編碼（避免 bg 硬編碼＋text token 在深色模式脫鉤，UAT W6-3）
              "rounded bg-[#F1F5F9] px-2 py-[2px] text-[12px] text-[#475569]"
        }
      >
        {done ? t("signature.signed") : t("signature.awaiting")}
      </span>
    </div>
  );
  return (
    <div className="flex flex-col gap-2">
      {row(t("signature.engineer"), signed)}
      {row(t("signature.customer"), customerConfirmed)}
      <span className="text-[11px] text-[var(--text-disabled)]">{t("signature.note")}</span>
    </div>
  );
}
