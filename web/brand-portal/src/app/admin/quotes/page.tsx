"use client";

import { useEffect, useState } from "react";
import { FileText, Plus, Trash2 } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import WorkOrderPicker from "@/components/quotes/WorkOrderPicker";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";
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
// CR-0129：急件補審佇列項（GET /quotes/audit-queue）
interface AuditQueueItem {
  id: string;
  version: number;
  state: string;
  total_amount: string | null;
  audit_due_at: string | null;
  work_order_id: string | null;
  quote_number: string | null;
  customer_name: string | null;
  overdue: boolean;
  emergency_class: string | null;
}

// UAT W6-1：急件標籤走 i18n（admin.quotesAudit.emergency）——此處只留值域
const EMERGENCY_VALUES = [
  "locked_out",
  "trapped_inside",
  "safety_risk",
  "angry_high_risk",
] as const;

// UAT P2-12：報價品項類別中文化（DB quote_line_items.category 值域 labor/material/other）
const LINE_CATEGORY_LABEL: Record<string, string> = {
  labor: "工資",
  material: "材料",
  other: "其他",
};

// UAT P3：報價「已接受但總額 —」——total_amount 只在加/刪明細時重算，急件補審
// 佔位等路徑可能為 null；有明細價時前端以「明細合計」fallback 顯示。
function quoteTotalFallback(q: Quote): string | null {
  if (q.total_amount != null) return q.total_amount;
  if (q.lines.length === 0) return null;
  let sum = 0;
  for (const l of q.lines) {
    const p = l.customer_price != null ? parseFloat(l.customer_price) : NaN;
    if (Number.isNaN(p)) return null;
    sum += p * l.quantity;
  }
  return String(sum);
}

function auditRemainLabel(
  tAudit: (key: string, vars?: Record<string, string | number>) => string,
  item: AuditQueueItem,
): { text: string; danger: boolean } {
  if (!item.audit_due_at) return { text: tAudit("notStarted"), danger: false };
  const remainMs = new Date(item.audit_due_at).getTime() - Date.now();
  if (remainMs <= 0) return { text: tAudit("overdue"), danger: true };
  const mins = Math.floor(remainMs / 60000);
  return {
    text: tAudit("remaining", { h: Math.floor(mins / 60), m: mins % 60 }),
    danger: mins < 60,
  };
}

// CR-0095：報價列表項（GET /quotes，免手貼 UUID）
// CR-0160：補卡階段脈絡——CR-0128 報價先行的報價在開單前 work_order_id=NULL，
// 單號/客戶名不存在，改以裝置標籤＋聯絡電話呈現，避免整列空白像壞掉。
interface QuoteListItem {
  id: string;
  work_order_id: string | null;
  work_order_number: string | null;
  quote_number: string | null;
  state: string;
  total_amount: string | null;
  created_at: string | null;
  customer_name: string | null;
  version: number;
  problem_card_id: string | null;
  problem_card_label: string | null;
  contact_phone: string | null;
}

// 瀏覽模式列「尚無報價的工單」需要的最小工單欄位
interface WorkOrderLite {
  id: string;
  document_number: string | null;
  customer_name: string | null;
  status: string;
}
// 工單狀態中文標籤（v2 七態 created/assigned/accepted/in_progress/completed/confirmed/cancelled；
// inquiring/closed 為 v1 值保留防禦）
const WO_STATUS_LABEL: Record<string, string> = {
  created: "已建立",
  inquiring: "詢價中",
  assigned: "已派工",
  accepted: "已接單",
  in_progress: "服務中",
  completed: "已完工",
  confirmed: "客戶已確認",
  closed: "已結案",
  cancelled: "已取消",
};

