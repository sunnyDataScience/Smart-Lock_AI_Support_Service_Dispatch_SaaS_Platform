# `web/src/hooks/`

React hooks 統一存放位置（per ADR-0024 §3 S1 Phase 3.1）。

## 命名慣例

- 檔名：`use*.ts`（單檔 hook）
- 對應底層 transport / 純函式 utility 留在 `web/src/lib/`（如 `lib/realtime.ts` 是 transport，`hooks/useRealtimeChannel.ts` 是 React 包裝）

## 現有 hooks

| Hook | 用途 | 底層 |
|---|---|---|
| `useRealtimeChannel` | 訂閱單一 realtime 頻道 | `@/lib/realtime` |
| `useSSEChannel` | 訂閱單一 SSE 頻道 | `@/lib/sse` |
| `useBroadcast` | BroadcastChannel API 包裝（跨 tab 通訊）| 原生 BroadcastChannel |
| `usePaginatedFetch` | cursor-based 分頁列表 fetch（loading/error/cache 抽象）| `@/lib/api` + `@/lib/cache` |

### `usePaginatedFetch` 用法

```tsx
const wo = usePaginatedFetch<WorkOrder>({
  path: "/api/v1/work-orders",
  query: { status: "open" },
  pageSize: 20,
});
// wo.items, wo.error, wo.hasMore
// wo.loadMore() — 取下一頁 append
// wo.refresh() — 重置從 cursor=null 開始
// wo.mutate(prev => prev.filter(...)) — CRUD 後就地更新 items（SWR mutate 慣例）

// loading 區分（per Phase 3.3 backlog C1）
wo.loadingInitial  // 首頁尚未到貨 — 顯示整列 skeleton
wo.loadingMore     // items 已有資料、append 或 refresh 中 — 顯示底部 spinner
wo.loading         // 上述任一（任何 fetch 進行中）
```

要求後端回應符合 `PaginatedResponse<T>` 信封：`{items, next_cursor, has_more, total_count?}`。

### `mutate` API（per Phase 3.3 backlog C2）

對齊 SWR `mutate` 慣例 — caller 在 CRUD 後就地更新 hook items，避免 `refresh()` 全抓帶來的「資料消失再出現」閃爍：

```tsx
// delete
await api.delete(`/api/v1/manuals/${id}`);
wo.mutate(prev => prev.filter(m => m.id !== id));

// upsert（新增至最前）
const created = await api.post(...);
wo.mutate(prev => [created, ...prev.filter(m => m.id !== created.id)]);

// patch single
wo.mutate(prev => prev.map(m => m.id === id ? { ...m, status: "done" } : m));
```

注意：mutate 是純 local state update，不會觸發後端重新 fetch；若需要對齊後端最新，請改用 `refresh()`。

## 規劃中（Phase 3.3 backlog）

詳見 [docs/4-exploration/phase-3.3-backlog-2026-q2.md](../../../../docs/4-exploration/phase-3.3-backlog-2026-q2.md)：
- 10 個 page 待遷移（admin/customers、refunds、warranty-claims、sentiment-alerts 等）
- 1 個 hook 擴展待評估（非分頁版 `useFetch` for inventory）

## 規則

- hooks 不可直接 import `@/lib/api.ts` 的 raw fetch — 應透過 thin wrapper（如 `usePaginatedFetch`）或 domain-specific hook 包裝
- `"use client"` 一律放第一行
