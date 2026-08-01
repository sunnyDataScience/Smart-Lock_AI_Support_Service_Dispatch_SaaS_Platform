---
id: CR-0197
title: 品牌授權閘門要不要真的啟用（fail-closed 已實作，等營運資料與業主裁決）
status: decided
created: 2026-07-31
author: Claude（代跑 SC-13～19 整合測試時發現）
triggers: [Architecture boundary, Test plan]
related: [FR-TEC-02, FR-TEC-03, FR-J01, TC-DISPATCH-06, CR-0060, CR-0114]
---

# CR-0197 — 品牌授權閘門要不要真的啟用

## 1. 一句話

程式碼已依測試計畫改成 fail-closed（commit `49de54d3`），但 **prod 的品牌授權名單從
2026-06-20 建立至今從未被營運填過真實資料** —— 閘門啟用與否是營運決策，不是技術決策。

---

## 2. 需求追溯（先確認「原本有沒有這條要求」）

業主問的正是這題。答案是**有，而且在你自己的正典裡**。

| 出處 | 條文 |
|---|---|
| `smartlock-docs/enterprise/04_SRS.md` **FR-TEC-02**（KYC / 認證准入） | 「KYC + 認證上傳 → 人工審核 → 認證生效 **+ 品牌授權** → `technician.certified` / `technician.brand_authorized` 事件」<br>**驗收欄：「未過准入閘門不得進入派工候選集」** |
| 同上 **FR-TEC-03**（OHS 派工媒合） | 「`POST /technicians:match`（技能／地區／**品牌授權**／可用性）→ 排序候選」 |
| `smartlock-docs/enterprise/03_PRD.md` **FR-J01** | 「技師身分單一真相：跨租戶身分／技能／**品牌授權**／認證（KYC）／排班／評分」 |
| 整合測試計畫 `② 測試案例主表` **TC-DISPATCH-06** | 判準：「品牌授權過濾擋下；**無授權資料時不得 fail-open 放行**（fail-closed 驗證）」<br>驗證哪些需求欄：**FR-TEC-02、FR-TEC-03** |

追溯鏈完整：SRS → 測試計畫 → 測試案例。**fail-closed 符合 FR-TEC-02 的驗收條文。**

### 2.1 但正典沒有規定的邊界

FR-TEC-02 規範的是「**技師**未過准入閘門不得進候選集」。
它**沒有**規定「**整個品牌**都沒有任何授權名單時該怎麼辦」。

那個邊界是 CR-0060 實作時自己補的判斷，而測試計畫後來把它判為不合規。
兩種讀法都能自圓其說：

- **(a) fail-closed**：沒有人被授權過 → 沒有人能進候選集 → 擋（TC-DISPATCH-06 的讀法）
- **(b) fail-open**：沒有資料可判 → 不阻擋（CR-0060 原實作的讀法）

---

## 3. 為什麼原本是 fail-open（歷史，不是疏漏）

`CHANGELOG.md` 對 CR-0060（2026-06-20）的記載：

> **CR-0060 技師技能矩陣 + 品牌授權**：審計 #12 #13 / BR-M07-01。技師原僅 capabilities
> JSONB 自由清單，無結構化技能矩陣／品牌授權。**沿會議 mock-first 授權**建資料模型：
> migration 063 `technician_skill` + `technician_brand_authorization` + **seed 示範（is_mock）**。
> `dispatch_service` 候選清單／auto_match 加品牌授權過濾（`_brand_authorized_ids`：
> 未授權／認證過期技師排除；**無授權資料保守不過濾**）。

關鍵：**資料模型照需求建，但授權資料本身從一開始就是 mock**。當時若真的擋下去，demo 會跑不動。
「保守不過濾」是那個時空下的合理選擇，不是寫錯。

### 3.1 追溯鏈斷點（順帶修正）

程式碼註解引用的需求編號是 **`BR-M07-01`**，但該編號在 `smartlock-docs/` **零命中** ——
只存在於 CHANGELOG 與程式碼／測試註解。研判是 2026-07-08 大掃除刪除 tracked `docs/` 樹時
一併消失（查 git 歷史）。本 CR 一併把程式碼註解指向現行正典的 **FR-TEC-02 / FR-TEC-03**。

---

## 4. prod 實際資料（2026-07-31 唯讀查詢，經 cloud-sql-proxy）

### 4.1 授權表現況（`lock_tech.technician_brand_authorization`）

| 品牌 | 有效授權筆數 |
|---|---|
| Generic | 13 |
| Yale | 13 |
| Kaadas | 13 |
| Philips | 13 |
| Samsung | 13 |

**整齊的「各 13 筆」＝ CR-0060 的 `is_mock` seed 原封不動，營運從未新增或修改。**

