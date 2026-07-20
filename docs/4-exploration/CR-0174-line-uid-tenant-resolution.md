---
id: CR-0174
title: 多租戶 LINE line_uid → tenant 反解(消除硬編 default 誤配)
status: draft
type: change-impact-analysis
date: 2026-07-20
related-findings: R29(codegraph LINE 推播稽核)
source-report: .claude/context/decisions/codegraph-tech-line-push-trace-2026-07-20.md
---

# CR-0174 多租戶 LINE line_uid → tenant 反解(消除硬編 default 誤配)

## 1. 背景與動機(WHY)

CR-0028/CR-0017 上線後,消費者/品牌側 webhook(`POST /line/webhook`,`api/routers/line_webhook.py:200`)在處理 rich menu「查進度 / 綁定」postback 時,**沒有可信的 tenant 來源**,只能退回一個硬編 default 租戶做 binding 查詢。稽核 finding **R29** 判定為 confirmed(嚴重度低但確實存在的多租戶隔離弱點)。

現況痛點(引具體 file:line):

- **硬編 default tenant**:`api/routers/line_webhook.py:92-94` 定義 `_DEFAULT_TENANT_FOR_LINE_LOOKUP = os.getenv("LINE_DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001")`。這是「CR-0013 Stage 2」臨時的 multi-tenant lookup hint 缺位補丁。
- **查進度只認 default 租戶**:`_handle_get_progress`(`line_webhook.py:107-109`)無條件以 `tenant_id=_DEFAULT_TENANT_FOR_LINE_LOOKUP` 呼 `resolve_user_by_line_uid`。其 step-1 `get_active_binding`(`line_binding_service.py:181-203`)是 **tenant-scoped**(`WHERE tenant_id = %s AND line_user_id = %s AND unbound_at IS NULL`)——**非 default 租戶的綁定者,step-1 一律查不到**(此段實際是 fail-safe,不會誤配,只是查不到)。
- **真正的跨租戶洩漏在 step-2 fallback**:`resolve_user_by_line_uid`(`line_binding_service.py:226-231`)step-2 執行 `SELECT id FROM users WHERE line_user_id = %s LIMIT 1`——**完全無 tenant 條件**,會跨租戶命中任一持有該 `line_user_id` 的 user。目前 webhook 端 R29 分支只回推一般追蹤連結(`{WEB_BASE_URL}/track/orders`,無 PII 落在推播內容),故實際嚴重度低;但這條全域 fallback 是設計層的隔離破口,一旦日後在此路徑回推工單細節即成 PII 跨租戶洩漏。
- **資料模型允許一 uid 多租戶綁定**:migration `018-line-bindings.sql:39-41` 的唯一索引是 `(tenant_id, line_user_id) WHERE unbound_at IS NULL`——**同一 line_uid 可在多個租戶各有一筆 active binding**。當前 default-only 查詢在此情境下語意未定義。

不做的後果:webhook 查進度/綁定入口的租戶解析永遠依賴一個寫死的 UUID,只有「default 租戶」的客戶能正確查進度;多租戶正式營運後,非 default 租戶客戶查進度會落到全域 users fallback,產生不可預期的跨租戶命中,且無法安全擴充回推內容。

## 2. 變更範圍(WHAT)

核心:**把「硬編 default tenant」改為「由 line_uid 反解出明確單一 tenant」**,並將解析語意收斂為 fail-closed。

建議方案(待 §8 裁決後定案):

1. **新增反解查詢路徑**:於 `line_binding_service` 加一個以 `line_user_id` 為主鍵、**不預設 tenant** 的解析函式,例:
   `SELECT tenant_id, user_id FROM saas.line_binding WHERE line_user_id = %s AND unbound_at IS NULL`,依 §8(b) 裁決的歧義規則決定 0/1/多筆時的行為。
2. **webhook 首選由 payload 取 tenant**:若 LINE 官方帳號為 per-tenant(§8(a)),優先從 webhook payload 的 `destination`(bot userId)或 channel 對映出 tenant,取代硬編 default;反解僅作為次選。
3. **收斂 fail-closed**:`_handle_get_progress` / `_handle_binding_start` 找不到「明確單一租戶綁定」即回「尚未綁定」,**不再落回全域 `users` fallback**(依 §8(c) 裁決)。
4. **`resolve_user_by_line_uid` 契約調整**:對齊反解結果,step-2 全域 users fallback 加 tenant 條件或移除(§8(c))。

