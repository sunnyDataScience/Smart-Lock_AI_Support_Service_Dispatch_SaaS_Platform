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
 * - 不自動 invalidate cache（mutation 後請自行 `mutate(updater)` 或 `refresh()`）
 *
 * 用法：
 *   const wo = usePaginatedFetch<WorkOrder>({
 *     path: tenantPath("/work-orders"),
 *     query: { status: "open" },
 *     pageSize: 20,
 *   });
 *   wo.items, wo.loading, wo.error, wo.hasMore, wo.loadMore(), wo.refresh()
 *
 *   // 區分 initial skeleton vs inline spinner：
 *   wo.loadingInitial  // true 時 page 顯示整列 skeleton
 *   wo.loadingMore     // true 時列表底顯示 spinner（含 refresh 場景）
 *
 *   // CRUD 後 optimistic local update：
 *   await api.delete(tenantPath(`/work-orders/${id}`));
 *   wo.mutate(prev => prev.filter(w => w.id !== id));
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";

/** 後端標準分頁回應信封（對齊 OpenAPI `CursorPage` schema） */
export interface PaginatedResponse<T> {
  items: T[];
  next_cursor?: string | null;
  has_more?: boolean;
  total_count?: number;
}

export interface UsePaginatedFetchOptions {
  /** API path，如 tenantPath("/work-orders") */
  path: string;
  /** 每頁筆數，預設 20 */
  pageSize?: number;
  /** 額外 query params（不含 limit / cursor — hook 自動加） */
  query?: Record<string, string | number | boolean | undefined>;
  /**
   * 觸發重新載入的 key（query 變動時請改本字串，hook 會偵測並 refresh）。
   * 範例：`queryKey={`status=${filter}`}`。缺省時只在 mount 載入一次。
   */
  queryKey?: string;
  /** 是否啟用 fetch（false 時不發 request，用於條件式載入），預設 true */
  enabled?: boolean;
  /**
   * 客製錯誤訊息格式（譬如要顯示 errorCode + status）。
   * 不指定時使用 `toUserMessage` — 取 `ApiError.message` 或 fallback 字串。
   */
  formatError?: (err: unknown) => string;
  /**
   * 每次 fetch 成功後的副作用 hook — 可拿 raw response 訪問 hook 標準
   * 信封以外的自訂 field（如 notifications 的 `unread_count`）。
   * 不指定時不執行任何副作用。
   */
  onSuccess?: <R extends PaginatedResponse<unknown>>(res: R) => void;
  /**
   * 響應 item 轉換器（CR-0005/0006 step 3/3：v2 meta-wrap shape → flat UI shape）。
   * 不指定時 raw items 直接套用泛型 T。
   *
   * @example
   *   path: tenantPath("/sops/drafts"),
   *   mapItem: (doc: KBDocumentSop) => kbDocumentToSopDraft(doc),
   */
  mapItem?: (raw: unknown) => unknown;
}

export interface UsePaginatedFetchResult<T> {
  items: T[];
  /** next_cursor — null 表示已到底 */
  cursor: string | null;
  /** 還能 loadMore 嗎 */
  hasMore: boolean;
  /** 後端回應 `total_count` — 後端有提供時才有值 */
  totalCount: number | undefined;
  /** 上次成功 fetch 完成的時間（供 page 顯示「上次更新 hh:mm」）；初次未完成前為 null */
  lastFetchedAt: Date | null;
  /** 任何 fetch 進行中（首次載入、loadMore、或 refresh） */
  loading: boolean;
  /** 初次載入中（items 仍空、首頁尚未到貨）— 用於顯示整列 skeleton */
  loadingInitial: boolean;
  /** 追加載入或 refresh 中（items 已有資料、底部 spinner / refresh icon 旋轉） */
  loadingMore: boolean;
  /** user-facing 錯誤訊息（ApiError.message 或 generic）；null 表示無錯 */
  error: string | null;
  /** 取下一頁（append） */
  loadMore: () => Promise<void>;
  /** 重新從 cursor=null 開始（reset） */
  refresh: () => Promise<void>;
  /**
   * 外部 CRUD 後就地更新 hook items（不重新打 API）— 對齊 SWR `mutate` 慣例。
   *
   * @example
   *   // 樂觀 delete（manuals 為 KEEP flat，沿用 legacy path）
   *   await api.delete(`/api/v1/manuals/${id}`);
   *   mutate(prev => prev.filter(m => m.id !== id));
   *
   *   // 樂觀 upsert（新增至最前）
   *   const created = await api.post(...);
   *   mutate(prev => [created, ...prev.filter(m => m.id !== created.id)]);
   */
  mutate: (updater: (items: T[]) => T[]) => void;
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
    queryKey,
    enabled = true,
    formatError = toUserMessage,
    onSuccess,
    mapItem,
  } = opts;

  const [items, setItems] = useState<T[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [totalCount, setTotalCount] = useState<number | undefined>(undefined);
  const [lastFetchedAt, setLastFetchedAt] = useState<Date | null>(null);
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
        const rawItems = res.items ?? [];
        const newItems = (mapItem ? rawItems.map(mapItem) : rawItems) as T[];
        setItems((prev) => (append ? [...prev, ...newItems] : newItems));
        const nextCursor = res.next_cursor ?? null;
        setCursor(nextCursor);
        // 優先用後端權威旗標 has_more；缺欄位時 fallback 用 next_cursor 判斷
        setHasMore(res.has_more ?? nextCursor !== null);
        // total_count 只有後端有提供時更新；缺欄位時保留前次值
        if (typeof res.total_count === "number") setTotalCount(res.total_count);
        setLastFetchedAt(new Date());
        // caller 可訪問 raw response 訪問 hook 標準信封外的自訂 field
        onSuccess?.(res);
      } catch (err) {
        setError(formatError(err));
        // 失敗保留現有 items；hasMore 不變（讓 user 重試 loadMore 或 refresh）
      } finally {
        setLoading(false);
      }
    },
    [path, pageSize, enabled, formatError, onSuccess],
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

  const mutate = useCallback((updater: (items: T[]) => T[]) => {
    setItems(updater);
  }, []);

  // 首次 + path / pageSize / enabled / queryKey 變動時觸發（reset to first page）
  useEffect(() => {
    if (enabled) {
      fetchPage(null, false);
    }
    // queryKey 是顯式觸發 refetch 的 dependency；query object 本身不放入避免無謂 re-fetch
  }, [fetchPage, enabled, queryKey]);

  // derived loading flags — caller 可二選一展示（初次 skeleton vs 增量 inline）
  const loadingInitial = loading && items.length === 0;
  const loadingMore = loading && items.length > 0;

  return {
    items,
    cursor,
    hasMore,
    totalCount,
    lastFetchedAt,
    loading,
    loadingInitial,
    loadingMore,
    error,
    loadMore,
    refresh,
    mutate,
  };
}
