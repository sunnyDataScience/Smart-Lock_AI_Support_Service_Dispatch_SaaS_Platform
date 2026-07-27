---
title: 測試計畫（Test Plan）
version: 1.1
status: active
owner: QA Lead
last-updated: 2026-07-23
upstream:
  - smartlock-docs/enterprise/04_SRS.md
  - smartlock-docs/00_platform/P1/05_platform_architecture_L1.md
  - smartlock-docs/00_platform/P2/09_integration_data_flow.md
  - smartlock-docs/api/P3/13_security_checklist.md
  - smartlock-docs/agent/P3/13_security_checklist.md
  - smartlock-docs/web/P3/13_security_checklist.md
  - smartlock-docs/data-pipeline/P3/13_security_checklist.md
  - smartlock-docs/enterprise/05_NFR.md
  - smartlock-docs/enterprise/20_Test_Cases.md
---

# 19. 測試計畫（Test Plan）

> 本文件回答：本平台**測什麼、用什麼策略與工具、在哪些環境測、各階段進入/退出條件為何、覆蓋率與品質門禁如何定義**。
> QA 執行以 [./規格統控整理/SmartLock_整合測試計畫.xlsx](./規格統控整理/SmartLock_整合測試計畫.xlsx) ⑧「客戶需求與測試情境」及⑨「測試案例與執行紀錄」為主；領域檢核與端到端旅程收於隱藏附錄 C，需求/QTM/架構追溯收於隱藏附錄 A/B 與 [./20_Test_Cases.md](./20_Test_Cases.md) §2.1，供 QA Lead/SA 審核。驗收框架見 [./22_UAT_Report.md](./22_UAT_Report.md)。

## 1. 文件元資訊

| 欄位 | 內容 |
|---|---|
| 對應需求文件 | [./04_SRS.md](./04_SRS.md)（FR 編號源）· [./05_NFR.md](./05_NFR.md)（SLO/指標源）· [./03_PRD.md](./03_PRD.md)（KPI 驗收源）|
| 讀者 | QA Lead、各子系統開發、Release Manager、業主（品質門禁裁決）|
| 維護節奏 | 每 release cycle 覆核；門檻變更須業主簽核 |
| 受控基線 | 65 FR + 106 NFR；TS-01～TS-12；171 筆 QTM；QA 追溯缺口 0，含未核定門檻者明確阻擋通過簽核 |
| 追溯主鍵 | `04_SRS/05_NFR REQ ID` → `QTM-<REQ ID>` → `TS` → 指定 `TC` → SIT/UAT 證據 |

### 1.1 受控系統測試情境基線

<!-- BEGIN GENERATED QA SCENARIO BASELINE -->
> 此表由 `_relations/rq_verified_by_tc.yaml` 的 `ts` 欄推導；旅程層驗收見 `28_Scenarios.md` 與《整合測試計畫》④，需求層覆蓋見 §2.1。

| 情境 ID | 情境 | 優先 | 主要測試方法 | 關聯 REQ 數 | 追溯基線 |
|---|---|---|---|---:|---|
| TS-01 | LINE AI 自助與轉真人 | P0 | 送文字/照片/急件/假簽章/重送→對話、問題卡、escalation 對帳 | 11 | _relations/rq_verified_by_tc.yaml |
| TS-02 | 問題卡→報價→開單 | P0 | 草擬卡→補齊→quote v1→送客→確認→CS 1-click→WO created | 7 | _relations/rq_verified_by_tc.yaml |
| TS-03 | 自動派工與技師接單 | P0 | 5→10→20km 媒合→指派→技師接/拒/逾時→品牌狀態與投影對帳 | 7 | _relations/rq_verified_by_tc.yaml |
| TS-04 | 現場、加價、requote 與結案 | P0 | 到場→施工→三種加價邊界→客戶接/拒→存證→結案 gate | 4 | _relations/rq_verified_by_tc.yaml |
| TS-05 | 收款、退款、帳本與結算 | P0 | 收款→對帳→退款分層→月結→commission event→reconcile | 4 | _relations/rq_verified_by_tc.yaml |
| TS-06 | 技師註冊、KYC 與生命週期 | P0 | 註冊→敏感文件→審核→品牌授權→排班→停權/復權 | 1 | _relations/rq_verified_by_tc.yaml |
| TS-07 | 知識精煉 HITL 閉環 | P0 | 汲取→提煉→diff→核可/拒絕→雙路發佈→來源/租戶對帳 | 8 | _relations/rq_verified_by_tc.yaml |
| TS-08 | 租戶、OIDC、RBAC 與 License 開通 | P0 | 品牌申請→核准→org/License→bundle/建庫/綁 LINE→角色矩陣負測 | 15 | _relations/rq_verified_by_tc.yaml |
| TS-09 | 資料、migration 與 audit 可重現 | P0 | 從空庫/舊版套 migration→重套→注入 drift→跑 raw/bronze/silver→驗 hash | 12 | _relations/rq_verified_by_tc.yaml |
| TS-10 | 安全、隱私與合約紅線 | P0 | 全端點矩陣→攻擊/跨租戶→forget/legal hold→影像 double gate→Family review | 35 | _relations/rq_verified_by_tc.yaml |
| TS-11 | 效能、容量、降級與可觀測 | P1 | 階梯壓測→斷 LLM/Redis/Kafka/OHS/Casdoor→觀察降級、lag、alert、recovery | 16 | _relations/rq_verified_by_tc.yaml |
| TS-12 | Flow/Vertical Pack/Agent Config 治理 | P1 | 匯入 pack→非法 DSL→高風險 HITL→canary→SLO halt→rollback→audit 對帳 | 0 | _relations/rq_verified_by_tc.yaml |
<!-- END GENERATED QA SCENARIO BASELINE -->

