---
title: _flows-bdd-test/ Per-File Review Notes
phase: CROSS-PHASE
status: Active
last_updated: 2026-05-07
owners: [PM, Tech Lead, QA Lead]
status: superseded
superseded_by: docs_v2/4-exploration/audits/flows-review-notes.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
---

# _flows-bdd-test/ — Per-File Review Notes

> **目的**：對 `_flows-bdd-test/` 9 份檔案逐一深度 review，列出結構摘要、編號系統、cross-refs、對齊狀態、開放問題、修正建議。為後續 `_alignment-matrix.md` 主對齊矩陣提供原料。
>
> **預期讀者**：PM（決策影響評估）、Tech Lead（修正建議落地）、QA Lead（測試規格對齊）。
>
> **與其他文件的關係**：
>
> - 本檔記錄**現況觀察與建議**（非 SSOT）
> - 主對齊矩陣 SSOT：[[_alignment-matrix]]（次階段建立）
> - 上層索引：[[_MOC]]

---

## _MOC.md

**檔案路徑**：docs/_flows-bdd-test/_MOC.md
**行數**：62
**Frontmatter**：`title: Flows, BDD & Test Governance | phase: CROSS-PHASE | status: Active | owners: [PM, Tech Lead, QA Lead]`
**內部編號系統**：無（純導航索引）

### 結構摘要

- ## Documents（3 分組：User Flow / Journey、BDD Specifications、Test Plan & PM Alignment）
- ## Reading Order（8 步驟）
- ## Cross-References（4 條：parent design、parent discover、HOME、GATE-MAP）

### Outbound cross-refs

- `[[../02-design/_MOC]]`、`[[../00-discover/_MOC]]`、`[[../HOME]]`、`[[../GATE-MAP]]`
- 內部 8 個檔案 wikilink（Documents 表 + Reading Order）

### 對齊狀態

- ✅ 已是最新狀態（PR #35 合併後即重建）
- ⚠ 缺 `_review-notes.md`（本檔）+ 未來 `_alignment-matrix.md` 索引（待 Phase 4 補）

### 開放問題

1. Reading Order 8 步是否包含 `_MOC.md` 本身（建議）

### 修正建議


| 位置          | 現況       | 建議                                                                          |
| ----------- | -------- | --------------------------------------------------------------------------- |
| Documents 表 | 3 分組 8 檔 | 加入 `_review-notes.md` 與 `_alignment-matrix.md` 兩項，新增「Governance / Review」分組 |


---

## E1x--user-journey-map.md

**檔案路徑**：docs/_flows-bdd-test/v-model-left/E1x--user-journey-map.md
**行數**：567
**Frontmatter**：無 YAML（僅標題列 metadata：v1.0、2026-03-31、消費者 V1.0 已上線、其餘 V2.0 未實作）
**內部編號系統**：4 角色（消費者 / 技師 / 管理員 / 客服主管）× stage 1-N + 異常流程 4 類

### 結構摘要

- ## 1. 消費者旅程地圖 (8 階段)
- ## 2. 技師旅程地圖 (6 階段)
- ## 3. 管理員旅程地圖 (5 階段)
- ## 4. 情緒曲線總覽
- ## 5. 關鍵決策點分析
- ## 6. 客服主管旅程 (6 階段)
- ## 7. 異常流程使用者旅程 (4 類流程)

### Outbound cross-refs

- `02_project_brief_and_prd.md`、`05_architecture_and_design_document.md`、`executive_architecture_overview.md`（line 8 — 關聯文件）
- `requirements/10_work_order_interaction_flows.md`（line 523 — 異常流程對應）

### 對齊狀態

- ✅ 與 E7 BDD 主流程對齊：消費者 8 階段對應 F-101/F-102/F-103/F-104/F-107/F-108
- ✅ 技師 6 階段對應 F-201（5 scenario）
- ✅ 管理員 5 階段對應 F-105 + F-205
- ⚠ §1.6 派工細節 vs E7 F-202 智慧派工引擎：E1x 簡述「根據品牌技能、區域、評分自動匹配」，但無權重順序，與 F-202 line 1056-1060 score_breakdown 描述精度不一致
- ⚠ §6 客服主管旅程：E7 BDD 無單一對應 Feature，散布在 F-105/F-205/F-207
- ❌ 4 個 BDD 缺口流程（F-011/F-016/F-022/F-023）E1x 未覆蓋

