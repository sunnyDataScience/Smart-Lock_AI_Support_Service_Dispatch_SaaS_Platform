--- 
id: CR-0173
title: technicians.line_user_id 欄位級加密（重審 HD-4=a）
status: draft
type: change-impact-analysis
date: 2026-07-20
related-findings: R6（codegraph LINE 推播稽核）
source-report: .claude/context/decisions/codegraph-tech-line-push-trace-2026-07-20.md
---

# CR-0173 technicians.line_user_id 欄位級加密（重審 HD-4=a）

> ⚠️ 本 CIA 是 **gate**：§8「Human Decisions Required」未獲業主裁決前，**不得**進入實作。本 CR 的核心動作是「重審一項既有 accepted decision（CR-0169 HD-4=a）」，依 `.claude/rules/change-governance.md`，推翻已裁決設計必須先產 CIA 等業主裁決。

## 1. 背景與動機（WHY）

### 稽核 finding（R6，confirmed）
2026-07-20 codegraph LINE 推播全鏈稽核（source-report §4 風險登記表 R6）確認：

- **`technicians.line_user_id` 明文落庫**。寫入端 `bind_by_code` 直接 `UPDATE technicians SET line_user_id = %s`（`api/services/technician_line_service.py:139`；另有換綁去重的等值比對 `WHERE line_user_id = %s` @ `:128-129`）。
- 唯一的保護是**回傳層遮蔽**：`get_binding` 只回尾碼 `f"…{lid[-6:]}"`（`api/services/technician_line_service.py:164`），DB 內仍是完整明文。
- Schema 佐證：`SQL/tech_authority/Schema_line_notify.sql:8` `line_user_id VARCHAR(64)`，`:10` COMMENT 明載「**明文存、UI 遮蔽**」。
- 此為 **CR-0169 業主已裁決設計 HD-4=a**（`technician_line_service.py:3-4`「HD-4=a（line_user_id 明文,UI 遮蔽）」，2026-07-17 裁決）。

### 現況痛點
LINE `userId`（`U` 開頭 33 碼）屬**個資（PII）邊界**——它是可定位、可推播到特定自然人的識別碼。目前一旦 **DB 被 dump、備份外流、或含 SQL 片段的日誌外洩**，即直接暴露所有已綁定技師的 LINE userId，可被第三方用平台 channel token（若一併外洩）向技師推播、或做跨資料集關聯。at-rest 僅靠 Cloud SQL 磁碟層透明加密（CMEK）保護，**擋不住合法連線的 dump 與應用層日誌**。

### 不做的後果
- PII 以明文長期沉澱在技師權威庫（lock_tech）`technicians` 表，攻擊面隨綁定技師數線性增長。
- 若後續有合規稽核（PDPA / GDPR 類「最小化 + 加密 at-rest」要求）觸發，需回頭補做且要對存量列回填加密，成本更高。
- **注意**：客戶側 `saas.line_binding`（`api/services/line_binding_service.py`）同樣存放 LINE userId，同屬 PII；本 finding 只針對技師側，但威脅模型一致（見 §8 HD-F 範圍問題）。

## 2. 變更範圍（WHAT）

**建議方案（源自 R6 defer_reason）**：對 `technicians.line_user_id` 做**欄位級可逆加密**。關鍵約束是 **line_user_id 是 LINE push 的目標位址**——`_push` payload `{"to": line_user_id}`（`:194`）、`notify_assignment`（`:255,263`）、`notify_pool_new`（`:270,283`）都直接 SELECT 出來當 push `to`，故**不能用雜湊（不可逆）**，只能可逆加密。

