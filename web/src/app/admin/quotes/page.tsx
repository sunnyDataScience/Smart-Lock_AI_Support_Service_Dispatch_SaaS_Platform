"use client";

import { useEffect, useState } from "react";
import { FileText, Plus } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api, tenantPath } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";

interface CatalogItem {
  code: string;
  name: string;
  price: string | null;
}
interface QuoteLine {
  id: string;
  item_name: string;
  category: string;
  quantity: number;
  customer_price: string | null;
  unit_price?: string | null;
  service_code: string | null;
  material_code: string | null;
}
interface Quote {
  id: string;
  work_order_id: string | null;
  version: number;
  state: string;
  total_amount: string | null;
  expiry_at: string | null;
  snapshot_hash: string | null;
  is_mock: boolean;
  lines: QuoteLine[];
  cost_visible: boolean;
  public_path?: string | null; // 送客戶後回傳的客戶端查看連結（CR-0032 Phase C）
}

const STATE_COLORS: Record<string, string> = {
  draft: "bg-[#E2E8F0] text-[#475569]",
  pending_approval: "bg-[#FEF3C7] text-[#92400E]",
  approved: "bg-[#DBEAFE] text-[#1E40AF]",
  sent: "bg-[#E0E7FF] text-[#4338CA]",
  accepted: "bg-[#DCFCE7] text-[#15803D]",
  rejected: "bg-[#FEE2E2] text-[#B91C1C]",
  expired: "bg-[#F1F5F9] text-[#94A3B8]",
};

function price(v?: string | null): string {
  if (v == null) return "—";
  return `NT$ ${Math.round(parseFloat(v)).toLocaleString()}`;
}