本輪(R29 defer 原因)**不動 code**:上述①觸發 Domain model + Architecture boundary,②③需業主裁決產品/資料模型語意,不可腦補。

## 3. CIA 觸發面向

| 面向 | 命中 | 說明 |
|---|---|---|
| **Domain model** | ✅ | 新增「line_uid → tenant」跨租戶解析概念,翻轉既有「tenant 為已知輸入」的存取假設;`saas.line_binding` 的「一 uid 可多租戶 active」需明確定義歧義語意。 |
| **Architecture boundary** | ✅ | 新增不帶 tenant 的跨租戶查詢路徑,改變多租戶隔離邊界;webhook 是否從 payload 取 tenant 牽動 channel↔tenant 對映這一新邊界。 |
| **API contract** | ✅ | `resolve_user_by_line_uid` 現行簽章強制帶 `tenant_id`(`line_binding_service.py:206-208`),反解會翻轉此契約(改回傳 tenant 或改為選填 tenant)。屬 service 內部契約,非對外 HTTP endpoint。 |
| **DB schema** | ⚠️ 可能 | migration `018`(🟡 pending-apply)本身不需改;但若歧義規則採「取最近綁定」需依賴 `updated_at`/`unbound_at` 排序穩定,可能需補索引。詳見 §5。 |
| **External integration** | ✅ | 涉及 LINE 官方帳號與 tenant 的對映(per-tenant channel 與否),屬 LINE 整合面決策。 |
| **Test plan** | ✅ | 需新增跨租戶反解、歧義、fail-closed 的測試類別。 |
| **User/Business flow** | ➖ | 使用者可見流程(查進度/綁定)行為不變,僅解析正確性提升;不新增主流程分支。 |

## 4. API contract 影響

**對外 HTTP endpoint:無變動。**`POST /line/webhook` 的 request/response、status code 不變(仍一律 200/202,LINE retry 由 service CAS 保冪等)。

**Service 內部契約(會變):**

- `line_binding_service.resolve_user_by_line_uid(*, tenant_id: str, line_user_id: str) -> str | None`(`line_binding_service.py:206`)
  - 現行:強制 `tenant_id`;step-1 tenant-scoped binding + step-2 全域 users fallback。
  - 提案:改為(方案 A)`tenant_id` 變選填 + 新增 `resolve_binding_by_line_uid(line_user_id) -> {tenant_id, user_id} | None`;或(方案 B)新增獨立反解函式、`resolve_user_by_line_uid` 維持原簽章不動,由 webhook 先反解 tenant 再呼原函式。**方案 B 破壞面最小**(原簽章不動,只加新函式),建議優先,實際採哪案待 §8 定。
  - 呼叫端盤點(已 grep 確認,production 僅一處):`api/routers/line_webhook.py:107` `_handle_get_progress`。測試呼叫端:`api/tests/test_cr_0013_line_binding.py:118,141`(monkeypatch 該函式)。**無其他 production caller**,簽章調整波及面可控。

## 5. Domain model / DB schema 影響

- **Entity**:`saas.line_binding`(migration `018-line-bindings.sql:13`)。欄位齊備(`tenant_id`,`user_id`,`line_user_id`,`bind_method`,`bound_at`,`unbound_at`,`updated_at`),**反解所需資料已存在,無需新欄位**。
- **既有索引**:
  - `line_binding_tenant_line_unique_active`(`018:39-41`)= `(tenant_id, line_user_id) WHERE unbound_at IS NULL`——**保證同 tenant 內唯一,但不跨 tenant 唯一**,故一 uid 多租戶 active 在 schema 層是允許的(這正是 §8(b) 歧義的根源)。
  - 目前**沒有** `line_user_id` 單欄索引;反解查詢 `WHERE line_user_id = %s AND unbound_at IS NULL` 會全表掃描。**若採反解,建議新增 partial index** `ON saas.line_binding(line_user_id) WHERE unbound_at IS NULL`(需新 migration)。
