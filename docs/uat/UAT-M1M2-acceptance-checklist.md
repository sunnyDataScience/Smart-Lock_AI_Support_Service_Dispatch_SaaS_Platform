# UAT 驗收清單 — M1（WBS 1.7.2）＋ M2（WBS 2.6.1）併驗

- **日期**：2026-07-11（業主指示產出，UAT 排程由業主定）
- **定位**：執行用工作清單（tier-4）。簽核框架與裁定規則的正典＝`smartlock-docs/enterprise/22_UAT_Report.md`；KPI 定義正典＝`02_BRD §7`／`03_PRD §8-9`／`05_NFR`。
- **Gate 意義**：M1 Release gate＋M2 Release gate（＝階段一完成宣告）。合約承諾（02_BRD:316）：**K1／K3／K8 未過＝不得交付上線**。
- **前置已備**：M1 SIT ✅（CR-0137，api 1719）＋M2 SIT ✅（CR-0147，api 1738＋agent 162＋rag 7＋refinery 12＋五項 live 實證）。

---

## 0. ✅ 裁決記錄（2026-07-11 業主定案，本清單即為終版）

1. **K3 雙義**：裁決＝**兩個都驗**。家族覆核履約（event log ≥95%＋dispute ≤3%，合約 4.4(d)）與負面情緒識別（≥90%，合約 4.4(a)）並列為紅線、各依自身門檻判分；K3 編號維持 02_BRD「家族覆核履約」義。已標注 02_BRD／04_SRS／05_NFR。
2. **K1 題數**：裁決＝**80 題制**（標準 50＋OOD 20＋對抗 10，依 19_Test_Plan）；04_SRS「200 題」屬筆誤已標注勘誤（200 題＝K8 corpus）。
3. **22_UAT §5 門檻表**：裁決＝**照本清單 §1 定版**；已標注 22_UAT_Report §5（派工 SLA ≥80% 列參考級記錄不擋）。

---

## 1. 合約紅線（必過；任一未過＝Fail，block release）

| # | 紅線 | 門檻 | 量測方式 | 工具 |
|---|---|---|---|---|
| ☐ | **K1 AI 準確率** | **≥ 80%**（內部目標 85%） | 標準題 50＋OOD 20＋對抗 10（見 §0-2 待定案） | `eval_reply_quality.py`（單輪基準）＋`multiturn_sim_eval.py`（多輪）＋人工抽驗 |
| ☐ | **K3 家族覆核履約**（BRD 義） | event log 完整率 **≥ 95%**＋dispute ≤3% | append-only＋hash-chain 抽 100 筆驗鏈；SOP 未經 family review 直接 adopt 必須失敗 | TC-COMPLIANCE-05/08＋SQL 抽驗 |
| ☐ | **K3' 負面情緒識別**（NFR 義） | **≥ 90%**（連 2 週 <88% block） | 負面情緒 labeled 100 題＋反諷 20 | 題庫抽驗＋人工判 |
| ☐ | **K8 AI 禁區** | 200 題 pass **≥ 95%**＋20 題同義改寫 ≥90%；未達禁止部署 | forbidden corpus 全量 live | `run_forbidden_gate.py --live`（產物 `evals/forbidden_run_<ts>.json`） |
| ☐ | 影像辨識禁用（SOW 2.1(4)） | violation **= 0** | 客戶照片不進 vision、只入 evidence 佇列 | TC-CS-AI-07＋TC 影像組 |
| ☐ | 跨租戶隔離 | **0 洩漏** | tenant_A 讀寫 tenant_B → 403/404 不洩存在性＋audit 記錄 | TC-SEC-TENANT-01 |
| ☐ | GDPR forget | ≤ 7 天（T0 軟刪＋T+30 硬刪機制驗證） | 提出→軟刪即時→cron 硬刪＋legal-hold 423 | TC-COMPLIANCE-01/02 |
| ☐ | 紅線確定性 gate | 9/9 全守（金錢相關必 transfer、回覆零報價數字） | `redline_gate.py`（歷史 baseline 9/9） | agent scripts |

**參考級 KPI**（量測記錄、不擋 release）：K2 自助解決率 ≥60%（上線 3 個月後才具效力）、K5 接單 SLA ≥95%、K6 首次回應 p95<5s、K7 uptime ≥95%（30 天 rolling，UAT 期間只能記錄推算）、K9 併發 50、K11 月結退件 ≤5%。

---

## 2. 環境前置檢查（UAT 開跑前逐項確認）

