"use client";

import { useEffect, useState } from "react";
import { WifiOff, Wifi } from "lucide-react";

/**
 * NetworkErrorBanner — 網路斷線/復線橫幅
 *
 * 監聽 navigator.onLine + window 的 'online'/'offline' 事件：
 *   - 離線時：顯示橘色警告橫幅，固定於頁面頂部
 *   - 重新連線時：短暫顯示 3s 綠色「已恢復連線」後自動隱藏
 *
 * 不強制 mount 在 layout — 由上層應用（例如未來的 ToastProvider）
 * 自行決定是否掛載、掛在哪個 layout group。SSR 安全：在 hydrate 完成前
 * 不渲染任何東西，避免 navigator is not defined。
 *
 * 為什麼不接 Toast：Toast 是 transient，網路斷線是 persistent state，
 * 必須一直顯示直到復線；用 banner 語意更貼近實際行為。
 */

type Status = "online" | "offline" | "reconnected";

const RECONNECT_BANNER_MS = 3000;

export default function NetworkErrorBanner() {
  const [status, setStatus] = useState<Status>("online");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // 初始化用 navigator.onLine 校正首次狀態（hydrate 完才能讀）
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      setStatus("offline");
    }

    const handleOffline = () => setStatus("offline");
    const handleOnline = () => {
      // 從 offline 切到 reconnected，3 秒後自動消失
      setStatus((prev) => (prev === "offline" ? "reconnected" : "online"));
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  // reconnected 狀態 3s 後自動回到 online
  useEffect(() => {
    if (status !== "reconnected") return;
    const timer = window.setTimeout(() => {
      setStatus("online");
    }, RECONNECT_BANNER_MS);
    return () => window.clearTimeout(timer);
  }, [status]);

  if (!mounted || status === "online") return null;

  const isOffline = status === "offline";

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 top-0 z-[60] flex justify-center px-4 pt-2"
    >
      <div
        className={`flex animate-[fadeIn_180ms_ease-out] items-center gap-2 rounded-md border px-3 py-2 text-[13px] font-medium shadow-sm ${
          isOffline
            ? "border-[var(--badge-warn-bg,#FEF3C7)] bg-[var(--badge-warn-bg,#FEF3C7)] text-[var(--badge-warn-fg,#B45309)]"
            : "border-[var(--badge-success-bg,#D1FAE5)] bg-[var(--badge-success-bg,#D1FAE5)] text-[var(--badge-success-fg,#065F46)]"
        }`}
      >
        {isOffline ? (
          <WifiOff className="h-4 w-4" aria-hidden="true" />
        ) : (
          <Wifi className="h-4 w-4" aria-hidden="true" />
        )}
        <span>
          {isOffline ? "網路連線中斷，正在嘗試重連…" : "已恢復連線"}
        </span>
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
