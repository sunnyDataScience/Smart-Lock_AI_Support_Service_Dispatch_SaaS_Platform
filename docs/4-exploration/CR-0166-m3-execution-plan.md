# CR-0166 — M3 多品牌規模化總執行計畫（業主 goal 啟動）

- **日期**：2026-07-12
- **啟動依據**：業主 goal「把 M3 部分也做完，並且幫我測試 UAT」＝27_Roadmap §5 階段閘第 4 條「業主裁決確認啟動」正式成立（前三條：M1+M2 Release gate 走 UAT 中、≥2 付費租戶條件由業主豁免解讀）。
- **CIA 觸發面向**：Architecture boundary（Kafka 事件骨幹）、API contract（License/撤證/webhook）、DB schema（多項 migration）、External integration（Casdoor subscription、Kafka）、Business flow（K3'、reviewer 升級）。

---

## §1 範圍盤點（三個來源合併）

### A. WBS §4 M3 工作包（27_Product_Roadmap_WBS）

| WBS | 項目 | 可行性評估 |
|---|---|---|
| 3.1.1 | Kafka 事件骨幹（commission.accrued／工單投影事件，替換 outbox 輪詢） | 本機 compose 可落地；prod 待上雲 |
| 3.1.2 | 技師工作台改吃 CQRS 投影（跨品牌工單聚合） | 依賴 3.1.1 |
| 3.2.1 | 期末對帳 reconcile 閘門（品牌計費 vs 平台結算對平） | 依賴 3.1.1 |
| 3.3.1 | License → provisioning 自動化（開站腳本化） | 可做（Casdoor 已落地） |
| 3.4.1 | 雲端拓撲對齊（tech/platform 上雲＋技師庫上雲） | **OPS，需 GCP 授權/費用——業主協同** |
| 3.5.1 | 第 2 品牌開站演練（dry-run，**M3 Release gate**） | 本機可演練（LINE 綁定用測試通道） |

### B. 各 CR「延 M3」治理欠帳

1. webhook_idempotency 表接線（LINE webhook DB 層去重，跨實例/重啟防護）
2. X-Initiator/X-Approver header UUID 驗證＋instant rollout autocommit 部分狀態修復（審計斷鏈）
3. 家族覆核 reviewer 缺席 >24h 升級（端點已宣稱 SLA）
4. 品牌授權撤證 live API（technician_brand_authorization 執行期授/撤——現僅 seed）
5. audit hash-chain prev_hash 並發競態（rowlock）
6. M18 config 受保護層 override 擋
7. owner_role_codes per-namespace owner 治理（現寫死 admin-only）
8. PII 遮蔽（llm_usage_log 明文＋log scrub 系統化）
9. License 訂閱 gate（0707 會議 #20；查證報告＝執行面零實作，殘樁三件）
10. refinery publisher 第二軌 family gate（俟啟用——**維持俟啟用，不提前**）
11. v1 API 收斂遷移/移除（2.5.1 殘，被 CR-0145 §8 三待決阻擋）

### C. UAT 未結（goal「幫我測試 UAT」）

- K3' 負面情緒偵測＝**功能本體未實作**（合約 4.4(a) 紅線；agent 端零實作、無寫入點、無題庫）
- K1 判分方式待裁（單輪 rubric 0.623 vs 80% 門檻；repo 判讀=rubric 低估）
- wave1 spec 裁決類 3 件（技師拒單端點、F7 >2000 主管覆核 RBAC 擴權、F10 L1 發起角色）
- 每輪 M3 功能完成後照 wave1/2 模式自動驗收＋最終 wave4 總驗收

## §9 建議實作順序（每輪一 branch，完成即 UAT）

| 輪 | 內容 | 性質 |
|---|---|---|
| R0 | AI 紅線 eval 收尾（K8 補記＋commit）——進行中 | UAT |
| R1 | 治理欠帳批次（§1-B 1~8：webhook 冪等、UUID 驗證、reviewer 升級、撤證 API、hash-chain rowlock、受保護層、owner_role_codes、PII 遮蔽） | 低風險高確定性 |
| R2 | K3' 負面情緒偵測（agent 偵測→sentiment_alerts＋通知；120 題題庫＋≥90% eval） | 紅線補洞 |
| R3 | License 訂閱 gate＋console 管理 UI＋模組開通（§1-B 9） | M3 商業核心 |
| R4 | Kafka 事件骨幹＋CQRS 投影＋reconcile 閘門（3.1.1/3.1.2/3.2.1） | M3 架構 |
| R5 | License→provisioning 自動化＋第 2 品牌開站演練 dry-run（3.3.1/3.5.1，M3 gate） | M3 收官 |
| R6 | 雲端拓撲對齊（3.4.1）——腳本與 checklist 我備妥，執行需業主 GCP 協同 | OPS |
| R7 | v1 API 收斂（視 D5 裁決） | 清欠 |
| R8 | UAT wave4 總驗收＋驗收文件回填 | UAT |

