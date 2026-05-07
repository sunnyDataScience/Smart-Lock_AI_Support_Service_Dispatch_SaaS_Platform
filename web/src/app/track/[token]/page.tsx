/**
 * /track/[token] — 消費者匿名工單追蹤頁面（Q3=C 共用機制）
 *
 * 入口：LINE 推播短連結（例：https://app.example.com/track/<signed-token>）
 * 後端：GET /api/v1/public/work-orders/{token}/status (operationId: getWorkOrderPublicStatus)
 *
 * 設計重點：
 *   - mobile-first（消費者主要從 LINE webview 開啟）
 *   - CSR（避免 token 進 server log）
 *   - 不帶 Authorization / X-Tenant-ID header（public endpoint 用 token 簽章驗證）
 *   - 錯誤處理：404 → 連結無效；410 → 連結已失效
 *   - PII 已由後端 mask（technician_name 只露姓 + 「師傅」；phone 末四碼）
 */

"use client";

import { use, useEffect, useState } from "react";

type Params = { token: string };

// 直接打 public endpoint — 不走 src/lib/api.ts（會帶 Authorization / X-Tenant-ID）
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

type Status =
  | "pending"
  | "scheduled"
  | "on_the_way"
  | "in_progress"
  | "completed"
  | "cancelled";

interface PublicWorkOrderStatus {
  work_order_id: string;
  status: Status;
  scheduled_at?: string | null;
  completed_at?: string | null;
  technician_name?: string | null;
  technician_phone_masked?: string | null;
  eta_minutes?: number | null;
}

const STATUS_LABEL: Record<Status, string> = {
  pending: "預約中",
  scheduled: "已排定",
  on_the_way: "技師前往中",
  in_progress: "施工中",
  completed: "已完工",
  cancelled: "已取消",
};

const STATUS_COLOR: Record<Status, string> = {
  pending: "bg-slate-100 text-slate-700 border-slate-200",
  scheduled: "bg-blue-50 text-blue-700 border-blue-200",
  on_the_way: "bg-amber-50 text-amber-700 border-amber-200",
  in_progress: "bg-indigo-50 text-indigo-700 border-indigo-200",
  completed: "bg-green-50 text-green-700 border-green-200",
  cancelled: "bg-red-50 text-red-700 border-red-200",
};

type FetchState =
  | { kind: "loading" }
  | { kind: "ok"; data: PublicWorkOrderStatus }
  | { kind: "error"; message: string; code: "expired" | "not_found" | "rate_limit" | "other" };

export default function PublicTrackPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { token } = use(params);
  const [state, setState] = useState<FetchState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function fetchStatus() {
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/public/work-orders/${encodeURIComponent(token)}/status`,
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

        const data = (await res.json()) as PublicWorkOrderStatus;
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
    }

    setState({ kind: "loading" });
    fetchStatus();

    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold text-slate-900">工單即時追蹤</h1>

        {state.kind === "loading" && <TrackSkeleton />}

        {state.kind === "error" && (
          <ErrorPanel message={state.message} code={state.code} />
        )}

        {state.kind === "ok" && <StatusPanel data={state.data} />}
      </div>
    </main>
  );
}

function TrackSkeleton() {
  return (
    <div
      data-testid="track-skeleton"
      className="mt-6 animate-pulse space-y-3"
      aria-busy="true"
      aria-label="載入工單狀態中"
    >
      <div className="h-6 w-32 rounded bg-slate-200" />
      <div className="h-4 w-48 rounded bg-slate-100" />
      <div className="h-4 w-40 rounded bg-slate-100" />
      <div className="h-4 w-44 rounded bg-slate-100" />
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
  return (
    <div
      role="alert"
      data-testid="track-error"
      data-error-code={code}
      className="mt-6 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700"
    >
      <p className="font-medium">無法載入工單資訊</p>
      <p className="mt-1 text-[13px]">{message}</p>
    </div>
  );
}

function StatusPanel({ data }: { data: PublicWorkOrderStatus }) {
  const showEta =
    data.status === "on_the_way" && data.eta_minutes != null;

  return (
    <div className="mt-6 space-y-4" data-testid="track-status">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500">工單編號</span>
        <span className="font-mono text-xs text-slate-700">
          #{data.work_order_id.slice(0, 8)}
        </span>
      </div>

      <div>
        <span className="text-xs text-slate-500">目前狀態</span>
        <div className="mt-1">
          <span
            data-testid="status-badge"
            className={`inline-block rounded-full border px-3 py-1 text-[13px] font-medium ${STATUS_COLOR[data.status]}`}
          >
            {STATUS_LABEL[data.status]}
          </span>
        </div>
      </div>

      {showEta && (
        <div className="rounded-md bg-amber-50 px-3 py-2 text-[13px] text-amber-800">
          技師預計 <strong>{data.eta_minutes}</strong> 分鐘內抵達
        </div>
      )}

      <InfoRow label="預約時間" value={formatDateTime(data.scheduled_at)} />
      <InfoRow label="完工時間" value={formatDateTime(data.completed_at)} />
      <InfoRow label="服務技師" value={data.technician_name ?? "—"} />

      {data.technician_phone_masked && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-500">技師電話</span>
          <span className="font-mono text-[13px] text-slate-700">
            {data.technician_phone_masked}
          </span>
        </div>
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