export default function QuotesPage() {
  const t = useTranslations("admin.quotes");
  const [services, setServices] = useState<CatalogItem[]>([]);
  const [materials, setMaterials] = useState<CatalogItem[]>([]);
  const [woId, setWoId] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [pick, setPick] = useState("");
  const [qty, setQty] = useState(1);
  const [linkPath, setLinkPath] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const c = await api.get<{
          services: { service_code: string; service_name: string; suggested_customer_price: string | null }[];
          materials: { material_code: string; material_name: string; suggested_price: string | null }[];
        }>(tenantPath("/quote-catalog"));
        setServices(c.services.map((s) => ({ code: s.service_code, name: s.service_name, price: s.suggested_customer_price })));
        setMaterials(c.materials.map((m) => ({ code: m.material_code, name: m.material_name, price: m.suggested_price })));
      } catch (e) {
        setError(e instanceof ApiError ? `${e.errorCode} (${e.status})` : String(e));
      }
    })();
  }, []);

  function fail(e: unknown) {
    setError(e instanceof ApiError ? `${e.errorCode} (${e.status})` : String(e));
  }

  async function createQuote() {
    if (!woId.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ data: Quote }>(tenantPath(`/work-orders/${woId.trim()}/quotes`), { urgent: false });
      setQuote(res.data);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function addLine() {
    if (!quote || !pick) return;
    setBusy(true);
    setError(null);
    const isService = pick.startsWith("SVC-");
    try {
      const res = await api.post<{ data: Quote }>(tenantPath(`/quotes/${quote.id}/lines`), {
        service_code: isService ? pick : null,
        material_code: isService ? null : pick,
        quantity: qty,
      });
      setQuote(res.data);
      setPick("");
      setQty(1);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function transition(action: string) {
    if (!quote) return;
    setBusy(true);
    setError(null);
    try {
      const hasBody = action === "approve" || action === "reject";
      const path = tenantPath(`/quotes/${quote.id}:${action}`);
      const res = hasBody
        ? await api.post<{ data: Quote }>(path, { comment: null })
        : await api.post<{ data: Quote }>(path, {});
      setQuote(res.data);
      // 送客戶成功 → 後端回傳客戶端查看連結
      if (res.data.public_path) setLinkPath(res.data.public_path);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function fetchLink() {
    if (!quote) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.get<{ data: { public_path: string } }>(tenantPath(`/quotes/${quote.id}/public-link`));
      setLinkPath(res.data.public_path);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    if (!linkPath) return;
    const url = `${window.location.origin}${linkPath}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard 不可用時忽略（使用者可手動選取輸入框複製）
    }
  }

  const actions = quote ? nextActions(quote.state) : [];
  // 已送客戶（含後續狀態）才有客戶連結
  const hasCustomerLink = quote != null && ["sent", "accepted", "rejected", "expired"].includes(quote.state);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <FileText className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
          <span className="rounded bg-[#FEF3C7] px-2 py-[2px] text-[11px] text-[#92400E]">{t("mockBadge")}</span>
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

          {/* 建報價 */}
          <div className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">{t("woId")}</span>
              <input
                value={woId}
                onChange={(e) => setWoId(e.target.value)}
                placeholder="work_order uuid"
                className="w-80 rounded border border-[var(--border)] px-3 py-2 font-mono text-[12px]"
              />
            </label>
            <button
              onClick={createQuote}
              disabled={busy || !woId.trim()}
              className="rounded bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {t("createDraft")}
            </button>
          </div>

          {quote && (
            <div className="flex flex-col gap-5">
              {/* 報價頭 */}
              <div className="flex flex-wrap items-center gap-4 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4">
                <div className="text-sm">
                  <span className="text-[var(--text-secondary)]">{t("quoteId")}: </span>
                  <span className="font-mono text-[12px]">{quote.id}</span>
                </div>
                <span className={`rounded px-2 py-[2px] text-xs font-medium ${STATE_COLORS[quote.state] ?? "bg-gray-100"}`}>
                  {t(`state.${quote.state}`)}
                </span>
                <div className="text-sm text-[var(--text-secondary)]">v{quote.version}</div>
                <div className="ml-auto text-lg font-bold text-[var(--text-primary)]">{price(quote.total_amount)}</div>
              </div>

              {/* 加項 */}
              {(quote.state === "draft" || quote.state === "pending_approval") && (
                <div className="flex flex-wrap items-end gap-3 rounded-lg border border-dashed border-[var(--border)] p-4">
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-[var(--text-secondary)]">{t("item")}</span>
                    <select
                      value={pick}
                      onChange={(e) => setPick(e.target.value)}
                      className="w-80 rounded border border-[var(--border)] px-3 py-2 text-sm"
                    >
                      <option value="">{t("pickItem")}</option>
                      <optgroup label={t("services")}>
                        {services.map((s) => (
                          <option key={s.code} value={s.code}>
                            {s.name} · {price(s.price)}
                          </option>
                        ))}
                      </optgroup>
                      <optgroup label={t("materials")}>
                        {materials.map((m) => (
                          <option key={m.code} value={m.code}>
                            {m.name} · {price(m.price)}
                          </option>
                        ))}
                      </optgroup>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-[var(--text-secondary)]">{t("qty")}</span>
                    <input
                      type="number"
                      min={1}
                      max={999}
                      value={qty}
                      onChange={(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-24 rounded border border-[var(--border)] px-3 py-2 text-sm"
                    />
                  </label>
                  <button
                    onClick={addLine}
                    disabled={busy || !pick}
                    className="flex items-center gap-1 rounded border border-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary)] disabled:opacity-50"
                  >
                    <Plus className="h-4 w-4" /> {t("addLine")}
                  </button>
                </div>
              )}

              {/* 項目表 */}
              <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("name")}</th>
                      <th className="px-3 py-2 text-left">{t("category")}</th>
                      <th className="px-3 py-2 text-right">{t("qty")}</th>
                      {quote.cost_visible && <th className="px-3 py-2 text-right">{t("cost")}</th>}
                      <th className="px-3 py-2 text-right">{t("custPrice")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quote.lines.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-3 py-6 text-center text-[var(--text-disabled)]">
                          {t("noLines")}
                        </td>
                      </tr>
                    ) : (
                      quote.lines.map((l) => (
                        <tr key={l.id} className="border-t border-[var(--border)]">
                          <td className="px-3 py-2 text-[var(--text-primary)]">{l.item_name}</td>
                          <td className="px-3 py-2 text-[var(--text-secondary)]">{l.category}</td>
                          <td className="px-3 py-2 text-right">{l.quantity}</td>
                          {quote.cost_visible && (
                            <td className="px-3 py-2 text-right font-mono text-[var(--text-disabled)]">{price(l.unit_price)}</td>
                          )}
                          <td className="px-3 py-2 text-right font-mono font-medium">{price(l.customer_price)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* 狀態機操作 */}
              {actions.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {actions.map((a) => (
                    <button
                      key={a}
                      onClick={() => transition(a)}
                      disabled={busy}
                      className={`rounded px-4 py-2 text-sm font-medium disabled:opacity-50 ${
                        a === "reject"
                          ? "border border-red-300 text-red-600"
                          : "bg-[var(--primary)] text-white"
                      }`}
                    >
                      {t(`action.${a}`)}
                    </button>
                  ))}
                </div>
              )}

              {/* 客戶端查看連結（已送客戶才有） */}
              {hasCustomerLink && (
                <div className="rounded-lg border border-[var(--border)] bg-[#F8FAFC] p-4">
                  <div className="mb-2 text-sm font-medium text-[var(--text-primary)]">{t("customerLink")}</div>
                  {linkPath ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        readOnly
                        value={`${typeof window !== "undefined" ? window.location.origin : ""}${linkPath}`}
                        className="min-w-0 flex-1 rounded border border-[var(--border)] bg-white px-3 py-2 font-mono text-[12px] text-[var(--text-secondary)]"
                      />
                      <button
                        onClick={copyLink}
                        className="rounded border border-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary)]"
                      >
                        {copied ? t("copied") : t("copyLink")}
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={fetchLink}
                      disabled={busy}
                      className="rounded border border-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary)] disabled:opacity-50"
                    >
                      {t("getLink")}
                    </button>
                  )}
                </div>
              )}

              {quote.snapshot_hash && (
                <p className="text-[12px] text-[var(--text-disabled)]">
                  {t("snapshot")}: <span className="font-mono">{quote.snapshot_hash.slice(0, 16)}…</span>
                </p>
              )}
              <p className="text-[12px] text-[var(--text-disabled)]">{t("note")}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function nextActions(state: string): string[] {
  switch (state) {
    case "draft":
      return ["submit", "send"];
    case "pending_approval":
      return ["approve", "reject"];
    case "approved":
      return ["send"];
    case "sent":
      return ["accept"];
    default:
      return [];
  }
}