### 開放問題

1. 派工匹配演算法透明度：行 131 簡述太抽象，與 E7 F-202 不對齊
2. 客訴升級 SLA：行 342（24h）vs 行 510（高 anger_level < 24h、其他 < 3 工作日）描述不一致
3. 異常流程是否觸發回到常規流程？例如缺料後二次到場是新工單還是狀態跳轉？

### 修正建議


| 位置       | 現況                   | 建議                                        |
| -------- | -------------------- | ----------------------------------------- |
| line 131 | 派工只說「品牌技能、區域、評分」     | 補配重順序，對齊 E7 F-202 + dispatch-weights spec |
| line 342 | 「客訴 SLA」無分級          | 補「anger_level ≥ 4 → < 24h；其他 → < 3 工作日」   |
| line 562 | 「SOP 標記診斷不完整 → 扣績效分」 | 補扣分規則與績效影響週期                              |


---

## E5x--workflow-work-order.md

**檔案路徑**：docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
**行數**：3,476
**Frontmatter**：無 YAML（> 區塊聲明 v1.0、2026-03-31、設計完成待開發）
**內部編號系統**：Flow 1-13（含 Flow 11-13 補充）+ S1-S7 階段 + §16-§24 缺口補充

### 結構摘要

- §1-§3：完整狀態機（13 → 16 狀態擴充）、6 角色定義、SLA 定義
- §4-§13：Flow 1-10（正常路徑、拒單重派、範圍變更、缺料、延遲、退款、保固爭議、品質、客訴、門外觀）
- §14-§15：升級矩陣、知識沉澱閉環
- §16-§24：S1/S2 詢問報價、工單狀態擴充、Flow 11-13、異常返回節點、OKR 追蹤

### Outbound cross-refs

- `[[E1--project-brief-and-prd.md]]` (line 8)
- `[[E5--api-design-specification.md]]` (line 9)
- `[[diagnostic-intelligence-architecture.md]]` (line 14) — Layer 6 知識沉澱
- `[[optimization-strategy.md]]` (line 15)
- `[[E5x--workflow-admin-governance]]` (line 3409, 3425) — Flow 9 → G4 銜接

### 對齊狀態

- ❌ 與 E7x F-001~F-023 SSOT **無明確對應**：檔內無 F-XXX 編號，無法驗證 Flow 1-13 對應哪些 SSOT
- ❌ 與 E7 BDD F-1XX/F-2XX **無明確 cross-link**
- ✅ 與 workflow-dispatch.md 對齊：Flow 2 ↔ dispatch §4 拒單重派 / Flow 1 ↔ dispatch §2 媒合
- ✅ 與 workflow-admin-governance.md 對齊：Flow 9 ↔ G4 爭議仲裁（§27 補遺明確銜接）
- ✅ 狀態機一致：§1 + §18 共 16 狀態，轉換圖完整
- ⚠ 角色命名：本檔 6 角色（Customer/AI_System/Dispatch_Engine/Technician/Admin/Finance），但 admin-governance 7 角色（細化 Admin 為 super_admin/tenant_admin/operations_manager/accountant/support_agent/dispatch_officer/auditor）— 「客服代客戶」中介角色未明確

### 開放問題

1. **F-XXX 對應缺失（最大缺口）**：Flow 1-13 該對應哪些 E7x F-001~F-023 ？
2. S1/S2 階段（詢問/報價）與既有 Flow 1-10（始於 created）的銜接？
3. Flow 11-13 細節完整度遠低於 Flow 1-10
4. 退款雙簽規則散在 §9 / §23，誰是最終簽核（Finance vs Admin）？

### 修正建議


