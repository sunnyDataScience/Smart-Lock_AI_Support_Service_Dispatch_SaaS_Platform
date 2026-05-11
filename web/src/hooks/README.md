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

## 規劃中（待 Phase 3.2/3.3）

- `usePaginatedFetch` — 共用 loading/error/cache 抽象（取代 13 個 page 內重複的 useState+setLoading+setError pattern）

## 規則

- hooks 不可直接 import `@/lib/api.ts` 的 raw fetch — 應透過 thin wrapper（如 `usePaginatedFetch`）或 domain-specific hook 包裝
- `"use client"` 一律放第一行
