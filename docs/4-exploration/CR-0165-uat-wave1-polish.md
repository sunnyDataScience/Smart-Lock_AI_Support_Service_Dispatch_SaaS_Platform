# CR-0165 — UAT wave1 打磨項收尾（六件合批）

- **日期**：2026-07-11
- **來源**：UAT 第一波自動驗收「已知待做／打磨」清單（`.claude/context/quality/uat-wave1-2026-07-11-findings.md`），業主 2026-07-11 選定本輪範圍。
- **分支**：`fix/uat-wave1-polish`
- **CIA 觸發面向**：API contract（F6a 錯誤碼、F12 冪等語意）、DB schema（F2 CHECK migration）、Domain data（F9 dispatch_logs 寫入語意）、Business flow（F6b 完整度閘）、Seed／營運資料（SEED-1）。
- **查證方法**：6 個並行 agent 讀碼＋live 庫唯讀實查（5433／5434），全數 confirmed。

---

## §1 查證事實（六件全屬實）

### F6a 轉工單缺地址回泛用錯誤
- raise 點在共用 service `api/services/work_order_service.py:444-450`：`VALIDATION_ERROR` + 英文訊息 "customer_address required: not found in user profile and not provided"，v1／v2 兩個 convert 端點都走到。
- 前端 brand-portal 把 `VALIDATION_ERROR` 映成泛用「輸入的資料有誤」——使用者無從得知缺地址。
- 既有先例：結案硬閘 `ADDRESS_REQUIRED_FOR_CLOSE`（`work_order_service.py:1139`，繁中訊息），四站 `apiError.ts:78` 皆有映射。
- 附帶發現：CR-0042 完整度閘門檻判斷為嚴格小於（`score < min_c`），5 欄只缺地址時 score=0.8 恰好不小於門檻 0.8 → 閘門放行、落到 service 層泛用錯誤——缺地址永遠繞過結構化 `INCOMPLETE_PROBLEM_CARD`。

### F6b 完整度閘不 fallback user.address
- `assert_completeness`（`api/services/problem_card_service.py:486-550`）的 customer_address 只來自 body 參數，SQL 未 join users。
- 下游建單 `create_from_problem_card` 早有 fallback（`work_order_service.py:444` `customer_address or user_address`）→ 閘門會 422 擋掉一筆實際建單能成功的轉換，兩層不一致。
- 誤擋發生條件：門檻調 >0.8、或同時缺其他欄位時。

### F2 problem_cards.emergency_class 無 DB CHECK
- 欄位由 migration 091 引入，僅 `VARCHAR(30)` 無約束；live 5433 實查 `pg_constraint` CHECK = 0 筆，存量僅 1 列且為 NULL（無違規）。
- 合法四類 `_VALID_EMERGENCY_CLASSES = {locked_out, trapped_inside, safety_risk, angry_high_risk}`（`problem_card_service.py:373`），API 寫入點有應用層驗證；缺口＝繞過 API 的直接 DB 寫入無防線，一旦入庫即被 `IS NOT NULL` 判定當急件**跳過報價 gate**。defense-in-depth 缺 DB 層。
- migrations 目前最大編號 100 → 新檔取 101。

### F9 手動派工 :assign 不寫 dispatch_logs
- `assign_order`（`work_order_service.py:1557-1693`）全程無 `INSERT INTO dispatch_logs`；`reassign_order` 有寫（`:1789-1795`，action='reassign'）且另補 `work_order_events`。
- 全 repo 只有 reassign 一處寫 dispatch_logs；**四條手動派工入口**（v2 :assign、legacy /work-orders/{id}/assign、legacy /dispatch/assign、dispatch_v2 assign）全部委派 `assign_order` → 改一個函式全覆蓋。
- action 值採 'assign'（API enum＋seeds 慣例；Schema.sql:810 註解的 'manual_assign' 為過期註解，寫了也會被 `_coerce_action` 折成 assign）。
- 更廣斷鏈（accept／reject／timeout／cancel 也無寫入點）超出本輪，另開 CR 追蹤。