| 位置                    | 現況                   | 建議                                                |
| --------------------- | -------------------- | ------------------------------------------------- |
| 目錄（line 22-38）        | 未列 S1-S7 階段          | 在 Flow 上方插入「階段定義 S1-S7」章節                         |
| §1.2 狀態圖（line 64-100） | 13 狀態圖；§18 另有 16 狀態圖 | 合併為單一 16 狀態轉換圖，§18 改寫為「擴充規則說明」                    |
| §2.1 角色表              | 6 角色，無中介角色           | 新增 Admin 子註「可代客提爭議」或新增 Customer_Representative 角色 |
| §4-§13 Flow 標題        | 無 F-XXX 編號           | 每個 Flow 標題後附 (對應 F-NNN)，待 alignment-matrix 確認     |
| §16-§18               | S1/S2 與 Flow 1 銜接模糊  | 新增 Mermaid 圖 S1 → S2 → Flow 1（created）            |
| §27 Flow 9 補遺         | 專注 G4 銜接             | §12 後插「Flow 9 總結」，§27 只寫銜接規則                      |


---

## E5x--workflow-dispatch.md

**檔案路徑**：docs/_flows-bdd-test/v-model-left/E5x--workflow-dispatch.md
**行數**：811
**Frontmatter**：無 YAML（> 聲明「設計文件 V2.0 派工營運基礎設施規格」、2026-04-22）
**內部編號系統**：§1-§9（缺失項目清單 + 技術規格）+ HIGH/MEDIUM 優先度

### 結構摘要

- §1：技師排班系統（SQL schema + 可用性判斷）
- §2：媒合演算法（權重公式 + 完整流程）
- §3：技師薪酬分潤（時薪 / 計件 / 分潤 + 月結）
- §4：拒單重派（exponential backoff + 15 min 逾時）
- §5：客戶設備主檔
- §6：技師技能分類體系
- §7：報表 SQL + API
- §8-§9：新增表彙總、現有系統整合點

### Outbound cross-refs

- `[[E5x--workflow-work-order]]` (line 6) — 前置文件
- `[[02-design/specs/dispatch-weights]]` (line 160) — 權重 SSOT

### 對齊狀態

- ✅ 與 work-order.md 對齊：明確標前置；§4 拒單重派 ↔ work-order Flow 2
- ✅ 與 dispatch-weights spec 對齊：§2.2 引用 + 內嵌權重值（W_dist=0.35 / W_skill=0.30 / W_rating=0.20 / W_load=0.15 / bonus +0.10/+0.05）
- ⚠ 與 admin-governance.md **缺銜接**：admin-governance 無稽核 / 庫存 / 薪酬監控的反向引用
- ⚠ 角色命名不一致：「派工員」(dispatch_officer) 在 admin-governance §1.1 出現，dispatch.md 未定義
- ❌ 與 F-003~F-005 派工流程 **缺 F-XXX 對應**

### 開放問題

1. dispatch-weights spec 路徑 `02-design/specs/dispatch-weights` 是否與目錄結構相符？
2. §3 薪酬定義 3 模式但無實作代碼、SQL schema、計算公式
3. §6 技能體系與 §2.3 算法 `tech_skills` 解耦，但無 schema 連結
4. §7 報表 API 標 HIGH 但內容僅 5 行
5. §5 客戶設備 schema 無權限說明（誰可編輯 / 讀）

### 修正建議


| 位置                      | 現況               | 建議                                                                                |
| ----------------------- | ---------------- | --------------------------------------------------------------------------------- |
| 目錄（line 12-20）          | 7 項缺失，無分類        | 分「核心流程 §1-§4」與「基礎設施 §5-§7」                                                        |
| §2.2 評分公式（line 162-178） | 僅權重表             | 新增「權重調優機制」：A/B test / 性能監控 / 季度評審                                                 |
| §3 薪酬（line 301-389）     | 定義但無公式           | 補 `calc_technician_payment()` Python，含月結 / 稅扣 / 提前支付                              |
| §5 客戶主檔（line 476-563）   | Schema 無權限       | 補 RBAC：dispatch_officer 讀寫、customer 只讀自身、support_agent 讀全部                        |
| §7 報表 API（line 644-780） | 5 行概述            | 拆 3 endpoint：dispatch-efficiency / technician-performance / customer-satisfaction |
| 全檔                      | 無 F-003~F-005 引用 | §1-§4 各小節開頭補「對應 F-NNN」                                                            |


---

## E5x--workflow-admin-governance.md