## §8 Human Decisions Required

1. **D1 上雲（3.4.1）**：A=列業主協同待辦（我備妥腳本/checklist，你有空一起跑）／B=現在就做（需你即時給 GCP 授權）。**建議 A**。
2. **D2 Kafka 選型**：A=Redpanda（Kafka 相容、單容器無 ZK、本機輕）／B=Apache Kafka（正典、運維重）。**建議 A**（ADR 記錄相容性承諾，介面走標準 Kafka protocol，未來可換）。
3. **D3 K3' 偵測實作**：A=agent turn 內 LLM 判定（與回覆同 turn 順帶產出，寫 sentiment_alerts＋通知，題庫 AI 產＋你抽驗）／B=關鍵詞規則先上（快但誤報高）。**建議 A**。
4. **D4 License enforcement MVP 範圍**：A=全做（plan 資料結構＋enforcement middleware＋refinery 模組 gate＋console License UI＋brand 條件渲染）／B=先做 enforcement＋refinery gate，console UI 下一輪。**建議 A**（M3 核心，一次到位）。
5. **D5 CR-0145 三待決**（v1 收斂前置）：①auth 定位（建議：宣告 auth 為 v1 永久例外，Casdoor R3 落地時再重評）②platform_* 系列（建議：宣告 platform 面 v1 長期承諾，不開 v2 平面）③5-gate 名實（建議：以 ADR-003 三步為準棄 8-stage）。照建議則 R7 只做「caller 歸零的 v1 遷移/移除」。
6. **D6 wave1 spec 裁決 3 件**：①技師拒單端點——建議做（併 R1，缺口明確）②F7 >2000 主管覆核 RBAC 擴權——建議做（SUPERVISOR 可達化）③F10 L1 發起角色——建議維持現狀（退款流程 uatFlags 隱藏中，接金流時再對）。
7. **D7 K1 判分**：A1 單輪 rubric ≥80% 為準（=未過，需知識改善輪後重測）／A2 改「多輪 L1＋紅線 gate＋人工抽驗」綜合判（標注 19_Test_Plan）／A3 維持 80% 但以 escalation/safety＋人工抽驗為準。**建議 A2**（與 repo 既有 eval framework 判讀一致）；無論何者，領域外失守＋自行判定授權/保固兩個真實守線缺口併 R2 修。
8. **D8 2.1.1 R3（localStorage 退場＋三站 SSO 複製）**：原「業主排程」——要併入本計畫（建議：併 R7 後）還是繼續另案？

### 裁決記錄

（D1–D8 待業主回覆）

#### 業主追加裁決（2026-07-12「Redpanda＋照建議」）

- **D2＝Redpanda**（Kafka 協定相容、單容器、可換）；集中共用（非 per-brand）；初期低量不叢集化。
- **D5＝照建議**：①auth 宣告 v1 永久例外 ②platform 面 v1 長期承諾不開 v2 ③以 ADR-003 三步為準棄 8-stage → R7 只做 caller 歸零的 v1 遷移/移除。
- **D7＝照建議**：K1 判分改「多輪 L1＋紅線 gate＋人工抽驗」綜合判（標注 19_Test_Plan）。
- **D1＝照建議**：R6 上雲列業主協同待辦（腳本/checklist 備妥，一起跑）。

#### R1 子裁決（查證後之實作層選項——依建議值先行實作，業主回覆可覆寫）

1. webhook 冪等：**mark-first**（照 CR-0001 §8 Q5 原規格，at-most-once）；cleanup 放 **api realtime cron**（7 天 TTL 已裁決值）。
2. SoD header：**格式＋存在性驗證（選項 B）**、錯誤碼統一 **422**（repo 慣例）；交易化含 start_rollout（instant/canary）＋rollback；其餘 6 個同病 router 收斂列後續輪。
3. reviewer 升級：通知對象＝**tenant 內 admin/operations_manager**；24h 起算＝reviewed_at；形式＝notification＋audit（dashboard 紅燈列後續）；「≥3 件未審→CR 替補提名」列 Phase II。
4. 撤證 API：**平台側**三端點；**軟撤**（authorized=FALSE 保留歷史）；audit 走 **saas.technician_lifecycle_event CHECK 擴充**（migration 104）；brand 值 trim 自由輸入；「最後一張撤掉→fail-open 維持現狀」**列 D9 待業主確認**（營運地雷已標記）。
5. hash-chain：**只上 pg_advisory_xact_lock**（純程式，chain_seq migration 列後續）；lock_timeout 2s 逾時維持 fail-soft；**family_reviews 同型鏈一起修**。
6+7. 受保護層＋owner：**同一 migration 103**（is_protected 欄＋owner_role_codes 回填）＋同一 gate 函式；admin 永遠 bypass；**payment_gate=is_protected+admin-only**；其餘 19 namespace owner=operations_manager（建議表照查證）；seed 與程式同輪上。
8. PII：scrub util 昇格共用＋audit payload 入鏈前遮蔽（高置信樣式：email/電話/身分證/LINE uid，不含地址啟發式避免誤殺稽核證據）＋log filter＋三處 email 明文改遮蔽；llm_usage_log＝**選項 A**（現無寫入者，標注未來寫入必經 scrub）；forget_request.subject_email 處置列 D10 待裁。
9. 拒單端點：**回 'created' 清 technician_id**（pool 可搶）；通知＝created_by＋audit（最小）；熔斷觸發**另立 CR**（本輪落 dispatch_logs 計數地基）；pool 即時性接受重整可見。

