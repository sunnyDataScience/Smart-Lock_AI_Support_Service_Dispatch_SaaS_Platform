/**
 * /scope-change/[token] — 消費者匿名 Scope Change 同意頁面（Q9=B）
 *
 * 入口：技師於現場提案追加項目 → 後端推 LINE 短連結 →
 *       消費者開啟此頁 → 看項目明細 + 金額 → 同意 / 拒絕
 *
 * 後端：
 *   - GET  /api/v1/public/scope-changes/{token}  (operationId: getScopeChangeProposalPublic)
 *   - POST /api/v1/public/scope-changes/{token}  (operationId: respondScopeChangePublic)
 *
 * 設計重點：
 *   - mobile-first（消費者多從 LINE webview 開）
 *   - CSR；不帶 Authorization / X-Tenant-ID（public endpoint）
 *   - 防呆：accept 後 disable 按鈕（avoid 雙擊）
 *   - 狀態為 pending 才顯示按鈕；其他唯讀
 */

"use client";

import { use, useEffect, useState } from "react";

type Params = { token: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

type ProposalStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "expired"
  | "superseded";

interface ProposalItem {
  name: string;
  description?: string | null;
  quantity: number;
  amount_delta: number;
}

interface PublicScopeChangeProposal {
  proposal_id: string;
  work_order_id: string;
  status: ProposalStatus;
  reason?: string | null;
  items: ProposalItem[];
  total_delta: number;
  expires_at: string;
}

interface PublicScopeChangeResult {
  proposal_id: string;
  decision: "accept" | "reject";
  recorded_at: string;
  next_step?: string | null;
}

const STATUS_LABEL: Record<ProposalStatus, string> = {
  pending: "等待您回覆",
  accepted: "已同意",
  rejected: "已拒絕",
  expired: "已逾時",
  superseded: "已被新提案取代",
};

const STATUS_BADGE: Record<ProposalStatus, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  accepted: "bg-green-50 text-green-700 border-green-200",
  rejected: "bg-slate-100 text-slate-700 border-slate-200",
  expired: "bg-red-50 text-red-700 border-red-200",
  superseded: "bg-slate-100 text-slate-700 border-slate-200",
};

type FetchState =
  | { kind: "loading" }
  | { kind: "ok"; data: PublicScopeChangeProposal }
  | { kind: "error"; code: "expired" | "not_found" | "rate_limit" | "other"; message: string };

