"use client";

/**
 * usePollingEffect — 週期性執行 fn(signal)，用於「有新資料時自動刷新」。
 *
 * 設計考量：
 * - 不引入 SWR / React Query；與 lib/cache 的 30s staleTime 不打架 —— 呼叫端把
 *   傳入的 signal 交給 `api.get(path, { signal })` 即 bypass 快取取新鮮資料
 *   （見 lib/api.ts：GET 帶 signal 就不走 cache）。
 * - 防重疊：前一次 fn 未結束不啟動下一次（慢後端不會堆積請求）。
 * - 分頁隱藏時暫停（document.hidden）省流量；回到前景立即補跑一次，不必等整個 interval。
 * - 卸載時 abort 進行中的 fn（呼叫端據 signal 中止 fetch、避免對已卸載元件 setState）。
 *
 * 不做的事：不管 fn 的錯誤顯示（輪詢失敗靜默，下一 tick 再試）、不回傳狀態。
 *
 * 用法：
 *   usePollingEffect(
 *     async (signal) => { const res = await api.get(path, { signal }); setX(res); },
 *     { intervalMs: 8000, enabled: !loading },
 *   );
 */

import { useEffect, useRef } from "react";

export interface UsePollingEffectOptions {
  /** 輪詢間隔（毫秒）。<= 0 視為停用。 */
  intervalMs: number;
  /** 是否啟用，預設 true。false 時完全不輪詢。 */
  enabled?: boolean;
}

export function usePollingEffect(
  fn: (signal: AbortSignal) => Promise<void>,
  { intervalMs, enabled = true }: UsePollingEffectOptions,
): void {
  // fn 多為 caller inline arrow（每 render 新 reference）；用 ref 穩定身份，
  // 避免放進 effect deps 造成每 render 重建 interval。
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!enabled || intervalMs <= 0) return;

    let stopped = false;
    let running = false;
    let controller: AbortController | null = null;

    const tick = () => {
      if (stopped || running) return;
      if (typeof document !== "undefined" && document.hidden) return;
      running = true;
      controller = new AbortController();
      void fnRef
        .current(controller.signal)
        .catch(() => {
          // 輪詢失敗靜默 —— 呼叫端自理錯誤顯示，下一 tick 再試
        })
        .finally(() => {
          running = false;
        });
    };

    const timer = setInterval(tick, intervalMs);

    // 回到前景立即補跑一次（不用枯等整個 interval）
    const onVisible = () => {
      if (typeof document !== "undefined" && !document.hidden) tick();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      stopped = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      controller?.abort();
    };
  }, [enabled, intervalMs]);
}