## 2. 測試範圍

### 2.1 In-Scope（6 系統 + 平台整合層）

| 系統 | 測試重點 | 深度參考 |
|---|---|---|
| **agent**（LockCore LINE Bot AI 客服）| LINE webhook 驗簽、Turn 狀態機、工具白名單、記憶隔離、escalation 建卡、AI 安全紅線 | `../agent/P1/05_architecture_and_design.md` |
| **api**（FastAPI 派工控制平面）| 80+ 端點契約、工單/報價/派工/結算狀態機、RBAC enforce、SoD、冪等、GDPR | `../api/P1/05_architecture_and_design.md` |
| **web**（Next.js 多站前端）| 多 portal 路由 gate（UX 層）、E2E 使用者旅程、a11y、後端授權為唯一邊界之驗證 | `../web/P3/13_security_checklist.md` |
| **data-pipeline**（Medallion + SQL migration）| bronze-only sourcing、migration 冪等/drift、三庫一致性 | `../data-pipeline/P3/13_security_checklist.md` |
| **knowledge-refinery**（知識精煉 HITL）| draft 審核後寫入、OIDC reviewer、LiveSkill draft、未核可零落地、references ↔ pgvector 同源 | `../../knowledge-pipeline/refinery/`；`./15_SDS.md` §9 |
| **technician-platform**（技師共享池）| `API_SURFACE=tech` 路由面、tech authority、現行媒合與目標 OHS 差異、Kafka opt-in、CQRS 投影、佣金對帳 | `../../api/`；`../../web/tech-portal/`；`../../SQL/tech_authority/`；`./15_SDS.md` §7 |
| **00_platform**（整合層）| 跨系統整合點（LINE/Vertex/Casdoor/Kafka）、四方 RBAC、可觀測性 SLI | `../00_platform/P2/09_integration_data_flow.md` |

### 2.2 Out-of-Scope（明列）

- AI 自主 final quote（**永久禁止**，僅做負向測試，見 20_Test_Cases §5）。
- AI 影像內容辨識（合約 SOW 2.1(4) 永久禁用，violation=0 為紅線 gate）。
- 跨平台統一取消入口（LINE/Web/電話）、bulk cancel/dispatch、GDPR 自助 portal —— 🔜 規劃中，Phase II 啟動再納入。
- 零件級（part-level）保固自動化 —— 🔜 規劃中（BOM 欄位已預留，先以整機保固 fixture 覆蓋）。

## 3. 測試策略與測試金字塔

```
            ┌──────────────┐
            │ Manual UAT   │ ← 業主簽核（含合約紅線），見 22_UAT_Report
            ├──────────────┤
            │ E2E + Perf   │ ← Playwright 主流程 + 負載測試
            ├──────────────┤
            │ Contract     │ ← OpenAPI 契約 / Kafka event schema（consumer-driven）
            ├──────────────┤
            │ Integration  │ ← DB + LINE mock + LLM mock
            ├──────────────┤
            │  Unit        │ ← 覆蓋率 ≥ 80%（GA 硬門檻）
            └──────────────┘
              Forbidden Eval（橫切，block-deploy gate）
```

