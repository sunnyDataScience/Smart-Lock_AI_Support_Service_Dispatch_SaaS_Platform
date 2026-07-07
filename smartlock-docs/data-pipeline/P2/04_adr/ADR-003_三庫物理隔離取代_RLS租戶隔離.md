# ADR-003: 三庫物理隔離取代 RLS 租戶隔離

**狀態：** 已接受（物理隔離運作中；RLS 骨架成死碼未清算，見 §4）| **日期：** 2026-07-07（回溯記錄現況）

> ⚠️ 本 ADR 回溯記錄「租戶隔離策略從 RLS 邏輯隔離切換到一品牌一 DB 物理隔離」的決策，並**誠實記載切換未清算的代價**：schema 內 `tenant_id`/`saas.tenant`/RLS 骨架成為死碼/半成品，誤導開發者以為多租戶邏輯隔離已就緒。RLS 去留須先過 ADR-0030 tier-1 裁決。

---

## 1. 背景與問題

Smart Lock 是 SaaS 平台，多個智慧鎖品牌（Chatlock/Dormakaba/Kaadas…）共用同一套系統，各品牌的客服、派工、工單、金流資料**必須互相隔離**。早期設計走 **RLS（Row-Level Security）邏輯隔離**：所有表帶 `tenant_id`，靠 Postgres row-level policy 過濾。

但在演進過程中出現三個現實壓力：

- **強隔離需求**：品牌是競爭對手，資料外洩風險高；RLS 靠 app 正確設 `SET ROLE`/`set_config`，一旦漏設就跨租戶洩漏（fail-open 風險）。
- **RLS 落地複雜**：7 表 policy + session config + non-owner app role，須先過 tier-1 架構裁決（ADR-0030），遲遲未落地。
- **技師跨品牌**：技師身分需跨品牌共用（一個師傅服務多品牌），與「品牌完全隔離」的 RLS 模型張力大。

**問題核心**：如何在「品牌資料強隔離」與「技師身分跨品牌共用」之間取得平衡，且不卡在遲未落地的 RLS 裁決？

---

## 2. 考量的選項

### 選項 A：一品牌一 DB 物理隔離（現行）

| 面向 | 評估 |
|---|---|
| **隔離強度** | 最強；品牌資料在不同 DB 實例，物理不可跨 |
| **fail 模式** | fail-closed；連錯庫就是連不到，不會靜默洩漏 |
| **技師共用** | 另設技師權威庫 `lock_tech`，品牌庫保留投影 + 雙寫鏡射 |
| **平台治理** | 另設平台庫 `lock_platform`（管理員/品牌申請）|
| **缺點** | 部署擴散（每品牌一庫）；跨庫無交易；一致性靠應用層雙寫；既有 RLS/tenant_id 骨架成死碼 |

### 選項 B：RLS 邏輯隔離（原設計）

| 面向 | 評估 |
|---|---|
| **隔離強度** | 中；靠 policy + app 正確設 session |
| **fail 模式** | fail-open 風險；漏設 session 即跨租戶洩漏 |
| **部署** | 單庫，省實例 |
| **缺點** | 7 表 policy 落地複雜、須過 ADR-0030；技師跨品牌與強隔離張力；競品同庫的信任成本 |

### 選項 C：schema-per-tenant（同庫不同 schema）

| 面向 | 評估 |
|---|---|
| **隔離強度** | 中高；schema 級隔離 |
| **部署** | 單庫多 schema |
| **缺點** | schema 數隨品牌線性增長，migration 需對每 schema 套；PostgreSQL search_path 管理複雜；仍是同實例（物理未分）|

---

## 3. 決策

**選擇：選項 A — 一品牌一 DB 物理隔離（三庫分裂）**

依三個 CR 逐步落地：

| DB | 實例名（範例）| 內容 | 決策 |
|---|---|---|---|
| **品牌庫** | `lock_AI_data` | 全 schema（~100 表），**一品牌一庫** | CR-0110（20260702 會議裁決，`MIGRATION_REGISTRY.md:100`）|
| **技師庫（權威）** | `lock_tech` | 品牌庫子集 6-7 表（技師身分域）| CR-0112 方案 B（20260703，`split-tech-db.sh:1-8`）|
| **平台庫** | `lock_platform` | 獨立 3 表（users/revoked_jti/brand_applications）| CR-0114（`Schema_platform.sql:1-11`）|

**關係語意：**
- **品牌庫全 schema 每品牌部署一份**（物理多租戶，取代 RLS 邏輯隔離）。
- **技師庫 = 權威**；品牌庫保留技師列當**投影**（35 張品牌表 FK 指向 `users/technicians`，投影讓 FK/派工/佣金 JOIN 免改）；一致性靠 api **雙寫鏡射（tech_mirror）** + `--verify` 比對（`split-tech-db.sh:5-8,38-55`）。
- 平台庫 `users` 欄位刻意對齊品牌庫 `users` 子集（含 084 帳號安全欄），使 `core/auth.py` lockout 查詢跨庫共用（`Schema_platform.sql:24-31`）。

