---
title: CR-0039 完工硬閘 — 照片≥N / 簽名 / serial gate（BR-M08-03）
status: implemented
tier: 4-exploration
created: 2026-06-19
owner-decision: ✅ 2026-06-19 業主裁決全採建議預設（見 §8）
related: CR-0026(公單欄位) / CR-0027(電子工單) / BR-M08-03 / test-plan §46 / ADR-0053(serial_required)
---

> ✅ **§8 已裁決（2026-06-19，全採建議預設）+ 已實作（見 §10 進度）。** 屬 CR-0038 階段1「公單收尾」首要項。

## 1. 動機（WHY）

CR-0038 風險 #4 + 會議「公單收尾」：**師傅目前可以無照片、無簽名、無序號完工**。
`work_order_service.complete_order` 只檢查狀態機（accepted|in_progress → completed），
把 signature/photos 打包成 `service_report` **字串**，**不驗任何完整性**。這是：
- Beta 測試計畫 §46 明列驗收項（「M08 完工照<3張阻擋」）。
- 客訴 / 帳務爭議的源頭（無證據完工 → 無法佐證、無法核銷、保固責任不清）。

## 2. 觸發面向（7 選哪些）

| 面向 | 命中 | 說明 |
|---|:-:|---|
| API contract | ✅ | 完工端點新增 422 失敗路徑（INSUFFICIENT_PHOTOS / SIGNATURE_REQUIRED / SERIAL_REQUIRED）|
| Domain model | ✅ | 完工 invariant：completed 必須有足量證據 |
| Business rule | ✅ | 照片門檻 / serial 觸發條件 / 硬擋 vs 軟擋 |
| DB schema | 🟡 | 不一定 —— 門檻值入 M18 config（仿 CR-0036），可不動 schema；欄位（serial_number/service_category）migration 036 已有 |
| Test plan | ✅ | 新增完工硬閘 component 測試 |

## 3. 現況（grounded，file:line）

- `api/services/work_order_service.py:580 complete_order(tenant_id, wo_id, summary, actual_amount)` — **僅狀態機檢查**，summary 直接寫 `service_report`，零完整性驗證。
- 呼叫者 **3 處**（`work_orders_v2.py:320`、`:682 onsite_completion_v2`、`work_orders.py:220` v1）→ gate 必須放 **service 層**才全覆蓋（放 router Pydantic 會漏其他兩條）。
- `work_orders_v2.py:599 _CompletionSubmitRequest`：`photo_evidence_ids` min_length=**1**（spec 要 3）、`signature_evidence_id` 僅 min_length=1（非空字串，**未驗證真存在於簽名紀錄**）。
- 可用欄位：`work_orders.service_category`(install/warranty_in/warranty_out/repair)、`serial_number`、`inventory.serial_required`(ADR-0053；`:consume` 已有 422 gate)。

## 4. API 契約變更

完工端點（`POST /tenants/{tid}/work-orders/{woId}/onsite/completion` + v1）新增**前置驗證**，失敗回 422 RFC7807：

| error_code | 觸發 | 訊息 |
|---|---|---|
| `INSUFFICIENT_PHOTOS` | 完工照片數 < 門檻（預設 3）| 完工照片至少 N 張 |
| `SIGNATURE_REQUIRED` | 無 signature 或簽名紀錄不存在 | 完工需客戶簽名 |
| `SERIAL_REQUIRED` | serial gate 命中但 `serial_number` 空 | 此案需登錄鎖體序號才可完工 |

成功路徑與回傳不變（CompletionResult）。**Breaking**：原本只帶 1 張照片就能完工的 client 會開始收 422 → 前端完工頁需配合（補張數提示 + serial 欄）。

## 5. 領域 / 資料

- **不新增表**。門檻值走 **M18 config**（namespace `completion_policy`：`min_photos`、`require_signature`、`serial_required_categories`），仿 CR-0036 訂金 config，**不寫死**（符會議紅線）。migration 047 僅 seed config（idempotent）。
- serial gate 觸發：讀 `work_orders.service_category` 比對 config `serial_required_categories`。
- 既有 completed 工單 **不回溯**（grandfather）。

## 6. 測試計畫

`test_cr_0039_completion_gate.py`（component，真 DB）：
- 照片 2 張 → 422 INSUFFICIENT_PHOTOS；3 張 → 通過。
- 無簽名 / 簽名 id 不存在 → 422 SIGNATURE_REQUIRED。
- service_category=install 且無 serial → 422 SERIAL_REQUIRED；有 serial → 通過。
- service_category=repair（不在 serial_required_categories）→ 無 serial 也可完工。
- config 缺失 fallback 預設（min_photos=3）。
- 既有 completed 工單不受影響。