| 層級 | 範圍 | 工具 | 負責 |
|---|---|---|---|
| Unit | service/函式/業務規則 | pytest + pytest-cov | dev |
| Integration | DB、adapter、外部 API（mock） | pytest-asyncio（+ testcontainers）| dev |
| Contract | OpenAPI 相容 + Kafka event schema | schemathesis（🔜 規劃中納 CI）+ consumer-driven 契約測試 | QA |
| E2E | LINE → AI → 問題卡 → 工單 → 結案（happy + edge）| **Playwright** | QA |
| Performance | 併發負載 / SLO 驗證 | 壓測工具（k6 🔜 規劃中導入）| QA + Ops |
| Security | 授權負向、SoD、prompt injection、跨租戶隔離 | pytest 負向案例 + injection 題庫 | QA + Sec |
| Compliance | sentiment 門檻、家族覆核、影像禁用、GDPR forget | 自動 eval + 人工 UAT | QA + 法務 |
| Forbidden Eval | AI 越權紅線題庫（block-deploy）| pytest + LLM-judge | QA + Domain Expert |

**對抗思維原則**：每條 KPI 先想 gaming surface（如自助率把硬規則案件混進分母）、每條 NFR 找 negative case（50 併發 OK 不代表 500 併發不雪崩、GDPR forget 遇 legal-hold 怎辦）。

## 4. 測試工具鏈與框架

| 子系統 | Unit / Integration | E2E | 備註 |
|---|---|---|---|
| agent | `cd agent && pytest`（`agent/tests/`，含 `test_e2e_mock_turn.py` / `test_skills_loaded.py` / `test_tool_allowlist.py` / `test_litellm_provider.py` / `test_line_gateway.py` / `test_memory.py`）| — | 主測試入口 |
| api | `cd api && uv run pytest -m unit`（PR gate）；`-m component`（需 live DB + 全 migration）| — | component 套件排 nightly |
| web | TypeScript strict + lint | `cd web/<站台> && npx playwright test`（`web/<站台>/tests/e2e/`，四站拆分後各自持有，ADR-028）| Playwright 為唯一 E2E 框架 |
| data-pipeline | pytest（migration 冪等 / drift 驗證）| — | drift-check 進 CI 為 P0 行動項 |
| technician-platform / knowledge-refinery | `api/tests/test_technician_*` + `knowledge-pipeline/refinery/tests/` | `web/tech-portal/tests/e2e/` + refinery 人工審核旅程 | 程式已落地；Kafka、OIDC/License、refinery 排程與 CD 依部署條件列 PARTIAL |

命名慣例：測試檔 `test_<主題>.py`；CR 對應測試 `test_cr_NNNN_<slug>.py`；E2E spec `<flow>.spec.ts`。

## 5. 測試環境（三層 + 三庫物理隔離）

### 5.1 環境分層

| 環境 | 資料來源 | PII 狀態 | Refresh 機制 |
|---|---|---|---|
| **local / sandbox** | synthetic（pytest factory）| 全假 | dev 隨需 reset（`redeploy-local` 全量重建 + smoke）|
| **CI** | synthetic + 匿名化歷史案例 | 全匿名 | 每 pipeline 重建 |
| **staging** | synthetic + 匿名化歷史案例 + mock LINE channel | 全匿名 | 每週 reset |
| **prod-mirror（UAT）** | 匿名化 + 業主同意之抽樣真實案例 | 匿名 + opt-in | 每 UAT 輪次 reset |

### 5.2 三庫物理隔離下的測試資料

多租戶隔離採**一品牌一 DB 物理隔離**（`../api/P3/13_security_checklist.md` B-01）：

| 庫 | 連線 | 測試要求 |
|---|---|---|
| 品牌庫 `lock_AI_data`（×N，per-brand）| `POSTGRES_URI` | 每品牌獨立 seed；跨品牌讀寫負向測試 |
| 技師權威庫 `lock_tech` | `TECH_POSTGRES_URI` | 技師身分/排班 seed；**漏設 URI 不得靜默 fallback 單庫**（啟動守衛測試）|
| 平台庫 `lock_platform` | `PLATFORM_POSTGRES_URI` | platform_admin 憑證隔離測試（獨立 JWT 密鑰）|

`tenant_id` 欄位級隔離 + RLS policy 為 🔜 規劃中的輔助防線；測試環境設計以物理隔離為主軸。migration 一律純 SQL forward-only，測試環境套用後必驗 `schema_migrations` 與 registry 一致（drift 即 CI 失敗）。

## 6. 測試資料策略

