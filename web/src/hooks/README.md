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
// wo.items, wo.loading, wo.error, wo.hasMore
// wo.loadMore() — 取下一頁 append
// wo.refresh() — 重置從 cursor=null 開始
```

要求後端回應符合 `PaginatedResponse<T>` 信封：`{items, next_cursor, total?}`。

## 規劃中（待 Phase 3.3）

- 改寫 13 個直接 `import api` 的 page 改用 `usePaginatedFetch`（per ADR-0024 §3 S1）

## 規則

- hooks 不可直接 import `@/lib/api.ts` 的 raw fetch — 應透過 thin wrapper（如 `usePaginatedFetch`）或 domain-specific hook 包裝
- `"use client"` 一律放第一行
