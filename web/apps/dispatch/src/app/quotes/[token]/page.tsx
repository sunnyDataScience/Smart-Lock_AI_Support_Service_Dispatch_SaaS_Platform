/**
 * /quotes/[token] — 消費者匿名報價查看 / 確認頁面（CR-0032 Phase C）
 *
 * 入口：LINE 推播短連結（例：https://app.example.com/quotes/<signed-token>）
 * 後端 v2：
 *   GET  /consumer/quotes/{token}  (operationId: getConsumerQuoteV2, M16)
 *   POST /consumer/quotes/{token}  (operationId: respondConsumerQuoteV2, body {decision})
 *
 * 設計重點：
 *   - mobile-first（消費者主要從 LINE webview 開啟）
 *   - CSR；不帶 Authorization / X-Tenant-ID（public token 簽章驗證，purpose=quote_view）
 *   - 只露客戶最終價（後端 include_cost=False，結構上不含內部成本 unit_price）
 *   - sent 狀態才可同意/拒絕；其餘狀態唯讀
 */

"use client";

import { use, useEffect, useState } from "react";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type Params = { token: string };

// 直接打 consumer endpoint — 不走 src/lib/api.ts（會帶 Authorization / X-Tenant-ID）
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

type QuoteState =
  | "draft"
  | "pending_approval"
  | "approved"
  | "sent"
  | "accepted"
  | "rejected"
  | "expired";

interface ConsumerQuoteLine {
  id: string;
  item_name: string;
  category: string;
  quantity: number;
  customer_price: string | null;
  service_code: string | null;
  material_code: string | null;
}

interface ConsumerQuoteView {
  quote_id: string;
  state: QuoteState;
  total_amount: string | null;
  lines: ConsumerQuoteLine[];
  expires_at: string | null;
  snapshot_hash: string | null;
}

const STATE_COLOR: Record<QuoteState, string> = {
  draft: "bg-slate-100 text-slate-700 border-slate-200",
  pending_approval: "bg-amber-50 text-amber-700 border-amber-200",
  approved: "bg-blue-50 text-blue-700 border-blue-200",
  sent: "bg-indigo-50 text-indigo-700 border-indigo-200",
  accepted: "bg-green-50 text-green-700 border-green-200",
  rejected: "bg-red-50 text-red-700 border-red-200",
  expired: "bg-slate-100 text-slate-500 border-slate-200",
};

type FetchState =
  | { kind: "loading" }
  | { kind: "ok"; data: ConsumerQuoteView }
  | { kind: "error"; message: string; code: "expired" | "not_found" | "rate_limit" | "other" };

function money(v?: string | null): string {
  if (v == null) return "—";
  return `NT$ ${Math.round(parseFloat(v)).toLocaleString()}`;
}

