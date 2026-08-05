---
id: CR-0207
title: 稽核鏈、法遵與個資保護 —— 7 支合規 TC 回查證後的缺口分流與裁決
status: draft
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [User/Business flow, API contract, Domain model, DB schema, External integration, Test plan, Architecture boundary]
related: [TC-NFR-AUD-01, TC-NFR-PRIV-01, TC-COMPLIANCE-01, TC-COMPLIANCE-02, TC-COMPLIANCE-03, TC-COMPLIANCE-05, TC-COMPLIANCE-08, FR-API-16, FR-REF-03, FR-REF-04, FR-REF-05, NFR-Aud-001, NFR-Aud-004, NFR-Aud-005, NFR-Aud-006, NFR-Aud-007, NFR-Priv-004, NFR-Priv-005, NFR-Priv-006, NFR-Priv-007, NFR-Priv-008, NFR-Priv-009, NFR-Priv-010, NFR-Comp-002, NFR-Comp-004, NFR-DQ-001, BR-PII-001a, BR-PII-001b, BR-SOP-002, BR-AI-003, CR-0109, CR-0115, CR-0164, CR-0166, CR-0176, CR-0183, CR-0184]
---

# CR-0207 — 稽核鏈、法遵與個資保護

> 本 CR 命中 CIA 全部 **7 個觸發面向**。這本身就是訊號：它不該當成一張 CR 一次做完。
> §6 打分 **10 分**（7–12 區間）＝「架構重審 + 模組拆分（多 CR + 跨 sprint）」。

---

## 1. 一句話

7 支合規 TC 回查證後，**兩件事比走查文件寫的更嚴重、且都不可逆**：①GDPR 的 T+30 硬刪 cron
因為缺一個必填參數，**從上線至今每一列都必然 TypeError，第二階段實質從未執行過**，而測試的
mock 照著壞的呼叫端寫所以 CI 永遠綠；②品牌 admin 可以列出並匯出**整個部署（含其他品牌）**的
稽核事件 —— 請業主裁決這兩條先怎麼止血，以及 legal-hold / consent 撤回 / PII log filter 等
6 項合約紅線缺口的取捨順序。

---

## 2. 需求追溯（先確認「原本有沒有這條要求」）

### 2.1 有明確正典條文的（要修的理由來自這裡）

| TC | 判定基準子項 | 需求 ID | 正典出處 | 位階 |
|---|---|---|---|---|
| TC-COMPLIANCE-01 | T+30 硬刪 cron 執行 + ledger append | FR-API-16 / NFR-Priv-008 | `smartlock-docs/enterprise/04_SRS.md:307`、`05_NFR.md:127` | **合約下限** |
| TC-COMPLIANCE-01 | 記憶（`agent.*`）與營運資料同步涵蓋 | NFR-Priv-006 | `05_NFR.md:125`（明列「agent 記憶 tenant+user_id default-deny 測試」）| **合約下限** |
| TC-COMPLIANCE-02 | 7d 內客戶通知（含預計解除時間）| FR-API-16 / NFR-Priv-005 / BR-PII-001b | `04_SRS.md:307`、`05_NFR.md:124`、`04_SRS.md:501`（🔴）| **合約下限** |
| TC-NFR-PRIV-01 | legal hold 解除 | NFR-Priv-004 / BR-PII-001a | `05_NFR.md:123`、`04_SRS.md:500`（🔴「永久且不可逆，解除需 ADR change」）| **合約下限** |
| TC-NFR-PRIV-01 | log 一律 PII scrubbing | NFR-Priv-009 | `05_NFR.md:128` | 營運目標 |
| TC-COMPLIANCE-03 | log 輸出無明文 PII | NFR-Comp-004 | `05_NFR.md:216` | **合約下限** |
| TC-COMPLIANCE-05 | 覆核率 100% 報表 | NFR-Aud-004 / NFR-Comp-002 | `05_NFR.md:163`（驗證方式明寫「覆核率報表」）、`:214` | **合約下限** |
| TC-COMPLIANCE-05 | 缺席 >24h → 升級 + 暫停 publish | FR-REF-05 / BR-SOP-002 | `04_SRS.md:345`、`:516`（🔴）| **合約下限** |
| TC-NFR-AUD-01 | append-only、JSON + trace_id | NFR-Aud-001 | `05_NFR.md:160` | **合約下限** |
| TC-NFR-AUD-01 | AI 決策可追溯（`transfer_event.rule_triggered_by`）| NFR-Aud-005 / BR-AI-003 | `05_NFR.md:164`、`04_SRS.md:514`、entity 定義在 `04_SRS.md:84` | 營運目標 |
| TC-NFR-AUD-01 | Config change audit 含 why | NFR-Aud-006 | `05_NFR.md:165` | 營運目標 |
| TC-NFR-AUD-01 | Read-side access log | NFR-Aud-007 | `05_NFR.md:166` | 營運目標 |
| TC-NFR-PRIV-01 | DEK rotation 90d | NFR-Priv-007 | `05_NFR.md:126` | 營運目標 |
| TC-COMPLIANCE-08 | bronze-only、PDF 只引 URL、provenance 不信 LLM | NFR-DQ-001 / FR-REF-04 / BR-KN-001 | `05_NFR.md:172`、`04_SRS.md:344`、`:518` | **合約下限（知識正確性紅線）** |

`04_SRS.md:535` 另把 **FR-API-16、BR-SOP-002、BR-PII-001a~d** 列為「合約紅線 100% pass，違反 = block release」。
本 CR 的 P0 全部落在這條線上。

### 2.2 正典**沒有**規定、或正典之間矛盾的（這幾項本身就是要裁決的事）

**(1) TC-NFR-PRIV-01 的「第三方處理可稽核」在正典零對應。**
該判定基準出自 `smartlock-docs/enterprise/20_Test_Cases.md:440`，但該 TC 驗的七條需求
（NFR-Priv-001/002/003/004/007/009/010，`05_NFR.md:120-129`）**沒有任何一條談委外／受託處理者**。
全 repo（api / SQL / smartlock-docs）對 `sub_processor` / `data_processor` / 受託處理 / 第三方處理
零命中。→ **這是需求缺失，不是實作缺失。**

**(2) `audit_events` 沒有 `tenant_id` —— 正典兩處說法相反。**

- `05_NFR.md:125` NFR-Priv-006「跨租戶隔離 0 leakage」，驗證方式是「**一品牌一 DB 物理隔離驗證**」；
  `19_Test_Plan.md:139` 明說「`tenant_id` 欄位級隔離 + RLS policy 為 **🔜 規劃中**的輔助防線」；
  `23_Deployment_Guide.md:127`「一品牌一 GCP 專案 —— 此即 per-brand 物理隔離在雲端的落點」。
  → 依此讀法，`audit_events` 不需要 `tenant_id`，隔離由部署拓樸提供。
