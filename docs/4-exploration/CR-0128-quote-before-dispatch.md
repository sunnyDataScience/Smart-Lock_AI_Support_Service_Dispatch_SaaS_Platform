# CR-0128: 報價先行——WO.created 硬綁 Quote 客戶確認（WBS 1.2.1）

- **日期**: 2026-07-09
- **狀態**: done（2026-07-09 實作完成）
- **觸發面向**: Business flow（BR-WO-01）、工單/報價狀態機、API contract（convert 前置）、DB schema（急件欄位）
- **上游正典**: ADR-015 不變式①②（Accepted 2026-07-07）、02_BRD §5.7 WorkOrder/Quote 狀態機、BR-WO-01「線上報價 → 客人確認 → 才開單派工」、0707 會議 §五（AI #4）

## §1 現況 vs 目標（差距盤點，全部對 code 查證）

| # | 目標（ADR-015①/BRD §5.7）| 現況 | 差距 |
|---|---|---|---|
| G1 | Quote 先綁問題卡，客戶確認後才開單 | `quote.problem_card_id` 欄位**已存在**、`work_order_id` 可空（041-quote-engine.sql）——但 `create_quote()` 只接 `work_order_id`（必須先有工單）；前端報價 UI 走 `POST /work-orders/{id}/quotes` + WorkOrderPicker | 新增 PC 層建報價路徑（`work_order_id=NULL`）；convert 時回填 |
| G2 | convert gate：PC.confirmed **AND**（Quote 客戶確認 OR 急件）；違反 → `425 QUOTE_NOT_CUSTOMER_CONFIRMED`／`409 QUOTE_STATE_INVALID` | `create_from_problem_card()` 只驗 PC.confirmed + address——**零 quote 檢查** | 開單 gate 本體 |
| G3 | 急件 carve-out 四類（`pc.emergency_class`）跳過 quote 直接開單 | DB 無 `emergency_class` 欄；`problem_cards.urgency` 值域＝low/normal/high/urgent（優先級語意，與 4 類急件分類不同軸） | 需定急件判定欄位（§8 D2）|
| G4 | 急件開單 → quote 進 `retrospective_audit_only` →（客戶簽認）`customer_confirmed`；4h timer＝**WBS 1.2.2 另案** | quote 狀態機（`_TRANSITIONS`）：draft→pending_approval→approved→sent→accepted\|rejected\|expired\|superseded——無補審狀態 | 本輪只鋪狀態與轉移，timer/佇列留 1.2.2 |
| G5 | 結案硬閘：address **AND**（quote 確認 OR 急件補審完成）| close 只驗 address（`ADDRESS_REQUIRED_FOR_CLOSE` 422）| close gate 補 quote 分支 |
| G6 | 中央轉移表 enforce | WO 無中央 `_TRANSITIONS`（散落各 endpoint；前端各自維護 `*_FROM` 集合）| 建 DB 7 值（created/assigned/accepted/in_progress/completed/confirmed/cancelled）轉移表，違反 → 409 `INVALID_STATUS_TRANSITION` |

**詞彙對映備註**：runtime DB 狀態 7 值 ↔ API enum 16 值由 `_DB_STATUS_TO_API` 映射（設計稿語彙）；BRD §5.7 的 created→dispatched→on_site→…為 business 視角，明文「狀態值域由 pack flow DSL 定義」——本輪**不改 enum 值域**，以 DB 7 值建轉移表並文件化對映（避免 16 值 enum 改名的全前端爆炸）。Quote 的 `accepted` ≡ BRD `customer_confirmed`（公開 token accept 端點已存在，LINE LIFF 同意流已上線）。

## §4 契約影響

- `POST /problem-cards/{id}/convert-to-work-order`：新增 quote 前置驗證；新錯誤碼 `425 QUOTE_NOT_CUSTOMER_CONFIRMED`、`409 QUOTE_STATE_INVALID`（依 §8 D1 策略生效）。
- 新端點：`POST /problem-cards/{id}/quotes`（PC 層建報價，`work_order_id=NULL`）。
- quote 狀態機新增 `retrospective_audit_only` 與其轉移（急件 carve-out 開單時由系統寫入）。
- DB：`problem_cards.emergency_class`（§8 D2 採 a 時，additive migration）；quote 表零 schema 變更。
- 前端（§8 D1 採 a 時）：問題卡詳情頁建報價/送客戶/狀態徽章 + convert 按鈕 gate 提示；WO 詳情頁報價區沿用。

