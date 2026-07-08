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
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import type { components } from "@shared/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];

/**
 * DispatchOrderView — 標準化派工單 6 模組視圖（CR-0091）。
 *
 * 依「電子鎖安裝與維修派工單整合分析報告.pdf」6 大模組組織既有 work_orders 欄位，
 * 模組 1/2/3/5 的標準化欄位可內嵌編輯（PATCH /work-orders/{id}/fields，CR-0026/0043/0047
 * 缺的編輯 UI），模組 4 免責同意串 admin 唯讀 GET，模組 5 計費沿用 quote-items，
 * 模組 6 簽認顯示狀態。label 採繁中（對齊 WorkOrderDetailSidebar 既有硬編慣例）。
 */

// ── enum → 繁中（與 WorkOrderDetailSidebar 對齊）──
const SERVICE_CATEGORY: Record<string, string> = {
  install: "安裝新機",
  warranty_in: "保固內維修",
  warranty_out: "保固外維修",
  repair: "維修",
};
const WARRANTY_STATUS: Record<string, string> = {
  in_warranty: "保固內",
  out_warranty: "保固外",
  not_applicable: "不適用",
};
const RAIN_EXPOSURE: Record<string, string> = {
  indoor: "室內",
  outdoor_covered: "室外有遮雨",
  outdoor_exposed: "室外無遮雨",
};
const PAYMENT_METHOD: Record<string, string> = {
  cash: "現金",
  bank_transfer: "轉帳",
  credit_card: "刷卡",
  line_pay: "LINE Pay",
};
const DOOR_TYPE: Record<string, string> = {
  iron: "鐵門",
  wood: "木門",
  steel: "鋼門",
  other: "其它",
};
const COMPLETION_STATUS: Record<string, string> = {
  pending_report: "待完工回報",
  pending_photos: "待照片",
  pending_customer_confirm: "待客戶確認",
  pending_cs_review: "待客服審核",
  completed: "已完工",
  closed: "已結案",
};

type FieldType = "text" | "select" | "date" | "bool" | "number";
interface FieldDef {
  key: string; // WorkOrderFieldsPatchRequest 欄位
  label: string;
  type: FieldType;
  enumMap?: Record<string, string>;
  suffix?: string;
}

// 可編輯欄位（嚴格對齊後端 WorkOrderFieldsPatchRequest 白名單）
const M1_FIELDS: FieldDef[] = [
  { key: "customer_name", label: "客戶名稱", type: "text" },
  { key: "customer_phone", label: "聯絡電話", type: "text" },
  { key: "customer_address", label: "服務地址", type: "text" },
];
const M2_FIELDS: FieldDef[] = [
  { key: "brand", label: "品牌", type: "text" },
  { key: "model", label: "產品型號", type: "text" },
  { key: "serial_number", label: "產品序號 (S/N)", type: "text" },
  { key: "dealer", label: "購買地點 / 經銷商", type: "text" },
  { key: "install_date", label: "安裝日期", type: "date" },
  { key: "purchase_date", label: "購買日期", type: "date" },
  { key: "rain_exposure", label: "安裝環境與遮雨", type: "select", enumMap: RAIN_EXPOSURE },
  { key: "door_type", label: "門扇材質", type: "select", enumMap: DOOR_TYPE },
  { key: "door_thickness", label: "門厚", type: "text", suffix: "mm" },
  { key: "is_interior_door", label: "室內門", type: "bool" },
];
const M3_FIELDS: FieldDef[] = [
  { key: "service_category", label: "服務類別", type: "select", enumMap: SERVICE_CATEGORY },
  { key: "warranty_status", label: "保固狀態", type: "select", enumMap: WARRANTY_STATUS },
];
const M5_FIELDS: FieldDef[] = [
  { key: "payment_method", label: "付款方式", type: "select", enumMap: PAYMENT_METHOD },
  { key: "invoice_no", label: "發票號碼", type: "text" },
  { key: "special_door_surcharge", label: "特殊門型加價", type: "bool" },
];

const ALL_EDITABLE = [...M1_FIELDS, ...M2_FIELDS, ...M3_FIELDS, ...M5_FIELDS];

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  return v.slice(0, 10);
}
function fmtPrice(v?: string | null): string {
  if (v == null) return "—";
  const n = parseFloat(v);
  return Number.isNaN(n) ? "—" : `NT$ ${n.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}`;
}
function displayValue(order: WorkOrder, f: FieldDef): string {
  const raw = (order as Record<string, unknown>)[f.key];
  if (f.type === "bool") return raw ? "是" : "否";
  if (raw == null || raw === "") return "—";
  if (f.type === "date") return fmtDate(String(raw));
  if (f.enumMap) return f.enumMap[String(raw)] ?? String(raw);
  return `${raw}${f.suffix ? ` ${f.suffix}` : ""}`;
}

interface Props {
  order: WorkOrder | null;
  onUpdated: (wo: WorkOrder) => void;
}