**檔案路徑**：docs/_flows-bdd-test/v-model-left/E5x--workflow-admin-governance.md
**行數**：630
**Frontmatter**：無 YAML（> 聲明 v0.1 draft、2026-04-23、Claude 起草待人工校對）
**內部編號系統**：Flow G1-G4（4 條治理流程）

### 結構摘要

- §1：共通定義（7 角色、權限碼格式、前置條件、SLA）
- §2 Flow G1：RBAC 角色生命週期（建立 / 授權 / 撤銷 / 調整 / 刪除 + WS 即時生效）
- §3 Flow G2：稽核日誌查詢與匯出（分頁 / 篩選 / 24h 內匯出異步）
- §4 Flow G3：庫存低警報與補貨（閾值 / 觸發 / 補貨 / 進銷存）
- §5 Flow G4：爭議仲裁（4 種觸發 / 一級調解 / 二級裁決 / 金額雙簽 / 三級終審）
- §6：跨 Flow 關聯（與 work-order Flow 交集點）
- §7-§8：校對檢核表、變更記錄

### Outbound cross-refs

- `[[rbac-dynamic-spec.md]]` (line 10) — RBAC 資料模型
- `[[audit-log-spec.md]]` (line 11)
- `[[inventory-management-spec.md]]` (line 12)
- `[[warranty-dispute-spec.md]]` (line 13)
- `[[E5x--workflow-work-order.md]]` (line 14) — 13 工單 Flow
- `[[E5x--frontend-architecture.md §8.3]]` (line 15) — 動態 RBAC 契約

### 對齊狀態

- ✅ 與 work-order §27 對齊：Flow 9 → G4 爭議銜接明確
- ✅ 與 spec 文件對齊：RBAC / Audit / Inventory 主檔皆引用
- ⚠ 與 dispatch.md **無交集**：派工員角色在 §1.1 出現但無相關 Flow
- ⚠ **角色定義 7 vs 6**：work-order 6 角色（Customer/AI_System/Dispatch_Engine/Technician/Admin/Finance）vs admin-governance 7 角色（super_admin/tenant_admin/operations_manager/accountant/support_agent/dispatch_officer/auditor）— 「Admin」與「tenant_admin」是否同一？「Finance」與「accountant」是否對應？
- ❌ 與 F-019/F-020/F-007 治理流程 **無 F-XXX 對應**

### 開放問題

1. 角色命名混淆：work-order 「Admin」vs admin-governance 「tenant_admin / support_agent / operations_manager」三者差別不明
2. G1 權限變更：< 5s WS 推送，但 WS 斷線降級機制只說「下次登入生效」
3. G2 稽核事件：無詳細列表 / schema / 保留期政策
4. G3 補貨流程：警報觸發定義但無採購單核准流程 / 廠商整合
5. G4 雙簽門檻 5000 元：來源（policy / config / hard-code）未說明
6. 缺 G-0 共通流程：稽核事件分桶（RBAC / DISPUTE / INVENTORY / REFUND）

### 修正建議


| 位置         | 現況                       | 建議                                                   |
| ---------- | ------------------------ | ---------------------------------------------------- |
| §1.1 角色表   | 7 角色無對 work-order 6 角色映射 | 新增「對應 work-order 角色」欄                                |
| §1.2 權限碼   | 格式定義無清單                  | 補「附錄：全系統權限碼 Catalogue」（50+ 碼）                        |
| §2 Flow G1 | 4 觸發 + WS < 5s           | 補「G1 權限變更失敗降級」：WS timeout → 本地 TTL cache + 下次登入校驗    |
| §3 Flow G2 | 查詢 + 匯出無事件分類             | 補「稽核事件類型表」：resource type × action                    |
| §4 Flow G3 | 警報觸發無補貨 endpoint         | 4.6 新增「補貨流程」`POST /inventory/purchase-order` 完整 spec |
| §5 Flow G4 | 5000 元雙簽未定義來源            | 補註：「門檻可配置，見 config/dispute-config.yml」               |
| §6 跨 Flow  | 簡列無詳述                    | 展開為表格：work-order Flow ↔ admin-governance Flow        |
| 全檔         | 無 F-019/F-020/F-007 引用   | G1-G4 標題或開頭補「對應 F-NNN」                               |