要改的面向：
1. **落庫加密**：寫入端（`bind_by_code:139`）加密後存；讀取端集中到**單一 decrypt helper**，所有 push 呼叫端經它還原明文。
2. **Schema**：`line_user_id` 欄位型別/寬度調整（密文 base64 長度 > 64，`VARCHAR(64)` 不夠）+ 一次性 **migration 回填**存量明文列並輪換為密文。
3. **可搜尋性難題**：換綁去重的等值查詢 `WHERE line_user_id = %s`（`:128-129`）與 `notify_pool_new` 的 `WHERE line_user_id IS NOT NULL`（`:270-271`）——隨機 IV 的 AES-GCM 密文非確定性，等值比對會失效，需決定確定性加密或 blind index（見 §8 HD-C）。
4. **金鑰管理**：引入 crypto 金鑰 + 輪換機制（pgcrypto 或應用層 AES-GCM + KMS）。

> 本 CR **僅產出 CIA**；方案細節（pgcrypto vs app-AES-GCM、可搜尋性策略、金鑰保管、是否含客戶側）皆為 §8 待裁決項，裁決後才依 §9 實作。

## 3. CIA 觸發面向

| 面向 | 命中 | 為何 |
|---|---|---|
| User / Business flow | ❌（間接） | 技師綁定/派工推播 UX 不變（成功仍收得到推播）；但實作漏一處 decrypt 會讓推播全掛，屬品質風險非流程變更 |
| API contract | ⚠️ 輕微 | `GET /technicians/me/line-binding` 回傳的 `line_user_id_masked` 語義不變（仍尾 6 碼），但產生方式改為「decrypt 後取尾碼」；request/response schema **不變**（見 §4） |
| **Domain model** | ✅ | `line_user_id` 從「明文識別碼」變為「加密識別碼 + 解密邊界」，改變 entity 的儲存不變式（invariant：庫內不可為明文）與生命週期（寫入即加密、讀取即解密） |
| **DB schema** | ✅ | 欄位型別/寬度變更 + **存量列 migration 回填加密**；可能新增 blind index 欄位；可能需啟用 pgcrypto extension |
| **External integration** | ✅ | LINE push `to` 位址的還原正確性攸關推播是否送達；若採 KMS 則新增對 GCP KMS 的整合依賴 |
| Test plan | ✅ | 需新增 crypto round-trip、migration 回填、換綁等值查、推播 decrypt 全鏈測試 |
| **Architecture boundary** | ✅ | 引入 crypto/金鑰管理層屬 architecture change（對照 CLAUDE.md「新增工具/邊界屬 architecture change」原則） |

命中 **≥4 個硬觸發面向**，CIA gate 成立。

## 4. API contract 影響

- **無新增/刪除 endpoint**。
- `GET /technicians/me/line-binding`（`get_binding`）：response schema **不變**（`bound` / `line_user_id_masked` / `notify_pool_new` / `platform_line_configured`）。唯一變化是 `line_user_id_masked` 的**產生方式**——目前 `lid[-6:]` 直接對明文取尾碼（`:164`），加密後需先 decrypt 再取尾 6 碼。對前端**無破壞性**。
- 內部端點 `POST /api/v1/internal/technicians/notify-assign` / `notify-pool`：payload/簽章**不變**（仍傳 `technician_id` + 工單摘要，不含 line_user_id）。
- 綁定 webhook `POST /technicians/line-webhook`：contract 不變。

> 結論：對外 API contract **實質無破壞**，屬內部實作變更。（HD-E 若決定取消 masked 尾碼顯示，則 response 語義才會變——見 §8。）

## 5. Domain model / DB schema 影響

**Entity**：`technicians`（技師權威庫 lock_tech，經 `require_tech_conn` / `tech_db_enabled` 連線；**非** saas 庫——見 §6 連線注意）。

**欄位變更**：
- `line_user_id VARCHAR(64)` → 需容納密文。AES-GCM(96b IV + 128b tag + 33B 明文) base64 約 ~90 chars，`VARCHAR(64)` **不足**；改 `TEXT` 或 `BYTEA`（依 §8 HD-B 方案而定）。
- 可能**新增 blind index 欄位**（如 `line_user_id_bidx`，存 `HMAC(key, line_user_id)`）以支援等值查（§8 HD-C）。