1. **Persona 三維鋪設**：fixture 以「客戶旅程 × tenant 邊界 × RBAC 角色」設計，不為 entity 而 fixture。範例規模：50 名消費者 × 5 品牌 × 3 型號 ≈ 750 個問題卡情境；500 名技師可用性矩陣（技能/地區/品牌授權/檔期）。
2. **Tenant 邊界 fixture**：B2C 家戶 / 建商 A/B（對照組）/ 品牌商 A / 建案子層各一組；每對 tenant 至少 1 讀 + 1 寫跨租戶嘗試，預期 403/404 + audit 記錄。
3. **合成資料**：pytest factory（每個 factory 必帶 `tenant_id`；PII 欄位用 `zh_TW` locale Faker 假資料；禁止未經匿名化的 prod dump）。
4. **PII 匿名化管線**：Extract（唯讀快照）→ Anonymize（姓名/電話/地址/LINE id/簽名全替換）→ Scrub（照片 OCR 偵測證件/車牌/門牌後模糊化）→ Validate（re-scan 零 PII）→ Store（匿名 fixture 入 git + audit 紀錄）。
5. **Failure injection**：webhook 重送、LLM timeout、DB 連線抖動、Kafka consumer lag、quote 過期 cron 等失效情境各配 fixture（比例目標：每一 P0 happy path 至少配 1 個 failure 案例）。
6. **Eval 題庫**：AI 準確率標準題 50 + OOD 20 + 對抗 10；負面情緒 labeled 100 + 反諷 20；**Forbidden 200 題**（final_quote 40 / discount 30 / warranty_free 30 / legal_safety 30 / cross_tenant 30 / image_moderation 20 / other 20）+ 20 題同義改寫抗過擬合。每 sprint 增 ≥10 題輪換。
7. **知識來源治理**：產品知識 references 嚴格源自 `knowledge-pipeline/storage/bronze/`（原 `data/storage/bronze/`，2026-07-09 ADR-029 改名）；PDF 來源只引 URL 不抄內容（測試含 provenance 驗證）。

## 7. 品質門禁與覆蓋率目標

| Gate | 門檻 | 驗證方式 |
|---|---|---|
| **Unit 覆蓋率（GA 硬門檻）** | **≥ 80%** | pytest-cov CI gate |
| Unit 覆蓋率（Alpha 階段目標）| ≥ 70%（過渡目標，GA 前須達 80%）| 同上 |
| P0 FR 覆蓋 | 100%（每條至少 1 happy + 1 alt）| 21_Traceability_Matrix 對帳 |
| P1 FR 覆蓋 | ≥ 90% | 同上 |
| E2E 主流程 | ≥ 4 條（LINE→AI→問題卡→工單→結案 等）| Playwright CI 〔標注 2026-07-10：已掛 `e2e-main-flows.yml`——品牌登入/5 角色 gate/工單 v2/派工佇列 v2/技師 flow ×5 spec＋跨實例 WS（CR-0151）；LINE→AI 入口段屬 agent 面另議〕|
| Forbidden Eval | 每次 deploy pass ≥ 95% + 改寫題 ≥ 90%（**block-deploy**）| eval pipeline |
| 未結 P0 / P1 缺陷 | 0 / 0 | 缺陷追蹤系統 |
| KPI 驗收門檻 | 依 [./03_PRD.md](./03_PRD.md) KPI 定版（負面情緒 ≥90%、家族覆核 100%、影像禁用 violation=0、GDPR forget ≤7d 等合約紅線 100% pass）| eval + 人工 UAT |
| RBAC 授權強制 | **enforce 為上線前 P0 必達門檻**：非授權角色（technician/vendor）寫金流/派工/設定一律 403 | TC-SEC-RBAC-*（GA 退出條件）|

## 8. 分階段測試框架（Alpha / Beta / RC / GA）

| 階段 | 誰測 | 環境 | 目的 | Entry | Exit |
|---|---|---|---|---|---|
| **Alpha** | 內部 / CI 自動 | local compose（api+postgres+seeds）/ CI | 邏輯正確性、契約、紅線自動冒煙 | code merge 至分支 | unit 全綠無 collection error；關鍵 component 套件（完工硬閘/Evidence 治理/異常框架/退款取消 SoD/RBAC/Config）在套齊 migration 的 DB 全綠；P0 spec 缺口清空或業主豁免 |
| **Beta** | 業務代表多角色點測（會計/客服主管 + 營運/派工）| staging + mock LINE | 真實多角色操作、UX、可見性、權限邊界 | Alpha Exit + redeploy smoke 全過 | 點測 checklist 全勾；可見性/權限/硬閘無洩漏；外部依賴未接項標 blocked 可經業主豁免手動跳過 |
| **RC** | QA + 紅線量化 gate | prod-mirror + eval pipeline | 紅線量化（跨租戶 0 洩漏、Forbidden ≥95%、sentiment ≥90%、SLA、hash-chain 篡改偵測）| Beta 通過 | 100 組跨租戶 mutation 0 leakage；月結 cron 實測；audit hash chain 驗證通過；效能 SLO baseline 達標 |
| **GA** | 上線冒煙 + canary | production | 上線健康、監控、初始匯入 | RC gate 全綠 | **unit 覆蓋率 ≥80%**；canary 10%→50%→100% 各觀察段 SLO 不破；P0/P1 缺陷清零；22_UAT 簽核完成 |

