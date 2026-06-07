# WBS 統計口徑修正 — Enhancement Roadmap 納入 — 2026-06-07

## §1 觸發事件

業主於 6/07 操作前後端（dev server :3000 + uvicorn :8001）時，逛 12 個 admin page 看到 83 個 disabled placeholder button：

| Page | disabled 數 |
|---|---|
| /admin/inventory | 27 |
| /admin/reports/technician-ranking | 8 |
| /admin/dispatch-queue | 7 |
| /technicians | 6 |
| /accounting | 6 |
| /problem-cards | 5 |
| /accounting/revenue | 5 |
| /admin/reports/revenue | 5 |
| /work-orders | 4 |
| /admin/customers | 4 |
| /accounting/invoices | 4 |
| /admin/reports/kpi | 2 |
| **總計** | **83** |

業主質疑：「WBS 99.8% 但這麼多按鈕禁用，是不是數字算錯？」

## §2 Root Cause

原 WBS 公式 4 維加權：

| 維度 | 數字 | 權重(估) |
|---|---|---|
| Phase 5-7 產品 MVP | 100% | 大 |
| Phase 8 UAT | 0% | 小 |
| Phase 9 P4 | ~88% | 中 |
| Phase II 9 FR | 100% | 大 |

→ 加權算出 99.8%

**問題**：這 4 維**只算 milestone level**，沒涵蓋 `web/docs/page-status.md` 列的 10 條 Enhancement Roadmap（既有 admin page 的 placeholder enhancement）。

`page-status.md` 開頭就寫明：
> ⏳ **待接入**：依賴尚未開發的模組

但這些 ⏳ **沒有反映到** `system-completion-status.md` 的 WBS 數字。兩份文件 SoT 不一致 → 業主感知落差。

## §3 Enhancement Roadmap 真實完成度盤點

| # | Roadmap | 完成度 | 證據 |
|---|---|---|---|
| 1 | 後端 5 組新 endpoints（subflow + 排班）| **100%** ✅ | T5-T10 完整提交流程 |
| 2 | WebSocket / SSE server 啟用 | **~25%** | 前端 ✅，後端 server ⏳ |
| 3 | 媒體上傳 endpoint | **100%** ✅ | media_v2 已掛 |
| 4 | 派工 AI 推薦引擎 (A37) | **~70%** | backend candidate detail ready, drawer 已寫 |
| 5 | 滿意度 / NPS 模組 | **0%** | customers / KPI 多項指標待 |
| 6 | 保固詳情頁 + 證據上傳 | **0%** | warranty-claims / disputes 待 |
| 7 | inventory_transactions 寫入路徑 | **0%** | inventory 補貨/編輯/紀錄全部 disabled |
| 8 | Reports metrics endpoint 擴充 | **0%** | reports/* 切片/排序/匯出全部 disabled |
| 9 | 批次/多步審批流程 | **~50%** | refund 雙簽 ✅, accounting 批次 ⏳ |
| 10 | PWA SW + 離線快取 | **~30%** | manifest ✅ SW ⏳ |

**平均 37.5%**。

對應 user 看到的 83 disabled：
- `inventory` 27 個 → roadmap #7（0%）
- `reports/*` 15 個 → roadmap #8（0%）
- `accounting` 15 個 → roadmap #9（50%）
- `customers/warranty` 11 個 → roadmap #5 + #6（0%）
- `dispatch-queue/technicians/etc` 15 個 → roadmap #2 + #4 + 其他

## §4 新 WBS 公式

### 80/20 split

```
WBS = 原四維 × 0.8 + Enhancement × 0.2
    = 99.8% × 0.8 + 37.5% × 0.2
    = 79.84% + 7.5%
    = 87.34%
≈ 87%
```

### 詳細加權表（system-completion-status 改用）

| 維度 | 完成度 | 權重 | 貢獻 |
|---|---|---|---|
| Phase 5-7 產品 MVP（V2.0 派工+會計+KPI）| 100% | 24% | 24.0% |
| **Phase 5-7 Enhancement Roadmap (10 條，新加)** | **37.5%** | 16% | 6.0% |
| Phase 8 UAT 上線 | 0% | 4% | 0% |
| Phase II UAT 上線 | 0% | 4% | 0% |
| 架構遷移 P4 | 88% | 12% | 10.6% |
| Phase II SaaS 模組 | 100% | 20% | 20.0% |
| Verified（Playwright + 整鏈路）| 100% | 20% | 20.0% |
| **加權總計** |  |  | **~87%** |

## §5 對 user 的承諾真實性

| 之前說 | 真實情況 |
|---|---|
| 「前後端 code 都完成」 | 對 Phase II 9 FR 是真實的；對 Phase 5-7 admin 後台是**部分真實**（核心流程 100%，但 enhancement 0-37.5%） |
| 「WBS 99.8%」 | **過於樂觀**，未納入 Enhancement Roadmap |
| 「剩 0.2% 結構性」 | 真實是「核心 + Phase II 99.8% / Enhancement 37.5%」混合 |

## §6 WBS 100% 真實路徑（更新版）

1. **Phase II UAT + Phase 8 UAT 上線**（業務期程）→ +4%
2. **P4 Stage 7 v1 router 刪除**（30 day 觀察 + 業主簽）→ +1.4%
3. **Enhancement Roadmap 0% 的 4 條**（NPS / 保固 / inventory / Reports）→ +6%（最大塊）
4. **WS server 啟用**（roadmap #2 25% → 100%）→ +2%
5. **PWA SW**（roadmap #10 30% → 100%）→ +1%
6. **批次審批**（roadmap #9 50% → 100%）→ +1%

加總可推 87% → 100%。

## §7 影響文件

- ✅ `web/docs/system-completion-status.md` — 總體 99.8% → 87%，新增 Enhancement Roadmap 維度 + 加權貢獻欄
- ✅ `CHANGELOG.md` `[Unreleased]` — 加 Decisions 條目
- ✅ 本檔 `docs/_audit/wbs-recalc-2026-06-07.md`
- ⚠️ `pending-business-decisions-2026-06-06.html` — progress bar 98.7% → 87%（待 user 確認是否更新）

## §8 對齊文件

- `web/docs/page-status.md` — 10 條 Enhancement Roadmap 原始清單（280 lines）
- `docs/_ops/wbs-100-closeout-plan.md` — 原 100% 收尾計畫（未含 Enhancement）
- 對應業主操作：12 page × 83 disabled 截圖