**受影響讀寫點（全部需經 decrypt helper，漏一處即推播送密文致全掛）**：
| 點 | file:line | 動作 |
|---|---|---|
| 寫入（綁定） | `technician_line_service.py:139` | 改為加密後寫 |
| 換綁去重等值查 | `technician_line_service.py:128-129` | `WHERE line_user_id = %s` 等值比對，密文非確定性會失效 → 需 blind index 或確定性加密 |
| 讀取遮蔽 | `technician_line_service.py:164` | decrypt 後取尾 6 碼 |
| 解綁 | `technician_line_service.py:173` | SET NULL，不受影響 |
| 派單推播 | `technician_line_service.py:255,263` | SELECT 後 decrypt 再當 push `to` |
| 池單廣播 | `technician_line_service.py:270-271,283` | SELECT + `WHERE line_user_id IS NOT NULL`（NULL 判斷不受影響）+ decrypt |
| push 目標 | `technician_line_service.py:194` | `{"to": <decrypted>}` |

**Migration（回填）**：
- 一次性把存量明文列讀出 → 加密 → 寫回；同時建立 blind index 欄位值（若採此方案）。
- 需在 lock_tech 連線上執行（**非** saas）；若採 pgcrypto 需先 `CREATE EXTENSION pgcrypto`（**Cloud SQL 是否允許/已啟用＝[待確認]**）。
- 回填期間並發寫入（新綁定）需一致（建議短暫維護窗或雙寫過渡）。
- Schema SQL 落點沿用 `SQL/tech_authority/Schema_line_notify.sql`（冪等可重跑慣例）+ 新增 `SQL/migrations/NNN-line-user-id-encrypt.sql` 回填腳本。

## 6. External integration 影響

- **LINE Messaging API**：push `to` 必須是**明文** userId。decrypt 正確性 = 推播送達的必要條件；任一讀取點漏 decrypt → 密文送進 `api.line.me` → 該推播 400/靜默失敗（技師鏈 fail-soft、無 outbox 補償，遺失不可見——參 source-report R10）。
- **金鑰管理整合**：若採應用層 AES-GCM，需新增金鑰來源（GCP KMS 或 Secret Manager env——MEMORY 記載 secrets 現放 GCP Secret Manager；**是否用 KMS＝[待確認]**）。
- **跨庫/跨 service 連線注意**：欄位在**技師權威庫（lock_tech）**，與 saas 庫分屬不同連線（`require_tech_conn`）。金鑰須在技師 API deployment 可取得；雲端可能 品牌api / tech api 兩 deployment（source-report §2 接縫），需確認解密發生的 service 具備金鑰。
- **pgcrypto 路線**：金鑰若以 SQL 參數傳入，須避免落入 query log（pgcrypto 的已知風險）。

## 7. 測試計畫影響

新增 / 調整測試（現有相關測試：`agent/tests/test_line_gateway.py`；API 側 pytest 需新增）：
1. **crypto round-trip 單元測試**：encrypt→decrypt 還原 = 原 userId；不同 IV 同明文密文不同（若隨機 IV）。
2. **綁定→推播全鏈**：`bind_by_code` 寫入後，`notify_assignment` / `notify_pool_new` decrypt 出的 `to` == 原 userId。
3. **換綁等值查**：同一 line_user_id 換綁到另一技師時，去重 `WHERE line_user_id = %s`（或 blind index）仍能命中舊列並解除。
4. **masked 尾碼**：`get_binding` 回傳 `…` + 正確尾 6 碼（decrypt 後）。
5. **migration 回填**：存量明文列回填後可正確 decrypt；回填冪等（重跑不雙重加密）。
6. **金鑰輪換**：舊金鑰密文在輪換後仍可讀（多金鑰版本）或重加密後可讀。
7. **負向**：漏 decrypt 的呼叫端應被測試捕捉（可加 lint/型別邊界：DB 讀出的 line_user_id 型別標注為「密文」，經 helper 才轉明文）。