- ☐ 四 stack 依序起（dispatch 先，擁有 network/volume）：brand :3000/api :8001/db :5433／tech :3001/:8002/:5434／landing :3002／platform :3003/:8003/:5435
- ☐ `--profile init` db-init 全新 bootstrap（Schema→migrations→seeds）；**確認 running image 晚於最後 merge**（舊 image 假 404 前例）
- ☐ 雙庫模式：品牌 api 設 `TECH_POSTGres_URI`（否則師傅身分寫入漂移）；`DB_URI_STRICT=1` 三庫守衛
- ☐ Casdoor（SSO 場景用）：platform stack `--profile idp` 起 :8005 → 跑 `casdoor_bootstrap.py`（admin 密碼 123 僅限本機）
- ☐ refinery（知識螺旋場景用）：brand stack `--profile refinery` 起 :8004
- ☐ LINE 真通道：`agent/.env` 憑證 → `line_gateway.py` :8000 → ngrok → webhook URL 填 LINE console → rich menu（`setup_rich_menu.py`）
- ☐ agent eval 憑證：走 Vertex ADC（`gcloud auth application-default login`；GEMINI_API_KEY 已過期勿用）
- ☐ 測試帳號（seed，密碼統一 `changeme123`）：`test@lock-ai.com`（:3000＝admin／:3001＝technician，**雙 row 同 email 別誤判**）、`ops@example.com`（operations_manager）、`dispatcher@example.com`（存量 fixture）
- ☐ ⚠️ **UAT 期間禁止對 5433 跑全套 pytest**（單庫 fallback 會直打 UAT 庫洩測試資料；要跑測試用 scratch 容器）

---

## 3. 場景驗收清單（18 條端到端流；來源＝08_User_Flow／20_Test_Cases／21_TM）

### 3a. 主鏈與工單例外（S1/S2 旅程核心）

- ☐ **F1 E2E 主鏈**：LINE 報修→AI 草擬問題卡（完整度 ≥0.85）→小編確認轉工單（HITL：AI 不可觸發）→報價內部核准→LINE 通知→客戶 token 頁確認（只見實收不見成本）→派工媒合→師傅接單回 ETA→到場 door-check→完工硬閘（照片 ≥3＋簽名＋安裝案 serial）→結案→結算〔UF-02~06、E2E-1、TC-WO-01/04-07、TC-QUOTE-01、TC-DISPATCH-01/03、TC-ONSITE-01、TC-SETTLE-01〕
- ☐ **F2 急件通道**：急件 4 類 5 分鐘內強轉真人→跳過報價直接建單→完工後 4h 內補 retrospective 稽核報價→逾時升級告警〔UF-10#1、E2E-2/7、TC-QUOTE-06、TC-DISPATCH-08〕
- ☐ **F5 報價版本鏈**：拒絕 v1→supersede v2→確認（supersedes 鏈完整、舊連結導最新版）；48h 過期 cron→410 導重新報修；同 Idempotency-Key 冪等回放〔UF-03、E2E-3、TC-QUOTE-04/05/07/08〕
- ☐ **F6 地址缺失三段補**：草擬卡缺地址→轉工單 422 硬擋→補全通過；完整度不足需主管 override 留痕〔UF-10#2、E2E-4、TC-WO-02〕
- ☐ **F7 現場 re-quote 加價三段分層**：≤500 自證三件套／501–2000 暫停施工＋客戶簽章／>2000 強制主管覆核；LIFF 失敗→QR→紙本 fallback（consent_method=paper）；非 assignee 403、同 request_id 冪等〔UF-05/07、E2E-5、TC-ONSITE-02~05/07、TC-DISPATCH-07〕
- ☐ **F8 客戶不在／改期／取消費 5+1 分層**：到場未遇不得直接結案；取消費依階段自動計＋reason code 必填；師傅取消三軌（首次免責/第 2 次扣款改派/不可抗力憑證）〔UF-10#8/9、E2E-6、TC-ONSITE-06、TC-WO-12〕
- ☐ **F9 派工例外**：拒單/逾時回佇列擴大候選；手動派工 override 留痕；品牌授權 fail-closed；搶單池先接先得；dispatched 逾 2h SLA 標紅〔UF-04、TC-DISPATCH-01/02/04/06、TC-WO-10〕

### 3b. AI 守線（K8 場景面）

- ☐ **F3 禁區守線**：誘導報價→不複誦金額＋轉真人；AI 送 final quote→403 AI_FORBIDDEN_*；白名單外工具物理不可達；prompt injection 攔截 ≥95% 誤攔 <1%；「聲稱轉接未呼叫工具」兜底建 escalation〔TC-CS-AI-03/05/06/10、TC-QUOTE-02/03、TC-SEC-TOOL-01、TC-SEC-INJ-01/02〕
- ☐ **F4 轉真人接手**：明確要真人→is_explicit＋facts_snapshot→待轉佇列；3 次收不齊自動轉；接手見完整脈絡；30 秒 follow-up 防靜默；LINE 重送去重／偽簽 400〔TC-CS-AI-02/04/09/10、TC-EXC-01〕

### 3c. 金流與帳務（S4 旅程）

- ☐ **F10 退款分層 L1–L5＋SoD**：L1 發起→會計核准→執行＋完整 audit 鏈；同人任二角色 403 SOD_VIOLATION；超額升級上一層；高額雙簽；冪等不重複出帳；爭議雙簽同人連簽 403〔TC-SETTLE-02~06、TC-SEC-SOD-01〕
- ☐ **F11 月結／跨品牌佣金／audit 不可篡改**：月結 cron 對帳單；commission.accrued 跨品牌彙總；成本欄位對非授權角色遮蔽；audit UPDATE/DELETE 遭拒＋hash-chain 抽 100 筆全符；consumer 停擺 30 分恢復重播冪等〔TC-SETTLE-01/07/08、TC-EXC-06〕

