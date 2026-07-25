# CR-0181 — 報價 Expire 全面改 7 天（validity + confirm_token TTL），expired 單保留

- **日期**：2026-07-25
- **來源**：0723 團隊會議決議 §十三（`meetings/20260724/20260723 lock-AI 會議記錄.md`）＋業主 0725 裁決
- **狀態**：業主已裁決，依 §9 實作中
- **分支**：`feat/cr-0181-quote-expire-7d`（L2）

## §1 背景與動機

0723 會議討論報價 Expire 處理：Irene 提出「Reject 與 Expire 是否回同一個地方」，團隊共識是 48hr 太短（產業特性，客戶常隔幾天才回頭）。會議決議（記錄 §十三）：

1. Expire 時間拉長為 7 天
2. 不做 UI 讓使用者調整，需要調整時改資料庫參數化
3. 過了 7 天完全清掉，不留 Expire 單

盤點 code 後發現「48hr」在系統中對應**兩個不同旋鈕**，會議記錄未區分：

| 旋鈕 | 現值 | 出處 |
|---|---|---|
| 報價本身有效期 `_VALIDITY_DAYS_NORMAL/URGENT` | 14 天（一般）/ 3 天（急件） | BR-M04-05 / CR-0044，已 DB 參數化（M18 `quote_validity_policy`，fallback 寫在 code） |
| 客戶確認連結 confirm_token TTL 上限 `_CONFIRM_TOKEN_MAX_DAYS` | 2 天（48h） | FR-API-02 合約明文；`_ttl_days_from` 取 min(報價有效期, 48h) |

會議成員實際感受到的「48hr 就死」是 confirm_token TTL——客戶收到的連結 48 小時失效，即使報價本身還有效。

## §2 變更範圍（業主裁決版）

1. **報價有效期 fallback**：一般 14 天 → **7 天**；急件 3 天 → **7 天**（統一 7 天）。M18 config `quote_validity_policy` 仍為 runtime SSOT（DB 改值即生效、不做 UI），本 CR 只改 code fallback 預設並同步 prod config。
2. **confirm_token TTL 上限**：48h（2 天）→ **7 天**。維持「取 min(報價有效期, 上限)、至少 1 天」邏輯不變，只改上限常數。
3. **expired 單保留**：業主推翻會議決議第 3 點——**不做清除**。現行為（expired 只改狀態、資料保留）即為正確行為，不新增 purge job。

### 明確不動的相鄰 48h（避免誤傷）

- `technician_kyc_service.py:TOKEN_TTL_HOURS = 48`（KYC 上傳 token，與報價無關）
- `work_order_service.py:_AUTO_CONFIRM_DEFAULTS`（公單完工 48h 自動確認，Q063，與報價無關）
- `work_order_service.py:hours_by_urgency`（派工時效 SLA，與報價無關）

## §3 CIA 七面向

| 面向 | 命中 | 說明 |
|---|---|---|
| User/Business flow | ✅ | BF 報價流程的過期時點改變。精確語意：有效期錨定**建立時**（now+7d，send 不重錨），客戶收到連結後的實際窗口＝min(報價剩餘有效期, 7d)——內部審批停留 N 天則客戶窗口 7−N 天（原制下同樣自 create 錨定，此非新問題） |
| API contract | ✅ | FR-API-02 合約明文「confirm_token TTL=48h」→ 改 7 天，屬 tier-2 契約變更 |
| Domain model | ❌ | quote 實體結構、狀態機均不變 |
| DB schema | ✅ | **migration 115**（retire 054 種的 14/3 全域 active row → 7/7；含 namespace 防呆 upsert，standalone 可套）；無表結構變更 |
| External integration | ❌ | LINE 通道機制不變（僅文案若提到 48 小時需同步） |
| Test plan | ✅ | `test_cr_api02_confirm_token_ttl.py` 等鎖 48h 行為的測試需改寫 |
| Architecture boundary | ❌ | 無 |

## §4 觸點盤點（workflow `quote-expire-7d-sweep` 65 觸點；29 需改，以下為核銷結果）

### 已修改

| 觸點 | 變更 |
|---|---|
| `api/services/quote_engine_service.py:45` | `_VALIDITY_DAYS_NORMAL/URGENT` 14/3 → 7/7（fallback） |
| `api/services/quote_engine_service.py:706` | `_CONFIRM_TOKEN_MAX_DAYS` 2 → 7（min/至少 1 天 clamp 邏輯不動） |
| `SQL/migrations/115-quote-validity-7d.sql`（新增） | **關鍵**：054 已把 14/3 種進 `saas.config_version` 全域 active row，DB 值覆蓋 code fallback——retire 舊 row＋插入 7/7 active；冪等（拋棄式 PG16 二套驗證）；已登記 MIGRATION_REGISTRY |
| `api/services/config_service.py:36` | `DEFAULT_CONFIG["quote"]` 佔位 14/3 → 7/7（quote engine 不讀它，但避免兩套 config 值矛盾） |
| `api/routers/quote_v2.py:38` | `urgent` Field description「3d」→「7d（CR-0181 拉平）」 |
| `api/openapi.yaml` ×6（L54/495/519/5394/5431/5489） | 48h 合約文字全改 7d＋註 CR-0181；state 機補「expired row retained, never purged」 |
| `web/{4 站}/src/types/api.generated.ts` | `generate-api-types.sh` runtime 再生（含順帶收斂 CR-0177 login schema 漂移）；四站 `tsc --noEmit` 全綠 |
| `api/tests/test_cr_api02_confirm_token_ttl.py` | 6 案改鎖 7 天（cap=7、30d 截 7、3d 跟報價、下界 1 天保留） |
| `api/tests/test_config_defaults_p1c.py`、`test_cr_0044_esales_config.py` | 斷言 14/3 → 7/7；後者 component 測試需 DB 先套 115 才綠（docstring 已註明） |
| `smartlock-docs/enterprise/04_SRS.md` §3.2 後、`08_User_Flow.md` UF-03 圖後＋例外表後 | append-only 標注 ×3（不改寫原文） |
| `SQL/migrations/MIGRATION_REGISTRY.md`、`CHANGELOG.md` | 登記＋Changed 條目 |

