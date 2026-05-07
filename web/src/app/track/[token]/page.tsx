/**
 * /track/[token] — 消費者匿名工單追蹤頁面（Q3=C 共用機制）
 *
 * 入口：LINE 推播短連結（例：https://app.example.com/track/<signed-token>）
 * 後端：GET /api/v1/public/work-orders/{token}/status (operationId: getWorkOrderPublicStatus)
 *
 * ## Q3=C/Q9=B Implementation TODO
 *
 *  1. 用 generated TS type：components["schemas"]["PublicWorkOrderStatus"]
 *  2. 串接 fetch（無需 Authorization header；走 NEXT_PUBLIC_API_BASE）
 *  3. 處理三種錯誤：
 *       - 404 → "連結無效或已過期"
 *       - 410 → "工單已封存（完工 90 天）"
 *       - 429 → "查詢過於頻繁，請稍候"
 *  4. ETA polling：on_the_way 狀態每 30 秒重抓一次（其他狀態不 poll）
 *  5. 點 technician_phone_masked → 顯示「致電技師」按鈕（href=tel:）
 *  6. 接 LINE LIFF：偵測 user agent，已在 LINE 內開的話可省略額外身分驗證
 *  7. SSR vs CSR：建議 CSR（避免 token 進 server log）
 */

"use client";

import { use } from "react";

type Params = { token: string };

export default function PublicTrackPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { token } = use(params);

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold text-slate-900">
          工單即時追蹤
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Token: <code className="break-all text-xs">{token.slice(0, 16)}…</code>
        </p>

        <div className="mt-6 rounded border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
          <p className="font-medium text-slate-700">
            SKELETON — Q3=C/Q9=B implementation TODO
          </p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-slate-500">
            <li>Call GET /api/v1/public/work-orders/{`{token}`}/status</li>
            <li>Render status / scheduled_at / technician_name / phone</li>
            <li>Handle 404 / 410 / 429 with friendly messaging</li>
            <li>Poll every 30s when status === &quot;on_the_way&quot;</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