### SEED-1 seed 兩庫技師不一致
- 品牌庫 seed 種 4 名展示技師（tech-chen/huang/wu/zhang@example.com，disabled 佔位 hash）＋test@lock-ai.com；權威庫（5434 lock_tech）**無任何 seed 檔**，唯一 bootstrap 是 `split-tech-db.sh` 初次全量拷貝＋「非空即跳過」冪等 → 品牌庫重灌 seed 後不再傳播，漂移必然再現。
- live 實查（2026-07-11）：品牌 6 名技師 vs 權威 2 名；差集＝4 名投影-only 展示技師。子表同漂移（technician_skill 8 vs 2、brand_authorization 20 vs 5）。
- 危險機制：`tech_mirror.mirror_rows:99-102` 對權威庫查無的 id 會 DELETE 品牌投影列＋`technicians` FK ON DELETE CASCADE → 對投影-only 技師觸發鏡射即連鎖刪光品牌側身分資料（UAT F9「登入即刪技師資料」現象根源）。
- ⚠️ 不可用 `split-tech-db.sh --force` 對齊（TRUNCATE 權威庫再以品牌側覆蓋，會蓋掉真實註冊帳號權威憑證）。
- test@lock-ai.com 品牌雙 row（admin＋technician）／權威單 row 為刻意設計，不動。

### F12 註冊冪等 fail-open
- guard 有掛、表存在；真正缺口＝`idempotency_guard` 缺 `X-Tenant-ID` header 時**靜默 return None**（`core/idempotency.py:125-127`）——不 lookup、不落庫、不回放。
- register 是公開無登入端點，curl／Postman 只帶 Idempotency-Key 即重現；瀏覽器動線因前端恆注入 fallback tenant 不受影響（live 查到 1 筆落庫佐證）。
- 不對稱：缺 Idempotency-Key 硬 400，缺 X-Tenant-ID 靜默略過。
- `/vendors/register`（auth.py:347）同樣有此洞。

---

## §2 影響面

| 項 | 面向 | 影響 |
|---|---|---|
| F6a | API contract | convert 缺地址錯誤碼 `VALIDATION_ERROR` → 專用碼（repo 內僅 1 個測試斷言此路徑舊碼） |
| F6b | Business flow | 完整度閘放行條件放寬（只解擋不新增擋），與建單層對齊 |
| F2 | DB schema | 品牌庫 problem_cards 加 CHECK（NOT VALID＋VALIDATE 分離，存量預檢） |
| F9 | Domain data | 手動派工開始寫 dispatch_logs；真打 assign 的既有測試 cleanup 需確認 FK 順序 |
| SEED-1 | Seed／營運 | live 5434 一次性補齊＋seed 制度化；不動品牌 seed |
| F12 | API contract | 公開註冊端點缺 X-Tenant-ID 時冪等從 no-op 變公共命名空間 dedup |

## §4 Source-of-Truth 衝突

本輪無正典互相矛盾；F9 的 Schema.sql:810 action 註解（'manual_assign' 等）與 API enum／seeds 慣例（'assign' 等 6 值）不一致，屬過期註解 → 順手標注修正，不改 enum。

---

## §8 Human Decisions Required

> 業主裁決記錄（2026-07-11）：見文末「裁決」。

1. **F6a 錯誤碼**：A=新專用碼 `ADDRESS_REQUIRED_FOR_CONVERT`（建議，語意精準）／B=沿用 `ADDRESS_REQUIRED_FOR_CLOSE`（訊息「才能結案」在 convert 情境語意錯亂，不建議）。
2. **F6a 附帶**：是否順修完整度閘「score==門檻放行」邊界，讓缺地址能收到結構化 `INCOMPLETE_PROBLEM_CARD`？（閘門行為變更，影響 override 流程；不修則缺地址由 service 層專用碼擋，效果已達）
3. **F6b fallback 鏈**：A=只 fallback users.address，與建單完全鏡射（建議）／B=閘門與建單同時納入 pc.location（改動面大、pc.location 語意未必可派工）。
4. **F2 prod 預檢**：套 101 前預檢若查出違規存量（本機為零），remap 四類之一或清 NULL（降回非急件）？——可留待 prod 套用時再裁。
5. **F9 細節**：(a) notes 存整段 `[ASSIGNED:{reason_code}] reason_text`（建議）或只存 reason_text；(b) 是否同補 `work_order_events` event_type='assign' 對齊 reassign timeline（建議補）。
6. **SEED-1**：(1) 方向 A=往權威庫補齊 4 名展示技師（建議）／B=品牌庫刪除（動 5 個 seed 檔 FK＋2 測試＋dashboard KPI，不建議）；(2) 若 A，密碼用 disabled 佔位 hash（建議，維持展示技師慣例）或 changeme123（擴大可登入面）；(3) 制度化：只一次性補 live，或同時新增權威庫 seed 步驟進 bootstrap 工作流（建議做，否則重灌必再漂移）。
7. **F12**：(1) B=僅兩個公開註冊端點 opt-in fallback 公共 tenant 命名空間（建議）／A=guard 全域 fallback（匿名 client 弱 key 互相回放、輕微資訊外洩面，不建議）；(2) 缺 X-Tenant-ID 比照缺 key 硬 400，或 fallback（公開端點 client 無從得知 tenant，傾向 fallback）。