export default function DispatchOrderView({ order, onUpdated }: Props) {
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
          <h2 className="text-[17px] font-bold text-[var(--text-primary)]">標準化派工單</h2>
          <span className="text-[12px] text-[var(--text-secondary)]">（6 模組）</span>
        </div>
        {!editing ? (
          <button
            onClick={startEdit}
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--primary)] px-3 py-1.5 text-[13px] font-semibold text-[var(--primary)] hover:bg-[var(--primary-light)]"
          >
            <Pencil className="h-4 w-4" /> 編輯欄位
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50"
            >
              <Check className="h-4 w-4" /> {saving ? "儲存中…" : "儲存"}
            </button>
            <button
              onClick={() => setEditing(false)}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 text-[13px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              <X className="h-4 w-4" /> 取消
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}

      <ModuleSection n={1} title="基礎案件資訊">
        <FieldGrid order={order} fields={M1_FIELDS} editing={editing} draft={draft} setDraft={setDraft} />
        <ReadOnlyRow label="維修／施工日期" value={fmtDate(order.scheduled_time)} hint="（由排程管理）" />
      </ModuleSection>

      <ModuleSection n={2} title="設備與環境辨識">
        <FieldGrid order={order} fields={M2_FIELDS} editing={editing} draft={draft} setDraft={setDraft} />
      </ModuleSection>

      <ModuleSection n={3} title="工單類型與狀態">
        <FieldGrid order={order} fields={M3_FIELDS} editing={editing} draft={draft} setDraft={setDraft} />
        <ReadOnlyRow label="維修原因 / 狀況" value={order.problem_type || "—"} hint="（源自問題卡）" />
        <ReadOnlyRow
          label="保固到期日"
          value={fmtDate(order.warranty_expiry_date)}
          hint="（輸入序號/購買日後自動計算）"
        />
        <ReadOnlyRow
          label="完工狀態"
          value={order.completion_status ? COMPLETION_STATUS[order.completion_status] ?? order.completion_status : "—"}
          hint="（由完工流程管理）"
        />
        {order.status_reason && <ReadOnlyRow label="狀態原因" value={order.status_reason} />}
      </ModuleSection>

      <ModuleSection n={4} title="施工免責與合規">
        <ConsentPanel workOrderId={order.id} />
      </ModuleSection>

      <ModuleSection n={5} title="多維度計費核銷">
        <FieldGrid order={order} fields={M5_FIELDS} editing={editing} draft={draft} setDraft={setDraft} />
        <BillingPanel workOrderId={order.id} finalAmount={order.customer_final_amount} />
      </ModuleSection>

      <ModuleSection n={6} title="雙方責任簽認">
        <SignaturePanel order={order} />
      </ModuleSection>
    </div>
  );
}

function ModuleSection({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-[var(--border)] bg-[#FBFCFE] p-4">
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
  return (
    <div className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
      {fields.map((f) => (
        <div key={f.key} className="flex items-center justify-between gap-3">
          <span className="text-[13px] text-[var(--text-secondary)]">{f.label}</span>
          {editing ? (
            <FieldInput f={f} value={draft[f.key]} onChange={(v) => setDraft((p) => ({ ...p, [f.key]: v }))} />
          ) : (
            <span className="text-right text-[13px] font-medium text-[var(--text-primary)]">
              {displayValue(order, f)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function FieldInput({ f, value, onChange }: { f: FieldDef; value: unknown; onChange: (v: unknown) => void }) {
  const cls =
    "w-[180px] rounded border border-[var(--border)] px-2 py-1 text-[13px] focus:border-[var(--primary)] focus:outline-none";
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
  if (f.type === "select" && f.enumMap) {
    return (
      <select value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} className={cls}>
        <option value="">—</option>
        {Object.entries(f.enumMap).map(([v, label]) => (
          <option key={v} value={v}>
            {label}
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
const CONSENT_LABEL: Record<string, string> = {
  new_installation: "新機安裝同意聲明",
  lock_destruction: "破壞鎖施工免責特別說明",
  personal_data: "個人資料保護法條款",
};
function ConsentPanel({ workOrderId }: { workOrderId: string }) {
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
  if (!items) return <span className="text-[13px] text-[var(--text-secondary)]">載入中…</span>;

  return (
    <div className="flex flex-col gap-2">
      {items.map((c) => (
        <div key={c.consent_type} className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-[13px] text-[var(--text-secondary)]">
            <ShieldCheck className="h-4 w-4 text-[var(--text-disabled)]" />
            {CONSENT_LABEL[c.consent_type] ?? c.title}
          </span>
          {c.accepted ? (
            <span className="rounded bg-[#DCFCE7] px-2 py-[2px] text-[12px] font-medium text-[#15803D]">
              已同意{c.accepted_at ? ` · ${fmtDate(c.accepted_at)}` : ""}
            </span>
          ) : (
            <span className="rounded bg-[#FEF3C7] px-2 py-[2px] text-[12px] text-[#92400E]">待客戶簽署</span>
          )}
        </div>
      ))}
      <span className="text-[11px] text-[var(--text-disabled)]">客戶簽署透過 LINE 免責連結，本頁僅顯示狀態。</span>
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
      <span className="text-[12px] font-semibold text-[var(--text-secondary)]">費用明細</span>
      {error ? (
        <span className="text-[12px] text-[var(--text-disabled)]">{error}</span>
      ) : !items ? (
        <span className="text-[13px] text-[var(--text-secondary)]">載入中…</span>
      ) : items.length === 0 ? (
        <span className="text-[13px] text-[var(--text-disabled)]">尚無計費明細</span>
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
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">總計金額</span>
        <span className="font-mono text-[14px] font-bold text-[var(--text-primary)]">{fmtPrice(finalAmount)}</span>
      </div>
    </div>
  );
}

// ── 模組 6：雙方簽認（狀態顯示；簽名動作走頁面既有簽名鈕）──
function SignaturePanel({ order }: { order: WorkOrder }) {
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
            : "rounded bg-[#F1F5F9] px-2 py-[2px] text-[12px] text-[var(--text-secondary)]"
        }
      >
        {done ? "已簽認" : "待簽認"}
      </span>
    </div>
  );
  return (
    <div className="flex flex-col gap-2">
      {row("工程師簽名", signed)}
      {row("客戶驗收簽名", customerConfirmed)}
      <span className="text-[11px] text-[var(--text-disabled)]">簽名動作透過上方「簽名」按鈕；此處依工單狀態顯示。</span>
    </div>
  );
}
