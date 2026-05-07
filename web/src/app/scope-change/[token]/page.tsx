/**
 * /scope-change/[token] — 消費者匿名 Scope Change 同意頁面（Q9=B）
 *
 * 入口：技師於現場提案追加項目 → 後端推 LINE 短連結 →
 *       消費者開啟此頁 → 看項目明細 + 金額 → 同意 / 拒絕
 *
 * 後端：
 *   - GET  /api/v1/public/scope-changes/{token} (operationId: getScopeChangeProposalPublic)
 *   - POST /api/v1/public/scope-changes/{token} (operationId: respondScopeChangePublic)
 *
 * ## Q3=C/Q9=B Implementation TODO
 *
 *  1. Type：components["schemas"]["PublicScopeChangeProposal"]
 *  2. 顯示提案 items[]、總額、reason、expires_at 倒數
 *  3. accept/reject 按鈕 → POST + 簽收彈窗（記錄 IP / UA via 後端）
 *  4. 處理 status：
 *       - pending → 顯示按鈕
 *       - accepted/rejected/expired/superseded → 唯讀顯示結果
 *  5. 提交後：禁用按鈕、顯示 next_step 訊息
 *  6. 防誤觸：accept 需二次確認（modal）
 *  7. 失敗復原：POST 409 → 重新 GET 拉最新狀態
 *  8. LINE LIFF：可選擇關閉 webview / 回 chat
 */

"use client";

import { use } from "react";

type Params = { token: string };

export default function PublicScopeChangePage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { token } = use(params);

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold text-slate-900">
          施工範圍變更確認
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Token: <code className="break-all text-xs">{token.slice(0, 16)}…</code>
        </p>

        <div className="mt-6 rounded border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
          <p className="font-medium text-slate-700">
            SKELETON — Q3=C/Q9=B implementation TODO
          </p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-slate-500">
            <li>GET /api/v1/public/scope-changes/{`{token}`} 拉提案明細</li>
            <li>Render items[] + total_delta + expires_at 倒數</li>
            <li>POST 同上 path 帶 decision: &quot;accept&quot; | &quot;reject&quot;</li>
            <li>狀態為 pending 時才顯示按鈕；其他狀態唯讀顯示結果</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
