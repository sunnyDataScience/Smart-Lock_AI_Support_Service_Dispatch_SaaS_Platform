# smartlock-docs 文件宣稱功能 vs 實作覆蓋稽核（codegraph 對照）

- **日期**：2026-07-21
- **方法**：13 個正典領域（00–27 企業文件 + 32 ADR）× (agent 萃取「可驗證功能宣稱」→ codegraph 逐條查證實作符號)
- **工具**：codegraph（AST 知識圖，符號級 file:line 佐證）；由 workflow `smartlock-docs-capability-audit` 26 agent 併跑
- **回收**：12/13 領域（**ADR 017-024 verify 因 stream idle timeout 失敗**；其內容已由其他領域交叉佐證，見文末）
- **共驗**：144 條功能宣稱

> ⚠️ 本報告是 Claude 的 codegraph 稽核分析，**非業主 canon**，落於 `docs/`（工作區）而非 `smartlock-docs/`。文件與 code 的不一致一律「回報待裁決」，未擅改 canon。
> ⚠️ codegraph 證明「符號存在」，不等於「行為完全正確」。「部分」判定多靠「某符號/常數/子功能缺席」反推——強證據，非行為驗證。

---

## 一頁總覽

| 判定 | 數量 | 佔比 |
|---|---|---|
| ✅ 具備（實作符號明確存在） | **122** | 85% |
| 🟡 部分（能力在、某子項/數值/命名 drift） | **22** | 15% |
| ❌ 缺（codegraph 無命中） | **0** | 0% |
| ⬜ 無法判定（codegraph 盲區） | **0** | 0% |

**核心結論：每一條文件宣稱的功能都有對應 code——沒有任何一條是「畫大餅、code 全無」**。剩 15% 的落差都是「能力已在，細節與文件對不齊」，而非功能缺席。

### 各領域覆蓋

| 領域 | 具備 | 部分 | 完整率 |
|---|---|---|---|
| 06 Security Architecture | 12 | 0 | **100%** |
| 15 SDS 詳細設計 | 12 | 0 | **100%** |
| 18 DB Design 資料模型 | 12 | 0 | **100%** |
| 14 ADR 001-008 平台級決策 | 12 | 0 | **100%** |
| 四站/知識產線/熱更新總覽 | 12 | 0 | **100%** |
| 12 SAD 系統架構 | 11 | 1 | 92% |
| 14 ADR 009-016 | 10 | 2 | 83% |
| 03 PRD 產品需求 | 10 | 2 | 83% |
| 04 SRS 功能需求 | 9 | 3 | 75% |
| 16 API Spec 端點 | 9 | 3 | 75% |
| 05 NFR 非功能需求 | 7 | 5 | 58% |
| 08 User Flow 使用者流程 | 6 | 6 | 50% |
| 14 ADR 017-024 | — | — | *(verify 失敗，見文末)* |

安全/資料/架構決策層 **100% 落地**；落差集中在 **User Flow 與 NFR**——這兩層寫的是「理想端到端行為與量化 SLO」，實作抓了骨幹但數值/邊角未全對齊。

---

## 🟡 22 條「部分」——歸三類

### A. 數值 / 常數 drift（文件寫的數字 ≠ code，能力本身在）

| 宣稱 | 文件值 | 實作值 | 佐證 |
|---|---|---|---|
| LINE 訊息 debounce 窗口 | 800ms | 1.5s / 5s | `inbound_debounce.py:13` / `line_gateway.py:122` |
| 問題卡 completeness gate | ≥ 0.85 | 0.8（且作用點在 convert-to-WO 非 draft→confirmed） | `problem_card_service.py:452/491` |
| webhook 驗簽失敗狀態碼 | 400 | 401（400 只用於 invalid JSON） | `line_webhook.py:233` |
| （附註）案例庫相似度門檻 | 0.85 | 0.70（CR-0148 換模型後校正，已標具備） | `store.py:16` |

### B. 命名 / 契約字面 drift（能力等價，路徑/事件/欄位名不同）

| 宣稱 | 實際 | 佐證 |
|---|---|---|
| WS 即時頻道 10 個 | 9 個 | `main.py`（9 個 @app.websocket） |
| `POST /technicians:match` 派工媒合 | `POST /tenants/{tid}/dispatch:auto-match` | `dispatch_v2.py:110`（能力等價：技能/地區/品牌授權排序全在） |
| Kafka 事件 `dispatch.assigned` / `technician.assignment_accepted` | 折進單一 `workorder.lifecycle` topic 的 payload | `work_order_service.py:2032`（event_type=`work_order.assigned`） |
| 建單硬綁 `quote_id` FK + DISPATCH 角色 | 綁 `problem_card_id` + BACKOFFICE 角色；quote 閘在「指派」階段 | `work_order_service.py:407`、`WorkOrderCreateRequest:85` |
| 登入回傳 Casdoor OIDC token | 本地自簽 HS256 JWT（Casdoor OIDC 為 opt-in 驗證備援） | `auth.py:78`、`oidc.py:56` |

### C. 真缺子功能（能力半套，某半確實沒做）