const STATE_COLORS: Record<string, string> = {
  draft: "bg-[#E2E8F0] text-[#475569]",
  pending_approval: "bg-[#FEF3C7] text-[#92400E]",
  approved: "bg-[#DBEAFE] text-[#1E40AF]",
  sent: "bg-[#E0E7FF] text-[#4338CA]",
  accepted: "bg-[#DCFCE7] text-[#15803D]",
  rejected: "bg-[#FEE2E2] text-[#B91C1C]",
  expired: "bg-[#F1F5F9] text-[#94A3B8]",
  // 急件補審佔位 / 改版作廢（原缺 → 徽章顯示 i18n key 路徑）
  retrospective_audit_only: "bg-[#FFEDD5] text-[#9A3412]",
  superseded: "bg-[#F1F5F9] text-[#94A3B8]",
};

function price(v?: string | null): string {
  if (v == null) return "—";
  return `NT$ ${Math.round(parseFloat(v)).toLocaleString()}`;
}

export default function QuotesPage() {
  const t = useTranslations("admin.quotes");
  const tAudit = useTranslations("admin.quotesAudit");
  const [services, setServices] = useState<CatalogItem[]>([]);
  const [materials, setMaterials] = useState<CatalogItem[]>([]);
  const [woId, setWoId] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 深連結 ?open=<id> 進來＝「聚焦單張報價」模式：既然是專程開這一張，就不再堆疊
  // 建報價列 / 急件佇列 / 全部報價列表 / 待報價工單（業主回報「開了還顯示全部報價很亂」）。
  const [openFocus, setOpenFocus] = useState(false);

  const [pick, setPick] = useState("");
  const [qty, setQty] = useState(1);
  const [linkPath, setLinkPath] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [invoiceMsg, setInvoiceMsg] = useState<string | null>(null);
  const [quotes, setQuotes] = useState<QuoteListItem[]>([]); // CR-0095 報價列表
  // CR-0129 急件補審佇列（15_SDS §4.5：待補審報價＋剩餘時間/逾時）
  const [auditQueue, setAuditQueue] = useState<AuditQueueItem[]>([]);
  // 瀏覽模式「尚無報價的工單」清單來源（與報價算差集）；woTruncated=工單超過 100 筆只載前頁
  const [workOrders, setWorkOrders] = useState<WorkOrderLite[]>([]);
  const [woTruncated, setWoTruncated] = useState(false);
  // CR-0101（業主裁決：誠實版·零後端）：選定工單時帶入其問題卡 context（品牌/型號/症狀），
  // 報價時免切回問題卡翻。自動「建議定價品項」需推薦引擎（未實作），故不猜、只帶 context。
  const [pcContext, setPcContext] = useState<{
    brand?: string;
    model?: string;
    symptom?: string;
    woNumber?: string; // 選定工單的友善公單號（TP-000002），供列表 scoped 標題用
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
        setError(friendlyError(e));
      }
    })();
    // CR-0095：載入報價列表 + 處理工單頁深連結 ?wo=（免手貼 UUID）
    void fetchAuditQueue(); // CR-0129 急件補審佇列
    (async () => {
      const list = await fetchQuotes();
      setQuotes(list);
      const params = new URLSearchParams(window.location.search);
      const open = params.get("open"); // CR-0095：列表「開啟」新分頁深連結 → 載入該報價
      if (open) {
        setOpenFocus(true); // 聚焦模式：只顯示這張報價，隱藏其餘瀏覽區塊
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
    // 載入工單清單，供瀏覽模式列「尚無報價的工單」（與報價 client 端算差集）。
    // 端點上限 100，超過則 has_more=true → 誠實標註只顯示前 100 筆，不靜默截斷。
    (async () => {
      try {
        const res = await api.get<{ items: WorkOrderLite[]; has_more?: boolean }>(
          `${tenantPath("/work-orders")}?limit=100`,
        );
        setWorkOrders(res.items ?? []);
        setWoTruncated(Boolean(res.has_more));
      } catch {
        /* 工單清單載入失敗不阻斷報價工作台 */
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
          data: {
            brand?: string;
            model?: string;
            problem_card_id?: string;
            document_number?: string;
          } | null;
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
          setPcContext({
            brand: wo?.brand,
            model: wo?.model,
            symptom,
            woNumber: wo?.document_number,
          });
        }
      } catch {
        if (!cancelled) setPcContext(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [woId]);

  // 工單選擇變動（清除回瀏覽 / 切換到別張工單）時，若目前開啟的報價不屬於這張
  // 工單 → 收起報價詳情。否則回到「全部列表」瀏覽模式時，會殘留上一張報價的編輯區
  // （業主回報：明明在全部列表卻看到 TP-xxx-Qn 詳情）。報價詳情只屬於其所屬工單脈絡。
  // loadQuote 會先 setQuote 再 setWoId(該報價的 work_order_id)，故開啟報價時兩者一致、不誤清。
  useEffect(() => {
    const id = woId.trim();
    // truthy guard：work_order_id 為 null 的報價（未綁工單）無工單脈絡可比，不自動收起。
    setQuote((q) => (q && q.work_order_id && q.work_order_id !== id ? null : q));
  }, [woId]);

  function fail(e: unknown) {
    setError(friendlyError(e));
  }

  async function fetchQuotes(): Promise<QuoteListItem[]> {
    try {
      const res = await api.get<{ data: QuoteListItem[] }>(tenantPath("/quotes"));
      return res.data ?? [];
    } catch {
      return []; // 列表載入失敗不阻斷工作台
    }
  }

  async function fetchAuditQueue() {
    try {
      const res = await api.get<{ data: AuditQueueItem[] }>(tenantPath("/quotes/audit-queue"));
      setAuditQueue(res.data ?? []);
    } catch {
      setAuditQueue([]); // 佇列載入失敗不阻斷報價工作台
    }
  }

  // CR-0129 紙本簽認：急件補審完成（LIFF 路徑=開啟報價後照常「送客戶」）
  async function auditCompletePaper(id: string) {
    const comment = window.prompt("紙本簽認佐證說明（簽單編號/照片 evidence 參照）：");
    if (comment === null) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(tenantPath(`/quotes/${id}:audit-complete`), { comment: comment.trim() || null });
      await fetchAuditQueue();
      setQuotes(await fetchQuotes());
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
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
      cacheInvalidate("GET:"); // 新草稿才會出現在列表（清 GET /quotes 舊快取）
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

  // CR：刪除整張報價單（僅草稿/待核可刪，硬刪 cascade）。破壞性動作，先確認。
  async function deleteQuote(id: string) {
    if (typeof window !== "undefined" && !window.confirm(t("deleteConfirm"))) return;
    setBusy(true);
    setError(null);
    try {
      await api.delete(tenantPath(`/quotes/${encodeURIComponent(id)}`));
      if (quote?.id === id) setQuote(null); // 若刪的是目前開啟的報價 → 收起編輯區
      // 樂觀更新：先即時把該筆從列表移除，免等下方 refetch 的網路往返。
      setQuotes((prev) => prev.filter((q) => q.id !== id));
      // GET /quotes 在頁面載入時已被快取（30s staleTime）；不清快取，fetchQuotes
      // 會讀回「仍含剛刪那筆」的舊列表（業主回報：刪草稿後不馬上刷新）。
      // cache key 含完整 URL（GET:${host}${path}:${tenant}），path-prefix 對不上，
      // 故用廣域 "GET:" 清全部 GET 快取（與 cases 頁等各頁慣例一致）。
      cacheInvalidate("GET:");
      setQuotes(await fetchQuotes()); // 與後端對帳（cascade 刪除後的真實列表）
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
      cacheInvalidate("GET:"); // 狀態變更須反映到列表（清 GET /quotes 舊快取）
      setQuotes(await fetchQuotes()); // 狀態變更後刷新列表
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  // 「拒了重估→新版本」（會議 §六「拒了重估」／CR-0032 版本鏈）：rejected/expired 是終態，
  // 依既定版本鏈模型不就地「重開」（客戶已看過的版本為不可變紀錄），而是建立新版本 v+1
  // draft 繼續。工單報價走 /work-orders/{wo}/quotes；報價先行（無工單）走
  // /problem-cards/{pc}/quotes（pc 從已載入的報價列表取，get_quote 未回 problem_card_id）。
  async function requoteNewVersion() {
    if (!quote) return;
    const pcId = quotes.find((q) => q.id === quote.id)?.problem_card_id ?? null;
    const woForRequote = quote.work_order_id;
    if (!woForRequote && !pcId) {
      setError("找不到此報價對應的工單或問題卡，無法建立新版本（請回列表以工單重新開報價）");
      return;
    }
    setBusy(true);
    setError(null);
    setLinkPath(null);
    try {
      const path = woForRequote
        ? tenantPath(`/work-orders/${woForRequote}/quotes`)
        : tenantPath(`/problem-cards/${pcId}/quotes`);
      const res = await api.post<{ data: Quote }>(path, { urgent: false });
      setQuote(res.data); // 直接切到新版本 draft 繼續編輯
      cacheInvalidate("GET:"); // 新版本要出現在列表（清 GET /quotes 舊快取）
      setQuotes(await fetchQuotes());
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

  // 報價列表 scoped 規則：選定工單 → 只列「這張工單」的報價（避免與工單脈絡混淆，
  // 不再把別張工單的報價混進來）；未選工單 → 瀏覽模式，顯示全部報價。
  const trimmedWo = woId.trim();
  const scoped = trimmedWo.length > 0;
  const visibleQuotes = scoped
    ? quotes.filter((q) => q.work_order_id === trimmedWo)
    : quotes;
  // scoped 標題優先用 WO context 撈到的公單號；撈不到時退回列表項自帶的公單號。
  const woNumberLabel = pcContext?.woNumber ?? visibleQuotes[0]?.work_order_number ?? null;

  // 瀏覽模式「尚無報價的工單」：所有工單扣掉已有報價者，並排除終態（已結案/已取消，
  // 列在「待報價」會誤導）。讓管理員一眼看出哪些工單還沒開報價、可直接「去報價」。
  const quotedWoIds = new Set(quotes.map((q) => q.work_order_id).filter(Boolean));
  const woNoQuote = workOrders.filter(
    (wo) => !quotedWoIds.has(wo.id) && wo.status !== "cancelled" && wo.status !== "closed",
  );

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <FileText className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
          {/* 「示意資料」僅在開啟的報價真為 mock 時才標（is_mock）；原本恆亮會誤導真資料畫面 */}
          {quote?.is_mock && (
            <span className="rounded bg-[#FEF3C7] px-2 py-[2px] text-[11px] text-[#92400E]">{t("mockBadge")}</span>
          )}
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

          {/* 聚焦模式：回到完整報價工作台的返回連結 */}
          {openFocus && (
            <a
              href="/admin/quotes"
              className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-[var(--primary)] hover:underline"
            >
              ← 返回報價列表
            </a>
          )}

          {/* 建報價 —— 用公單號（TP-000001）/ 客戶名選工單，免手貼 UUID */}
          {!openFocus && (
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
          )}

          {/* CR-0129 急件補審佇列（15_SDS §4.5）：完工後 4h 內須補審——LIFF 補送或紙本簽認 */}
          {!openFocus && auditQueue.length > 0 && (
            <div className="mb-6 rounded-lg border border-[#FDBA74] bg-[#FFF7ED] p-4">
              <div className="mb-2 flex items-center gap-2">
                <span className="text-[14px] font-bold text-[#9A3412]">{tAudit("title")}</span>
                <span className="rounded bg-[#FFEDD5] px-2 py-[2px] text-[11px] text-[#9A3412]">
                  {tAudit("deadlineNote")}
                </span>
              </div>
              <div className="flex flex-col gap-2">
                {auditQueue.map((q) => {
                  const remain = auditRemainLabel(tAudit, q);
                  return (
                    <div key={q.id} className="flex flex-wrap items-center gap-3 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px]">
                      <span className="font-mono text-[12px] text-[var(--text-secondary)]">
                        {q.quote_number ?? `Q${q.version}`}
                      </span>
                      <span className="text-[var(--text-primary)]">{q.customer_name ?? "—"}</span>
                      {q.emergency_class && (
                        <span className="rounded bg-[#FEE2E2] px-2 py-[2px] text-[11px] font-semibold text-[#991B1B]">
                          {(EMERGENCY_VALUES as readonly string[]).includes(q.emergency_class)
                            ? tAudit(`emergency.${q.emergency_class}`)
                            : q.emergency_class}
                        </span>
                      )}
                      <span className={`rounded px-2 py-[2px] text-[11px] font-semibold ${remain.danger ? "bg-[#FEE2E2] text-[#991B1B]" : "bg-[#F1F5F9] text-[#475569]"}`}>
                        {remain.text}
                      </span>
                      <span className="text-[12px] text-[var(--text-secondary)]">
                        {q.state === "sent" ? tAudit("sentWaiting") : tAudit("pendingLines")}
                      </span>
                      <div className="ml-auto flex items-center gap-2">
                        <button
                          onClick={() => loadQuote(q.id)}
                          disabled={busy}
                          className="rounded border border-[var(--primary)] px-3 py-[4px] text-[12px] font-semibold text-[var(--primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
                        >
                          {tAudit("fillAndSend")}
                        </button>
                        <button
                          onClick={() => auditCompletePaper(q.id)}
                          disabled={busy}
                          className="rounded bg-[#9A3412] px-3 py-[4px] text-[12px] font-semibold text-white hover:opacity-90 disabled:opacity-50"
                        >
                          {tAudit("paperDone")}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

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

          {/* CR-0095 報價列表 — 點選即開，免手貼 UUID（顯示友善公單號 TP）；聚焦模式不顯示 */}
          {!openFocus && (scoped || quotes.length > 0) && (
            <div className="mb-6 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <div className="border-b border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)]">
                {scoped ? `${woNumberLabel ?? "本工單"} 的報價` : "全部報價"}（{visibleQuotes.length}）
              </div>
              {visibleQuotes.length === 0 ? (
                <div className="px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
                  尚無報價，點上方「建立草稿」新增
                </div>
              ) : (
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
                  {visibleQuotes.map((q) => (
                    <tr key={q.id} className="border-t border-[var(--border)] hover:bg-[var(--bg-page)]">
                      <td className="px-3 py-2 font-mono text-[13px] font-semibold text-[var(--text-primary)]">
                        {q.quote_number ?? q.work_order_number ?? (q.problem_card_id ? (
                          // CR-0160：卡階段報價（報價先行，尚未開單）——正式單號待開單回填後出現
                          <span className="inline-flex flex-wrap items-center gap-2 font-sans">
                            <span className="rounded bg-[#FEF9C3] px-2 py-[2px] text-[11px] font-medium text-[#854D0E]">
                              報價先行（未開單）
                            </span>
                            <span className="text-[12px] text-[var(--text-secondary)]">
                              {q.problem_card_label ?? "問題卡"}・Q{q.version}
                            </span>
                          </span>
                        ) : "—")}
                      </td>
                      <td className="px-3 py-2 text-[var(--text-secondary)]">{q.customer_name ?? q.contact_phone ?? "—"}</td>
                      <td className="px-3 py-2">
                        <span className={`rounded px-2 py-[2px] text-xs font-medium ${STATE_COLORS[q.state] ?? "bg-gray-100"}`}>
                          {t(`state.${q.state}`)}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right font-mono">{price(q.total_amount)}</td>
                      <td className="px-3 py-2 text-right">
                        <div className="inline-flex items-center gap-2">
                          <a
                            href={`/admin/quotes?open=${q.id}`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-block rounded border border-[var(--primary)] px-3 py-1 text-xs font-medium text-[var(--primary)] hover:bg-[var(--primary-light)]"
                          >
                            {t("open")}
                          </a>
                          {/* 僅草稿/待核可刪整張；已送客戶/接受的報價為紀錄不可刪 */}
                          {(q.state === "draft" || q.state === "pending_approval") && (
                            <button
                              type="button"
                              onClick={() => deleteQuote(q.id)}
                              disabled={busy}
                              title={t("deleteQuote")}
                              aria-label={t("deleteQuote")}
                              className="inline-flex h-7 w-7 items-center justify-center rounded text-[var(--text-disabled)] hover:bg-red-50 hover:text-red-600 disabled:opacity-40"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              )}
            </div>
          )}

          {/* 瀏覽模式（未選工單）才列「尚無報價的工單」，提醒哪些工單待開報價；聚焦模式不顯示 */}
          {!openFocus && !scoped && woNoQuote.length > 0 && (
            <div className="mb-6 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <div className="border-b border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)]">
                尚無報價的工單（{woNoQuote.length}）
              </div>
              <table className="w-full text-sm">
                <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-3 py-2 text-left">公單號</th>
                    <th className="px-3 py-2 text-left">客戶</th>
                    <th className="px-3 py-2 text-left">狀態</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {woNoQuote.map((wo) => (
                    <tr key={wo.id} className="border-t border-[var(--border)] hover:bg-[var(--bg-page)]">
                      <td className="px-3 py-2 font-mono text-[13px] font-semibold text-[var(--text-primary)]">
                        {wo.document_number ?? wo.id.slice(0, 8)}
                      </td>
                      <td className="px-3 py-2 text-[var(--text-secondary)]">{wo.customer_name ?? "—"}</td>
                      <td className="px-3 py-2">
                        <span className="rounded bg-[var(--bg-page)] px-2 py-[2px] text-xs text-[var(--text-secondary)]">
                          {WO_STATUS_LABEL[wo.status] ?? wo.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => setWoId(wo.id)}
                          className="inline-block rounded border border-[var(--primary)] px-3 py-1 text-xs font-medium text-[var(--primary)] hover:bg-[var(--primary-light)]"
                        >
                          去報價
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {woTruncated && (
                <div className="border-t border-[var(--border)] px-4 py-2 text-[11px] text-[var(--text-disabled)]">
                  工單超過 100 筆，此處僅比對前 100 筆；請用上方「選擇工單」搜尋特定工單。
                </div>
              )}
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
                <div className="ml-auto flex items-baseline gap-2">
                  {/* UAT P3：total_amount 為 null 時以明細合計 fallback */}
                  {quote.total_amount == null && quoteTotalFallback(quote) != null && (
                    <span className="text-[11px] text-[var(--text-disabled)]">依明細合計</span>
                  )}
                  <span className="text-lg font-bold text-[var(--text-primary)]">
                    {price(quoteTotalFallback(quote))}
                  </span>
                </div>
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
                            {/* UAT P2-12：labor/material 原始碼 → 中文 */}
                            <td className="px-3 py-2 text-[var(--text-secondary)]">
                              {LINE_CATEGORY_LABEL[l.category] ?? l.category}
                            </td>
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

              {/* 拒絕/過期＝終態，無狀態機動作可走；提供「建立新版本重估」續行（會議「拒了重估」）。
                  不就地重開，因客戶已看過的版本為不可變紀錄，重估一律走新版本 v+1（版本鏈模型）。 */}
              {(quote.state === "rejected" || quote.state === "expired") && (
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[#FDBA74] bg-[#FFF7ED] p-4">
                  <div className="text-sm text-[#9A3412]">
                    此報價已<strong>{quote.state === "rejected" ? "被拒絕" : "過期"}</strong>，屬終態不可再改。
                    若要重新報價，請建立新版本繼續（舊版本保留為紀錄）。
                  </div>
                  <button
                    onClick={requoteNewVersion}
                    disabled={busy}
                    className="ml-auto rounded bg-[#9A3412] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
                  >
                    建立新版本重估
                  </button>
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