- 但現況是**單庫多租戶**：`SQL/migrations/004-config-m18.sql:41-51` 有 `saas.tenant` 表，
  註解自述「Production tenants are created via onboarding」；`api/services/gdpr_forget_service.py:151-177`
  的 docstring（2026-08-02 資安掃描後補）直接寫「漏了就等於品牌 A 的 admin 可以讀、軟刪、**硬刪**
  品牌 B 的使用者 PII」——團隊自己已把單庫多租戶當成 live risk 在防。
  → 依此讀法，缺 `tenant_id` 就是實打實的跨租戶外洩。

**兩種讀法都能自圓其說，差別在「per-brand 物理隔離是現況還是目標」。這是 D1 的核心。**

**(3) NFR-Priv-005「≤7d 執行 **OR** customer notice」是二擇一，但 legal-hold 情境下第一條走不通。**
`05_NFR.md:124` 原文是 OR。可是 legal-hold 的定義就是「不能執行」，所以在 TC-COMPLIANCE-02 的
情境裡 OR 實質退化成「只能走 customer notice」。正典沒把這個退化寫明。

**(4) BR-PII-001a 說 legal-hold「永久且不可逆」，但正典同時說「解除需 ADR change」——
「不可逆」與「可以用 ADR 解除」互斥。** 程式碼選了第三種：同一端點、同一權限、隨時可解
（`api/services/media_service.py:339`）。三方都不一致。

---

## 3. 歷史成因（不是疏漏，是當時的合理選擇）

| 缺口 | 當時的決策 | 現在為什麼不夠 |
|---|---|---|
| `audit_events` 無 `tenant_id` | `api/services/audit_log_service.py:8` 自述「audit 為部署層級事件，本期不做 tenant 過濾」；`SQL/migrations/116-audit-chain-checkpoint.sql:4` 同樣寫「落庫：品牌庫（部署層級全域鏈，無 tenant_id）」 | 「部署層級」在 per-brand 物理隔離下成立；在單庫多租戶下，一條全域鏈就是一條跨租戶可讀的鏈 |
| GDPR 硬刪 cron 缺 `tenant_id` | `tenant_id` 是 **CR-0183 補漏（2026-07-27）**才變成必填 —— `_get_request` 加了租戶歸屬校驗（`gdpr_forget_service.py:151-177`），`hard_delete` 簽章跟著改（`:344-346`），但 cron 呼叫端沒同步 | 測試的 mock 簽章（`api/tests/test_gdpr_hard_delete_cron.py:60/:96/:127`）照著**壞的呼叫端**寫，所以修改沒被擋下來 |
| legal-hold 只認 `uploader_user_id` | CR-0164 D2 的原始情境是「技師自己上傳、技師自己提 forget」 | 爭議案件裡證據常由技師/客服上傳、subject 只是當事人 |
| logging 無 filter | `api/core/pii_scrub.py:4-5` 的模組 docstring **自述**要供「audit payload 遮蔽…、**log filter** 等接管道使用」——設計時就規劃了，只是沒接 | `api/core/pii_crypto.py:102-104` 記錄 2026-08-02 探針實跑打 request-password-reset 後**在容器 log 直接掃到完整 email 明文**：風險已被證實發生過 |
| 家族覆核率報表 | `api/services/sop_performance_service.py` 早於 `family_reviews` 表（CR-0079/074 migration）存在 | 報表算的是 admin 初審率，被當成覆核率用 |

---

## 4. 回查證與走查文件的差異（先修正事實，再談要不要修）

外部測試人員 Luca 的走查文件（`docs/uat/static-walkthrough-20260803/`）整體品質高，但本組有 **1 項實質判定錯誤**
與 **4 項引用偏移**，先更正，否則會依錯誤前提做決策：

| # | 走查文件的說法 | 回查證的事實 |
|---|---|---|
| **實質錯誤** | TC-COMPLIANCE-08：「`references/` 樹**無程式化校驗**、不在 audit 範圍」 | **錯**。`scripts/ci/references-provenance-check.py` 存在，第 1 行即自述「FR-REF-04：references 側 bronze provenance gate」，`REF_DIR` 於 `:26-29` 直指 references 樹，`:52-70` 逐檔驗 frontmatter 與 brand 對齊。整份走查漏掉這個檔 |
| 引用偏移 | TC-NFR-AUD-01 步驟 6 寫 `rule_triggered_by` 全樹零命中 | `api/openapi.yaml:6341` 有一處。但**實質結論仍成立**——那是 `GuardrailCheckResponse` 的 in-flight 回應 enum，不是持久化稽核欄；`transfer_event` 這張表在 api / SQL / agent **確實**零命中 |
| 引用偏移 | TC-NFR-PRIV-01 把 retention 指到 `media_service.py:216` | 實際在 `:196-205`（`:213-226` 是 sha256 去重 block） |
| 引用偏移 | TC-NFR-PRIV-01 把 NFR-Priv-010「技師工單投影」對到 `api/core/tech_mirror.py` | `tech_mirror.py:1-18` 自述是「技師**身分**投影（技師權威庫 → 品牌庫）」，方向與主體都不對。真正的技師端工單讀取是 row-level scope（`api/routers/work_orders_v2.py:190-191`），**無欄位級最小化** |
| 引用偏移 | TC-COMPLIANCE-05 SLA cron「每小時掃」 | 文件沒錯（`DEFAULT_INTERVAL_S=3600`，`family_review_sla_cron.py:25`），是**原始碼 docstring 自己寫「每日掃」**（`:3`）矛盾 |

另有一項走查文件判為缺口、回查證認為**判重**：

> TC-COMPLIANCE-05「缺席 >24h → **暫停 publish**」判為無對應。實際上 adopt gate
> （`api/services/sop_draft_service.py:405-417`）**從 t=0 起就無條件擋住 publish**，比
> BR-SOP-002 要求的「≥24h 才暫停」更嚴。下游不會壞，**不需要改 code**。

---

## 5. 程式碼現狀（每條都開檔覆核過）

### 5.1 🔴 P0-A：GDPR T+30 硬刪自動化從未成功執行過任何一列

```
api/services/gdpr_forget_service.py:344-346
    async def hard_delete(*, request_id: str, tenant_id: str, actor_user_id: str | None = None) -> dict:
                                             ^^^^^^^^^^^^^^^^ 必填、無預設值

api/realtime/gdpr_hard_delete_cron.py:102-110   SELECT id FROM saas.forget_request ...   ← 只取 id
api/realtime/gdpr_hard_delete_cron.py:118-121   await gdpr_forget_service.hard_delete(
                                                    request_id=request_id,
                                                    actor_user_id=None,
                                                )                                        ← 沒傳 tenant_id
api/realtime/gdpr_hard_delete_cron.py:127-131   except Exception: errors += 1; logger.exception(...)
```

每一列必然 `TypeError`，被 `except Exception` 吞成 `errors += 1`。
cron **已接生產**（`api/realtime/job_registry.py:196`、`api/routers/lifespan_health.py:72`）。
→ **兩階段 GDPR 的第二階段等於不存在**，只能靠 admin 手動打 `:hard-delete`
（`api/routers/gdpr_forget_v2.py:162-171`，該處有正確傳 `tenantId`）。