---

## E7--bdd-scenarios.md

**檔案路徑**：docs/_flows-bdd-test/v-model-right/E7--bdd-scenarios.md
**行數**：1,521
**Frontmatter**：v1.1 | 2026-04-04 | Active | 開發團隊
**內部編號系統**：F-101~~F-109 (V1.0, 9 Feature) + F-201~~F-210 (V2.0, 10 Feature) = 19 Feature × 3-6 sc/F = ~~85 scenario；§Ⅲ.b 對照表（PR #33 加）映射 E7x F-001~~F-023

### 結構摘要

- ## Ⅰ. BDD 核心原則 + 通用語言表
- ## Ⅱ. Gherkin 語法速查
- ## Ⅲ. Feature 文件清單
- ## Ⅲ.b Feature ↔ E7x 流程編號對照（v1.1 新增 PR #33）
- ## Ⅳ. V1.0 BDD 情境
- ## Ⅴ. V2.0 BDD 情境
- ## Ⅵ. 最佳實踐

### Outbound cross-refs

- `[[_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness]]`（line 16, 126, 131）
- `[[_flows-bdd-test/decision-log/E7x--pm-alignment-Q1-Q10]]`（line 131 — 缺口綁 Q3/Q5/Q7）

### 對齊狀態

- ✅ §Ⅲ.b 對照表 19 Feature ↔ 23 流程 N:M 對應完整（PR #33 + #34 已驗）
- ✅ 4 個 BDD 缺口（F-011/F-016/F-022/F-023）明確標註綁 PM Q3/Q5/Q7
- ✅ 5 個反向缺口（F-103/F-106/F-109/F-203/F-206）有 BDD 但 E7x 沒列獨立流程
- ✅ V1.0 / V2.0 Feature scenarios 詳細，標籤 @happy-path/@sad-path/@edge-case 完整
- ⚠ F-107 情緒分流閾值不一致：line 767 寫 0.90、line 802 寫 0.85；合約 9.3 寫 90%

### 開放問題

1. F-011/F-016/F-022 補 BDD 何時？目前無 ETA
2. F-023 錯誤頁/離線：(a) 新增 F-110？(b) 併入既有 Feature？(c) @wip？
3. F-107 情緒分流閾值 0.85 vs 0.90：應以何為準？

### 修正建議


| 位置                   | 現況                   | 建議                                    |
| -------------------- | -------------------- | ------------------------------------- |
| line 126             | §Ⅲ.b 標題縮排            | 改 H3 強調「雙重對應矩陣」                       |
| line 147,152,158,159 | 4 缺口列 ⚠ 無對應          | 補「目標完成日期：2026-Q2」                     |
| line 164-165         | 「等 PM 拍板」            | 補當前狀態：「PM review 中，目標 2026-02-28 前定案」 |
| line 767             | `confidence >= 0.90` | 標「合約驗收下限，內部目標 ≥ 0.95」                 |
| line 802             | `confidence >= 0.85` | 改 `>= 0.90` 或補理由註腳                    |


---

## E7x--test-plan-and-readiness.md

**檔案路徑**：docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md
**行數**：611
**Frontmatter**：`title: E7x — Test Plan and Readiness Roadmap | phase: DESIGN | gate: TR5 | status: Active | owners: [QA Lead, Tech Lead, PM]`
**內部編號系統**：F-001~F-023 流程 + Q1-Q10 PM 決策 + Tier A/B/C BDD + §0-§15 章節 + Wave 1/2 5 commit

### 結構摘要

- §0 Context / §1 TL;DR / §2 對齊矩陣 / §3 PM Q1-Q10 摘要
- §4 缺口分類 / §5 BDD 金字塔 / §6 5 層 mock 光譜
- §7 高風險場景 / §8 AI/LLM 測試 / §9 不要先做清單
- §10 Sprint 1 30 天計畫 / §11 Quality Gates / §12 Test Ownership
- §13 Verification / §14 Critical Files / §15 Change Log

### Outbound cross-refs