- **migration 狀態雷**:`018` 在 `MIGRATION_REGISTRY.md:40` 標 **🟡 pending-apply**——**production 可能尚未套用此表**。反解實作前須先確認 018 已在目標環境 applied(否則 `get_active_binding` 早已 fail;此為既有前置債,非本 CR 新引入)。
- **回填說明**:step-2 全域 `users.line_user_id` 是 legacy auto 綁定路徑(FR-0044,`018` 註解 line 55)。若 §8(c) 決定移除/加 tenant 條件於 users fallback,則**先前僅存在 `users.line_user_id`、未在 `saas.line_binding` 建 row 的舊綁定者會查不到**,需資料盤點:統計有多少 `users.line_user_id` 不存在對應 active `saas.line_binding`,決定是否需一次性回填(呼 `record_auto_binding` 補審計 row)。[待確認:此類 legacy row 數量]

## 6. External integration 影響

- **LINE 官方帳號 ↔ tenant 對映**:本 CR 的最佳解取決於「LINE 官方帳號是否 per-tenant」。若 per-tenant,webhook payload 的 `destination`(接收此 event 的 bot userId)即可反查 tenant,直接消除硬編 default 且無歧義——這是首選路徑。若為**單一共用官方帳號多租戶共用**,則 payload 無 tenant 資訊,只能靠 binding 反解 + §8(b) 歧義規則。[待確認:目前雲端是單一 `PLATFORM_LINE_CHANNEL_*` 共用,見 MEMORY「外部窗口」記 tech-portal/.env 憑證已到位——需確認品牌側 `LINE_CHANNEL_*` 是否 per-tenant]
- **跨 service**:本 CR 侷限品牌/消費者側 webhook(`line_webhook.py`)與 `line_binding_service`,**不觸及技師側**(`technician_line.py` 走 `technicians.line_user_id`,與 `saas.line_binding` 無 call edge)。
- **token**:無新增 token/憑證;若採 payload destination 反解,需確認 webhook 收到的 `destination` 欄位可用且穩定。

## 7. 測試計畫影響

新增/調整測試(檔案:`api/tests/test_line_webhook.py`、`api/tests/test_line_binding_service.py`、`api/tests/test_cr_0013_line_binding.py`):

1. **反解單一命中**:某 line_uid 僅在 tenant-A 有 active binding → 反解回 (tenant-A, user);查進度回正確連結。
2. **反解 fail-closed**:line_uid 無任何 active binding → 回「尚未綁定」,**且不觸發全域 users fallback**(驗證 SQL 未執行無 tenant 條件查詢)。
3. **跨租戶歧義**:同一 line_uid 在 tenant-A、tenant-B 皆 active → 依 §8(b) 裁決驗證(fail-closed 拒答 / 或取最近綁定並驗排序穩定)。
4. **legacy users fallback 邊界**:僅存在 `users.line_user_id`、無 `saas.line_binding` row 的舊綁定者 → 依 §8(c) 裁決驗證(查得到 / 或明確查不到)。
5. **payload destination 反解**(若採 §8(a) 路徑):webhook payload 帶 `destination` → 正確對映 tenant,不再讀 `LINE_DEFAULT_TENANT_ID`。
6. **回歸**:既有 `test_cr_0013_line_binding.py:105,129` 兩案(resolve 回 None / 回 user_id)需依新契約更新 monkeypatch 目標。

## 8. 🛑 Human Decisions Required(待業主裁決)

實作前必須有以下答案,這是 gate。

**HD-1:LINE 官方帳號是否 per-tenant?**
- 問題:品牌/消費者側 webhook 對應的 LINE 官方帳號(`LINE_CHANNEL_*`),是「每租戶一個」還是「全平台共用一個」?
- 選項:(a) per-tenant → webhook payload `destination` 可直接反查 tenant;(b) 共用單一帳號 → payload 無 tenant 資訊,須靠 binding 反解。
- 建議:若營運上可行,選 (a) 並改由 `destination` 取代硬編 default——**根治且無歧義**。[目前雲端實際配置待確認]

**HD-2:同一 line_uid 綁在多個租戶時,「查進度」該回哪個租戶?**
- 問題:schema 允許一 uid 多租戶 active(`018` 唯一索引僅 per-tenant)。反解命中多筆時如何裁?
- 選項:(a) **fail-closed 拒答**,回「請由對應品牌的連結查詢」(最安全,零誤配);(b) 取最近綁定(`ORDER BY bound_at DESC LIMIT 1`,需確保排序穩定);(c) 全部列出讓客戶選(需新 UI 互動)。
- 建議:MVP 選 (a) fail-closed;若產品要求單一入口體驗再議 (b)/(c)。