> ⚠️ 執行注意：pytest 單庫 fallback 會直打 5433 UAT 庫（MEMORY 記載），UAT 期間勿對 5433 跑全套；crypto 測試建議隔離庫或 mock 連線。

## 8. 🛑 Human Decisions Required（待業主裁決）

> 以下每條實作前**必須有答案**。這是 gate。

**HD-A — 是否推翻 CR-0169 HD-4=a（明文儲存）？**
- 選項 (a) 維持明文 + UI 遮蔽現狀 → **關閉本 CR**（R6 標記為 accepted risk，補文件說明威脅模型接受度）。
- 選項 (b) 改欄位級可逆加密（本 CR 主線）。
- 選項 (c) 折衷：僅倚賴 Cloud SQL 磁碟層 CMEK（現況已有）+ 加強日誌遮蔽，不動應用層。
- **建議 (b)**，但前提是先回答 HD-G（是否有實際合規/威脅驅動）——若無明確驅動，crypto 複雜度成本可能高於收益，(c) 為務實折衷。

**HD-B — 加密方案：pgcrypto vs 應用層 AES-GCM + KMS？**
- 選項 (1) **pgcrypto**（`pgp_sym_encrypt`）：DB 內加解密，改動集中在 SQL。缺點：金鑰以 SQL 參數傳遞有落 query log 風險；Cloud SQL 需允許 extension（[待確認]）。
- 選項 (2) **應用層 AES-GCM + GCP KMS**：金鑰不入 DB，符合最小信任；改動集中在 Python decrypt helper。缺點：新增 KMS 整合與 latency。
- **建議 (2)**（金鑰與資料分離、可攜、對齊既有 GCP Secret Manager/KMS 生態），但需 HD-D 確認金鑰保管。

**HD-C — 可搜尋性：換綁等值查怎麼辦？**（`:128-129` `WHERE line_user_id = %s`）
- 選項 (1) **Blind index**：新增 `line_user_id_bidx = HMAC(key, userId)` 欄位做等值查，密文另存（推薦，語義安全保留）。
- 選項 (2) **確定性加密**（AES-SIV / 固定 IV）：可直接等值查但弱化語義安全（相同明文密文相同）。
- 選項 (3) 改查詢策略（全表 decrypt 比對）——不可行，效能與安全皆差。
- **建議 (1)**。

**HD-D — 金鑰保管與輪換策略？**
- 金鑰放哪：GCP KMS / Secret Manager env（[待確認] 現行 secrets 慣例是否延用）。
- 輪換週期與輪換時存量列重加密策略（多金鑰版本共存 vs 一次性重加密）。
- **建議**：KMS 管理主金鑰、支援 key version，密文前綴標記版本以支援漸進輪換。

**HD-E — 遮蔽尾碼 UX 是否保留？**（`get_binding:164`）
- 選項 (a) 保留（decrypt 後取尾 6 碼，UX 不變，response schema 不變）。
- 選項 (b) 加密後索性完全不顯示尾碼（只回 `bound` 布林）。
- **建議 (a)**（維持現有 UX，改動最小）。

**HD-F — 範圍是否含客戶側 `saas.line_binding`？**
- 技師側 `technicians.line_user_id` 與客戶側 `saas.line_binding`（`line_binding_service.py`）同存 LINE userId、威脅模型一致。
- 選項 (a) 本 CR 只做技師側（範圍小、快落地，但 PII「只加密一半」）。
- 選項 (b) 一併納入客戶側（範圍大、一致，但跨兩 schema/兩 service）。
- **建議**：本 CR 先做技師側落地驗證方案，客戶側開 follow-up CR 沿用同 helper——但請業主確認是否接受過渡期客戶側仍明文。

