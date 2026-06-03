---
id: CR-0003
title: "全 tenant-scoped Cutover WBS（移除 dual-mount / legacy /api/v1）"
status: awaiting-owner-decision
tier: 4-exploration
owner: HYBRID
created: 2026-06-02
context: 產品尚未 release、全在開發階段 → 可直接 cutover（無 prod 用戶、無需 Sunset/漸進）
supersedes-strategy: CR-0002 的 dual-mount + Sunset 漸進路線（dev-phase 下改為直接 cutover）
generated-by: workflow full-cutover-wbs (Sonnet 分析 ×4 + Opus WBS)
---

# CR-0003：全 tenant-scoped Cutover WBS

> **端態**：runtime 無 `/api/v1`（auth/* 與 technicians/me/* 扁平化例外）；全業務端點 tenant-scoped；單一合併 spec；generated 型別覆蓋重生；legacy router 全刪；DeprecationMiddleware 移除。
> **dev-phase 簡化**（業主 2026-06-02）：無 prod 用戶 → 不需 Sunset/漸進退場、不需型別獨立 namespace 過渡；直接 cutover，回退靠 **git revert per wave**（仍保品質 gate：每波 component+E2E 綠）。

## 0. 現況盤點（workflow 核實 2026-06-02）
- endpoint 分類：**13 HAS_V2 / 12 NEEDS_V2 / 24 DROP_CANDIDATE / 3 KEEP（auth×2 + technicians/me/*）**。
- 前端：**59 web 檔** runtime 打 `/api/v1`（多模組 legacy+v2 並存）。
- **⚠️ agent 也打 /api/v1**：`agent/admin_api.py`(5) + `agent/app.py`(2) → 移除 legacy 會 404 打爆線上 LINE bot。**P4-T1 必須先遷 agent caller**。
- spec：2 份未合併（30+57 paths），唯一衝突是 `Error` schema（舊 enum vs RFC7807）。
- 型別：`generated.py`(38 py importer) + `api.generated.ts`(83 web importer) 皆從舊已刪 spec 生成。

## 1. 🛑 P0 業主決策（gate 全部後續；附建議，dev-phase + 全 tenant-scoped 意圖）

| # | 決策 | 我的建議（依「全 tenant-scoped + dev 直接遷」）|
|---|---|---|
| **Q1** | 端態是否保留 `/api` 前綴？型別 paths key 形狀 | **去掉 /api/v1**：業務端點 = `/tenants/{tid}/...`，平台級 = 扁平 `/auth`、`/health`、`/consumer`。spec server url 為 base、paths 照現狀。dev-phase 無相容包袱。|
| **Q2** | 型別覆蓋重生里程碑 | **一次性在 P4 cutover** 重生（dev-phase 不需漸進 namespace 過渡）|
| **Q3** | C-11 ~40 端點端態（扁平 vs 建 tenant-scoped v2）| **建 v2 tenant-scoped**（符合「全 tenant-scoped」）；唯 auth + me/* 扁平；純死表面（dashboard/stats 等若無 spec 且無價值）才 DROP。**這是 P2 最大 scope driver（→ ~25 模組要建 v2）**|
| **Q4** | refunds `/{id}/decision` 缺口 | **補 refunds_v2 decision endpoint**（`POST /tenants/{tid}/refunds/{id}/decision`），test_refund_dual_sign 遷 v2 |
| **Q5** | DeprecationMiddleware 命運 | cutover 後 `/api/v1` 消失 → **直接刪 middleware**（P4）|
| **Q6** | 合併 spec 是否收錄 auth 端點 | **收錄**（補 `/auth/login` 等為 platform-level path），讓型別正確生成、避免 importer 缺 key |

## 2. WBS 五階段（dev-phase 直接 cutover）

- **P0 決策 gate**：業主拍 Q1-Q6（不動 code）。
- **P1 Additive 準備**（不刪任何東西）：
  - P1-T1（opus）合併兩 spec 為單一檔（Error→RFC7807 正典、舊 ErrorV1）、spectral 0 errors。**全鏈根節點，先做**。
  - P1-T2（sonnet）型別重生（dev-phase 可直接準備覆蓋版，或先 v2 namespace 驗 key 形狀）。
  - P1-T3（sonnet）DeprecationMiddleware 改白名單（過渡用；P4 會整個刪）。
  - P1-T4（sonnet）補 refunds_v2 decision endpoint（Q4）。
- **P2 補齊 ~25 條 NEEDS_V2 / BUILD_V2 新 v2 router**（高度可平行，每條各自 CIA）：settlements / warranty-claims POST / dispatch:plan / exceptions(schedule-requests) / work-orders onsite arrival+completion / work-orders operational / kb documents(cases+manuals 統一) / sops(sop-drafts+family-reviews) / config m18(opus, HIGH) / 批次 admin(conversations/dashboard/notifications/inventory/disputes/reconciliations/invoices/media/reports/sentiment/data-corrections/technicians-onboard/vouchers-void) / OWNER_DECIDE(pricing-rules/dispatch-logs/resolution)。
- **P3 前端 + agent caller 全遷 v2**：59 web 檔 + agent admin_api/app.py caller → 0 個 /api/v1。測試遷移。
- **P4 一次性 cutover（destructive）**：刪 legacy router（逐模組 atomic commit 可 revert）→ 型別覆蓋重生 → auth/me 扁平化 → 移除 /api/v1 前綴 + 刪 DeprecationMiddleware。

**legacy 移除硬 gate（每模組）**：前端 runtime caller=0 **且** agent caller=0 **且** v2 component+E2E 綠。
**agent-coupled 模組**（conversations/problem-cards/refunds/warranty-claims/sop…）：**P4-T1 先遷 agent caller** 才能刪其 legacy。

## 3. 風險 + 回退
- **agent 404 風險**：P4-T1（遷 agent /api/v1 caller）設為刪 agent-coupled legacy 的硬 depends_on。
- **型別重生時序**：覆蓋重生必須在 legacy router 移除**之後**（否則舊 class 名消失炸 38 importer）。
- **回退三層**：P1/P2 純 additive（刪新增物即復原）；P3 前端逐模組 PR 可 revert；P4 逐 legacy router atomic commit 可 git revert 復活。
- **change-governance**：每個 P2 新 v2 模組 + P1-T4 + config 各自跑 CIA。

## 4. immediate next wave（P0 簽核後）
P1-T1 合併 spec（根節點）先做 → 平行 P1-T3 middleware 白名單 + P1-T4 refunds decision → 然後 P2 大規模平行建 v2。

---

## 5. 進度區（append-only）

- ✅ **P0 業主決策**：完成（dev-phase + 全 tenant-scoped）
- ✅ **P1 Additive**：完成（spec 合併 / 型別重生 / DeprecationMiddleware 白名單 / refunds_v2 decision）
- ✅ **P2 v2 router 補齊**：完成（含 W3 KB、W4 work-orders ops、W5 invoices、W6 media + dispatch-logs，全 ~25 條 + CR-0004 Track B 8 模組）
- ✅ **P3 track-A**：完成（agent admin_api/app.py + web 大部分 caller → v2，merge `27313e90`）
- ✅ **P3.5 Track-B drop-in**：完成（2026-06-04 取證收尾）— 4+1 模組（disputes/pricing/reconciliations/inventory/data-corrections）web caller 全清；驗收 `grep "api/v1.*\{pricing\|recon\|inventor\|data.correction\}" web/src` = 0；唯一例外 `accounting/page.tsx:189` 為 dual-sign UX rework，列產品 backlog 獨立追蹤
- ⏳ **P4 Cutover**：未啟動（依賴 P3 track-A 全 web caller 清零 — 目前仍 30 個 v1 caller，集中在 KB/refunds/warranty/technicians，需先收尾）

---
**🛑 Awaiting owner sign-off on §1 Q1-Q6（或「全照建議」）before P1 code.**