**Rollback 觸發條件（GA canary 期間）**：error rate 超過 SLO baseline、30 天 uptime 推算 < 90%、AI 準確率絕對值連 2 日低於門檻、Forbidden Eval 任一 deploy < 95% → 立即回滾前一 revision，並依 [./26_Incident_Postmortem.md](./26_Incident_Postmortem.md) 開事故單。

## 9. 非功能測試計畫

### 9.1 效能（指標定版見 [./05_NFR.md](./05_NFR.md)）

| 項目 | 目標（設計目標值）| 驗證 |
|---|---|---|
| LINE AI 首回應 | p95 < 5s / p99 < 8s | 負載測試 50 併發（V1）/ 100 併發（V2）|
| RAG 檢索回覆 | p95 < 8s | benchmark |
| Admin 後台頁面 | p95 < 2s | RUM |
| OHS 派工媒合 | p95 < 300ms | benchmark（technician-platform）|
| WS 派工推播 | < 1s（同實例）/ 端到端 < 2s | 整合測試 |
| Outbox 事件 lag | p99 ≤ 30s | metric 斷言 |
| 負向：500 併發 ramp-up | graceful degrade（429/罐頭回覆），不得 5xx 雪崩 | 壓測（🔜 規劃中）|

### 9.2 安全（詳細案例見 20_Test_Cases §8/§10）

- 授權：RBAC enforce 負向矩陣（12 角色 × 12 資源 × 4 動作）、deny-by-default、繞過前端直呼 api。
- SoD：initiator/approver/executor 任二相同 → 403 `SOD_VIOLATION`。
- Prompt injection ≥ 50 題攔截 ≥ 95%、誤攔 < 1%；工具白名單外呼叫物理不可達。
- 跨租戶隔離 100 組 mutation 0 洩漏；三庫 URI 啟動守衛。

### 9.3 無障礙

Admin 後台 + 師傅 web + 客戶 LIFF 全面 **WCAG 2.2 AA**：對比 ≥ 4.5:1（金額文字升級 7:1）、觸控目標 ≥ 44×44 px、鍵盤導覽全功能、screen reader（NVDA / VoiceOver）任務成功率 ≥ 90%（n=10）、`prefers-reduced-motion` 支援。

### 9.4 合規

- GDPR forget：兩階段（T0 軟刪 → T+30 硬刪 cron）E2E + legal-hold 衝突路徑（423 + 客戶通知）。
- 影像辨識禁用：pre-commit 靜態掃描 + runtime 雙 gate，violation = 0。
- 家族覆核：SOP publish 前 100% 覆核 + ledger 不可篡改（UPDATE/DELETE 被拒 + hash chain 抽驗）。
- Evidence retention：1y 預設 / RMA +3y / legal-hold 永久，cron 軟刪驗證。

## 10. 缺陷分級與 rollback 觸發

| 級別 | 定義 | 處置 |
|---|---|---|
| **P0** | 金錢錯帳、跨租戶洩漏、授權繞過、合約紅線違反、資料遺失 | 阻斷 release；GA 後觸發即 rollback + 事故流程 |
| **P1** | 主流程斷點、SLA 引擎失效、審計斷鏈 | 阻斷 GA；限期修復 |
| **P2** | 次要功能缺陷、UX 問題、非阻斷效能退化 | 排入 backlog，不阻斷（UAT 可 conditional pass）|

## 11. 角色與職責（RACI）

| 活動 | QA Lead | Dev | Release Mgr | 業主 | 法務/DPO |
|---|---|---|---|---|---|
| 測試計畫維護 | A/R | C | C | I | C |
| Unit / Integration | C | A/R | I | — | — |
| E2E / 契約 / 效能 | A/R | C | I | — | — |
| Forbidden Eval 題庫 | A/R | C | I | C | C |
| 合規測試（GDPR/合約紅線）| R | C | I | A | A/R |
| 階段 gate 裁決 | R | C | A | **A（簽核）** | C |
| UAT 簽核 | C | — | R | **A** | C |

---

*文件結尾 — 19_Test_Plan.md v1.1 / 2026-07-23*
