"use client";

import { useState } from "react";
import { ShieldAlert, X, RefreshCw } from "lucide-react";
import { useRealtimeChannel } from "@shared/hooks/useRealtimeChannel";

/**
 * 訂閱 /realtime/rbac，收到 RbacPermissionChanged 後顯示頂部 banner，
 * 提示使用者重新整理頁面以套用最新權限。
 *
 * 設計：登入後 session 不知道權限是否變更，故收到事件後不能直接靜默更新
 * （後端 token claim 不會自動更新），需要使用者主動 reload 觸發 token refresh。
 */
export default function RbacChangedBanner() {
  const [pending, setPending] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useRealtimeChannel<{ role_id?: string; changed_codes?: string[] }>({
    channelPath: "/realtime/rbac",
    onMessage: () => {
      setPending(true);
      setDismissed(false);
    },
  });

  if (!pending || dismissed) return null;

  return (
    <div className="fixed left-1/2 top-4 z-[60] flex w-[min(92vw,560px)] -translate-x-1/2 items-center gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 shadow-lg">
      <ShieldAlert className="h-4 w-4 flex-shrink-0 text-amber-700" />
      <div className="flex flex-1 flex-col">
        <span className="text-[13px] font-semibold text-amber-900">
          權限已更新
        </span>
        <span className="text-[11px] text-amber-800">
          系統管理員調整了角色權限，請重新整理頁面以套用最新設定
        </span>
      </div>
      <button
        type="button"
        onClick={() => location.reload()}
        className="flex items-center gap-1 rounded-md bg-amber-600 px-3 py-1 text-[12px] font-semibold text-white hover:bg-amber-700"
      >
        <RefreshCw className="h-3 w-3" />
        重新整理
      </button>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="flex h-7 w-7 items-center justify-center rounded-md text-amber-800 hover:bg-amber-100"
        aria-label="先不處理"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}
