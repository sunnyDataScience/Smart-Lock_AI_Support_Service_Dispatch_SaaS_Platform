# TC-PLT-FLOW-01 — 工單積木引擎：Flow DSL 匯入與靜態拒絕

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **不一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主** | 未啟動應用服務；TC 指名的識別碼在程式碼樹零命中，無可執行之對應測試 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | 全 repo grep（`api/`、`web/`、`SQL/`、`agent/`、`scripts/`）+ `smartlock-docs/enterprise/04_SRS.md`、`smartlock-docs/enterprise/bdd/SC-18.feature` |
| 優先級 / 路徑類型 | P1 / failure＋recovery |
| 事實結論 | TC 指名的功能識別碼（Flow DSL、block、積木、Vertical Pack、guard、狀態轉移驗證、版本回退）在程式碼樹**零命中**：`DSL`（大小寫敏感）在 `api/ web/ SQL/ agent/ scripts/` 零命中；`flow_dsl` / `block_library` / `積木` / `vertical_pack` / `workflow_definition` / `flow_version` / `block_type` 全零命中。唯一帶 `FR-PLT-07` 字樣的檔案全屬文件與 drawio 圖，`04_SRS.md:387` 該列本身標示「🔜 規劃中 AI Onboarding Compiler」。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：合法與非法 Flow DSL/Block fixture
- 步驟：匯入合法 DSL，再匯入未知 block、缺 guard、非法狀態轉移與破壞性版本
- 預期結果（判定基準）：非法檔在發佈前被靜態拒絕且無 runtime side effect；合法版本可審計、可回退
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P1
- 驗證需求：FR-PLT-07｜屬於旅程腳本：SC-18

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 匯入合法 Flow DSL | — | **找不到**：無 DSL 匯入端點／解析器 |
| 未知 block 拒絕 | — | **找不到**：無 block 型別註冊表 |
| 缺 guard 拒絕 | — | **找不到**：無 guard 概念之程式碼實作 |
| 非法狀態轉移拒絕 | — | **找不到**：無可設定之流程狀態機（既有狀態機為硬編碼，見「觀測到的其他事實」） |
| 破壞性版本拒絕 | — | **找不到** |
| 發佈前靜態拒絕、無 runtime side effect | — | **找不到** |
| 合法版本可審計 | — | **找不到**（flow 層面）；其他物件的版本／稽核見「觀測到的其他事實」 |
| 合法版本可回退 | — | **找不到**（flow 層面） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 租戶 Admin | 匯入合法 Flow DSL | `FlowDefinitionImported` | schema 驗證 | — | **找不到** |
| 租戶 Admin | 匯入含未知 block 的 DSL | `ImportRejected(UNKNOWN_BLOCK)` | 積木庫白名單 | — | **找不到** |
| 租戶 Admin | 匯入缺 guard 的 DSL | `ImportRejected(MISSING_GUARD)` | guard 必填 | — | **找不到** |
| 租戶 Admin | 匯入非法狀態轉移 | `ImportRejected(INVALID_TRANSITION)` | 狀態機驗證 | — | **找不到** |
| 租戶 Admin | 回退到前一版 flow | `FlowVersionRolledBack` | 版本化 | — | **找不到** |
| 系統 | 記錄 flow 變更 | `FlowChangeAudited` | 全程稽核 | — | **找不到** |

---

## 逐層走查

### 步驟 1 — TC 指名識別碼的 grep 結果

- **動作**：於程式碼樹搜尋 TC 前置／步驟提及的識別碼
- **預期**：至少一個非零命中
- **實際**：全部零命中

```
git grep -rn "DSL" -- api/ web/ SQL/ agent/ scripts/
（無輸出，exit=1）

git grep -rlni "flow_dsl|flow dsl|block_library|積木|vertical pack|vertical_pack" -- api/ web/ SQL/ agent/ scripts/
（無輸出，exit=1）

git grep -rln "workflow_definition|flow_version|block_type" -- api/ SQL/
（無輸出，exit=1）
```

### 步驟 2 — `FR-PLT-07` 的命中分佈