export default function PublicScopeChangePage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { token } = use(params);
  const [state, setState] = useState<FetchState>({ kind: "loading" });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<PublicScopeChangeResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    (async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/public/scope-changes/${encodeURIComponent(token)}`,
          { cache: "no-store", credentials: "omit" },
        );
        if (cancelled) return;

        if (res.status === 404) {
          setState({
            kind: "error",
            code: "not_found",
            message: "連結無效或已過期，請聯絡客服協助。",
          });
          return;
        }
        if (res.status === 410) {
          setState({
            kind: "error",
            code: "expired",
            message: "連結已失效，請聯絡客服取得最新狀態。",
          });
          return;
        }
        if (res.status === 429) {
          setState({
            kind: "error",
            code: "rate_limit",
            message: "查詢過於頻繁，請稍候再試。",
          });
          return;
        }
        if (!res.ok) {
          setState({
            kind: "error",
            code: "other",
            message: `查詢失敗（${res.status}），請稍後再試。`,
          });
          return;
        }

        const data = (await res.json()) as PublicScopeChangeProposal;
        setState({ kind: "ok", data });
      } catch {
        if (!cancelled) {
          setState({
            kind: "error",
            code: "other",
            message: "網路連線失敗，請稍後再試。",
          });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function respond(decision: "accept" | "reject") {
    if (submitting || result) return;

    if (decision === "accept") {
      const ok = window.confirm("確認同意此追加項目並繼續施工？");
      if (!ok) return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      const res = await fetch(
        `${API_BASE}/api/v1/public/scope-changes/${encodeURIComponent(token)}`,
        {
          method: "POST",
          credentials: "omit",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision }),
        },
      );

      if (res.status === 409) {
        // 提案狀態已變更 → 重新拉
        setSubmitError("提案狀態已變動，正在重新整理…");
        try {
          const refresh = await fetch(
            `${API_BASE}/api/v1/public/scope-changes/${encodeURIComponent(token)}`,
            { cache: "no-store", credentials: "omit" },
          );
          if (refresh.ok) {
            const data = (await refresh.json()) as PublicScopeChangeProposal;
            setState({ kind: "ok", data });
          }
        } catch {
          // ignore — submitError 已顯示
        }
        return;
      }

      if (!res.ok) {
        setSubmitError(`提交失敗（${res.status}），請稍後再試。`);
        return;
      }

      const data = (await res.json()) as PublicScopeChangeResult;
      setResult(data);
    } catch {
      setSubmitError("網路連線失敗，請稍後再試。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold text-slate-900">
          施工範圍變更確認
        </h1>

        {state.kind === "loading" && <ProposalSkeleton />}

        {state.kind === "error" && (
          <div
            role="alert"
            data-testid="scope-error"
            data-error-code={state.code}
            className="mt-6 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700"
          >
            <p className="font-medium">無法載入提案</p>
            <p className="mt-1 text-[13px]">{state.message}</p>
          </div>
        )}

        {state.kind === "ok" && (
          <ProposalPanel
            proposal={state.data}
            submitting={submitting}
            submitError={submitError}
            result={result}
            onRespond={respond}
          />
        )}
      </div>
    </main>
  );
}

function ProposalSkeleton() {
  return (
    <div
      data-testid="scope-skeleton"
      className="mt-6 animate-pulse space-y-3"
      aria-busy="true"
    >
      <div className="h-5 w-40 rounded bg-slate-200" />
      <div className="h-4 w-32 rounded bg-slate-100" />
      <div className="h-20 w-full rounded bg-slate-100" />
      <div className="h-10 w-full rounded bg-slate-100" />
    </div>
  );
}

interface ProposalPanelProps {
  proposal: PublicScopeChangeProposal;
  submitting: boolean;
  submitError: string | null;
  result: PublicScopeChangeResult | null;
  onRespond: (decision: "accept" | "reject") => void;
}

function ProposalPanel({
  proposal,
  submitting,
  submitError,
  result,
  onRespond,
}: ProposalPanelProps) {
  const showButtons = proposal.status === "pending" && !result;

  return (
    <div className="mt-6 space-y-4" data-testid="scope-proposal">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500">提案狀態</span>
        <span
          className={`inline-block rounded-full border px-3 py-1 text-[12px] font-medium ${STATUS_BADGE[proposal.status]}`}
        >
          {STATUS_LABEL[proposal.status]}
        </span>
      </div>

      {proposal.reason && (
        <div className="rounded-md bg-slate-50 p-3 text-[13px] text-slate-700">
          <p className="text-xs text-slate-500">技師說明</p>
          <p className="mt-1">{proposal.reason}</p>
        </div>
      )}

      <div>
        <p className="mb-2 text-xs text-slate-500">追加項目</p>
        <ul className="divide-y divide-slate-200 rounded border border-slate-200">
          {proposal.items.map((item, idx) => (
            <li key={idx} className="flex items-start justify-between p-3">
              <div className="min-w-0 flex-1 pr-3">
                <p className="truncate text-[13px] font-medium text-slate-900">
                  {item.name}
                </p>
                {item.description && (
                  <p className="mt-1 text-[12px] text-slate-500">
                    {item.description}
                  </p>
                )}
                <p className="mt-1 text-[11px] text-slate-400">
                  數量：{item.quantity}
                </p>
              </div>
              <span className="shrink-0 text-[13px] font-mono text-slate-900">
                {formatTwd(item.amount_delta)}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex items-center justify-between rounded-md bg-blue-50 px-3 py-2 text-[14px] text-blue-900">
        <span className="font-medium">總增減金額</span>
        <span className="font-mono font-semibold">
          {formatTwd(proposal.total_delta)}
        </span>
      </div>

      <p className="text-[11px] text-slate-500">
        提案有效至：{formatDateTime(proposal.expires_at)}
      </p>

      {submitError && (
        <div
          role="alert"
          className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800"
        >
          {submitError}
        </div>
      )}

      {result && (
        <div
          role="status"
          className="rounded border border-green-200 bg-green-50 px-3 py-3 text-[13px] text-green-800"
        >
          <p className="font-medium">
            {result.decision === "accept" ? "已同意此提案" : "已拒絕此提案"}
          </p>
          {result.next_step && (
            <p className="mt-1 text-[12px]">{result.next_step}</p>
          )}
        </div>
      )}

      {showButtons && (
        <div className="flex gap-3 pt-1">
          <button
            type="button"
            data-testid="scope-reject-btn"
            disabled={submitting}
            onClick={() => onRespond("reject")}
            className="flex-1 rounded-md border border-slate-300 bg-white px-4 py-2 text-[14px] font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "處理中…" : "拒絕"}
          </button>
          <button
            type="button"
            data-testid="scope-accept-btn"
            disabled={submitting}
            onClick={() => onRespond("accept")}
            className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-[14px] font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "處理中…" : "同意"}
          </button>
        </div>
      )}
    </div>
  );
}

function formatTwd(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}NT$ ${Math.round(n).toLocaleString("en-US")}`;
}

function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-TW", { hour12: false });
  } catch {
    return iso;
  }
}