export default function PublicQuotePage({ params }: { params: Promise<Params> }) {
  const { token } = use(params);
  const t = useTranslations("pages.quotesPublic");
  const [state, setState] = useState<FetchState>({ kind: "loading" });
  const [submitting, setSubmitting] = useState<null | "accept" | "reject">(null);

  async function load() {
    setState({ kind: "loading" });
    try {
      const res = await fetch(`${API_BASE}/consumer/quotes/${encodeURIComponent(token)}`, {
        cache: "no-store",
        credentials: "omit",
      });
      if (res.status === 404) return setState({ kind: "error", code: "not_found", message: t("errors.notFound") });
      if (res.status === 410) return setState({ kind: "error", code: "expired", message: t("errors.expired") });
      if (res.status === 429) return setState({ kind: "error", code: "rate_limit", message: t("errors.rateLimit") });
      if (!res.ok) return setState({ kind: "error", code: "other", message: t("errors.fail", { status: String(res.status) }) });
      const data = (await res.json()) as ConsumerQuoteView;
      setState({ kind: "ok", data });
    } catch {
      setState({ kind: "error", code: "other", message: t("errors.network") });
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!cancelled) await load();
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function respond(decision: "accept" | "reject") {
    setSubmitting(decision);
    try {
      const res = await fetch(`${API_BASE}/consumer/quotes/${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "omit",
        body: JSON.stringify({ decision }),
      });
      if (res.ok) {
        await load();
      } else if (res.status === 409) {
        // 狀態衝突（已回覆 / 已過期）→ 重新載入顯示最新狀態
        await load();
      } else {
        setState({ kind: "error", code: "other", message: t("errors.fail", { status: String(res.status) }) });
      }
    } catch {
      setState({ kind: "error", code: "other", message: t("errors.network") });
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold text-slate-900">{t("title")}</h1>
        {state.kind === "loading" && <QuoteSkeleton />}
        {state.kind === "error" && <ErrorPanel message={state.message} code={state.code} />}
        {state.kind === "ok" && <QuotePanel data={state.data} submitting={submitting} onRespond={respond} />}
      </div>
    </main>
  );
}

function QuoteSkeleton() {
  const t = useTranslations("pages.quotesPublic");
  return (
    <div data-testid="quote-skeleton" className="mt-6 animate-pulse space-y-3" aria-busy="true" aria-label={t("skeletonLabel")}>
      <div className="h-8 w-40 rounded bg-slate-200" />
      <div className="h-4 w-48 rounded bg-slate-100" />
      <div className="h-4 w-44 rounded bg-slate-100" />
      <div className="h-10 w-full rounded bg-slate-100" />
    </div>
  );
}

function ErrorPanel({
  message,
  code,
}: {
  message: string;
  code: "expired" | "not_found" | "rate_limit" | "other";
}) {
  const t = useTranslations("pages.quotesPublic");
  return (
    <div role="alert" data-testid="quote-error" data-error-code={code} className="mt-6 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <p className="font-medium">{t("errorTitle")}</p>
      <p className="mt-1 text-[13px]">{message}</p>
    </div>
  );
}

function QuotePanel({
  data,
  submitting,
  onRespond,
}: {
  data: ConsumerQuoteView;
  submitting: null | "accept" | "reject";
  onRespond: (d: "accept" | "reject") => void;
}) {
  const t = useTranslations("pages.quotesPublic");
  const tState = useTranslations("pages.quotesPublic.state");
  const stateColor = STATE_COLOR[data.state] ?? STATE_COLOR["sent"];
  const actionable = data.state === "sent";

  return (
    <div className="mt-6 space-y-5" data-testid="quote-view">
      {/* 狀態 + 總額 */}
      <div className="flex items-center justify-between">
        <span data-testid="quote-state" className={`inline-block rounded-full border px-3 py-1 text-[13px] font-medium ${stateColor}`}>
          {tState(data.state)}
        </span>
        <div className="text-right">
          <div className="text-xs text-slate-500">{t("fields.total")}</div>
          <div className="text-2xl font-bold text-slate-900">{money(data.total_amount)}</div>
        </div>
      </div>

      {/* 項目明細（只露客戶價） */}
      <div className="overflow-hidden rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500">
            <tr>
              <th className="px-3 py-2 text-left">{t("fields.item")}</th>
              <th className="px-3 py-2 text-right">{t("fields.qty")}</th>
              <th className="px-3 py-2 text-right">{t("fields.price")}</th>
            </tr>
          </thead>
          <tbody>
            {data.lines.map((l) => (
              <tr key={l.id} className="border-t border-slate-100">
                <td className="px-3 py-2 text-slate-700">{l.item_name}</td>
                <td className="px-3 py-2 text-right text-slate-600">{l.quantity}</td>
                <td className="px-3 py-2 text-right font-mono text-slate-700">{money(l.customer_price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <InfoRow label={t("fields.validUntil")} value={formatDateTime(data.expires_at)} />

      {/* 同意 / 拒絕（僅 sent 狀態） */}
      {actionable ? (
        <div className="flex gap-3">
          <button
            data-testid="quote-accept"
            disabled={submitting != null}
            onClick={() => onRespond("accept")}
            className="flex-1 rounded-md bg-green-600 px-4 py-3 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
          >
            {submitting === "accept" ? t("buttons.accepting") : t("buttons.accept")}
          </button>
          <button
            data-testid="quote-decline"
            disabled={submitting != null}
            onClick={() => onRespond("reject")}
            className="flex-1 rounded-md border border-red-300 px-4 py-3 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            {submitting === "reject" ? t("buttons.declining") : t("buttons.decline")}
          </button>
        </div>
      ) : (
        <div data-testid="quote-status-hint" className="rounded-md bg-slate-50 px-3 py-3 text-center text-[13px] text-slate-600">
          {t(`statusHint.${data.state}`)}
        </div>
      )}

      {data.snapshot_hash && (
        <p className="text-center text-[11px] text-slate-400">
          {t("fields.snapshot")}: <span className="font-mono">{data.snapshot_hash.slice(0, 16)}…</span>
        </p>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-[13px] text-slate-700">{value}</span>
    </div>
  );
}

function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-TW", { hour12: false });
  } catch {
    return iso;
  }
}