## §8 Human Decisions Required 🛑

| # | 決策 | 選項 | 待裁決 |
|---|---|---|---|
| D1 | Gate 生效策略 | ✅ **a. 硬 gate + 本輪補 PC 層報價最小 UI**（業主 2026-07-09）| ✅ |
| D2 | 急件判定欄位 | ✅ **a. 新增 `problem_cards.emergency_class` 4 類**（業主 2026-07-09）| ✅ |
| D3 | 存量工單處置 | ✅ **a. 存量豁免**——以 `work_orders.quote_gate_applied` 欄位標記 gate 後新單，結案閘只驗標記單（業主 2026-07-09）| ✅ |

## §9 Suggested Implementation Order（裁決後執行）

1. migration：`emergency_class`（D2a）＋ quote 狀態機補審狀態
2. `create_quote` 支援 PC 綁定（`work_order_id` 可空）＋ convert 回填 WO/補 quote_number
3. convert gate（425/409）＋ 急件 carve-out 寫 `retrospective_audit_only`
4. close gate 補 quote 分支（D3 cutoff）
5. WO 中央轉移表（DB 7 值）
6. 前端 PC 報價流（D1a）
7. 測試（gate 正反向、急件、存量豁免）＋ OpenAPI 設計稿同步 ＋ 治理三件套

### 進度

- ✅ S1 done：migration 091（`emergency_class`／`quote_gate_applied`／quote.state 註解／
  `idx_quote_problem_card_state`）＋ REGISTRY 補登
- ✅ S2 done：`create_quote` 雙綁定（PC 階段 work_order_id=NULL、版本沿綁定對象遞增）＋
  `assert_pc_quote_confirmed`（425/409）＋ `bind_quotes_to_work_order` ＋ `list_pc_quotes`
- ✅ S3 done：convert gate（急件 carve-out → 自動建 `retrospective_audit_only` 佔位報價；
  標準路徑回填綁定；`quote_gate_applied=TRUE`）；quote 狀態機 `audit_complete` 轉移＋
  補審中可編明細
- ✅ S4 done：完工硬閘補 `QUOTE_NOT_CONFIRMED_FOR_CLOSE`（僅驗 gate 後新單，D3a 豁免；
  主管 override 沿既有急修安全閥語意）
- ✅ S5 done：`_WO_TRANSITIONS` 中央轉移表（DB 7 值正典；各 `*_FROM` 為投影，
  對帳測試鎖同步）。現場修正輪＝既有 scope_changes 流程，轉移表已涵蓋回復路徑
- ✅ S6 done：前端 PC 詳情頁「線上報價（報價先行）」區塊（報價列表＋狀態徽章＋建立報價
  →深連結 `/admin/quotes?open=`＋急件四類標記 select＋開單按鈕 gate disabled 提示）
- ✅ S7 done：測試——新增 test_cr_0128_quote_gate 11 項（gate 正反向/急件佔位/補審轉移/
  完工閘/存量豁免/PC 版本/轉移表對帳）；既有 25 個 convert 呼叫點以 `seed_accepted_quote`
  helper 過閘（test_cr_0095 工廠改「過閘即刪」保留原測試意圖）。設計稿同步（錯誤碼對齊
  ADR-015、補審語意對齊 BRD、PC schema 加 emergency_class、close 422 補 quote 閘）
- ✅ 驗證：api unit 331＋component **871 passed**（隔離 scratch pgvector @5446，
  4 個既有環境失敗與本輪無關）；四站 tsc 0；brand-portal build 綠；
  `generate-api-types --check` 冪等過；spectral 0 errors

### 實作備註（與 ADR-015 字面差異）

- ADR-015 寫「`POST /work-orders` 要求 `quote_id`」——實作為 convert 端 gate
  **自動解析** PC 最新 accepted 報價（同一不變式，PC-centric 流程下免客戶端傳參錯誤）。
- 佔位報價於**急件開單當下**建立（BRD §5.7 語意），非舊設計稿 v2.3.0 的「完工後補建」；
  設計稿已同步修正。
- LINE 推送 uid 反查改 `quote → problem_cards` 直連（原 join work_orders 對 PC 階段
  報價會 dead-letter）；PC 階段 accept 的開票延後到 convert 回填綁定後（發票錨定
  work_order_id）——**遺留**：convert 後補開票目前留待人工（後台 from-quote），
  自動補開掛 1.2.2 一併處理。
