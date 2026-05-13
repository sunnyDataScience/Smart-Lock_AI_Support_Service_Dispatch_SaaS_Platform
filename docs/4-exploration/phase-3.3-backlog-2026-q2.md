# Phase 3.3 剩餘 Page Backlog（2026 Q2）

**對應 ADR：** [ADR-0024](../1-decisions/ADR-0024-tier1-refactor-revised.md) §3 S1
**對應 WBS：** [wbs-2026-q2-tactical-refactor.md](./wbs-2026-q2-tactical-refactor.md) §4.4
**狀態：** **MOSTLY DONE**（2026-05-12 完成 backlog 8/10；剩 2 個 page 因「不分頁/自訂信封」結構性不適 hook，標 NOT-APPLICABLE）
**建立日：** 2026-05-12 / **最終更新：** 2026-05-12

---

## 背景

ADR-0024 §3 S1 Phase 3.3 hands-on 階段（2026-05-11）確認適用 `usePaginatedFetch` 的 web page 實際為 **18 個**（plan 原估 13 個）。當輪推進完成 **8 個 page 遷移 + hook 演化 5 個擴展點**（has_more / totalCount / lastFetchedAt / queryKey / formatError），剩餘 10 個 page 因結構性阻塞（modal/mutate/dual-loading/多 tab/不分頁）留作 backlog 由獨立 PR 處理。

本文件記錄各 page 的具體阻塞點、hook 擴展需求、工作量估計，作為後續 pick up 時的起手依據。

## 已完成（16/18）

### 第 1 輪（PR #68-#72，2026-05-11）

| # | Page | PR |
|---|---|---|
| 1 | `web/src/app/work-orders/page.tsx` | #68 |
| 2 | `web/src/app/conversations/page.tsx` | #69 |
| 3 | `web/src/app/problem-cards/page.tsx` | #69 |
| 4 | `web/src/app/technicians/page.tsx` | #69 |
| 5 | `web/src/app/knowledge-base/sop-drafts/page.tsx` | #70 |
| 6 | `web/src/app/accounting/invoices/page.tsx` | #71 |
| 7 | `web/src/app/accounting/vouchers/page.tsx` | #71 |
| 8 | `web/src/app/admin/audit-events/page.tsx` | #72 |

### 第 2 輪（PR #75-#83，2026-05-12）— backlog 推進

| # | Page | PR | Hook 擴展 |
|---|---|---|---|
| C1 + C2 | hook 補 loadingInitial/loadingMore + mutate | #75 | — |
| 9 | `web/src/app/admin/customers/page.tsx` | #76 | 用 loadingInitial/loadingMore |
| 10 | `web/src/app/knowledge-base/family-reviews/page.tsx` | #77 | 雙清單頁 (history用hook) |
| 11 | `web/src/app/admin/sentiment-alerts/page.tsx` | #78 | mutate |
| 12 | `web/src/app/knowledge-base/manuals/page.tsx` | #79 | mutate |
| 13 | `web/src/app/admin/refunds/page.tsx` | #80 | mutate + refresh aliasing |
| 14 | `web/src/app/admin/warranty-claims/page.tsx` | #81 | mutate + queryKey on activeTab |
| 15 | `web/src/app/knowledge-base/cases/page.tsx` | #82 | main list 用 hook (search/export 保留) |
| 16 | `web/src/app/notifications/page.tsx` | #83 | mutate + onSuccess (unread_count) |

---

## A. Future PR 群 — 全部完成或標 NOT-APPLICABLE

| # | Page | 結果 | PR / 備註 |
|---|---|---|---|
| A1 | `web/src/app/admin/customers/page.tsx` | ✅ DONE | PR #76 — 用 loadingInitial/loadingMore |
| A2 | `web/src/app/admin/refunds/page.tsx` | ✅ DONE | PR #80 — 用 mutate + refresh aliasing；原 plan 寫「先抽 modal」hands-on 後判斷 modal/state 緊密耦合，抽出反而增加 prop 噪音 → 就地用 hook |
| A3 | `web/src/app/admin/warranty-claims/page.tsx` | ✅ DONE | PR #81 — 用 mutate + queryKey on activeTab；對齊 A2 pattern |
| A4 | `web/src/app/admin/sentiment-alerts/page.tsx` | ✅ DONE | PR #78 — 用 mutate API |
| A5 | `web/src/app/admin/inventory/page.tsx` | ❌ **NOT-APPLICABLE** | **不分頁**（single fetch limit=50）+ 客端 filter + summary computation；usePaginatedFetch 結構性不適。保留 page-local 設計 — 收益 < 風險 |
| A6 | `web/src/app/account/schedule/page.tsx` | ❌ **NOT-APPLICABLE** | hands-on 後發現 response 信封是 `ScheduleResponse`（含 workOrdersPerDay / leaveDays / standbyDays / pendingRequests 五個獨立 field），完全非 `PaginatedResponse` 信封；硬塞 hook 反扭曲 |

---

## B. 獨立 PR 群 — 全部完成

