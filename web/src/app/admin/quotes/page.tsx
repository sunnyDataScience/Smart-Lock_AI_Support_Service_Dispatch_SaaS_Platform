"use client";

import { useEffect, useState } from "react";
import { FileText, Plus, Trash2 } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import WorkOrderPicker from "@/components/quotes/WorkOrderPicker";
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
  work_order_number?: string | null; // CR-0095：友善公單號（TP-000001）
  quote_number?: string | null; // CR-0095：可讀報價單號（TP-000001-Q1）
  customer_name?: string | null;
}
// CR-0095：報價列表項（GET /quotes，免手貼 UUID）
interface QuoteListItem {
  id: string;
  work_order_id: string | null;
  work_order_number: string | null;
  quote_number: string | null;
  state: string;
  total_amount: string | null;
  created_at: string | null;
  customer_name: string | null;
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
  const [invoiceMsg, setInvoiceMsg] = useState<string | null>(null);
  const [quotes, setQuotes] = useState<QuoteListItem[]>([]); // CR-0095 報價列表
  // CR-0101（業主裁決：誠實版·零後端）：選定工單時帶入其問題卡 context（品牌/型號/症狀），
  // 報價時免切回問題卡翻。自動「建議定價品項」需推薦引擎（未實作），故不猜、只帶 context。
  const [pcContext, setPcContext] = useState<{
    brand?: string;
    model?: string;
    symptom?: string;
  } | null>(null);

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
    // CR-0095：載入報價列表 + 處理工單頁深連結 ?wo=（免手貼 UUID）
    (async () => {
      const list = await fetchQuotes();
      setQuotes(list);
      const params = new URLSearchParams(window.location.search);
      const open = params.get("open"); // CR-0095：列表「開啟」新分頁深連結 → 載入該報價
      if (open) {
        await loadQuote(open);
        return;
      }
      const wo = params.get("wo");
      if (wo) {
        setWoId(wo);
        const existing = list.find((q) => q.work_order_id === wo);
        if (existing) await loadQuote(existing.id); // 已有報價 → 直接開（避免誤建多張）
      }
    })();
  }, []);

  // CR-0101：選定工單 → 抓 WO（品牌/型號）+ 其問題卡（症狀）顯示 context（報價參考）。
  useEffect(() => {
    const id = woId.trim();
    if (!id) {
      setPcContext(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const woRes = await api.get<{
          data: { brand?: string; model?: string; problem_card_id?: string } | null;
        }>(tenantPath(`/work-orders/${encodeURIComponent(id)}`));
        const wo = woRes.data;
        let symptom = "";
        if (wo?.problem_card_id) {
          try {
            const pcRes = await api.get<{ data: { symptom?: string } | null }>(
              tenantPath(`/problem-cards/${encodeURIComponent(wo.problem_card_id)}`),
            );
            symptom = pcRes.data?.symptom ?? "";
          } catch {
            /* 問題卡撈不到不阻斷報價工作台 */
          }
        }
        if (!cancelled) {
          setPcContext({ brand: wo?.brand, model: wo?.model, symptom });
        }
      } catch {
        if (!cancelled) setPcContext(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [woId]);

  function fail(e: unknown) {
    setError(e instanceof ApiError ? `${e.errorCode} (${e.status})` : String(e));
  }

  async function fetchQuotes(): Promise<QuoteListItem[]> {
    try {
      const res = await api.get<{ data: QuoteListItem[] }>(tenantPath("/quotes"));
      return res.data ?? [];
    } catch {
      return []; // 列表載入失敗不阻斷工作台
    }
  }

  async function loadQuote(id: string) {
    setBusy(true);
    setError(null);
    setLinkPath(null);
    try {
      const res = await api.get<{ data: Quote }>(tenantPath(`/quotes/${id}`));
      setQuote(res.data);
      if (res.data.work_order_id) setWoId(res.data.work_order_id);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function createQuote() {
    if (!woId.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ data: Quote }>(tenantPath(`/work-orders/${woId.trim()}/quotes`), { urgent: false });
      setQuote(res.data);
      setQuotes(await fetchQuotes());
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

  // CR：移除報價明細（草稿/待核可改；後端重算總額後回傳）。
  async function removeLine(lineId: string) {
    if (!quote) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.delete<{ data: Quote }>(
        tenantPath(`/quotes/${quote.id}/lines/${encodeURIComponent(lineId)}`),
      );
      setQuote(res.data);
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
      setQuotes(await fetchQuotes()); // 狀態變更後刷新列表
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

  async function createInvoice() {
    if (!quote) return;
    setBusy(true);
    setError(null);
    setInvoiceMsg(null);
    try {
      const res = await api.post<{ data: { invoice_no?: string | null; id: string } }>(
        tenantPath("/accounting/invoices:from-quote"),
        { quote_id: quote.id },
      );
      const no = res.data.invoice_no || res.data.id.slice(0, 8);
      setInvoiceMsg(t("invoiceCreated", { no }));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
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

          {/* 建報價 —— 用公單號（TP-000001）/ 客戶名選工單，免手貼 UUID */}
          <div className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">{t("woPickerLabel")}</span>
              <WorkOrderPicker value={woId} onChange={setWoId} />
            </label>
            <button
              onClick={createQuote}
              disabled={busy || !woId.trim()}
              className="rounded bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {t("createDraft")}
            </button>
          </div>

          {/* CR-0101：依問題卡帶入 context（品牌/型號/症狀），報價時免切回問題卡翻 */}
          {pcContext && (pcContext.brand || pcContext.model || pcContext.symptom) && (
            <div className="mb-6 flex flex-col gap-1 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] p-4">
              <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
                依問題卡（報價參考）
              </span>
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px]">
                {(pcContext.brand || pcContext.model) && (
                  <span className="text-[var(--text-primary)]">
                    <span className="text-[var(--text-disabled)]">裝置：</span>
                    {[pcContext.brand, pcContext.model].filter(Boolean).join(" ")}
                  </span>
                )}
                {pcContext.symptom && (
                  <span className="text-[var(--text-primary)]">
                    <span className="text-[var(--text-disabled)]">症狀：</span>
                    {pcContext.symptom}
                  </span>
                )}
              </div>
              <span className="text-[11px] text-[var(--text-disabled)]">
                依此問題從下方挑選報價品項；自動定價品項建議需推薦引擎（未實作），故此處僅帶入問題參考、不自動猜價。
              </span>
            </div>
          )}

          {/* CR-0095 報價列表 — 點選即開，免手貼 UUID（顯示友善公單號 TP）*/}
          {quotes.length > 0 && (
            <div className="mb-6 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <div className="border-b border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)]">
                {t("listTitle")}（{quotes.length}）
              </div>
              <table className="w-full text-sm">
                <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-3 py-2 text-left">{t("quoteNo")}</th>
                    <th className="px-3 py-2 text-left">{t("customer")}</th>
                    <th className="px-3 py-2 text-left">{t("statusCol")}</th>
                    <th className="px-3 py-2 text-right">{t("total")}</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {quotes.map((q) => (
                    <tr key={q.id} className="border-t border-[var(--border)] hover:bg-[var(--bg-page)]">
                      <td className="px-3 py-2 font-mono text-[13px] font-semibold text-[var(--text-primary)]">{q.quote_number ?? q.work_order_number ?? "—"}</td>
                      <td className="px-3 py-2 text-[var(--text-secondary)]">{q.customer_name ?? "—"}</td>
                      <td className="px-3 py-2">
                        <span className={`rounded px-2 py-[2px] text-xs font-medium ${STATE_COLORS[q.state] ?? "bg-gray-100"}`}>
                          {t(`state.${q.state}`)}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right font-mono">{price(q.total_amount)}</td>
                      <td className="px-3 py-2 text-right">
                        <a
                          href={`/admin/quotes?open=${q.id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-block rounded border border-[var(--primary)] px-3 py-1 text-xs font-medium text-[var(--primary)] hover:bg-[var(--primary-light)]"
                        >
                          {t("open")}
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {quote && (
            <div className="flex flex-col gap-5">
              {/* 報價頭 */}
              <div className="flex flex-wrap items-center gap-4 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4">
                <div className="text-sm">
                  <span className="text-[var(--text-secondary)]">{t("quoteNo")}: </span>
                  <span className="font-mono text-[14px] font-semibold text-[var(--text-primary)]">
                    {quote.quote_number ?? quote.work_order_number ?? quote.id.slice(0, 8)}
                  </span>
                </div>
                <span className="font-mono text-[11px] text-[var(--text-disabled)]">{quote.id.slice(0, 8)}</span>
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
                      <th className="px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {quote.lines.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-3 py-6 text-center text-[var(--text-disabled)]">
                          {t("noLines")}
                        </td>
                      </tr>
                    ) : (
                      quote.lines.map((l) => {
                        // 僅草稿/待核可移除（已送客戶/接受的報價凍結，不可改）
                        const editable =
                          quote.state === "draft" || quote.state === "pending_approval";
                        return (
                          <tr key={l.id} className="border-t border-[var(--border)]">
                            <td className="px-3 py-2 text-[var(--text-primary)]">{l.item_name}</td>
                            <td className="px-3 py-2 text-[var(--text-secondary)]">{l.category}</td>
                            <td className="px-3 py-2 text-right">{l.quantity}</td>
                            {quote.cost_visible && (
                              <td className="px-3 py-2 text-right font-mono text-[var(--text-disabled)]">{price(l.unit_price)}</td>
                            )}
                            <td className="px-3 py-2 text-right font-mono font-medium">{price(l.customer_price)}</td>
                            <td className="px-3 py-2 text-right">
                              {editable && (
                                <button
                                  type="button"
                                  onClick={() => removeLine(l.id)}
                                  disabled={busy}
                                  title={t("removeLine")}
                                  aria-label={t("removeLine")}
                                  className="inline-flex h-7 w-7 items-center justify-center rounded text-[var(--text-disabled)] hover:bg-red-50 hover:text-red-600 disabled:opacity-40"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })
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
                  {/* CR-0095：報價送出已推 LINE 給客戶（含 postback 同意/拒絕）；網頁連結為備援 */}
                  <div className="mb-2 rounded bg-[#EFF6FF] px-3 py-2 text-[12px] text-[#1D4ED8]">
                    {t("lineApprovalHint")}
                  </div>
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

              {/* CR-0035 報價已接受 → 開立應收發票 */}
              {quote.state === "accepted" && (
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[var(--border)] bg-[#F0FDF4] p-4">
                  <button
                    onClick={createInvoice}
                    disabled={busy}
                    className="rounded bg-[#15803D] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {t("createInvoice")}
                  </button>
                  {invoiceMsg && (
                    <span className="text-sm font-medium text-[#15803D]">{invoiceMsg}</span>
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