### 進度

- ✅ **R0 done**（branch `test/uat-ai-redline-evals`，merge 待）：AI 紅線 eval——紅線 gate 9/9、多輪 redline 1.0/幻覺 0、K1 0.623（≈基準，判分待 D7）、**K8 82%→修正後 98.5% PASS**（judge 誤判校正＋SOP 保固守線 v1.4.0＋say-do 兜底）。K3' 查證＝功能未實作（R2）。
- ✅ **R1 done 9/9**（branch `feat/m3-r1-governance`）：webhook 冪等接線＋cleanup cron／SoD header UUID＋存在性＋交易化／reviewer 24h SLA cron／audit＋family hash-chain advisory lock／受保護層＋owner_role_codes（migration 103）／技師拒單端點（migration 104）／品牌授權撤證 live API（migration 105）／PII 遮蔽共用 util＋audit payload 遮蔽。api 1828 passed＋agent 195＋新測 18。migration 101-105 已套 live。
- ✅ **R2 done**（merge dev-ding）：K3' 負面情緒偵測——agent LLM 判定→gateway 接線→api sentiment_alerts 告警＋通知；120 題題庫 **live eval 100%（反諷 22/22）≥90% PASS**。
- ✅ **R3 done**（merge dev-ding）：License 訂閱 gate——tenant entitlements＋enforcement 原語＋platform console License API/UI＋refinery 模組 gate。migration 已套 live platform 庫。brand 端條件渲染併 R8。
- ⏳ **R4–R8 待續**：
  - **R4 Kafka 事件骨幹**＝承重架構變更（引入 message broker、CQRS 投影、替換 outbox，ADR-006/017），需業主 **D2 選型確認＋運維承諾** 才動工——不宜在假設預設上自動建置 production message broker。
  - **R5 provisioning＋第 2 品牌開站 dry-run**（M3 Release gate）＝可自動化推進（不依賴 Kafka）。
  - **R6 上雲**＝需業主 GCP 授權協同（D1）。**R7 v1 收斂**＝需 D5。
- ✅ **R4 設計備妥**（`CR-0166-R4-event-backbone-design.md`）：D2 選型建議 Redpanda＋topic schema＋outbox→Kafka 遷移路徑＋對帳閘門＋實作 WBS；待業主 D2 拍板後實作。
- ✅ **R8 UAT wave4 done（已建範圍）**（merge dev-ding）：6 面向多 agent 去偽驗收——R0 AI eval／R1 治理 9/9／R2 K3'／R3 License／R5 provisioning 全 **PASS 零功能回歸**（`uat-wave4-m3-report-20260712.md`）。回歸守門 2 非功能項已修（CHANGELOG 補登＋死角色 super_admin 移除）。UAT 驗收清單 §1 合約紅線 AI 面全綠回填。**M3 全項總驗收俟 R4/R6/R7 落地。**

## 已完成 UAT 紅線 gate 總結（R0–R3）

| 合約紅線 | 狀態 |
|---|---|
| K3' 負面情緒識別 | **✅ 100%**（R2，≥90%） |
| K8 AI 禁區 | **✅ 98.5%**（R0，≥95%） |
| 紅線確定性 gate | **✅ 9/9**（R0） · 多輪 redline **✅ 1.0** |
| K3 家族覆核履約 | 硬 gate 強制（CR-0164 C）＋逾時升級（R1-3）＋鏈保護（R1-5） |
| 影像辨識禁用 | ✅ 工具白名單物理不可達 |
| GDPR forget | ✅ CR-0164 D＋legal-hold 423 |
| K1 AI 準確率 | 單輪 rubric 0.623（判分待 D7；守線缺口併 SOP 強化） |