**主要 tradeoffs（明確接受的代價）：**
- **部署擴散**：每品牌一庫，套 migration、備份、監控都乘以品牌數。
- **無跨庫交易**：技師庫↔品牌庫靠應用層雙寫，無 ACID 跨庫保證。
- **RLS/tenant_id 骨架成死碼**：既有 schema 內的多租戶邏輯隔離半成品未清算。

---

## 4. 後果

### 正面收益

- **最強隔離**：品牌資料物理分庫，競品資料不可能同庫洩漏；fail-closed。
- **技師跨品牌解**：技師權威庫 + 投影 + 雙寫，兼顧「品牌隔離」與「技師共用」。
- **平台治理獨立**：平台庫承載管理員/品牌申請，與品牌營運資料分離。

### ⚠️ 負面現況（誠實記錄 — RLS 成死碼）

**租戶隔離策略切換未清算**，schema 內留有一整組 RLS 邏輯隔離的半成品，成為死碼 / 誤導風險：

| 死碼 / 半成品 | 狀態 | 佐證 |
|---|---|---|
| `public.work_orders.tenant_id` | multi-tenant 預留欄，**明標「目前 single-tenant」** | `Schema.sql:496`（CR-0031）|
| `saas.tenant` FK target | 最小 FK target 建了，但 RLS 未落地 | `004-config-m18.sql` |
| `saas.*` 多表 `tenant_id` | 補了欄位（如 009 `idx_dc_tenant_status_created`），但無 RLS policy 實際過濾 | `009-data-corrections-v2.sql` |
| RLS 7 表 policy（`004-rls`/`008-rls`）| **預留未落地**，標 🔒，須先過 ADR-0030 tier-1 裁決 | `MIGRATION_REGISTRY.md:24,29` |

> **誤導風險**：開發者看到 `tenant_id` 欄位 + `saas.tenant` FK + RLS 預留 migration，可能誤以為「多租戶邏輯隔離已就緒」，實際上**隔離完全靠物理分庫**，這些 tenant_id/RLS 是**死碼**。

**其他代價：**
- **部署擴散**：品牌×N + 技師 + 平台，手動套用一致性靠人工（P3/13 D-02）。
- **跨庫無交易**：雙寫鏡射無 ACID；`TECH_POSTGRES_URI` 漏設靜默退回單庫（P3/13 D-02b）。

### 影響範圍

- `SQL/Schema.sql`（tenant_id 死碼）、`SQL/migrations/*-rls.sql`（預留）
- `SQL/platform/Schema_platform.sql`（平台庫）
- `scripts/db/{apply-schema-prod,init-platform-db,split-tech-db}.sh`
- api 三面連線 + 雙寫鏡射邏輯
- `00_platform/P2/09 §6 R-05`（跨庫一致性）

### 重新評估觸發條件

- **ADR-0030 tier-1 裁決 RLS 去留**：若永久放棄 RLS → tenant_id/RLS 死碼應標 archived 或移除；若復活 RLS → 與物理隔離的關係需重新定義。
- 品牌數成長到物理分庫成本不可承受 → 重估 schema-per-tenant 或 RLS。

---

## 5. 執行計畫（現況 + 清算）

**現況（已落地）：**
1. 品牌庫全 schema，一品牌一庫（CR-0110）。
2. 技師權威庫 + 投影 + 雙寫鏡射（CR-0112，`split-tech-db.sh --verify`）。
3. 平台庫獨立 3 表（CR-0114，`init-platform-db.sh`）。

**清算（待決策，見 P4/08 §6 建議三）：**
1. **過 ADR-0030 tier-1 裁決**：RLS 是否永久放棄。
2. **若放棄**：`work_orders.tenant_id` 等死碼加明確 `DEPRECATED` COMMENT 或評估移除；`004-rls`/`008-rls` 預留標 archived。
3. **文件明載**：「租戶隔離 = 一品牌一 DB 物理隔離」為唯一策略。
4. **三庫 URI 啟動守衛**：禁止 `TECH_POSTGRES_URI` 漏設靜默 fallback（P3/13 DA-04）。

---

## 6. 選用影響區段

> 本決策顯著改變資料隔離模型與部署拓撲，填 6.2 / 6.6；效能未實質改變，略。

### 6.2 資料模型影響

- **隔離模型**：從「單庫 + tenant_id + RLS」切換到「多庫物理隔離」。
- **技師身分**：技師庫權威 + 品牌庫投影（FK 指向 `users/technicians`），雙寫鏡射同步。
- **死碼**：`tenant_id`/`saas.tenant`/RLS 骨架保留但不生效（見 §4）。
- **同步更新**：P1/05 §8.5-8.6、P4/08 §4.3、`00_platform` DDD Context Map。

### 6.6 部署影響

- **基礎設施**：品牌×N + 技師（:5434）+ 平台（:5435）多庫實例；三個 `*_POSTGRES_URI`（P2/06 §5）。
- **一致性**：跨庫無交易，靠應用層雙寫 + `--verify` 對帳。
- **風險連動**：`TECH_POSTGRES_URI` 漏設靜默退回單庫（P3/13 D-02b）；多庫手動套用擴散（P3/13 D-02）。
- **同步更新**：`00_platform/P1/05`（三庫詞彙）、`00_platform/P2/09 §6 R-05`、P3/13 §D、P4/08 §6 建議三。