**假綠的來源**：`api/tests/test_gdpr_hard_delete_cron.py:60`、`:96`、`:127` 三處都用
`async def fake_hard_delete(*, request_id, actor_user_id)` monkeypatch 掉真函式 —— 測試 fake 照著
**壞的呼叫端**寫，所以永遠綠。**只修 cron 不修測試，等於什麼都沒修。**

### 5.2 🔴 P0-B：品牌 admin 可讀取／匯出整個部署的稽核事件

```
api/core/deps.py:293            FULL_ACCESS_ROLES = ("admin",)          ← 是「品牌層 admin」
api/routers/audit_v2.py:46-76   list  — role_required(*FULL_ACCESS_ROLES) + path tenant guard
api/routers/audit_v2.py:178-198 export — cross-tenant guard + role in {"admin","ops"}
```

兩個端點都在 path 層比對「JWT tenant == path tenantId」，通過之後：

```
api/services/audit_log_service.py:270-300   list_audit_logs 的 WHERE 只有 event_type / created_at / actor_id
api/services/audit_log_service.py:355-375   _build_export_filters 的 WHERE 只有 event_type / created_at
                                            / actor_id / target_type
```

**兩處都不帶任何 tenant 條件，而 `audit_events` 表也沒有該欄**
（`SQL/Schema_v2_extensions.sql:240-254` 全表 14 欄 + `SQL/migrations/067-audit-hash-chain.sql:8-9`
的 `prev_hash`/`entry_hash`）。→ 租戶 A 的 admin 打 `/tenants/A/audit/events` 或
`/tenants/A/audit/exports`，拿到的是**含租戶 B 的全部稽核事件**。

對照組：`saas.config_audit`（`SQL/migrations/004-config-m18.sql:100-110`）**有** `tenant_id`。
所以這不是全專案一致的設計，是 `audit_events` 單獨的缺口。

前端已在用：`web/brand-portal/src/app/admin/audit-events/page.tsx:154`、
`web/brand-portal/src/components/admin/AuditExportModal.tsx:78-81`。

### 5.3 🟠 新發現（走查文件未涵蓋）：軟刪後 `users.line_user_id` 沒被清

```
SQL/Schema.sql:131   COMMENT ON COLUMN users.line_user_id IS
                     'LINE Platform 唯一使用者 ID (U + 32 hex)，消費者的唯一識別依據';

api/services/gdpr_forget_service.py:296-304  UPDATE users SET display_name='[REDACTED]',
                                             email='[REDACTED-'||id||']', phone=NULL {_enc_clear}
api/services/gdpr_forget_service.py:289-295  _enc_clear 清 display_name_enc / email_enc / phone_enc
                                             / email_bidx / phone_bidx
```

**`line_user_id` 不在清除清單內。** 而硬刪的 FK 阻擋路徑（`:379-407`）自述
「soft_delete 已把 PII 匿名化（GDPR Art.17 承認匿名化等同抹除）」、**「匿名化即終態」**——
但一個穩定的自然人唯一識別碼還留在庫裡，這個「匿名化」的主張站不住。
該路徑不是罕見情況：程式碼自己列出會擋住的 FK 是
`complaints / disputes / refund_requests / warranty_claims`（`:380-381`）。

**這同時是 5.4 的解法**：`users.line_user_id` 正是 `agent.memory_entry.user_id` 的 join 鍵
（`api/services/line_push_service.py:237-243` 已有這條映射路徑）——所以身分映射**不是缺口**，
缺的是「在 T0 就把它快照下來並清掉」。硬刪之後 users 列消失，那時才想接就接不上了。

### 5.4 🟠 agent 記憶完全不在 forget 範圍內

```
git grep -n "memory_entry" -- api        → 零命中
git grep -n "agent\." -- api/services/gdpr_forget_service.py api/realtime/gdpr_hard_delete_cron.py
                                          → 零命中
```

刪除能力**其實已經存在**，只是生產零呼叫端：
`agent/lockcore/agent/user_memory/manager.py:50`、`postgres_store.py:137`（
`DELETE FROM agent.memory_entry WHERE tenant=%s AND user_id=%s`）、`store.py:163`
—— 全 repo 只有測試在呼叫（`agent/tests/test_memory.py:78`、`test_memory_postgres.py:65/87/91`）。

`agent.escalation`（`SQL/migrations/033-agent-memory-schema.sql:47-55`）的
`facts_snapshot` JSONB 內含**手機與客人原話**，同樣不在 forget 範圍。
兩張表**都沒有 TTL / retention 欄位**（同檔 `:20-31`、`:47-55`）→ 永久保存。

### 5.5 🟠 legal-hold 的兩個方向都有問題

**誤放行（比誤擋危險）**：`api/services/gdpr_forget_service.py:72-79` 的
`_has_active_legal_hold` 關聯鍵只有 `media_files.uploader_user_id`。證據由技師/客服上傳、
subject 只是當事人時擋不住 → forget 照常執行 `destroy_dek`（`:311-312`）與 PII 覆寫（`:296-304`），
**不可逆**。

**解除無 gate**：`api/services/media_service.py:339` 的 `set_legal_hold(hold=True/False)`
同一端點、同一權限、無強制 reason，docstring 自述「自動觸發/解除規則待業主定義，本輪僅手動」。
與 BR-PII-001a（🔴，`04_SRS.md:500`）「永久且不可逆，解除需 ADR change」不符。

### 5.6 🟠 7d 客戶通知：欄位有、通知沒有、也不可稽核

- `deny_legal_hold`（`api/services/gdpr_forget_service.py:196-239`）docstring `:204-206` 自述
  「7 天內通知客戶（**業務 SOP 流程，本 service 只標 status**）」
- `notification` / `notify` / `push_notification` / `send_` 在 GDPR 兩檔零命中
- 專案**有** `notification_service.push_notification`（`api/services/notification_service.py:206`），
  且已被 `api/realtime/family_review_sla_cron.py:143-161` 使用 —— 只是沒接進 GDPR 流程
- `expected_release_at` 是可選欄（`api/routers/gdpr_forget_v2.py:49-51`），service 只驗
  `legal_hold_reason` 長度 ≥5（`:210-211`），**無下游消費者**
- **沒有任何欄位記錄「已通知」** → 7d SLA 既不可稽核也不可量測

### 5.7 🟡 consent 只能覆寫，不能撤回

`SQL/migrations/043-work-order-consents.sql:16-27` 無 `withdrawn_at` 欄；
`api/services/consent_service.py:113-123` 只有 upsert，`accepted=false` 覆寫會把
`accepted_at` **一併洗成 NULL**（`:121` 的 `now if accepted else None`）→ 原同意時點永久消失。
`withdraw` / `revoke` / 撤回 / opt_out 在 consent 相關檔零命中。
外部端點只有兩個（`api/routers/consumer_v2.py:340-377`：GET 取文本、POST 提交）。

