/**
 * 簡易 in-memory promise cache（給 GET request 用）
 *
 * 設計考量：
 * - 不引入 SWR / React Query，避免大改既有 fetch 模式
 * - 共享 in-flight promise — 同一 key 同時呼叫多次只發一個 request
 *   （解決 dashboard 首頁多元件同時 fetch 同 endpoint 的競態）
 * - staleTime（預設 30s）：成功的 response 在這段時間內重複 query 直接
 *   回 cached value
 * - 失敗不 cache：error promise 解析後立即從 map 移除
 * - tenant 隔離：key 帶 tenantId，避免 admin 切租戶後讀到舊資料
 *
 * 不做的事：
 * - 沒 LRU 上限（dashboard 場景頂多 ~10 個 key 同時活著）
 * - 沒 background refetch
 * - 沒 cache 持久化（reload 後消失）
 */

interface CacheEntry<T> {
  promise: Promise<T>;
  /** Date.now() 完成時間；in-flight 時為 0 */
  resolvedAt: number;
}

const cache = new Map<string, CacheEntry<unknown>>();

const DEFAULT_STALE_MS = 30_000;

/**
 * cacheGet — 共享 in-flight promise + staleTime 內回 cached value
 *
 * 用法：
 *   const data = await cacheGet(
 *     `GET:${url}:${tenantId}`,
 *     () => fetch(url).then(r => r.json()),
 *   );
 *
 * @param key   唯一 key（建議含 method + url + 關鍵 headers）
 * @param fetcher 真正執行 fetch 的函式（key miss / stale 時才呼叫）
 * @param staleMs 多久內共用快取（預設 30s）
 */
export async function cacheGet<T>(
  key: string,
  fetcher: () => Promise<T>,
  staleMs: number = DEFAULT_STALE_MS,
): Promise<T> {
  const now = Date.now();
  const hit = cache.get(key) as CacheEntry<T> | undefined;

  if (hit) {
    // in-flight（resolvedAt === 0）→ 共用同一 promise
    // 已解析且未過期 → 直接回 cached promise（其 .then 會立即觸發）
    if (hit.resolvedAt === 0 || now - hit.resolvedAt < staleMs) {
      return hit.promise;
    }
    cache.delete(key);
  }

  const promise = fetcher();
  const entry: CacheEntry<T> = { promise, resolvedAt: 0 };
  cache.set(key, entry as CacheEntry<unknown>);

  promise
    .then(() => {
      // 只有 cache 還在（沒被 invalidate）才更新 resolvedAt
      if (cache.get(key) === entry) {
        entry.resolvedAt = Date.now();
      }
    })
    .catch(() => {
      // 失敗的 promise 不該被快取 — 移除讓下次 query 重試
      if (cache.get(key) === entry) cache.delete(key);
    });

  return promise;
}

/**
 * cacheInvalidate — 清掉指定 key 或 prefix-match
 *
 * 用法（mutate 後）：
 *   cacheInvalidate("GET:/api/v1/work-orders");  // prefix 模糊清
 *   cacheInvalidate("GET:/api/v1/work-orders?limit=100:tenant1");  // 精確清
 */
export function cacheInvalidate(prefix: string): void {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
}

/** 清空整個快取（罕用，例如登出） */
export function cacheClear(): void {
  cache.clear();
}

/** dev-only：暴露 cache size 供觀察 */
export function cacheSize(): number {
  return cache.size;
}