### 查證後不動（重點）

- **expired 單清除**：code 中 `state='expired'` 唯一寫入點＝accept 時 lazy 檢查（`quote_engine_service.py:565`），無任何 purge/cron——「保留」即現行行為，零改動。
- **「對話自動結案→報價同步失效」（08_User_Flow 例外表 #4）**：純文件描述，code 無此連動——7 天有效期不會被 BR-CONV-01 對話 48h 結案吃掉（已入標注）。
- **相鄰 48h 全數不動**：KYC token（`technician_kyc_service`）、公單完工自動確認（Q063）、派工 SLA、SLA quote_expiring 24h 提醒（營運告警非過期判定）。
- **前端**：報價公開頁/後台/i18n 全吃 API 回傳 `expires_at`，無寫死天數；SLA 橫幅 threshold 隨 payload。無報價有效期調整 UI（符合會議「不做 UI」）。
- **LINE/agent**：話術全為泛稱「有效期限」無數字；SOP/SOUL 禁 AI 報價，無 48h 話術。
- **`api/models/generated.py:582`** `valid_until`「預設 48h」：2026-05-06 舊 spec 殘留，現行 openapi 無此欄、`generated.Quote` 無人 import——known-stale 不 regen（避免無關大 diff）。
- **`config-governance` 泛用頁**：quote_validity_policy 在 DB 有值後會出現在該頁可編輯（治理走 draft→rollout 雙簽），非「使用者調整 UI」，不動。

### 已知環境事項

- `test_cr_0136_observability.py::test_migration_drift_check_passes` 在 pytest 環境（連 5433 庫）**pre-existing 紅**：本機庫 100-114 未套（與本 CR 無關），115 自然加入清單；standalone 檔案層 drift-check ✅。
- 雲端 `saas.skill_revision` 若曾被品牌後台編輯出含「48 小時」話術，repo 內查不到——prod 套用腳本附驗證查詢。

## §8 Human Decisions Required

| # | 決策點 | 業主裁決 | 時間 |
|---|---|---|---|
| 1 | 會議的「48hr」指報價有效期還是 confirm_token TTL？ | **兩個都改 7 天**（「都改七天」） | 2026-07-25 |
| 2 | 急件有效期 3 天是否也拉平為 7 天（BR-M04-05 一般/急件區分消失）？ | 含在「都改七天」內，急件同 7 天 | 2026-07-25 |
| 3 | 會議決議「過 7 天完全清掉」是否實作 purge？ | **不清除，expired 單保留**（「expire保留」），推翻會議決議該點 | 2026-07-25 |

### 進度

- ✅ §9 步驟 1–4 done（feat/cr-0181-quote-expire-7d）：code 三常數＋migration 115（雙情境冪等驗證：054→115→115、全新庫→115→115）＋openapi 六處＋runtime spec 重匯＋四站型別再生（tsc 全綠）＋正典標注 ×6（04_SRS/08_User_Flow×2/02_BRD/03_PRD×2/20_Test_Cases）＋測試 3 檔（unit 347 passed）。對抗性覆核 2 lens 完成，4 should-fix 全數修正（生效條件矛盾統一為「無條件套 115＋重佈」、openapi 錨點措辭、115 namespace 防呆、正典補標注）。
- ⏳ §9 步驟 5 待業主：`!` 執行 `~/apply-quote-expire-7d.sh`（套 115 → 驗證 → 重佈 smart-lock-api）。

## §9 Suggested Implementation Order

1. `quote_engine_service.py`：`_VALIDITY_DAYS_NORMAL=7`、`_VALIDITY_DAYS_URGENT=7`、`_CONFIRM_TOKEN_MAX_DAYS=7`，同步註解（BR-M04-05 / FR-API-02 標注 CR-0181 修訂）
2. 依 §4 觸點清單同步：前端文案、LINE 訊息模板、`api/openapi.yaml` TTL 描述
3. 測試：改寫 48h 斷言為 7 天，補「急件=7 天」「fallback=7 天」案例；跑 scoped pytest + 全套
4. `smartlock-docs` 對應段落加標注（append-only，不改寫原文）；CHANGELOG `[Unreleased]`
5. prod 生效打包（業主 `!` 執行 `~/apply-quote-expire-7d.sh`）：**無條件**套 migration 115（冪等；不查證 prod 是否套過 054，兩種世界都被涵蓋）→ 驗證 config 讀值 → 重佈 smart-lock-api

## §10 過渡期存量（知情不動）

- **既存報價的 `expiry_at` 不回填**：改制前建立的一般單維持原 14 天、急件維持原 3 天到期（不延長不縮短）。
- **已送客戶的確認連結不自動延長**：exp 已烙進 HMAC token payload（stateless），重佈後 in-flight 的 sent 報價仍是舊 48h 連結——連結逾期時**重送報價**即取得 7 天新連結（客服既有操作，無需新功能）。
- **SLA `quote_expiring` 告警閾值 24h 不動**（`SLA_QUOTE_EXPIRING_MINUTES`，營運提醒非過期判定）；7 天有效期下「送出 24h 未回就提醒客服」語意仍成立，要調屬營運參數。