### 4.2 真實工單用到的品牌（`lock-ai-db.work_orders`）

| 品牌 | 工單 | 授權 |
|---|---|---|
| （NULL） | **77** | 不適用（`_brand_authorized_ids(None)` 回 None，維持不阻擋）|
| Chatlock | 2 | 🔴 無 |
| Philips | 1 | ✅ 有 |
| Dormakaba | 1 | 🔴 無 |

### 4.3 兩個重要觀察

**① 這道閘門目前對 95% 的工單完全無作用。**
81 張工單有 77 張 `brand` 是 NULL。查過成因——**不是程式 bug**：
`work_order_service.create_from_problem_card` 確實有帶 `pc_brand`，且時間分布顯示
NULL 的那批**停在 2026-06-07**，之後唯一一張（07-21）有品牌。那 77 張是歷史 seed/demo 資料。

**② 真正的風險在未來的單。**
prod 問題卡橫跨 8 個品牌，授權表只涵蓋 5 個。差集：

**Chatlock（11 張卡）、Dormakaba（10）、美樂（10）、Xiaomi（10）、Gateman（10）**

新開的工單會正常帶品牌 → 這五個品牌一旦開單，fail-closed 就會擋下自動派工。

---

## 5. 目前程式碼狀態（已 merge 至 dev-ding，**未部署 prod**）

commit `49de54d3`：

- `dispatch_service._brand_authorized_ids`：查無授權列由回 `None` 改回**空集合**
  （`brand` 為空仍回 `None` —— 「沒有品牌可判」與「判了但沒人符合」是兩件事）
- `work_order_service._assert_brand_authorized`：新增 `BRAND_AUTHORIZATION_LIST_EMPTY` 403，
  訊息直接給出兩條出路
- **主管 `override_reason` 安全閥維持不變** —— 那是 fail-closed 能安全落地的前提
- 三支釘住舊契約的既有測試同步更新並標注原因

---

## 6. 影響評估

| 面向 | 選 A（啟用） | 選 B（明確 defer） |
|---|---|---|
| 現有工單 | 3 張受影響（Chatlock 2 / Dormakaba 1，皆未結案，研判為 demo 單）| 0 |
| 未來工單 | 5 個品牌開單前必須先建授權名單 | 無限制 |
| 營運工作量 | 需為 5 個品牌 × N 位技師建授權（目前無 UI，只能打 API 或 SQL）| 0 |
| 稽核 / 合規 | 符合 FR-TEC-02 驗收條文 | 與 FR-TEC-02 不符，需在正典標注 deferred |
| 風險 | 名單沒建齊 → 派工受阻（有 override 安全閥）| 派工資格閘門形同虛設，且**看起來有在擋** |

**選 B 的隱性成本**：留一個「看起來有在擋、實際不擋」的閘門，比明確關掉更危險 ——
下一個讀這段程式碼的人（含 AI）會以為派工資格已受控。

---

## 7. 補資料的可行路徑（若選 A）

目前 `technician_brand_authorization` 的維護端點是
`PUT/DELETE /api/v1/platform/technicians/{id}/brand-authorizations/{brand}`（平台面），
**四站台皆無對應 UI**（只有 `shared-contract` 的型別）。所以補資料只能：

1. 打 API（需 platform_admin token）
2. 直接下 SQL（需 cloud-sql-proxy）
3. 先做 UI（平台 console「技師詳情 → 品牌授權」分頁）

---

## 8. ✅ Human Decisions（業主 2026-08-01 裁決：「照你建議處理」）

### 裁決結果

| # | 裁決 | 落地 |
|---|---|---|
| **D1** | **(c) 折衷** —— fail-closed + M18 config 開關，預設 off，逐租戶啟用 | migration 127 + `dispatch_service.brand_auth_enforced()` |
| **D2** | 暫不補資料 —— 開關預設 off，補資料不阻塞。待業主決定啟用時機再產 SQL 或做 UI | 未動 |
| **D3** | **(a) 不處理** 77 張 `brand` NULL 的歷史工單 —— 都是 2026-06-07 前的 demo 資料，且 NULL 不觸發閘門；回填反而會讓它們**開始**受閘門約束 | 未動 |
| **D4** | **(a) 指向 FR-TEC-02 / FR-TEC-03**，保留原編號不切斷與 CHANGELOG／既有測試的關聯 | `dispatch_service._brand_authorized_ids` docstring |

### 實作摘要（commit 見 §10）