### 裁決（2026-07-11 業主：「照建議」）

1. F6a＝**A** 新專用碼 `ADDRESS_REQUIRED_FOR_CONVERT`
2. F6a 附帶＝**不修** score==門檻邊界（最小變更）
3. F6b＝**A** 只 fallback users.address
4. F2＝**留待 prod 套用時再裁**（本機存量為零）
5. F9＝(a) notes 存整段 `[ASSIGNED:code] reason`；(b) **同補** work_order_events
6. SEED-1＝(1) **A** 往權威庫補齊；(2) **disabled 佔位 hash**；(3) **一次性補 live＋seed 制度化都做**
7. F12＝(1) **B** 僅兩個公開註冊端點 opt-in fallback 公共命名空間；(2) 缺 X-Tenant-ID **fallback**（不硬 400）

## §9 建議實作順序

1. **S1** F6a＋F6b（同域連動）：service 錯誤碼＋閘門 fallback＋四站 apiError 映射＋測試修正／新增
2. **S2** F9：`assign_order` 補 dispatch_logs（＋work_order_events 視裁決）＋service 層測試＋既有測試 FK cleanup 檢查
3. **S3** F2：migration 101（idempotent CHECK，NOT VALID＋VALIDATE）＋scratch 驗證＋live 5433 預檢後套用＋MIGRATION_REGISTRY 補列
4. **S4** F12：idempotency guard 工廠化＋技師／廠商兩註冊端點接上＋UUID 驗證＋測試三態
5. **S5** SEED-1：live 5434 一次性補齊（冪等 INSERT）＋權威庫 seed 制度化＋--verify 納 UAT smoke
6. **S6** 治理收尾：OpenAPI 錯誤碼 enum 補列、CHANGELOG、completion-status、UAT 驗收清單標注、commit

### 進度

- ✅ S1 done（branch `fix/uat-wave1-polish`）：F6a 專用碼 `ADDRESS_REQUIRED_FOR_CONVERT`（繁中訊息，v1/v2 共用 service 一次覆蓋）＋四站 apiError 映射＋F6b 閘門 LEFT JOIN users fallback（與建單層鏡射）。測試：convert 7＋completeness 新 2 全綠。
- ✅ S2 done：`assign_order` 補 dispatch_logs（action='assign'，notes=整段 note）＋work_order_events（v2 router 接 actor_user_id）；四條手動派工入口一次覆蓋。既有 3 個真打測試 cleanup 補 dispatch_logs 反序刪。Schema.sql dispatch_logs action 過期註解標注修正。
- ✅ S3 done：migration 101（emergency_class CHECK，NOT VALID＋VALIDATE 分離）＋**102**（work_order_events CHECK 補 'assign'；**查證途中發現 mark_supply_arrived 寫入值 'supply_arrived' 未列於 059 CHECK → 補料標記端點自建置必 500，一併補列**）。scratch 5473 全新 bootstrap＋冪等重套＋非法值擋/合法值放行驗證；live 5433 預檢 0 違規後套用＋schema_migrations 登記。
- ✅ S4 done：idempotency guard 工廠化（`make_idempotency_guard`）＋技師/廠商兩公開註冊端點 opt-in fallback 公共命名空間（zero-UUID）＋非 UUID header 500→400。新測試 4；**live 四情境實測**（首次 201/回放同 id token=null/異 body 409/缺 key 400，落庫 tenant=zero-UUID），實測資料已清。
- ✅ S5 done：權威庫 seed 檔 `SQL/seeds/tech_authority/technicians.sql`（5 名 seed 技師，disabled 佔位 hash，ON CONFLICT DO NOTHING）＋split-tech-db.sh 兩路徑自動套 seed（杜絕重灌漂移）；live 5434 補 4 users/4 technicians/8 skills/20 auths＋品牌庫回填 tech-chen cascade 事故遺失的 2 skills/5 auths → `--verify` **無漂移**（6=6/10=10/25=25）。
- ✅ S6 done：openapi.yaml 錯誤碼 enum 補 CONVERT 碼、MIGRATION_REGISTRY 101/102、CHANGELOG、completion-status、UAT 清單標注。
- 驗證總計：api 全套 **1811 passed / 2 skipped**（scratch 5473）＋四站 tsc 0＋兩 api 容器重建 health 200。