附帶：`api/services/consent_service.py:123` 的 `logger.info` 直接輸出完整 `ip_address`，
而 `api/core/pii_scrub.py:18-33` 的 5 條 regex **不含 IP 樣式**。

### 5.8 🟡 PII 遮蔽工具存在，但沒接在 logging 管道上

| 面向 | 現況 |
|---|---|
| 工具本體 | `api/core/pii_scrub.py:18-33`（LINE uid / email / 電話 / 身分證 / 地址 5 條 regex）、`:49-55` `scrub_text`、`:58-72` `scrub_audit_payload` |
| 掛載點① | OTel span 出站 `api/core/observability.py:77-89` —— **但 `:59-62` 在 `OTEL_EXPORTER_OTLP_ENDPOINT` 未設時整段早退** |
| 掛載點② | audit payload 入 hash 前 `api/services/audit_log_service.py:81-83` |
| logging 管道 | **無**。`api/main.py:141` 是 api 全樹唯一 logging 配置；`addFilter`/`dictConfig`/`setFormatter` 零命中。agent 側同樣只有 `agent/scripts/line_gateway.py:28` 一行 basicConfig |
| 呼叫點慣例 | `mask_email_for_log` 僅 3 個呼叫點（`password_reset_service.py:106`/`:126`、`staff_application_service.py:77`）；`[:8]` 截斷 65 處 |

**已證實發生過**：`api/core/pii_crypto.py:102-104` 記錄 2026-08-02 探針實跑後在容器 log
掃到完整 email 明文。

**走查文件只掃了 api/，agent 側同型風險未涵蓋**：
`agent/lockcore/channels/line_gateway.py:361`/`:461`/`:464`/`:539`/`:905`/`:950` 把上游回應本文
（`resp.text[:160~200]`）寫進 log。API 端 422 會回顯輸入值，而 persist / escalation payload
內含客人原話與 `facts_snapshot.phone` → 對方回 4xx 時可能把手機或原話寫進 log。

### 5.9 🟡 家族覆核率報表不存在（且現有報表算的是別的東西）

`api/services/sop_performance_service.py:94` 的 `approval_rate_pct` 分子分母全取自
`sop_drafts.status`（admin 初審），該檔對 `family_reviews` **零命中**；
`api/routers/reports_kpi.py` 同樣零命中。
既有測試釘住的也是初審率（`api/tests/test_sop_performance.py:77-78`，83.33%）。

gate 本身是完整的：`api/services/sop_draft_service.py:405-417`（425 `FAMILY_REVIEW_REQUIRED`）、
四眼 `api/services/family_review_service.py:223-231`（403 `SOD_VIOLATION`）、
hash chain `:234-252` + `SQL/migrations/074-family-review-ledger.sql:8-13`。
**缺的只有「證明覆核率 100%」的觀測面。**

### 5.10 🟡 兩支 provenance gate 沒接 CI

`.github/workflows/` 共 20 個 workflow，對 `references-provenance-check` 與 `audit_corpus`
**零命中**（對照組：`forbidden-eval-gate.yml`、`migration-drift-check.yml` 有接）。
兩支 gate 都能跑、都會 exit 1，但**沒有自動化強制力**。

`scripts/ci/references-provenance-check.py:11-15` 與 `04_SRS.md:344` 都自承：
references 側的「內容源自 bronze」目前**靠 authoring 紀律**，機器只驗結構與 brand 對齊；
「references ↔ pgvector CI 同源檢查」在正典標為 **🔜 規劃中**。

### 5.11 🟡 NFR-Aud-005 不是「部分實作」，是整個 entity 沒開發

`04_SRS.md:84` 定義的 **TransferEvent** entity（`(conversation_id, transfer_event_seq)` /
`rule_triggered_by` enum）在 api / SQL / agent **全樹不存在**。
`saas.ai_decision_trace` 表與 API 都在（`SQL/migrations/022-ai-decision-trace.sql:46` 有
`agent_version`，`api/routers/ai_governance_trace_v2.py:48-66` 有寫入端點，其 `:3` 自述
「agent runtime 呼」），但 `agent/` 全樹對 `log_decision` / `ai_decision_trace` **零命中**
→ 該表實質空轉。

agent 側的轉真人紀錄落在 `agent/lockcore/agent/user_memory/escalation.py:47-55` 的獨立表，
欄位無 `agent_version`、無 trace、不入 hash chain。

---

## 6. 影響評估

### 6.1 rewrite vs refactor 九維打分

| 維度 | 分 | 依據 |
|---|---|---|
| 產品目標是否改變？ | **0** | 沒變。合規是既有承諾（`04_SRS.md:535` 合約紅線），不是新目標 |
| 核心 User Flow 是否改變？ | **1** | 新增分支：consent 撤回（新端點）、legal-hold 拒絕後的 7d 通知、legal-hold 解除的獨立路徑。主流程不重寫 |
| Domain Model 是否改變？ | **1** | 新增概念：稽核事件的租戶歸屬（新不變式）、consent 的撤回生命週期、legal-hold 的可逆性語意、缺席的 TransferEvent entity。核心概念（hash chain 正規化內容）**視 D2 而定**——若選 (a) 把 `tenant_id` 入 hash，本項升為 2 |
| API Contract 是否大量破壞？ | **1** | 多 endpoint 變動：新增 consent 撤回、legal-hold release、`family_review_rate_pct` 新欄；audit list/export 加 tenant 過濾會**縮減**既有回傳集合（方向是收緊，但仍是行為破壞） |
| DB Schema 是否需重建？ | **2** | **本 CR 最痛的一維**。`audit_events` 加 `tenant_id` 後的 backfill 必須對 append-only 表下 UPDATE，而 `SQL/migrations/100-audit-events-append-only.sql:19-31` 的 trigger 會擋——唯一出路是 `session_replication_role='replica'`（檔頭 `:14-19` 自述的特權繞過），**那正是 append-only 設計要防的路徑，且繞過後不留痕**。且既有列的租戶歸屬多數無法從 payload 還原 |
| 模組邊界是否錯誤？ | **1** | 有些混亂：GDPR forget 要涵蓋 agent 記憶，但 `agent` schema 由 agent 擁有；api 直接 DELETE 牴觸既有分層，且 agent 有 SQLite / Postgres 兩種 store，api 只能處理其中一種 |
| 測試是否可信？ | **2** | **幾乎不可信**（在本 CR 涵蓋範圍內）：`test_gdpr_hard_delete_cron.py` 三個 fake 照壞簽章寫、CI 永遠綠、掩蓋 P0；`test_gdpr_forget.py` 兩支既存失敗（假 cursor 序列落後實作）；`test_cr_0166_pii_scrub.py` 只驗純函式不驗實際 log 輸出（`caplog` + PII 在 `api/tests/` 零命中）；`test_sop_performance.py:77-78` 釘的是錯的率 |
| 文件是否可信？ | **2** | **大量矛盾**：正典內部矛盾 3 處（§2.2 的 (2)(3)(4)）；走查文件本組 1 實質錯誤 + 4 引用偏移；原始碼 docstring 自相矛盾（`family_review_sla_cron.py:3` 說每日、`:25` 是每小時）；`api/services/audit_log_service.py:8` 的「本期不做」註解已被 CR-0183 的租戶隔離方向推翻但沒更新 |
| 團隊/AI 是否還理解系統？ | **0** | 理解。每個缺口都能精確定位到 `檔案:行號`，且多數帶 CR 編號註解說明當初決策 |