- **migration 127** `dispatch-policy-namespace.sql`：註冊 `dispatch_policy` namespace，
  `brand_auth_enforce` 預設 **false**。完全比照 118 的成因——`config_version.namespace`
  有 FK 指向 `config_namespace(code)`，**namespace 沒註冊開關就永遠開不了**。
  `is_protected=true` + owner 空集合（admin-only），准入閘門不得由租戶 override 關閉。
- **`dispatch_service.brand_auth_enforced()`**：讀開關；**config 讀取失敗一律視為未啟用**
  （default-off 開關讀不到設定時採現況行為才安全，比照 `_assert_reconcile_gate`）。
- 兩個判斷點共用同一開關（`_brand_authorized_ids` 與 `work_order_service._assert_brand_authorized`），
  語意必須一致，否則自動派工與手動派工會分岔。
- **關閉時記 info 而非靜默**：「閘門存在但沒在擋」必須看得見，否則會被誤以為派工資格已受控。

### 驗收

- `test_sc13_19_findings.py` 增為 **11 測試**，新增兩條釘住預設行為：
  `test_brand_gate_off_by_default_preserves_legacy_behaviour`（預設 off 不阻擋）與
  `test_brand_gate_falls_back_to_off_when_config_unreadable`（config 掛掉不變成擋人）。
  **這兩條比 fail-closed 那三條更重要** —— 它們釘住「業主還沒開閘門之前派工不會被打斷」。
- 兩支既有測試（cr_0060／cr_0114）改回釘**預設行為**（`is None`）並註明現在由開關決定；
  fail-closed 側由 `test_sc13_19_findings.py` 以 monkeypatch 開啟開關後驗證。
- migration 127 於 scratch 與 `lock_AI_data` 兩庫各連套兩次退出碼 0（冪等）。
- 全套對照 scratch 基線 **129 → 123 失敗，零新增**（含 drift check 綠）。

### 尚未做（等業主決定啟用時機）

1. 補 5 個品牌的授權名單（Chatlock／Dormakaba／美樂／Xiaomi／Gateman）
2. 平台 console 的品牌授權維護 UI（目前只有 API，四站台無 UI）
3. prod 套 migration 127 + 部署（**值為 false ＝ 行為與現況相同，可安全部署**）

---

## 8-原. 🛑 原始待裁決項（保留供追溯）

### D1：品牌授權閘門要不要真的啟用？

- **(a) 啟用** —— 維持已實作的 fail-closed，營運補齊 5 個品牌的授權名單後再部署
- **(b) 明確 defer** —— 回退 fail-closed，並在正典 FR-TEC-02 旁**標注**（非改寫）
  「品牌授權閘門 v1 不啟用，待 M__ 再開」，程式碼加明確註解說明它目前不具閘門效力
- **(c) 折衷** —— fail-closed 但加 M18 config 開關（namespace 如 `dispatch_policy`，
  `brand_auth_enforce` 預設 off），逐租戶啟用；比照 `reconcile_gate_enforce` 前例

### D2：若選 (a) 或 (c)，誰來補授權名單？

- **(a) 我產出 SQL 腳本**，你或營運確認技師×品牌對應後執行
- **(b) 我先做平台 console 的品牌授權 UI**（另開 CR，屬 feature）
- **(c) 營運自行打 API**

### D3：那 77 張 `brand` 為 NULL 的歷史工單要處理嗎？

- **(a) 不處理** —— 都是 2026-06-07 前的 demo 資料，且 NULL 不觸發閘門
- **(b) 回填** —— 從其問題卡補 brand（可回填 77 張），讓資料一致；
  但回填後這些單會**開始**受閘門約束

### D4：斷掉的 `BR-M07-01` 追溯鏈

- **(a) 改指向 FR-TEC-02 / FR-TEC-03**（本 CR 預設做法）
- **(b) 保留原編號** 並在正典補一份 BR 對照表

---

## 9. Suggested Implementation Order（待 §8 裁決後）

1. 依 D1 決定是否保留／改造 fail-closed
2. 依 D4 修正程式碼註解的需求追溯（低風險，可先做）
3. 依 D2 產出補資料路徑
4. 依 D3 決定歷史資料
5. 部署前重跑 §4 的 prod 盤點腳本確認涵蓋率
6. 更新 CHANGELOG 與 27_WBS 對應項

---

## 附錄：本 CR 的查證方式

- prod 資料經 `cloud-sql-proxy --gcloud-auth` 唯讀查詢，**只有 SELECT**；
  查畢已刪除暫存連線字串並關閉 proxy。
- 需求追溯以 `grep` 全庫比對，`BR-M07-01` 零命中為實測結果而非推測。
- 「品牌未傳遞」一度被誤判為 bug，經查 `create_from_problem_card` 有帶 `pc_brand`
  且 NULL 資料停在 06-07 → 修正為歷史資料，非程式缺陷。