- `[[E7--bdd-scenarios]]` + `#ⅲb-feature--e7x-流程編號對照`
- `[[E7x--pm-alignment-Q1-Q10]]`（§3 全題逐個連結）
- `[[02-design/specs/dispatch-weights]]` / `openapi.yaml` / `asyncapi.yaml` / `generated/api.generated.ts`
- `[[01-define/E2--statement-of-work]]`
- `[[03-develop/GR6]]` / `[[03-develop/GR7]]` / `[[04-deliver/GR10]]`
- `[[E1x--user-journey-map]]` / `[[E5x--workflow-*]]`（§14）

### 對齊狀態

- ✅ §1 與 §2 雙向對齊（PR #34 修正）：🟢13/🟡7/🔴3
- ✅ §2 對齊矩陣每行 F-001~F-023 與 E7 §Ⅲ.b cross-link
- ⚠ §3 PM Q1-Q10 預設已定但全部「⬜待拍」（見 pm-alignment §12）— **關鍵阻塞**
- ✅ §10 Sprint 1 task 與 Wave 1/2 5 commit 對齊
- ✅ §11 Quality Gates ↔ GR6-GR10 架構 gate
- ⚠ §8 nightly $50/month cap 仍無 PM 確認，fail-open warning 未入 CI
- ✅ §15 Change Log 完整記載 8 commit + 驗證

### 開放問題

1. PM Q1-Q10 全懸而未決 — 影響 BDD tier tag / fixture / 金流 / 角色矩陣
2. E7 §Ⅲ.b 對照表是否仍精確？（須驗證所有 Feature 都有對應）
3. Wave 3 deadline 不明 — Happy Path 8 條與 Wave 並行排程？
4. Schemathesis PR-gate `--check-only` 與 nightly 50 case fuzz 銜接？flaky rate 預測？
5. LINESimulator fixture 是否已驗證 F-001 完整流程？或只是 HMAC 工具？
6. Playwright smoke 5 journey 應為哪 5 條？

### 修正建議


| 位置               | 現況                   | 建議                                            |
| ---------------- | -------------------- | --------------------------------------------- |
| §1 TL;DR         | 「Wave 1+2 累計 5 流程升綠」 | 補表格：commit 雜湊 ↔ 流程提升對照（如 da61b1f = F-023）     |
| §3 表格            | 「合理預設」column         | 加腳註：「預設若 5min 內無異議即採用，反對 24h 內走 ADR」          |
| §15.2            | 5 commit 列出但無時間戳     | 補分支建立日 + merge 日 + review 狀態                  |
| §13 Verification | 列 5 個 make target    | 驗 Makefile 9 target 是否齊（commit 1ffb8d8 claim） |
| §4.1-§4.6        | P0/P1 分級無排程          | 加「Assignee + Sprint 目標日期」column               |


---

## E7x--pm-alignment-Q1-Q10.md

**檔案路徑**：docs/_flows-bdd-test/decision-log/E7x--pm-alignment-Q1-Q10.md
**行數**：617
**Frontmatter**：`title: PM Alignment — Q1–Q10 Decision Matrix | phase: DESIGN | gate: TR4 | status: Active (待 PM 拍板) | owners: [PM, Tech Lead, QA Lead]`
**內部編號系統**：Q1-Q10 + 90 min 議程 + 3 選項 (A/B/C) + §12 追蹤表 + §13 下游更新

### 結構摘要

- §0 為什麼必須先對齊（機會成本）
- §1 90 分鐘議程（5 時段 + 強制決議）
- §2-§11 Q1-Q10 各題詳解（業務脈絡 / 影響流程 / 3 選項對比 / 推薦預設 / 反向後果 / **PM 決策欄位** / 拍板後續更新）
- §12 決策追蹤表（10 row × 6 col）
- §13 拍板後下游更新（bash 指令稿 + 對應 SQL / 程式 / spec 修改清單）
- §14 Verification（24h 內驗證清單）
- §15 Change Log（初版 2026-05-07）

### Outbound cross-refs

- `[[E7x--test-plan-and-readiness]]` — §3 cross-link
- `[[E7--bdd-scenarios]]`、`[[E5x--workflow-*]]`、`[[02-design/specs/dispatch-weights]]`、`[[01-define/E2--statement-of-work]]`

### 對齊狀態