**HD-G — 觸發動機/合規來源？**（決定優先級）
- 是否有具體合規稽核要求（PDPA / GDPR / 客戶合約）觸發本 CR，或屬主動加固？[待確認]
- 影響 HD-A 的取捨與本 CR 排期。

## 9. Suggested Implementation Order

> 每步可獨立 review / revert；未過 §8 gate 不啟動。

1. **S0（前置）**：業主裁決 §8（尤其 HD-A/B/C/G）→ 確認 pgcrypto 可用性（HD-B(1) 時）或 KMS 金鑰路徑（HD-B(2) 時）。**gate**。
2. **S1 — decrypt/encrypt helper**：新增單一 crypto helper（含 blind index 計算，若 HD-C(1)），純函式 + round-trip 單元測試（§7-1）。**不接 DB，可獨立 review**。
3. **S2 — schema 變更**：`line_user_id` 型別/寬度調整 + blind index 欄位（若採），寫 `SQL/tech_authority/Schema_line_notify.sql`（冪等）+ 對應 migration 骨架。**不含回填**。
4. **S3 — 讀寫點集中改造**：`bind_by_code` 寫入加密（`:139`）、換綁等值查改 blind index（`:128-129`）、`get_binding` decrypt+mask（`:164`）、`notify_assignment`/`notify_pool_new`/`_push` 讀取 decrypt（`:255-263`/`:270-283`/`:194`）。全鏈測試（§7-2/3/4）。
5. **S4 — migration 回填**：`SQL/migrations/NNN-line-user-id-encrypt.sql` 一次性回填存量明文列 + blind index；冪等、可回退（§7-5）。以旗標/維護窗控並發。
6. **S5 — 金鑰輪換機制**：多金鑰版本支援 + 輪換 runbook（§7-6）。
7. **S6 — 收尾**：更新 `technician_line_service.py` 檔頭 HD-4 註解為「HD-4=b（加密儲存）」、`Schema_line_notify.sql` COMMENT；同步 CHANGELOG、新開 ADR（推翻 HD-4=a 屬架構決策，append-only 標舊 superseded）；更新完成度文件。

## 10. 風險與回退

**破壞性 / 主要風險**：
- **漏 decrypt 一處 → 推播全掛**（密文送進 LINE API）。緩解：讀取點**強制**經單一 helper，型別邊界標注「DB 讀出為密文」，加負向測試（§7-7）。技師鏈無 outbox 補償（source-report R10），遺失不可見，故 S3 全鏈測試為硬門檻。
- **migration 回填中斷/重跑雙重加密**。緩解：回填腳本冪等（以密文前綴版本標記判斷是否已加密）、可回退、短維護窗或雙寫過渡。
- **金鑰遺失 = 資料不可讀**（可逆加密的固有風險）。緩解：KMS 託管 + 金鑰備援；輪換保留舊版本直到重加密完成。
- **等值查失效**（隨機 IV）。緩解：HD-C blind index，S3 換綁測試覆蓋。
- **pgcrypto 金鑰落 query log**（若 HD-B(1)）。緩解：優先 HD-B(2) 應用層方案，或 pgcrypto 走 session 變數不入 statement log。
- **跨庫/跨 service 金鑰可得性**（lock_tech vs saas、雙 deployment）。緩解：確認 decrypt 發生的 service 具金鑰（§6）。

**灰度 / 回退開關**：
- 建議 S3 加 **feature flag（如 `LINE_UID_ENCRYPT_ENABLED`）**：開啟前雙讀（先試 decrypt，失敗 fallback 當明文）以支援回填期間新舊列並存；回填完成再收斂。
- **回退**：flag 關閉 → 讀取路徑回明文分支；但**存量已加密列在 flag 關閉後不可讀**——故回退窗僅限「回填尚未大規模執行前」，S4 執行後即為單向。此不對稱性須在 S0 讓業主知悉並納入排期決策。
- `[待確認]`：是否要求「零停機」回填（影響是否需雙寫過渡層）。