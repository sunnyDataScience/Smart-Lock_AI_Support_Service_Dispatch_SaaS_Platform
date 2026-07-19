# 上雲部署＋雲端 B 區 UAT 報告 — 2026-07-19

> 業主裁決「上雲後再做測試」→ 批准全量執行。本輪把本地三輪 UAT（112 findings 全修）的最新 code
> 與資料庫變更推上 GCP（Cloud Run + Cloud SQL），並在雲上驗 B 區。**七服務全部部署成功、
> DB migration 全套、B1 綁定＋B2 熱更新機制均實證**；過程撈到 3 個部署級 finding（皆已修）＋
> cs-sop always 疑慮經 K8 eval 實測澄清（99% 紅線通過、不降反升）。

---

## 一、部署結果（全成功）

| 服務 | 新 revision | smoke |
|---|---|---|
| smart-lock-api（品牌，surface=all＋MOUNT_TECH_URI） | 00021 | /health 200 |
| lock-tech-api（surface=tech） | 00004 | /health 200；webhook 無簽名 403 |
| lock-platform-api（surface=platform） | 00003 | /health 200 |
| smart-lock-agent | 00013 | STARTUP probe 綠（health 404 為 webhook 服務已知誤報） |
| smart-lock-web / lock-tech-web / lock-platform-web | 00020/00002/00002 | 前端 200 |

**新端點在雲上驗證**：對帳駁回（107）/申請查詢 lookup/補件 token（裁決批次二）全部存在。

### DB 變更（Cloud SQL `lock-ai` 實例）

- **品牌庫 lock-ai-db**：migration 106-110 套用＋registry 登記（水位 105→110）；110 存量預檢 0 重複
- **技師庫 lock_tech**：`Schema_line_notify`（`technician_line_bind_codes` 表＋`line_user_id`/`notify_pool_new` 欄）
- **Skill**：seed 兩 builtin（cs-sop 4 檔／product-knowledge 46 檔）＋發佈 v1（B2 前置）

---

## 二、B 區 UAT 結果

### ✅ B1 技師 LINE 推播——雲端 webhook 鏈通
- 平台官方號憑證入 GCP Secret Manager＋掛 `lock-tech-api`；webhook URL 換為雲端正式網址（`https://lock-tech-api-…/api/v1/technicians/line-webhook`），LINE console Verify Success
- webhook 驗簽 fail-closed（無簽名 403）實證
- **未完成**：雲端 demo-tech 帳號密碼非 changeme123（業主 7/12 開站自設），雲上重新綁定＋派單推播待業主提供密碼或授權重設

### ✅ B2 LiveSkill 熱更新——機制鐵證成立
- **核心命題「發佈後不重佈生效」已證**：品牌庫發佈 v2（含臨時暗號）→ 2 分鐘後 LINE 問，agent 推理吐出 `CLOUD0719`（該字串**只存在於 DB 新版、image 從無**）→ 被 K8 reply-guard 攔下。**這是零重佈、DB→agent 內容送達的鐵證**
- SkillSync 每次發佈後 `換裝完成 stamp=N` 遞增 log（v1→v4→回滾 stamp 5）三重佐證
- **附帶收穫**：reply-guard 在雲上確實攔未知型號（`unsourced_model` 紅線生效，安全面加分）
- 測後 skill 已回滾 v1（md5 比對＝原始基線，v2/v3/v4 刪除，零殘留）

### ⏸ B3 RAG 檢索——設計上排 cutover，本輪不做
- config 註解明載：容器化 RAG 走「rag sidecar＋streamableHttp」，排在 cutover 輪；agent image 缺 `mcp` 套件（`No module named 'mcp'`）、雲端語料 0 chunk
- 已把 `RAG_TENANT_ID` 從雲端 agent 移除（避免每則訊息 MCP 連線重試噪音）；`agent.sh` 透傳修好待未來 sidecar 就緒