- **動作**：全 repo 搜尋 TC 追溯的需求編號
- **預期**：程式碼中有實作對應
- **實際**：命中全落在文件與圖檔

```
git grep -rlni "flow.dsl|工單積木|onboarding compiler|FR-PLT-07" -- .
CHANGELOG.md
docs/system-completion-status.md
drawio/00_總覽/00-1_mindmap.drawio
drawio/01_平台層/01-2_core-vs-pack.drawio
drawio/03_執行層/03-4_state-machine.drawio
drawio/04_流程圖/04-4_knowledge-loop.drawio
drawio/05_共用核心/05-1_kernel.drawio
drawio/smartlock-platform-architecture.drawio
smartlock-docs/README.md
smartlock-docs/enterprise/00_Product_Strategy.md
smartlock-docs/enterprise/01_MRD.md
smartlock-docs/enterprise/02_BRD.md
smartlock-docs/enterprise/03_PRD.md
smartlock-docs/enterprise/04_SRS.md
smartlock-docs/enterprise/07_Journey_Map.md
…（其餘皆為 smartlock-docs 內文件）
```

無 `api/`、`web/`、`SQL/`、`agent/` 檔案命中。

### 步驟 3 — SRS 對 FR-PLT-07 的敘述

`smartlock-docs/enterprise/04_SRS.md:387`

```
| FR-PLT-07 | 工單積木引擎（平台核心）| DSL schema 凍結 | §2.3 flow DSL 執行器 + 積木庫 + Vertical Pack 載入；🔜 規劃中 AI Onboarding Compiler（客戶 SOP → draft DSL → 必過人審）| 碰金流/派工/同意書的 AI 產出流程 100% 過 HITL | ADR-P010/P011 |
```

該列的「前置條件」欄為「DSL schema 凍結」。

### 步驟 4 — SC-18 腳本對本 TC 的引用

`smartlock-docs/enterprise/bdd/SC-18.feature:10`

```
  # 驗收腳本案例（sc_verified_by_tc）: TC-EXC-02, TC-NFR-PERF-01, TC-PLT-CFG-01, TC-PLT-FLOW-01, TC-SEC-RBAC-03, TC-SETTLE-07
```

同檔 `:14-22` 的 happy scenario 措辭為「品牌需調整費率、文案、skill 客製層或流程積木 / When 於後台編輯 / And 版本化 / And 評估閘門 / And 分階段推出 / And 觀察 / And 必要時一鍵回滾」——其中「費率」「文案」「skill 客製層」三項在程式碼中有落點（見「觀測到的其他事實」），「流程積木」無。

---

## 既有測試證據

無對應既有測試。`git grep -rln "dsl\|flow_version\|block" -- api/tests` 未命中任何以 flow/DSL 為對象的測試檔。

---

## 觀測到的其他事實

1. **repo 內確有「版本化 + 發佈閘 + 回滾 + 稽核」的通用機制，但對象不是 flow**：
   - config 版本（M18）：`api/services/config_m18_service.py:334`（`create_draft`）、`:391`（`start_rollout`）、`:574`（`rollback`）、`:192-214`（`_append_audit` append-only）。
   - skill 版本：`api/services/skill_service.py:324-375`（`publish`，含發佈驗證閘 `validate_publishable`）、`:378-425`（`rollback`）、`:493-522`（`_write_audit`）。

2. **既有狀態機為硬編碼於 service，非可匯入之定義檔**：
   - 工單狀態轉移：`api/services/work_order_service.py`（`STATE_CONFLICT` 判定散於各轉移函式）。
   - 技師生命週期：`api/services/technician_lifecycle_service.py:39-46` 的 `_ALLOWED_TRANSITIONS` 為模組層 dict 常數。
   - 同檔 `:48-52` 另記錄一項既有事實：`_EVENT_TRANSITIONS` 表「目前**沒有任何地方讀它**（全檔唯一出現處就是這個定義）」。

3. TC 判定基準寫「非法檔在發佈前被靜態拒絕且無 runtime side effect；合法版本可審計、可回退」（出處：② 測試案例主表 TC-PLT-FLOW-01 列）／程式碼樹無 flow/DSL/block 的任何實作落點。此處僅並陳，不裁定。
</content>