**總分 = 10 分（7–12 區間）→ 行動：架構重審 + 模組拆分（多 CR + 跨 sprint）。**

**這個分數的意思**：不要把 §5 的 11 項當成一個 sprint 的 backlog 一次做完。
真正撐高分數的是 **DB schema（2）+ 測試不可信（2）+ 文件矛盾（2）** 這三維，而它們共用一個根因
——**「稽核／個資的租戶歸屬」這個概念在系統裡從來沒有被明確決定過**，於是每個模組各自
補了一半。先在 D1 把這件事定下來，其餘的實作才有依據；否則會做出互相矛盾的第二輪。

### 6.2 誠實分流：以下幾項我認為**不該現在修**

| 項目 | 理由 |
|---|---|
| TC-COMPLIANCE-05「暫停 publish」 | **判重，不需改 code**。adopt gate（`sop_draft_service.py:405-417`）從 t=0 起無條件擋，比 BR-SOP-002 的「≥24h 才暫停」更嚴。應在 CIA 裡標為「由 adopt gate 保證」，只補觀測 |
| TC-NFR-PRIV-01「第三方處理可稽核」 | **正典零需求 ID**（§2.2 (1)）。這是需求缺失不是實作缺失。**裁決前不要寫任何 code**——先請法務確認它指的是既有的跨庫投影，還是 GDPR Art.28 的處理者名冊 |
| TC-NFR-AUD-01 的 `trace_id` 欄 | 在 SigNoz/OTel 上線前是空轉。`api/core/observability.py:59-62` 在 `OTEL_EXPORTER_OTLP_ENDPOINT` 未設時整段早退 → 現在加欄位只會拿到一整欄 NULL。**應與可觀測性上線綁定，不獨立做** |
| NFR-Priv-007 DEK rotation 90d | 位階是**營運目標**非合約下限（`05_NFR.md:126`）。DEK 的主要用途是 per-subject crypto-shredding，輪換的邊際安全效益遠低於本 CR 的 P0；而重加密全部 subject 的密文欄是高風險批次作業。**建議 defer** |
| TC-COMPLIANCE-08 的內容級 bronze 溯源 | 要在 references frontmatter 加 `bronze_sources` 清單，**會動到已鎖定的 product_info 內容格式**（CLAUDE.md Architecture Lock 第 2 條）。**建議另開 CR 並先確認業主是否同意動 frontmatter**。本 CR 只做「gate 接 CI」 |
| NFR-Aud-005 / TransferEvent | 不是「部分實作」，是**本來就沒開發**（§5.11）。位階是營運目標。要做等於新增一個 domain entity + agent→api 的新整合，規模等同一張獨立 CR |

---

## 7. 可行路徑（各決策的技術選項與代價）

### 7.1 `audit_events` 租戶隔離的三條路

| 路徑 | 工作量 | 立即止血？ | 代價 |
|---|---|---|---|
| **加 `tenant_id` 欄 + 兩處 WHERE 過濾** | migration + service 2 處 + backfill 策略 | 否（migration + 部署週期）| backfill 要對 append-only 表下 UPDATE（需 `session_replication_role='replica'`，不留痕）；既有列歸屬多數無法還原 |
| **收緊角色：list/export 只開平台級（`user.tenant_id is None`）** | 2 個端點各一行 | **是（當天可上線、零 migration、零 hash 影響）** | 品牌 admin 的稽核頁面（`web/brand-portal/src/app/admin/audit-events/page.tsx`）與匯出（`AuditExportModal.tsx`）會全部 403 |
| **不處理，在正典標注** | 0 | 否 | 留一個「看起來有在做租戶隔離、實際沒有」的端點；`gdpr_forget_service.py:151-177` 已為同類問題寫過警語，這裡卻放著 |

### 7.2 agent 記憶納入 forget 的兩條路

- **(a) api 直接 `DELETE FROM agent.memory_entry / agent.escalation`**：最短路徑，但牴觸
  「`agent` schema 由 agent 擁有」的分層，且只能處理 Postgres store，SQLite store（本機/離線）處理不到。
- **(b) agent 端新增 purge 端點，api 旁路呼叫**：新 External integration，但 agent 側刪除能力已存在
  （`manager.py:50` / `postgres_store.py:137` / `store.py:163`），只需包一層端點 + 服務間認證。

**兩者共同前提**：`users.line_user_id` 必須在 T0 就快照進 `saas.forget_request`（見 §5.3）
—— 硬刪之後 users 列消失，映射就永久接不上了。

### 7.3 PII log filter 的落地順序

1. **止血（CIA 豁免，當天可做）**：改掉 `agent/lockcore/channels/line_gateway.py` 六處
   `resp.text[:N]`（只記 status_code），以及 `api/services/consent_service.py:123` 的完整 IP。
2. **管道級（須 CIA：Architecture boundary）**：`api/main.py:141` 與
   `agent/scripts/line_gateway.py:28` 各掛 `logging.Filter`。
   **技術風險**：Filter 內呼叫 `record.getMessage()` 會強制展開 `%s` 延遲格式化，之後必須
   改寫 `record.msg` 並清空 `record.args`，否則 handler 會二次格式化而炸。api 有約 150 條
   logger 呼叫大量使用 `%s` 延遲格式化，這個改動要先驗證不破壞既有語句。
3. **釘住（Test plan）**：補 `caplog` + PII 的測試，否則 filter 日後被移除不會有人知道。

---

## 8. 🛑 Human Decisions Required

> 以下 12 個決策點按優先序排列。**D1 / D3 / D4 是 P0，其餘可稍後**。
> 標 ⚖️ 者建議先過法務（窗口＝**Irene**）。
> 回覆格式：「D1 選 b」即可。

---

### D1 ⚖️ `audit_events` 的跨租戶可讀性怎麼處理？（P0）

現況：品牌 A 的 admin 可列出並匯出**含品牌 B 在內的全部**稽核事件（§5.2）。
正典對這件事有兩種相反讀法（§2.2 (2)）。

- **(a) 補 `tenant_id` 欄位 + list/export 一律過濾**
  代價：需 migration；既有列的 backfill 必須對 append-only 表下 UPDATE（`session_replication_role='replica'`
  特權繞過，不留痕）；多數既有列的租戶歸屬無法從 payload 還原，只能填 NULL 或猜。
- **(b) 先收緊角色**：list / export 只開平台級（`user.tenant_id is None`）的 admin，品牌 admin 一律 403
  代價：品牌後台的稽核頁與匯出功能立即失效（`web/brand-portal/src/app/admin/audit-events/page.tsx`、
  `AuditExportModal.tsx`），需要通知營運；但**零 migration、零 hash 影響、當天可上線**。