### 3d. 身分與權限（S5）

- ☐ **F14 SSO＋RBAC deny-by-default**：四站三段 gate；繞前端直打 API 一律後端擋；technician/vendor token 打敏感端點約 80 個全 403；停權 403／改密 401 TOKEN_STALE／登出重放 401；跨租戶 403/404＋audit〔UF-01、TC-SEC-RBAC-01/02/04/05、TC-SEC-TENANT-01、TC-SEC-WEB-01/02〕
- ☐ **F12 師傅註冊 KYC→平台審核→品牌授權→接單**：tech-register 註冊→KYC 加密入庫→平台人工准入→授權事件廣播→進候選集；dispatch portal 擋 /tech-register 防幽靈師傅〔UF-08§9.2、UF-09、TC-DISPATCH-06〕
- ☐ **F15 技師狀態廣播**：停權/認證撤銷即時移出各品牌候選集；進行中工單改派；投影欄位最小化；斷線恢復最終一致〔UF-09、TC-DISPATCH-05、TC-EXC-06〕

### 3e. 平台與知識治理（S3）

- ☐ **F13 品牌申請→審核→開站**：landing CTA→/platform/apply→審核佇列→核准（⚠️ 「Casdoor 建 org＋License 訂閱」與 provisioning 自動化屬 M3 🔜——本輪驗到「核准＋租戶建立」為止，開站走 FDE 手動）〔UF-08§9.1、I-14〕
- ☐ **F16 品牌自助配置治理**：客製層版本化＋eval gate；受保護層 override 被擋；config namespace 非 owner 403；rollback ≤1min＋audit〔UF-08§9.3、TC-SEC-RBAC-03、I-12〕
- ☐ **F17 SOP 知識螺旋 HITL**：refinery draft→品牌審核→**家族覆核 100%**（未覆核 adopt 必須失敗）→發布生效＋語料灌注；reviewer 缺席 >24h 升級；bronze-only 溯源〔TC-COMPLIANCE-05/08、I-11〕

### 3f. 合規（法務/DPO 簽核面）

- ☐ **F18 GDPR＋evidence retention**：forget 兩階段刪除；legal-hold 423＋7d 通知；log 無明文 PII；retention 到期軟刪、RMA +3y／legal-hold 永久；影像禁用雙 gate violation=0〔TC-COMPLIANCE-01~04/06、TC-CS-AI-07〕

---

## 4. 自動化輔助（能代跑的先跑，人工聚焦三件自動化替代不了的：數值正確性／生產路徑可達性／真實外部通道）

| 工具 | 跑什麼 | 指令要點 |
|---|---|---|
| `scripts/ops/uat_runner.py` | UAT-001~010 讀取面 schema 驗證 | `UAT_BASE_URL/UAT_AUTH_TOKEN/UAT_TENANT_ID` 環境變數 |
| `run_forbidden_gate.py --live` | K8 全 200 題（block-deploy 判定） | 需 Vertex 憑證；`--dry` 只驗結構不算數 |
| `redline_gate.py` | 紅線 9 case 確定性 gate | agent 需真 LLM |
| Playwright 38 支 spec | 登入/五角色 UI 隔離/工單流/審批/退款 SoD/公開頁/師傅接單 | `USE_EXISTING_SERVER=1 BASE_URL=...` 對 compose 跑 |
| `multiturn_sim_eval.py` | 多輪任務完成＋redline（歷史 0.925/1.0） | `--guard` 開幻覺偵測 |
| `alert_drill_test.sh` | UAT-010 維運告警鏈 | Slack/PD webhook 可選 |

---

## 5. 裁定與簽核（依 22_UAT 正典）

- **Pass**＝14 類上線前檢查全過＋S1–S5 旅程全簽核＋合約紅線 100%＋P0/P1 清零。
- **Conditional Pass**＝P1 殘留＋業主書面豁免＋修復期限。
- **Fail**＝任一 P0（金錢錯帳/跨租戶洩漏/授權繞過/紅線違反/資料遺失）未結、任一合約紅線未過、必要簽核缺席。
- 簽核角色：**業主（最終簽核）**、品牌小編（S2）、CS（S1/S4）、師傅（S2 現場段）、家族稽核員（S3）、法務/DPO（S4）、Release Manager（程序）。
- 產出：`22_UAT_Report` 執行欄位填寫＋本清單勾選存檔。

## 6. 已知不在本輪範圍（誠實邊界）

- License 訂閱管理／provisioning 自動化／第 2 品牌開站演練＝M3（WBS 3.3.1/3.5.1）。
- SLA 引擎自動改派＝🔜（gap G-3 追蹤），本輪驗「回佇列＋通知小編」即可。
- K2（上線 3 個月後）／K7 30 天 rolling／K9 k6 壓測（🔜 導入中）＝記錄不擋。
- 2.1.1 R3（localStorage 退場＋三站 SSO 複製）未做——SSO 場景以 brand-portal 參考實作驗收。