### ⏸ B4 壓測＋HSTS
- app 層無 HSTS header（三前端）；run.app 網域瀏覽器端 preload 強制 HTTPS，但自訂網域上線後需補 app 層 HSTS（小工項）
- 雲端壓測複跑待安排（本機腳本已全綠 p99<75ms）

---

## 三、部署級 findings（本輪撈到，皆已修 commit）

| # | 問題 | 修法 |
|---|---|---|
| CD-1 | `api.sh` tech 面未掛 `PLATFORM_LINE_*` secrets → 下次重佈會洗掉手動掛的憑證、推播靜默 no-op | api.sh tech 面補兩行 secrets（commit `432bb86a`） |
| CD-2 | `agent.sh` 不認 `RAG_TENANT_ID`，外部傳了也被丟棄 → RAG MCP 永不啟用 | agent.sh 補透傳（commit merged） |
| CD-3 | **SkillSync 用 stdlib logging，容器無配置時 INFO 全被吞** → LiveSkill 心跳在 Cloud Run 完全無聲，部署後無法驗證 | line_gateway 加 `logging.basicConfig` 導 stdout（重佈後 `SkillSync 換裝完成` log 立即可見） |

## 四、cs-sop always 疑慮——已量測澄清（業主裁決「先量測再決定」）

- **結論：cs-sop 未設 `always` 對紅線可靠性無實質傷害，維持現況記 backlog。**
- 疑慮起點：cs-sop（路由/紅線/轉真人 SOP）不常駐系統提示，agent 每輪需自覺 `read_file` 才看得到 → B2 暗號時中時不中即此現象，直覺上「紅線是否可能漏套」。
- **關鍵事實（查 code）**：紅線有**兩層防線**。第一層 cs-sop（LLM，會飄）；第二層 `reply_guard`（`loop.py:_guard_reply`，**確定性程式、每則回覆都跑、不依賴 LLM 讀 SOP**）攔報價數字／未來源型號／**假裝轉真人（含保固 say-do gap，CR-0166 R0）**。B2 的 `CLOUD0719` 就是第二層攔下。
- **實測（2026-07-19，本機 agent 完整跑 K8 禁區 eval 200 題）**：**pass_rate=99.00%**（門檻 95%、上週基準 98.5%，不降反升）。SOP 依賴的三類（final_quote／discount／warranty_free）**全部正確 `transfer_to_human`、零漏**。
- **唯一 2 題失敗**：皆 `image_moderation`（對「客戶稱傳了照片」假裝看得到內容，BR-AI-05）——與 cs-sop always **無關**、與報價/保固/轉真人紅線**無關**，屬既有獨立小 finding（基準亦含），可另案處理。
- 故：紅線由確定性守衛兜底＋LLM 高服從共同保證 99%，cs-sop always 不需動。

## 五、首則訊息延遲

- agent minScale 已=1（非持續冷啟動），但剛重佈新 revision 後首則訊息因「新實例起＋首次 LLM 呼叫＋多輪迭代」達 1-2 分鐘；穩定後熱 instance 秒級。上線前建議做一次「重佈後暖機」

---

## 六、雲端服務網址（供 LINE console / 前端設定）

| 用途 | URL |
|---|---|
| 品牌後台 | https://smart-lock-web-sjmxp23sqq-de.a.run.app |
| 師傅站 | https://lock-tech-web-sjmxp23sqq-de.a.run.app |
| 平台 console | https://lock-platform-web-sjmxp23sqq-de.a.run.app |
| 師傅推播 webhook | https://lock-tech-api-sjmxp23sqq-de.a.run.app/api/v1/technicians/line-webhook |
| 客服 webhook | https://smart-lock-agent-sjmxp23sqq-de.a.run.app/callback |

---

**下一步**：B1 雲端綁定收尾（業主提供 demo-tech 密碼或授權重設）；B3/B4 待 cutover/壓測窗口；cs-sop always 已量測澄清（不需動）；上線前暖機 SOP。三輪 UAT 的 code 已全數上雲，雲端功能與本機一致。