- **(c) 不處理**，在正典 NFR-Priv-006 旁**標注**（非改寫）：「`audit_events` 為部署層級全域鏈，
  租戶隔離依賴 per-brand 物理隔離（ADR-P005）；單庫多租戶期間品牌 admin 可見全域稽核」
  代價：外洩持續存在，且**看起來有在隔離**（path guard 會讓人以為隔離了）。

**我的建議：(b) 先做，再以另一張 CR 走 (a)。**
理由：(a) 的 backfill 是本 CR 唯一一個「修的動作本身會破壞既有防護」的操作——為了補租戶欄
而動用 append-only 的特權繞過，代價高於收益。先用 (b) 讓外洩**今天**停止（一行改動、可回退），
再讓 (a) 只對**新列**生效，舊列 `tenant_id` 留 NULL 代表「歸屬不明的歷史」——明確標示，
比亂猜可信。(c) 不建議：`gdpr_forget_service.py:151-177` 已為完全同型的問題寫過警語並修掉了，
同一個部署裡兩套標準說不過去。

> ⚖️ 需法務確認的部分：品牌 admin 看不到自己租戶的稽核日誌，是否違反與品牌的合約承諾？
> 若合約有「品牌可自行稽核」條款，(b) 就只能當臨時措施，(a) 必須排進本季。

---

### D2 若 D1 選 (a)：`tenant_id` 要不要進 hash chain？

`_canonical_audit_content`（`api/services/audit_log_service.py:47-57`）目前只涵蓋 7 個欄位。

- **(a) 入 hash**：`tenant_id` 成為防竄改內容的一部分
  代價：既有列全部驗證失敗，必須**再建一次** re-baseline checkpoint（CR-0184 機制）。
- **(b) 不入 hash**：只作查詢過濾欄
  代價：`tenant_id` 本身不受 hash 保護（但仍受 `SQL/migrations/100-audit-events-append-only.sql:19-31`
  的 DB trigger 保護，UPDATE 直接被擋）。

**我的建議：(b)。** CR-0184 的 checkpoint 語意是「歷史凍結、往後可驗」（`CHANGELOG.md:280`），
短期內第二次 re-baseline 會稀釋這個機制的可信度——稽核員看到「又重設了一次基準」會合理懷疑
基準本身。tenant_id 的竄改保護交給物理 append-only 就夠。

---

### D3 GDPR 硬刪 cron 修好之後，累積的 eligible 佇列怎麼放行？（P0）

修 cron 本身是單一函式內的 bug fix、無 contract 變動 → **CIA 豁免，不需等本 CR 裁決**（見 §9 步驟 0）。
但**修好之後的第一次成功執行**是有風險的：這條路徑從未成功跑過任何一列，而它做的是
**不可逆的實體刪除**（`gdpr_forget_service.py:392-394`，且 DEK 已在 T0 銷毀）。
累積的 `status='soft_deleted' AND hard_delete_eligible_at <= NOW()` 佇列會在第一輪一次爆開。

- **(a) 直接放行** —— 修完就讓 cron 正常跑，backlog 一次清掉
  代價：從未驗證過的程式碼路徑，第一次執行就對 prod 做不可逆刪除。
- **(b) 先 dry-run 盤點** —— 唯讀查 prod `saas.forget_request` 有幾列符合條件、逐列確認
  legal-hold 與 FK 狀況，再放行；第一輪把 `batch_size` 調到 1 觀察
  代價：多兩天。
- **(c) 修 cron 但先停用**（不註冊 job），只留手動端點，等業主逐列核可
  代價：GDPR 的 T+30 SLA 繼續靠人工，但至少是**知情的**人工。

**我的建議：(b)。** 「從未成功執行過的程式碼」+「不可逆」+「prod」三個條件同時成立時，
先看再跑的成本遠低於刪錯的成本。dry-run 只需要唯讀 SELECT。

---

### D4 ⚖️ GDPR forget 要不要涵蓋 agent 記憶？走哪條路？（P0）

TC 判定基準明列、NFR-Priv-006（`05_NFR.md:125`）明列「agent 記憶 tenant+user_id default-deny 測試」。
現況：`agent.memory_entry` / `agent.escalation` 完全不在 forget 範圍，且**兩張表都沒有 TTL**
（`SQL/migrations/033-agent-memory-schema.sql:20-31`、`:47-55`），`escalation.facts_snapshot`
內含手機與客人原話。

- **(a) api 直接 DELETE `agent.*`**
  代價：牴觸「`agent` schema 由 agent 擁有」的分層；只能處理 Postgres store。
- **(b) agent 端新增 purge 端點，api 旁路呼叫**
  代價：新 External integration（服務間認證、失敗重試、部分成功的處置）；但 agent 側刪除能力
  已存在（`manager.py:50` / `postgres_store.py:137` / `store.py:163`），只需包端點。
- **(c) 不做**，在正典標注 agent 記憶不在 forget 範圍
  代價：GDPR Art.17 直接不合規；且 `04_SRS.md:535` 把 FR-API-16 列為 block release 紅線。

**我的建議：(b)。**（a）看起來省事，但 api 直接寫 agent 的表會讓兩邊的 schema 演進互相綁死，
下次 agent 改 schema 就會炸在 GDPR 路徑上——那是最不該炸的地方。
(c) 我不建議，但如果業主決定 v1 先不做，**至少要給 agent 記憶一個 TTL**（例如 90 天自動清），
否則「永久保存客人原話與手機」這件事本身就是獨立的合規曝險，與 forget 有沒有做無關。

> **不論選哪條，都必須先做一件事**：在 T0 把 `users.line_user_id` 快照進
> `saas.forget_request` 並清掉該欄（§5.3）。硬刪之後 users 列消失，映射就永久接不上了。
> 這一步也順帶修掉「軟刪後自然人唯一識別碼還留著」的問題。

> ⚖️ 需法務確認：agent 對話記憶（含 LLM 產生的摘要）是否全部屬於 GDPR Art.17 的抹除範圍？
> 若部分屬於「基於法律義務保存」，保留範圍與期限需要 Irene 定。

---

### D5 ⚖️ legal-hold 解除要不要獨立 gate？

BR-PII-001a（🔴，`04_SRS.md:500`）：「legal-hold 永久且不可逆（解除需 ADR change）」。
程式碼：`api/services/media_service.py:339` 的 `set_legal_hold` 對 `hold=True/False` 走同一路徑、
同一權限、無強制 reason。

- **(a) 拆 set / release 兩條端點**：release 要求更高角色 + 強制 reason + 強制填 ADR 編號 + 寫 `audit_events`
  代價：新增端點（API contract）+ 前端改動。
- **(b) 維持現況**，在正典標注「解除須 ADR」為流程約束、非系統約束
  代價：🔴 紅線只存在於文件，系統上任何品牌 admin 隨時可解。
