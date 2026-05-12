# Phase 3.3 剩餘 Page Backlog（2026 Q2）

**對應 ADR：** [ADR-0024](../1-decisions/ADR-0024-tier1-refactor-revised.md) §3 S1
**對應 WBS：** [wbs-2026-q2-tactical-refactor.md](./wbs-2026-q2-tactical-refactor.md) §4.4
**狀態：** BACKLOG（Phase 3.3 主推進於 2026-05-11 完成 8/18 page，剩餘 10 個整理於此）
**建立日：** 2026-05-12

---

## 背景

ADR-0024 §3 S1 Phase 3.3 hands-on 階段（2026-05-11）確認適用 `usePaginatedFetch` 的 web page 實際為 **18 個**（plan 原估 13 個）。當輪推進完成 **8 個 page 遷移 + hook 演化 5 個擴展點**（has_more / totalCount / lastFetchedAt / queryKey / formatError），剩餘 10 個 page 因結構性阻塞（modal/mutate/dual-loading/多 tab/不分頁）留作 backlog 由獨立 PR 處理。

本文件記錄各 page 的具體阻塞點、hook 擴展需求、工作量估計，作為後續 pick up 時的起手依據。

## 已完成（8/18）

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

---

## A. Future PR 群（6 個 — admin / account domain）

| # | Page | 阻塞點 | Hook 擴展需求 | 工作量 |
|---|---|---|---|---|
| A1 | `web/src/app/admin/customers/page.tsx` | 雙 loading state（`loading` 初次 vs `loadingMore` 增量）+ 客端 `searchQuery` filter | hook 增加 `loadingMore` 區分 initial vs append phase | 1-2 小時 |
| A2 | `web/src/app/admin/refunds/page.tsx` | 18 useState（refund modal + approve/reject action + updatedAt + filters） | 無 hook 變更；需先抽 modal 與 action 邏輯為 sub-component | 2-3 小時 |
| A3 | `web/src/app/admin/warranty-claims/page.tsx` | 22 useState + `activeTab`（多 tab 各自 fetch）+ 多 filter + updatedAt | hook 已 fit；需設計 multi-tab fetch pattern（每 tab 一個 hook instance vs 共用 + queryKey） | 2-3 小時 |
| A4 | `web/src/app/admin/sentiment-alerts/page.tsx` | `handleUpdated` 直接 mutate hook items（`setItems(prev => prev.map(...))`） | hook 需暴露 `mutate(updater)` API | 1-2 小時 + hook +20 行 |
| A5 | `web/src/app/admin/inventory/page.tsx` | **不分頁**（single fetch limit=50）+ 客端 filter + summary computation | usePaginatedFetch 不適用；考慮獨立 `useFetch` 簡易 hook 或保留原狀 | **判斷 ROI 後**再做（可能不做） |
| A6 | `web/src/app/account/schedule/page.tsx` | 15 useState（含 schedule 編輯/儲存 flow），結構未深入 inspect | 待 inspect | 待估計（2-3 小時） |

---

## B. 獨立 PR 群（4 個 — 結構不適 single-hook）

| # | Page | 阻塞點 | 設計方向 | 工作量 |
|---|---|---|---|---|
| B1 | `web/src/app/notifications/page.tsx` | response 含 `unread_count`（不在 `CursorPage` schema）+ bulk actions（`selectedIds`、`bulkBusy`、`marking`）+ `useBroadcast` + `useRealtimeChannel` 整合 | 自訂 hook `useNotificationList`（extending usePaginatedFetch + unread_count + mutate）或保留 page 內 | 3-4 小時 |
| B2 | `web/src/app/knowledge-base/cases/page.tsx` | main list + search hits（替代 view）+ export modal + 多 toast/error 周邊 | 分 2 part：main list 用 hook；search 部分獨立 `useSearch` hook | 2-3 小時 |
| B3 | `web/src/app/knowledge-base/manuals/page.tsx` | delete confirm modal + upload flow + 外部 setItems mutate（delete 後 filter、upload 後 unshift） | 同 A4 需要 hook `mutate(updater)` | 1-2 小時（依 A4 hook 擴展完成順序） |
| B4 | `web/src/app/knowledge-base/family-reviews/page.tsx` | **雙清單頁**：pending（不分頁）+ history（分頁 + actionFilter） | history 用 usePaginatedFetch；pending 保留原 useState 邏輯 | 1-2 小時 |

---

## C. Hook 擴展總清單（跨 backlog 共需）

| 擴展 | 用途 | 受益 page 數 | 優先順序 |
|---|---|---|---|
| `loadingMore: boolean` | 區分初次載入 skeleton vs loadMore inline spinner | 1（A1 customers）+ 潛在多個 | M |
| `mutate(updater: (items: T[]) => T[]): void` | 外部 CRUD 後同步更新 hook items（取代 `refresh()` 全抓） | 至少 3（A4 sentiment-alerts、B3 manuals、未來其他 page） | **H** |
| 非分頁版本 `useFetch<T>(path, opts)` | 取代不需分頁的單頁 fetch | 1（A5 inventory）+ 潛在多個 | L（ROI 待評） |

### C2 `mutate` API 設計建議

對齊 SWR `mutate` 慣例：

```typescript
interface UsePaginatedFetchResult<T> {
  // ... existing fields
  mutate: (updater: (items: T[]) => T[]) => void;
}

// usage in page (e.g. manuals delete)
const { items, mutate } = usePaginatedFetch<Manual>({ path: "/api/v1/knowledge-base/manuals" });
await api.delete(`/api/v1/knowledge-base/manuals/${id}`);
mutate(prev => prev.filter(m => m.id !== id));  // optimistic local update
```

優點：caller 不需 `refresh()` 全抓重 fetch；UX 沒「資料消失再出現」閃爍。

---

## D. 優先順序建議（若日後 pick up）

1. **先做 hook 擴展 C2 `mutate(updater)`** —— unblocks A4 + B3 共 2 個 page，且 C2 是「hook 質感升級」（對齊 SWR `mutate` API），未來其他 page 也會用到
2. **A1 customers** —— 加 `loadingMore` flag 一次性解決 distinct loading semantics
3. **B4 family-reviews** —— 雙清單頁 pattern 對齊後，未來類似頁面可參考
4. **A2 refunds / A3 warranty-claims** —— admin 高使用度，但 useState 數量多需先 component 拆解
5. **B1 notifications** —— 最複雜，依賴 C2 mutate + 自訂 hook，建議最後做
6. **A5 inventory** + **A6 account/schedule** —— 視 ROI，可能 skip

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