- ✅ 文件完整：3 選項對比 + 推薦 + 影響評估 + 反向後果 + 決策欄位 + 下游清單齊全
- ⚠ **§12 全部「⬜待拍」**（截至 2026-05-07）— 推薦預設 A 出現 8 題、B 出現 2 題（Q4/Q5），若 100% 採預設則文件變說明書而非決策記錄
- ⚠ Q4/Q5 註腳改「自然日 / soft」但 §15 Change Log 未獨立記載調整時間 / 調整人
- ✅ 推薦預設與 E7x §3 表對齊（F-014 🟡 / F-013 🟢）
- ✅ 議程時長合理（90 min）+ 強制決議規則
- ⚠ §13 下游更新有 git checkout 指令但未見對應 PR 名

### 開放問題

1. §12 為什麼全是 ⬜待拍 — 若會議已 2026-05-07 召開為何無記錄？
2. Q4/Q5 預設調整何時進行？對齊會議前 or 後？
3. §13 各題後續更新 SQL/程式路徑正確性？例如 Q1 的 `_admin_user.sql` 是 V2.0 才有嗎？
4. 與 E7x §10 Sprint 1 銜接：對齊決策何時要出，才不拖累 Wave 3？
5. 反向選項實際 cost 估算（Q3=B 多 5 dev-day、Q1=B 修多少 fixture？）

### 修正建議


| 位置             | 現況              | 建議                                            |
| -------------- | --------------- | --------------------------------------------- |
| §0 機會成本        | 「每延一週 = 4 人.週」  | 量化：截至 2026-05-07 已延 N 天 = N person-day 損失     |
| §1 議程          | Q6 在「角色矩陣」輪     | Q6 與 Q1/Q2 角色定義性質不同，建議移輪或重分類                  |
| §12 表格         | 永遠「⬜待拍」         | 加「預計拍板日」column；commit tag 強制更新                |
| 各題後續更新         | 列檔案路徑無 reviewer | 加「Owner」+「Review gate」對應 §12 ownership matrix |
| §15 Change Log | 初版 2026-05-07   | Q4/Q5 預設調整應補獨立 row                            |


---

## E7x--module-specification-and-tests.md

**檔案路徑**：docs/_flows-bdd-test/v-model-left/E7x--module-spec-v1-core.md（前身：E7x--module-specification-and-tests.md，已 split）
**行數**：1,509
**Frontmatter**：`version: v2.0 | Last Updated: 2026-04-04 | Status: 草稿(Draft) | Lead Author: 開發工程師 | Reviewers: 技術負責人`
**內部編號系統**：模組 1-5（AI 層）+ 模組 6-21（V2.0 業務服務層）+ 規格 N-M + TC-{CM,PCE,TLR,...}-NNN + Addendum 實作對照表

### 結構摘要

- 封面 + 目錄
- 模組 1-5（DbC 規格 + Arrange-Act-Assert TC）：ConversationManager / ProblemCardEngine / ThreeLayerResolver / KnowledgeBaseManager / SOPGenerator
- §Addendum 實作模組對照（line 1400-1432）：規劃 5 模組 vs 實際 LangGraph nodes / Harness L1-L8
- V2.0 業務服務模組 16 個（模組 6-21）：RefundService / TechnicianMatcher / PricingEngine / ComplaintLifecycle / TechnicianRating / WorkOrderException / WarrantyClaim / AuditLogger / RBACService + 7 其他（僅職責簡述）

### Outbound cross-refs

- `docs/03_behavior_driven_development.md`（疑似舊路徑，待確認）
- `docs/05_architecture_and_design_document.md`、`docs/08_project_structure_guide.md`
- `SQL/Schema.sql` / `SQL/Schema_v2_extensions.sql`
- `docs/agent-harness-refactor/{gap-analysis,migration-roadmap,problem-card-spec,graph-flow-redesign}.md`（Addendum 參考）

### 對齊狀態