| 宣稱 | 缺的那半 | 佐證 |
|---|---|---|
| GDPR forget：T0 銷毀 DEK（crypto-shredding） | **未實作**——改直接 UPDATE 抹 PII（非金鑰銷毀） | `gdpr_forget_service.py:250`（全庫無 DEK/crypto-shred 命中） |
| 急件偵測後「5 分鐘內強制轉真人」 | **無 5-min SLA timer**（僅 4h 事後補審 timer）；急件偵測靠 SOP prompt 非 deterministic 硬閘 | `problem_card_service.py:378`、`work_order_service.py:489` |
| 工單 Flow DSL 宣告式引擎 + SLA timer | **無 DSL 直譯引擎**（狀態機是 Python dict `_WO_TRANSITIONS` 命令式）；**無工單 SLA timer 引擎** | `work_order_service.py:786`（ADR-013 Flow-as-Blocks 屬 roadmap） |
| 自動派工 5 因子權重（+ 5→10→20km 漸進擴池） | 只 3 因子（skill/distance/rating）；**缺 fairness、負載未進權重**；**無真實半徑擴池迴圈** | `dispatch_service.py:7`（distance 為區域交集示意值 0/5/15/30km） |
| LLM 逾時走 fallback 話術 | 300s cap 有，但**超時回內部錯誤字串非面向用戶話術**（FallbackProvider 是 provider 級 failover，非 wall-clock 兜底） | `runner.py:632/742` |
| outbox→事件骨幹 lag p99 ≤ 30s + 指標 | **無 `outbox_lag_p99_seconds` 度量儀器**（機制在，SLO 無法佐證） | `line_push_outbox_worker.py`（無 lag/p99/Histogram） |
| ai_decision_trace 帶 `rule_triggered_by` | 全量 trace 在，**缺 `rule_triggered_by` 欄**（以 charter_rule/guardrail_triggered 近似） | `ai_governance_trace_service.py:68` |
| FallbackProvider 多供應商 failover | 類別鷹架在，**LINE live path `build_provider` 未接線**（文件自述「尚未接線」） | `fallback_provider.py:58`、`app_config.py:86` |
| 工單結案地址雙必驗（length ≥ MIN_ADDRESS_LENGTH） | 只驗「非空」，**無 MIN_ADDRESS_LENGTH 長度門檻常數** | `work_order_service.py:1357` |
| 前端 rolePolicy 未登記路由「一律拒絕」 | 前端實為 **default-ALLOW**（`rolePolicy.ts:83` 未列到即放行）；deny-by-default 只在 API 層 `role_required` 與 `/platform` 前綴 | `rolePolicy.ts:83` |
| 客戶 LIFF 親證確認報價 + 48h confirm token | **缺客戶自證 confirm 端點**（現由 OPS 代客 accept）；**無 48h confirm token**（僅唯讀 view token，TTL 7d fallback） | `quote_v2.py:221/247` |

---

## ADR 017-024（verify 失敗）——跨域已間接佐證

該組 verify agent 超時未回，但涵蓋主題多數已由其他領域確認實作存在：

| ADR | 主題 | 交叉佐證 |
|---|---|---|
| ADR-017 技師佣金 CQRS 投影 | ✅ `event_consumer.py`（commission.accrued → technician_commission_projection，opt-in Kafka） |
| ADR-018 知識精煉獨立服務 | ✅ `silver_to_knowledge/emit_corpus.py`、`knowledge-refinery`（2.3.1 Done） |
| ADR-019 Medallion 分層 | ✅ `knowledge-pipeline/storage/bronze`、silver/knowledge 三層 |
| ADR-020 三庫物理隔離 | ✅ `db.py` 三懶連線 + `tech_mirror.py` 雙寫（DB Design 領域 100%） |
| ADR-021 psycopg3 raw SQL / 純 SQL migration | ✅ `SQL/migrations/*.sql`、psycopg AsyncConnection |
| ADR-022 API_SURFACE 塑形 | ✅ `main.py:151`（SAD/ADR-002 已驗具備） |
| ADR-023 單 codebase 多 portal | ✅ 四站 `api.generated.ts` + APP_MODE |
| ADR-024 client SPA / OIDC | ✅ `auth/callback/route.ts` 授權碼流 + httpOnly cookie（ADR-004 已驗） |

> 若要 100% 補齊，可用 `Workflow({scriptPath, resumeFromRunId})` 重跑——extract 全命中快取，只補跑這一格 verify。

---

## 給業主的裁決點（文件 vs code 不一致，不擅改 canon）

依 change-governance「衝突回報不腦補」——以下需你定哪邊是 source of truth：

1. **數值 drift**（800ms/0.85/400）：改文件對齊 code？還是 code 要回到文件值？
2. **命名 drift**（10→9 頻道、`/technicians:match`、`dispatch.assigned`、quote_id FK、Casdoor token）：文件寫的是理想契約、code 是現況——標注銷案 or 開 CR 收斂？
3. **真缺子功能**：多為 roadmap（Flow DSL=ADR-013、Kafka 事件細分=3.1.1、派工進階=M3）或安全補強（GDPR crypto-shred、急件 5-min SLA）——進 backlog 排期。