- **(c) 完全禁止解除**（DB CHECK：`legal_hold` 只能 false→true）
  代價：最符合字面「不可逆」，但誤設就永遠救不回來——而這是純手動操作，誤設是遲早的事。

**我的建議：(a)。** 正典自己就矛盾（「不可逆」vs「解除需 ADR change」，§2.2 (4)），
(a) 是唯一能同時滿足兩句話的讀法：解除**可以**發生，但必須留下與 ADR 對應的不可否認紀錄。

> ⚖️ 需法務確認：BR-PII-001a 的「不可逆」是法律要求還是內部政策？若是前者，(c) 才對。

---

### D6 legal-hold 的關聯鍵過窄要不要修？

`_has_active_legal_hold`（`api/services/gdpr_forget_service.py:72-79`）只認
`media_files.uploader_user_id`。爭議案件裡證據多由技師/客服上傳、subject 只是當事人
→ 擋不住 → forget 照常執行不可逆的 crypto-shred。

- **(a) 擴大為「subject 是關聯工單／問題卡的客戶」也算**
- **(b) 維持現況**（只擋自己上傳的）
- **(c) 更保守：subject 名下任一工單有 legal_hold media 即擋**

**我的建議：(a)。** 這是**誤放行**方向的缺口，比誤擋危險得多——誤擋可以再提一次 forget，
誤放行執行完就沒了。(c) 過寬會讓大量正常 forget 被擋住，反而製造 7d SLA 的壓力。

---

### D7 ⚖️ legal-hold 拒絕後的 7d 客戶通知走哪一邊？

NFR-Priv-005（`05_NFR.md:124`）是「≤7d 執行 **OR** customer notice」二擇一，
但 legal-hold 的定義就是不能執行（§2.2 (3)）。

- **(a) 實作通知**：`deny_legal_hold` 成功後呼叫 `notification_service.push_notification`
  （`api/services/notification_service.py:206`，已被 `family_review_sla_cron.py:143-161` 使用）；
  `expected_release_at` 改為必填（router + service 雙層校驗）；`saas.forget_request` 加 `notice_sent_at`
  代價：DB schema + API contract + 通知文案需法務定稿。
- **(b) 只補可稽核性**：加 `notice_sent_at` 欄 + 後台勾選「已通知」，**發送仍由人工**
  代價：SLA 可稽核但不可自動保證。
- **(c) 維持現況**（docstring 自述「業務 SOP 流程」），在正典標注
  代價：**7d SLA 既不可稽核也不可量測** —— 稽核時拿不出任何證據。

**我的建議：(b) 先做，(a) 排後面。** 理由：這條紅線真正的風險不是「沒發通知」而是
「**發了也證明不了**」。加一個 `notice_sent_at` 是一支 migration + 一個欄位，當週可完成，
立刻讓 SLA 可稽核；自動發送涉及通知文案的法律措辭，卡在 Irene 定稿上，不該擋住可稽核性。

> ⚖️ 需法務確認：通知文案；以及「customer notice」是否必須書面/可證送達（若是，站內通知不夠，
> 要走 email 或 LINE 並保存送達回執）。

---

### D8 PII log filter 要做到哪一層？

- **(a) 只做管道級 filter**（`api/main.py:141` + `agent/scripts/line_gateway.py:28` 各掛 `logging.Filter`）
- **(b) 只做止血**（改掉 agent 六處 `resp.text[:N]` + `consent_service.py:123` 的完整 IP）
- **(c) 兩者都做**，順序 (b) → (a) → 補 `caplog` 測試

**我的建議：(c)，但務必先 (b)。** (b) 是已知的具體外洩路徑、CIA 豁免、當天可做；
(a) 是跨切面基礎建設，有真實的技術風險（§7.3：`record.getMessage()` 會強制展開 `%s` 延遲格式化，
api 有約 150 條 logger 呼叫依賴它），需要獨立驗證。**先止血再做基建，不要倒過來。**

---

### D9 ⚖️ 「第三方處理可稽核」怎麼裁？（正典無此需求）

該判定基準只出現在 `20_Test_Cases.md:440`，對應的七條 NFR 沒有一條談委外處理者（§2.2 (1)）。

- **(a) 判為 NFR-Priv-010 既有的跨系統投影**（`api/core/tech_mirror.py:44-56` 的 7 欄白名單，已實作）
  → 修正 TC 判定基準措辭，本項銷案
- **(b) 判為 GDPR Art.28 / 個資法委外處理的處理者名冊** → 新開需求 ID，並決定治理形式（DB 表 or 文件）
- **(c) defer 到 Phase II**，正典標注

**我的建議：先請 Irene 裁，技術面我讀為 (a)。** 但這是法遵判斷不是技術判斷。
**裁決前不要寫任何 code** —— 若實際是 (b)，做出來的 tech_mirror 稽核報表完全不解決問題。

---

### D10 DEK rotation 90d（NFR-Priv-007）要不要做？

現況：`api/services/dek_service.py` 無 rotate 函式，`api/realtime/` 無排程；
`SQL/migrations/112-gdpr-dek-registry.sql:28` 的 `key_version` 恆為 `DEFAULT 1`、無遞增邏輯。

- **(a) 做**：新增 `dek_rotation_cron`（比照既有 cron 的 `job_registry` 註冊方式），
  門檻入 M18 config 而非寫死 90d
- **(b) defer**，正典標注

**我的建議：(b)。** 位階是**營運目標**非合約下限；DEK 的主要價值在 per-subject crypto-shredding
（已實作且有效），輪換的邊際安全效益低；而「重加密全部 subject 的 PII 密文欄」是高風險批次作業，
不該和本 CR 的 P0 搶同一個 sprint。

---

### D11 家族覆核率報表要做到哪一層？

NFR-Aud-004 / NFR-Comp-002（皆**合約下限**）的驗證方式明寫「覆核率報表」。
現況：`api/services/sop_performance_service.py` 對 `family_reviews` 零命中（§5.9）。

- **(a) 全套**：service 加 `family_review_rate_pct` + `api/openapi.yaml` 同步 +
  `web/brand-portal/src/app/admin/knowledge-base/sop-performance/page.tsx` 顯示 + 測試
- **(b) 只做後端**：加指標與稽核用 API，不動前端
- **(c) defer**

**我的建議：(a)。** 這是本組唯一「小到可以順手做完」的合約下限缺口——gate 本身完整、
hash chain 完整、四眼完整，缺的只是一個聚合查詢。沒有報表就無法證明「覆核率 100%」，
而 `04_SRS.md:535` 把 BR-SOP-002 列為 block release。

---

### D12 兩支 provenance gate 接 CI 到什麼程度？

- **(a) 新增 `.github/workflows/knowledge-provenance-gate.yml`**，paths 監看
  `knowledge-pipeline/pipeline/**` + references 樹，依序跑 `references-provenance-check.py`
  與 `audit_corpus`，任一非零即擋
- **(b) 不接**，維持人工跑
- **(c) (a) + 加內容級 bronze 溯源**（references frontmatter 加 `bronze_sources` 清單並由 gate 驗檔存在）