- ⚠ **§Addendum 揭露巨大 gap**：規劃 5 模組 vs 實際 LangGraph + Harness L1-L8 + V2.0 業務 16 模組；架構從 traditional layered 遷移至 LangGraph harness，但 module spec 主章節未同步
- ⚠ V2.0 業務服務模組 6-21 邊界不清：標題「V1.0 核心模組」實則含 V2.0 派工 / 帳務 / 品質
- ❌ 與 F-101~F-109 BDD Feature **缺明確對應**
- ✅ DbC 規格嚴謹：模組 1-2 的前置 / 後置 / 不變性 + AAA 測試案例可直接驅動 TDD
- ⚠ 模組 6-21 僅有名稱 / 路徑 / 職責，無 DbC 規格（與模組 1-5 完整度不符）
- ⚠ 引用 `docs/agent-harness-refactor/` 4 個檔，需確認存在

### 開放問題

1. 模組 1-5 為何只展開前 3 個（ConversationManager/ProblemCardEngine/ThreeLayerResolver）？KnowledgeBaseManager / SOPGenerator 完整規格在哪？
2. Harness L1-L8 與模組 1-5 對應關係？（ConversationManager 改名為 Harness L2 嗎？）
3. 模組 6-21 與 E7x §4.3 API 缺口對應？例如 `updateCustomer` 在 RBACService（模組 14）嗎？
4. 測試案例 TC-CM-001~TC-PCE-006 何時實裝為 pytest？目前 Tier 是？
5. Status 為何永遠 Draft（2026-04-04）？距 E7x 更新（2026-05-07）已 1 個月

### 修正建議


| 位置                | 現況                               | 建議                                                                       |
| ----------------- | -------------------------------- | ------------------------------------------------------------------------ |
| 標題                | 「V1.0 核心模組」含 V2.0 業務層            | 改「完整模組規格（V1.0 + V2.0）」+ toc 分層                                           |
| 模組 1-5 subheading | 無完成度 indicator                   | 加 ✅ 完整 DbC / ⏳ 部分 / ❌ 骨架                                                 |
| §Addendum         | 對照表 + Harness 模組分開               | 合併為「架構演進對照表」3 列：規劃 / V1.0 LangGraph+Harness / V2.0 業務 + migration status |
| line 1424-1431    | 引用 `agent-harness-refactor/` 4 檔 | 檢查存在；存在則 embed 摘要；不存在標 ⚠ TODO                                            |
| 模組 6-21           | 僅職責一行                            | 補「規格 N-1/N-2」框架 + 至少 2 個 TC skeleton                                     |
| V2.0 模組編號         | 6-21（16 個）                       | 確認連續性，模組 0 / Harness layer 命名位置                                          |


---

## 跨檔總結（給 Phase 3 alignment matrix 的輸入）

### 共通對齊缺口


| 缺口類型                                            | 影響檔                                      | 嚴重度              |
| ----------------------------------------------- | ---------------------------------------- | ---------------- |
| **3 個 E5x workflow 缺 F-XXX 對應引用**               | work-order / dispatch / admin-governance | 🔴 HIGH          |
| **module-spec 缺 F-101~F-109 BDD 對應**            | E7x module-spec                          | 🟡 MEDIUM        |
| **角色命名 6 vs 7（work-order vs admin-governance）** | work-order / admin-governance            | 🟡 MEDIUM        |
| **F-011/F-016/F-022/F-023 BDD Feature 缺**       | E7 + E7x test plan                       | 🟡 待 PM Q3/Q5/Q7 |
| **F-107 情緒分流閾值 0.85 vs 0.90 不一致**               | E7 BDD                                   | 🟡 MEDIUM        |
| **Q1-Q10 全部 ⬜待拍**                               | pm-alignment                             | 🔴 BLOCKING      |


### 共通優點

- ✅ E1x 旅程、E5x workflow、E7 BDD 主流程 cross-ref 完整
- ✅ E7x test plan §1/§2 與 PR #34 後內部一致
- ✅ E7 §Ⅲ.b PR #33 補上後填補了 BDD ↔ flow 對照斷層

### 最優先行動（Phase 4 修正候選）

1. 在 3 個 E5x workflow 各 Flow 標題後補「對應 F-NNN」
2. 統一角色命名（work-order vs admin-governance 角色映射表）
3. F-107 情緒分流閾值統一
4. module-spec Addendum 重整 + 模組編號分層
5. 等 PM Q1-Q10 拍板後（外力）才能解的：F-011/F-016/F-022/F-023 BDD 補完