| # | Page | 結果 | PR / 備註 |
|---|---|---|---|
| B1 | `web/src/app/notifications/page.tsx` | ✅ DONE | PR #83 — 用 mutate + `onSuccess` callback 訪問自訂 field `unread_count`（hook 新增 C4 extension）；原 plan 預估自訂 useNotificationList，hands-on 後改為 hook generic onSuccess 即可 |
| B2 | `web/src/app/knowledge-base/cases/page.tsx` | ✅ DONE | PR #82 — main list 用 hook，search/export 保留 page-local（單頁使用，抽 useSearch hook ROI 不對） |
| B3 | `web/src/app/knowledge-base/manuals/page.tsx` | ✅ DONE | PR #79 — 用 mutate API（delete filter + upload unshift） |
| B4 | `web/src/app/knowledge-base/family-reviews/page.tsx` | ✅ DONE | PR #77 — history 用 hook + queryKey on actionFilter；pending 保留原 useState |

---

## C. Hook 擴展總清單（執行結果）

| 擴展 | 結果 | PR | 用途 |
|---|---|---|---|
| C1 `loadingInitial` + `loadingMore` (derived) | ✅ DONE | #75 | 區分初次載入 skeleton vs loadMore inline spinner |
| C2 `mutate(updater: (items: T[]) => T[]): void` | ✅ DONE | #75 | 外部 CRUD 後同步更新 hook items（SWR 慣例） |
| C3 非分頁版本 `useFetch<T>(path, opts)` | ❌ **NOT BUILT** | — | hands-on A5/A6 後決定不做：兩個 candidate page (inventory + schedule) 結構各異（一個 client filter + summary、一個 5-field 自訂信封），共用 hook 反而 over-fit；保留 page-local |
| C4 `onSuccess?: (res) => void` callback | ✅ DONE | #83 | 訪問 hook 標準信封外的自訂 field（如 notifications 的 `unread_count`）；當時 B1 hands-on 後加入

### Hook 最終 API（PR #75 + #83 後）

```typescript
interface UsePaginatedFetchResult<T> {
  items: T[];
  cursor: string | null;
  hasMore: boolean;
  totalCount: number | undefined;
  lastFetchedAt: Date | null;
  loading: boolean;
  loadingInitial: boolean;   // C1
  loadingMore: boolean;      // C1
  error: string | null;
  loadMore: () => Promise<void>;
  refresh: () => Promise<void>;
  mutate: (updater: (items: T[]) => T[]) => void;  // C2
}

interface UsePaginatedFetchOptions {
  path: string;
  pageSize?: number;
  query?: Record<string, ...>;
  queryKey?: string;
  enabled?: boolean;
  formatError?: (err: unknown) => string;
  onSuccess?: (res: PaginatedResponse<T>) => void;  // C4
}
```

---

## D. 執行順序紀錄（實際）

依 backlog §D 推薦順序執行（全部完成）：

1. ✅ C1+C2 hook 擴展 → PR #75
2. ✅ A1 customers → PR #76
3. ✅ B4 family-reviews → PR #77
4. ✅ A4 sentiment-alerts → PR #78
5. ✅ B3 manuals → PR #79
6. ✅ A2 refunds → PR #80
7. ✅ A3 warranty-claims → PR #81
8. ✅ B2 cases → PR #82
9. ✅ B1 notifications + C4 onSuccess → PR #83
10. ❌ A5 inventory + A6 schedule — hands-on 後判 NOT-APPLICABLE

---

## E. 不在 backlog（已確認的設計決策）

| 項目 | 結論 | 來源 |
|---|---|---|
| repo root 雜訊 | 已清乾淨（無 `report/`、無 `web_design_spec_prompt_pipeline/`） | PR #65 |
| `agent/data/` `api/data/` 命名 | 保留（runtime 軸對齊） | ADR-0024 §3 S3 |
| `CLAUDE_TEMPLATE.md` 位置 | 保留 root（user-facing） | ADR-0024 §3 S3 |
| harness control flow 重構 | 不做（branching 性質）；改 introspection-only | ADR-0025 |
| SWR / TanStack Query 引入 | 不做（`lib/cache.ts` 已具備 staleTime + dedup） | ADR-0024 §3 S1 |

---

## F. ROI 評估觸發條件

| 條件 | 動作 |
|---|---|
| 任一 admin page (A1-A4) 使用頻率因 V2.0 上線後顯著上升 | 提升該 page 優先順序至 H |
| C2 mutate API 完成後 6 個月內無 caller 採用 | 從 backlog 移除 hook 擴展（避免 over-engineering） |
| inventory (A5) page UX 抱怨累積（如「重新載入太慢」） | 啟動 A5 + 設計 `useFetch` 非分頁 hook |
| family-reviews (B4) 整體 owner 換手 | 重新評估雙清單設計 |

---

## G. 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-12 | 初版 — 整理自 PR #68-#72 描述與 hands-on 階段發現 |
| 2026-05-12 | **MOSTLY DONE** — 後續 9 個 PR (#75-#83) 完成 backlog 8/10；剩 2 個 (A5 inventory / A6 schedule) hands-on 後判 NOT-APPLICABLE；hook 擴展完成 C1/C2/C4，C3 決定不做。Phase 3.3 最終 16/18 page 改用 hook |