**HD-3:`resolve_user_by_line_uid` step-2 全域 `users` fallback 去留?**
- 問題:`line_binding_service.py:226-231` 的 `SELECT id FROM users WHERE line_user_id = %s LIMIT 1` 無 tenant 條件,是跨租戶命中破口,也是 legacy auto 綁定相容路徑。
- 選項:(a) **移除**,只信 `saas.line_binding`(最乾淨,但 legacy 未建 binding row 者查不到,需回填);(b) 保留但**加 tenant 條件**(需先有明確 tenant,回到 HD-1/HD-2);(c) 暫留現狀直到 legacy 回填完成再移除。
- 建議:先做 §5 的 legacy row 盤點與回填,再選 (a);過渡期可 (c)。

**HD-4:migration 018 是否已在 production applied?**
- 問題:`MIGRATION_REGISTRY.md` 標 🟡 pending-apply。反解實作依賴此表存在。
- 選項:(a) 已 applied → 直接實作;(b) 未 applied → 本 CR 須含套用 018 的前置步驟。
- 建議:實作第一步先驗證,未套先套。[待確認]

## 9. Suggested Implementation Order

每步可獨立 review / revert:

1. **S0 前置盤點(不動 code)**:確認 migration 018 於各環境 applied 狀態(HD-4);統計僅存 `users.line_user_id`、無對應 active `saas.line_binding` 的 legacy row 數量(供 HD-3 決策)。
2. **S1 反解函式(純新增,不改既有契約)**:在 `line_binding_service` 加 `resolve_binding_by_line_uid(line_user_id)`,實作 HD-2 裁決的歧義規則 + 對應測試;若需要,同 commit 加 `line_user_id` partial index migration。此步不接線,零行為變更。
3. **S2 webhook 接線 + fail-closed**:`_handle_get_progress`(及 `_handle_binding_start` 如適用)改用反解結果替代 `_DEFAULT_TENANT_FOR_LINE_LOOKUP`,找不到明確單一 tenant 即回「尚未綁定」;若 HD-1=(a),同步改由 payload `destination` 取 tenant。移除或以 flag 包住 `_DEFAULT_TENANT_FOR_LINE_LOOKUP`。
4. **S3 收斂 users fallback(依 HD-3)**:先完成 legacy 回填(如需),再移除/加 tenant 條件於 `resolve_user_by_line_uid` step-2;更新 `test_cr_0013_line_binding.py` 回歸。
5. **S4 清理**:確認無 caller 依賴 `LINE_DEFAULT_TENANT_ID`env 後刪除該常數;更新 CHANGELOG + CR-0174 §進度 + 相關 ADR(若 HD 決策構成架構決策則新開 ADR)。

## 10. 風險與回退

- **破壞性**:
  - S1 純新增,無破壞。
  - S2/S3 改變查進度解析語意:fail-closed 化後,**原本靠全域 users fallback 才查得到的非 default 租戶客戶,會從「誤查到別租戶」變成「回尚未綁定」**——語意更正確但對特定客戶是可見行為變化,需 release note 告知。
  - S3 移除 users fallback 若回填不完整,legacy 綁定者查不到進度(功能退化)——**故 S3 強制以 S0 盤點為前置**。
- **灰度**:S2/S3 建議以 feature flag(如 `LINE_RESOLVE_BY_UID_ENABLED`)包住,先在單一租戶灰度驗證反解正確,再全開。
- **回退開關**:保留 `_DEFAULT_TENANT_FOR_LINE_LOOKUP` 常數與 `LINE_DEFAULT_TENANT_ID` env 直到 S4;S2/S3 出問題時關 flag 即回退到 default-lookup 舊行為,無需 revert code。
- **排序穩定性風險(僅 HD-2=b 時)**:「取最近綁定」須以 `bound_at`(必要時加 `id` tiebreak)穩定排序,避免同時間多筆造成非決定性回傳。
- **既有前置債**:migration 018 pending-apply 屬 R29 之外的既有風險,本 CR 於 S0 順帶驗證但不擴大範圍。