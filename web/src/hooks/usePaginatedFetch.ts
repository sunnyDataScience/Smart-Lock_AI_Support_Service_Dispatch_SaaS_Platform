"use client";

/**
 * usePaginatedFetch — cursor-based 分頁列表 fetch 抽象
 *
 * 提煉自 web/src/app 內 13+ 個 page.tsx 重複的 useState + setLoading +
 * setError + fetchPage(cursor, append) 模式（per ADR-0024 §3 S1 Phase 3.2）。
 *
 * 設計目標：
 * - 不引入 SWR / React Query（lib/cache.ts 已提供 30s staleTime + dedup）
 * - 直接套在後端「{items, next_cursor, total?}」的標準分頁回應上
 * - 共用 ApiError → user-facing 訊息轉換
 * - 提供 loadMore / refresh 兩個明確動作
 *
 * 不做的事：
 * - 不處理 offset-based 分頁（只 cursor-based）
 * - 不處理 mutation（POST/PATCH/DELETE 仍直接呼 api.* + 手動 invalidate cache）
 * - 不做 optimistic update
 *
 * 用法：
 *   const wo = usePaginatedFetch<WorkOrder>({
 *     path: "/api/v1/work-orders",
 *     query: { status: "open" },
 *     pageSize: 20,
 *   });
 *   wo.items, wo.loading, wo.error, wo.hasMore, wo.loadMore(), wo.refresh()
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";

/** 後端標準分頁回應信封 */
export interface PaginatedResponse<T> {
  items: T[];
  next_cursor?: string | null;
  total?: number;
}

export interface UsePaginatedFetchOptions {
  /** API path，如 "/api/v1/work-orders" */
  path: string;
  /** 每頁筆數，預設 20 */
  pageSize?: number;
  /** 額外 query params（不含 limit / cursor — hook 自動加） */
  query?: Record<string, string | number | boolean | undefined>;
  /** 是否啟用 fetch（false 時不發 request，用於條件式載入），預設 true */
  enabled?: boolean;
}

export interface UsePaginatedFetchResult<T> {
  items: T[];
  /** next_cursor — null 表示已到底 */
  cursor: string | null;
  /** 還能 loadMore 嗎 */
  hasMore: boolean;
  /** 任何 fetch 進行中（首次載入或 loadMore） */
  loading: boolean;
  /** user-facing 錯誤訊息（ApiError.message 或 generic）；null 表示無錯 */
  error: string | null;
  /** 取下一頁（append） */
  loadMore: () => Promise<void>;
  /** 重新從 cursor=null 開始（reset） */
  refresh: () => Promise<void>;
}

const DEFAULT_PAGE_SIZE = 20;

/**
 * 將 ApiError / unknown 轉為 user-facing 訊息。
 * 業務頁可在 catch 後自行覆寫 setError，本 helper 提供 sensible default。
 */
function toUserMessage(err: unknown): string {
  if (err instanceof ApiError) {
    return err.message || `HTTP ${err.status}`;
  }
  if (err instanceof Error) return err.message;
  return "未知錯誤";
}

export function usePaginatedFetch<T>(
  opts: UsePaginatedFetchOptions,
): UsePaginatedFetchResult<T> {
  const {
    path,
    pageSize = DEFAULT_PAGE_SIZE,
    query,
    enabled = true,
  } = opts;

  const [items, setItems] = useState<T[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // query 為 object，每次 render 都會是新 reference；用 ref 穩定身份避免無謂 re-fetch
  const queryRef = useRef(query);
  queryRef.current = query;

  const fetchPage = useCallback(
    async (afterCursor: string | null, append: boolean) => {
      if (!enabled) return;
      setLoading(true);
      setError(null);
      try {
        const q: Record<string, string | number | boolean | undefined> = {
          ...queryRef.current,
          limit: pageSize,
        };
        if (afterCursor) q.cursor = afterCursor;

        const res = await api.get<PaginatedResponse<T>>(path, { query: q });
        const newItems = res.items ?? [];
        setItems((prev) => (append ? [...prev, ...newItems] : newItems));
        const nextCursor = res.next_cursor ?? null;
        setCursor(nextCursor);
        setHasMore(nextCursor !== null);
      } catch (err) {
        setError(toUserMessage(err));
        // 失敗保留現有 items；hasMore 不變（讓 user 重試 loadMore 或 refresh）
      } finally {
        setLoading(false);
      }
    },
    [path, pageSize, enabled],
  );

  const loadMore = useCallback(async () => {
    if (loading || !hasMore || !cursor) return;
    await fetchPage(cursor, true);
  }, [fetchPage, loading, hasMore, cursor]);

  const refresh = useCallback(async () => {
    setCursor(null);
    setHasMore(true);
    await fetchPage(null, false);
  }, [fetchPage]);

  // 首次 + path/pageSize/enabled 變動時觸發
  useEffect(() => {
    if (enabled) {
      fetchPage(null, false);
    }
  }, [fetchPage, enabled]);

  return { items, cursor, hasMore, loading, error, loadMore, refresh };
}