## 7. 風險

- 前端完工頁未同步 → 師傅完工一律 422（高影響）。緩解：同 CR 補前端（張數提示 + serial 欄）或先 soft-warn 一個 sprint。
- serial gate 誤擋維修案 → 嚴格限定 `serial_required_categories`（預設只 install）。
- config 缺失 → 必須有 fallback 預設值，否則完工全擋。

---

## 8. 🛑 Human Decisions Required（等業主裁決）

| # | 決策 | 建議預設（依 spec/test-plan）| 業主裁決（2026-06-19）|
|:-:|---|---|---|
| **HD-1** | 完工照片最少張數 | **3**（test-plan §46）| ✅ **3 張**（統一，入 config min_photos）|
| **HD-2** | 硬擋 vs 軟擋 | **硬擋（422）+ 主管 override** | ✅ **硬擋 422 + 主管 override**（admin/dispatcher `:complete` 為 override 路徑，記 reason；技師 onsite 路徑硬擋）|
| **HD-3** | serial gate 觸發條件 | 只 **`service_category='install'`** | ✅ **只 install**（serial_required_categories=["install"]）|
| **HD-4** | 簽名驗證深度 | **驗證真存在於簽名紀錄** | ✅ **驗證 `digital_signatures` 真有該 wo 簽名**（非僅非空字串）|
| **HD-5** | 既有 completed 工單回溯 | **不回溯** | ✅ **不回溯**（grandfather，只對新完工生效）|

> **實作要點（裁決後補）**：override 路徑須加**非技師角色 guard**（admin/ops_manager/dispatcher 才可走 `:complete`），否則技師可繞過 onsite gate。門檻全入 M18 config `completion_policy`（min_photos / require_signature / serial_required_categories / allow_supervisor_override），不寫死。

## 9. Suggested Implementation Order（裁決後）

1. migration 047：seed `completion_policy` config（min_photos / require_signature / serial_required_categories）。
2. `complete_order` 加結構化參數（photo_evidence_ids / signature_evidence_id）+ 三道 gate（讀 config + 查簽名 + 查 service_category/serial）。
3. 3 個呼叫者傳入結構化證據；v1/v2 router 對齊。
4. `test_cr_0039_completion_gate.py` component 測試。
5. 前端完工頁：張數提示 + serial 欄 + 422 錯誤對應（同 CR 或 follow-up）。
6. `redeploy-local.sh` smoke + 更新 CHANGELOG / 完成度 / 本 CR §進度。

---

## 10. 進度

✅ **S1-S4 done（2026-06-19，branch `feat/cr-0039-completion-gate`）**：
- **migration 047** `completion_policy` config（min_photos=3 / require_signature / serial_required_categories=["install"] / allow_supervisor_override；is_mock:false 業主裁決定案）— 套 dev + 記 schema_migrations。
- **`work_order_service`**：`_enforce_completion_gate`（讀 config + fallback 預設）三道閘 + `_signature_exists`（查 digital_signatures 客戶簽名真存在，HD-4）；`complete_order` 加 5 參數（photo_evidence_ids / signature_evidence_id / is_override / override_reason / actor_role），gate 置於狀態檢查後。
- **routers**：技師 `/onsite/completion` 走正規閘（is_override=False，傳結構化證據）；`:complete` v2 + v1 為 admin/dispatcher **override 路徑**（記 summary 為 reason）+ **技師角色 403 guard**（防繞過 onsite 閘）。
- **error codes**：`INSUFFICIENT_PHOTOS` / `SIGNATURE_REQUIRED` / `SERIAL_REQUIRED`（422）+ override `VALIDATION_ERROR`（422，缺 reason）。
- **測試** `test_cr_0039_completion_gate.py` **8/8 pass**（照片<3 / 簽名缺/空 / 維修放行 / 安裝缺序號擋 / 安裝有序號放行 / override 缺reason擋 / override放行）；回歸 50 完工相關 component + 226 unit 全綠、0 破壞。

⏳ **follow-up（S5，未做）**：前端技師完工頁配合（照片≥3 提示 + serial 欄 + 422 友善訊息）；目前後端已硬擋，前端送 <3 照片會收 422（行為正確、訊息為中文 error）。**HD-5 不回溯**：既有 completed 工單不受影響（gate 只在 complete 動作時跑）。