**我的建議：(a)。** 兩支 gate 都寫好了、都會 exit 1，只是沒人保證它們會被跑——這是投報率最高的
一項。(c) 會動到**已鎖定的 product_info 內容格式**（CLAUDE.md Architecture Lock 第 2 條），
應另開 CR 並先確認業主是否同意動 frontmatter。

---

## 9. Suggested Implementation Order

### 步驟 0 — 不等裁決，立即執行（CIA 豁免）

| # | 動作 | 為什麼豁免 | 驗證 |
|---|---|---|---|
| 0-1 | 修 `api/realtime/gdpr_hard_delete_cron.py`：`SELECT id, tenant_id`（`:102-110`）+ 呼叫改 `hard_delete(request_id=..., tenant_id=str(row[1]), actor_user_id=None)`（`:118-121`）| 單一函式內、無 contract 變動的 bug fix | — |
| 0-2 | **同一 commit** 修 `api/tests/test_gdpr_hard_delete_cron.py:60/:96/:127` 三個 fake 簽章為 `(*, request_id, tenant_id, actor_user_id)` | 同上 | 三支測試須在**未改 fake 前先紅**（證明它們原本在說謊），改後綠 |
| 0-3 | agent 六處 `resp.text[:N]` 改為只記 `status_code`（`agent/lockcore/channels/line_gateway.py:361/:461/:464/:539/:905/:950`）；`api/services/consent_service.py:123` 的 `ip_address` 改遮蔽 | log message 字面修改 | `agent && pytest` 綠 |
| 0-4 | 修 `api/realtime/family_review_sla_cron.py:3` docstring「每日掃」→「每小時掃」（與 `:25` 的 3600 一致）| 註解修正 | — |
| 0-5 | 修 `api/services/audit_log_service.py:8` 的過期註解（「本期不做 tenant 過濾」已被 CR-0183 方向推翻）—— 改為指向本 CR 的 D1 | 註解修正 | — |

> **0-1 與 0-2 必須同一個 commit**。只修 cron 不修測試，下一次有人改簽章時同樣的事會再發生一次。

### 步驟 1 — 等 D1 / D3 / D4 裁決（P0，序列）

```
D1 裁決
 ├─ 選 (b) → 1-1  收緊 audit list/export 角色（2 個端點各一行）
 │            驗證：品牌 admin token 打 /audit/events 得 403；平台 admin 仍 200
 │            ⚠️ 上線前通知營運：品牌後台稽核頁會失效
 └─ 選 (a) → 1-1' migration 加 tenant_id + 兩處 WHERE + backfill 策略（需再答 D2）
              驗證：跨租戶 token 對照測試 + migration 冪等連套兩次 + drift check

D3 裁決（可與 D1 平行）
 └─ 1-2  prod dry-run 盤點（唯讀 SELECT，經 cloud-sql-proxy --gcloud-auth）
         → 回報符合條件的列數與其 FK / legal-hold 狀況 → 再依 D3 放行

D4 裁決
 └─ 1-3  【前置，不論 D4 選什麼都要做】T0 快照 line_user_id：
         migration 為 saas.forget_request 加 line_user_id_snapshot；
         soft_delete 的 UPDATE users 同句清 line_user_id（gdpr_forget_service.py:296-304）
         驗證：新增測試斷言軟刪後 users.line_user_id IS NULL 且 snapshot 有值
    └─ 1-4  依 D4 選項接 agent 記憶清除（(b) 需先定服務間認證與失敗處置）
```

### 步驟 2 — 可平行（P1，D5–D8）

| 分支 | 內容 | 相依 | 驗證 |
|---|---|---|---|
| A | D6 擴大 `_has_active_legal_hold` 關聯鍵 | 無 | 新增測試：他人上傳的 legal_hold 證據亦擋下 forget（423） |
| B | D5 拆 `set_legal_hold` 為 set / release | 無 | release 缺 reason / 缺 ADR 編號 → 400；成功 → `audit_events` 有紀錄 |
| C | D7 加 `notice_sent_at` + `expected_release_at` 必填 | 無 | `deny_legal_hold` 未帶 `expected_release_at` → 400 |
| D | D8 管道級 logging filter | **必須在 0-3 之後** | `caplog` 測試：打進 logger 的手機/email/身分證在最終輸出被遮蔽；且既有 `%s` 延遲格式化語句不變形 |

> A / B / C 三支互不相干可完全平行；D 必須排在 0-3 之後（先止血再基建）。

### 步驟 3 — 低相依，隨時可插（P2，D11 / D12）

| # | 內容 | 驗證 |
|---|---|---|
| 3-1 | D11 `sop_performance_service` 加 `family_review_rate_pct`（`family_reviews` LEFT JOIN `sop_drafts`）+ `api/openapi.yaml` + 前端 | `api/tests/test_sop_performance.py` 新斷言；`shared-contract` 型別同步 |
| 3-2 | D12 `.github/workflows/knowledge-provenance-gate.yml` | 故意破壞一個 reference 的 frontmatter → workflow 紅；還原 → 綠 |

### 步驟 4 — 等法務（D9，不排期）

Irene 回覆前**不動 code**。回覆後若為 (b)，另開 CR。

### 步驟 5 — 收尾（每步完成後都要做）

1. 本檔 §8 對應決策下補「✅ 裁決結果 + commit sha」
2. `CHANGELOG.md` `[Unreleased]` 的 Added / Changed / Decisions
3. 有架構決策（D1 選 (a)、D4 選 (b)）→ 新開 ADR（append-only）
4. 更新 `docs/uat/static-walkthrough-20260803/` 對應 TC 的「判定更正」標注
   —— 特別是 **TC-COMPLIANCE-08 的實質錯誤**（§4）必須更正，否則下一輪走查會沿用錯誤前提

---

## 附錄：本 CR 的查證方式與限制

- 全部技術結論以 `Read` 開檔覆核，行號為 `grep -n` 實測；未使用走查文件的二手行號。
- **未連 prod、未跑任何 pytest**（避免污染 5433 UAT 庫）。§5.1 的「從未成功執行過」是
  **靜態推論**（必填參數缺失 → 必然 `TypeError`），非 runtime 觀測；prod 的實際錯誤計數
  需由 D3 的 dry-run 或查 Cloud Run log 佐證。
- §5.2 的「跨租戶可讀」前提是**單庫多租戶**。若某個品牌實際跑在獨立 GCP 專案（
  `23_Deployment_Guide.md:127` 的目標架構），該部署不受影響。**現行 prod 屬哪一種，
  我無法從程式碼確認** —— 這正是 D1 要裁決的事。
- §5.3「軟刪後 `line_user_id` 沒被清」是本次回查證的**新發現**，走查文件未涵蓋；
  依據是 `gdpr_forget_service.py:289-304` 的 UPDATE 欄位清單與 `SQL/Schema.sql:131` 的欄位語意。
- `smartlock-docs/` 全程唯讀。§2.2 列出的 4 處正典矛盾**未修改任何原文**，依規定於本 CR 內陳述。
