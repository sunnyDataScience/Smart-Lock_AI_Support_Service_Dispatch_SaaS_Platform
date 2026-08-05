# SmartLock 本機靜態走查 — 2026-08-03

**本批文件為原始碼走查，非執行結果。** 未啟動任何服務；證據為程式碼原文（`檔案:行號`）與可離線執行的既有測試輸出。

> **取用說明（2026-08-04 補注）**：本目錄自 `origin/docs/uat-20260803-env-smoke`
> 單獨取入 `dev-ding`，**未帶入同批的 `docs/uat/uat-20260803/`**（正式機煙霧測試
> ENV-SMOKE 與其截圖），故原文提及的 `../uat-20260803/` 在本分支上不存在——
> 要看該份請至上述來源分支。
>
> 另需知悉：那份 ENV-SMOKE 判定為 FAIL（三站登入 `503 DB_UNAVAILABLE` /
> `500 INTERNAL_ERROR`、`/health` 回 `db: disconnected`），**成因是 2026-08-03
> 09:10 為 GCP 帳務封鎖止血而將 Cloud SQL 停機（`activationPolicy: NEVER`），
> 不是系統缺陷**；還原見 `scripts/ops/opsday-20260802-restore-from-cost-shutdown.sh`。
> 本批靜態走查即是在該狀態下無法執行動態測試的替代產出。

- 走查基準 commit：SC-01～SC-05 為 `c8687f5d`；SC-06～SC-09 為 `17aa40c5`；末批（前綴分組 A–F）為 `2cfeca92`（各文件結果表標明自身基準）
- 判定語彙：`一致` / `不一致` / `部分實作` / `無法靜態判定`
- 來源：`smartlock-docs/enterprise/規格統控整理/SmartLock_整合測試計畫.xlsx`（② 測試案例主表，130 支）

## 🔄 判定更正總表（2026-08-05 回程式碼查證）

本批走查完成後，另做了一輪「回程式碼查證」：把 9 支不一致 + 85 支部分實作
共 **94 支**逐一拿回現在的程式碼對，把文件引用的每個 `檔案:行號` 開檔覆核、
對宣稱「零命中」的識別碼以多種命名寫法重跑 grep。

| 查證結果 | 支數 |
|---|---|
| 判定正確 | 61 |
| **判重**（其實一致，不該改 code） | **11** |
| **判輕**（比原文更嚴重） | **22** |
| 引用的 `檔案:行號` 有誤 | 36 |

判重的 11 支模式一致：**把「用詞不同」當成「沒實作」**（例如「onsite 結束」找不到
同名觸發點，但完工回報 `complete_order` 就是；`ADDRESS_REQUIRED` 零命中，
但實作叫 `ADDRESS_REQUIRED_FOR_CONVERT`）。這些改 code 反而是錯的，
各該檔已在檔頭加「判定更正」標注，**原文一字未改**。

判輕的 22 支中最嚴重的兩支已修復並上線：`TC-QUOTE-09`（客戶在 LINE 點「同意報價」
全數 TypeError，非原文所說的「四條分支執行不到」）、`TC-AGT-TURN-01`
（兜底話術第二現場仍會讓客人的 AI 永久靜音）。

**更正後統計**：一致 38 / 部分實作 75 / 不一致 8 / 無法靜態判定 9（下表為更正前原始數字）。

---

## 目前統計

| 判定 | 數量 |
|---|---|
| 一致 | 27 |
| 不一致 | 9 |
| 部分實作 | 85 |
| 無法靜態判定 | 9 |
| 未走查 | 0 |

> **130 支全數走查完畢**（含樣板 TC-WO-01）。數字以各文件結果表的判定列實際統計。

### 判定為「不一致」者（9 支）

| TC ID | 一句話事實 |
|---|---|
| TC-CS-AI-07 | 照片以 base64 `image_url` 直送 LLM；TC 指名的 evidence 佇列全樹零命中 |
| TC-COMPLIANCE-06 | 靜態掃描 vision 呼叫命中 4 處；runtime 側找不到第二道 gate |
| TC-DISPATCH-01 | 見該文件 |
| TC-DISPATCH-03 | `technician.assignment_accepted` 零命中，實際發 `work_order.accepted` |
| TC-DISPATCH-04 | 見該文件 |
| TC-QUOTE-05 | 見該文件 |
| TC-SETTLE-04 | 兩條驗收條件皆無程式碼；`INSUFFICIENT_AUTHORITY` 僅存在於 `openapi.yaml` |
| TC-PLT-FLOW-01 | `flow_dsl` / `block_library` / `vertical_pack` / `workflow_definition` / `積木` / `DSL` 六個識別碼在 api/web/SQL/agent/scripts 全數零命中 |
| TC-AGT-CLARIFY-01 | `clarification_attempts` / `clarification_confirmed_at` 零命中；正典自身於 `04_SRS.md:595` 記載該行為已由 SOP 情境式紅線取代 |

> 同一 TC 隸屬多個 SC 時只計一次。SC-02 的 12 支中，TC-CS-AI-09、TC-SEC-MEM-01、TC-PERF-01 已於 SC-01 走查，不重複產檔。

## 走查紀錄

### 樣板

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-WO-01 | 一致 | 判定基準三條（工單 created、寫入 work_order_events 含 seq、AI 不可觸發）皆有對應程式碼實作 | [TC-WO-01.md](TC-WO-01.md) |

### SC-01（AI 客服進線，13 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-CS-AI-03 | 部分實作 | 建卡以「本輪 escalation 是否新增」為準，共三條寫入路徑，其中兩條不屬 TC 所述的「明確要真人／派工」 | [TC-CS-AI-03.md](TC-CS-AI-03.md) |
| TC-CS-AI-05 | 部分實作 | 主集合 200 題與 95% 門檻存在；改寫題 20 僅有不重疊的結構驗證，找不到 90% 門檻 | [TC-CS-AI-05.md](TC-CS-AI-05.md) |
| TC-CS-AI-06 | 部分實作 | 金額有 runtime regex 攔截與轉真人兜底；折扣／免費保固僅存在於 prompt 層 | [TC-CS-AI-06.md](TC-CS-AI-06.md) |
| TC-CS-AI-07 | **不一致** | 照片以 base64 `image_url` 送進 LLM；evidence 佇列在 api/agent/web/SQL 全數零命中 | [TC-CS-AI-07.md](TC-CS-AI-07.md) |
| TC-CS-AI-08 | 一致 | debounce 預設 5.0s，視窗內合併為單輪、視窗後另起一批 | [TC-CS-AI-08.md](TC-CS-AI-08.md) |
| TC-CS-AI-09 | 一致 | `event_id` 主鍵、入口即寫 `ON CONFLICT DO NOTHING`，無釋放路徑 | [TC-CS-AI-09.md](TC-CS-AI-09.md) |
| TC-CS-AI-11 | 部分實作 | 未知／殘缺標記只剝除不外洩；Chatlock 品牌判斷只在 prompt 層，gateway 不驗品牌 | [TC-CS-AI-11.md](TC-CS-AI-11.md) |
| TC-SEC-TOOL-01 | 一致 | 白名單六項與 TC 列舉相同，守線測試 3 passed | [TC-SEC-TOOL-01.md](TC-SEC-TOOL-01.md) |
| TC-SEC-MEM-01 | 部分實作 | 缺 scope 與未知 kind 皆 raise；跨 user/tenant 讀取回空清單而非 raise | [TC-SEC-MEM-01.md](TC-SEC-MEM-01.md) |
| TC-PERF-01 | 無法靜態判定 | p95 為執行期量測值；agent 端無 p95／SLO，`loadtest/` 標的為 API | [TC-PERF-01.md](TC-PERF-01.md) |
| TC-COMPLIANCE-06 | **不一致** | 靜態掃描 vision 呼叫命中 4 處；runtime 側找不到第二道 gate | [TC-COMPLIANCE-06.md](TC-COMPLIANCE-06.md) |
| TC-AGT-TURN-01 | 部分實作 | 一 webhook 至多一 Turn、SAVE 例外記 trace 且仍回覆；找不到專屬告警 | [TC-AGT-TURN-01.md](TC-AGT-TURN-01.md) |
| TC-NFR-PERF-01 | 無法靜態判定 | 需 k6/RUM/WS/RAG/OHS fixture 與實測數據，TC 本身規定資料不足即 Fail/Blocked | [TC-NFR-PERF-01.md](TC-NFR-PERF-01.md) |

### SC-02（故障報修到問題卡成立，12 支，本批新走查 9 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-CS-AI-01 | 一致 | 驗簽→Turn→transfer→ingest→建卡五環節連續可追，卡以 `source='ai_line'` 寫入 | [TC-CS-AI-01.md](TC-CS-AI-01.md) |
| TC-CS-AI-02 | 一致 | 驗簽為入口首個動作，失敗回 400 並直接 return，先於去重與 turn | [TC-CS-AI-02.md](TC-CS-AI-02.md) |
| TC-CS-AI-10 | 一致 | 兜底以位置感知判定承諾字樣，補寫 escalation 後由同輪轉發建卡 | [TC-CS-AI-10.md](TC-CS-AI-10.md) |
| TC-CS-AI-12 | 部分實作 | 四條件與「一次列齊」皆在 prompt 層；連續不滿無程式化計數器；固定輪數規則被明文禁止 | [TC-CS-AI-12.md](TC-CS-AI-12.md) |
| TC-WO-13 | 一致 | 24h 窗＋LIMIT 5＋`reversed()` 正序、append-only 聯集；serial 有帶；四層重送去重 | [TC-WO-13.md](TC-WO-13.md) |
| TC-DISPATCH-03 | **不一致** | `technician.assignment_accepted` 在程式碼零命中，實際發的是 `work_order.accepted` | [TC-DISPATCH-03.md](TC-DISPATCH-03.md) |
| TC-SEC-INT-01 | 一致 | 未配置 503、不符 401、`hmac.compare_digest` 常數時間，三條齊備 | [TC-SEC-INT-01.md](TC-SEC-INT-01.md) |
| TC-EXC-01 | 部分實作 | 去重一致；DLQ 為 outbox `status='dead'`，但無 1h review 期限、不涵蓋 inbound webhook | [TC-EXC-01.md](TC-EXC-01.md) |
| TC-NFR-REL-01 | 部分實作 | transfer／寫入有 spool 補送；push 送出失敗只記 log，不落 spool 不重送 | [TC-NFR-REL-01.md](TC-NFR-REL-01.md) |

已於 SC-01 走查、本 SC 沿用：[TC-CS-AI-09](TC-CS-AI-09.md)（一致）、[TC-SEC-MEM-01](TC-SEC-MEM-01.md)（部分實作）、[TC-PERF-01](TC-PERF-01.md)（無法靜態判定）。

### SC-03（急件強制轉真人，6 支，本批新走查 4 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-CS-AI-04 | 一致 | 「找真人」命中 `TRANSFER_KEYWORDS`，`is_explicit=True` 與 snapshot 同次 `log()` 寫入，卡以 `source='ai_line'`＋`urgency='high'` 落庫 | [TC-CS-AI-04.md](TC-CS-AI-04.md) |
| TC-QUOTE-06 | 部分實作 | `retrospective_audit_only` 佔位報價、4h 窗、逾時升 `ops_manager` 皆在；`audit_lag` 在程式碼零命中 | [TC-QUOTE-06.md](TC-QUOTE-06.md) |
| TC-DISPATCH-08 | 部分實作 | 任務載體為佔位報價而非獨立 task 表；`due=+4h` 在 `complete_order` 寫入，找不到「onsite 結束」觸發點；連 3 次逾時開 `emergency_audit_breach` CR | [TC-DISPATCH-08.md](TC-DISPATCH-08.md) |
| TC-COMPLIANCE-07 | 無法靜態判定 | 只有 `THRESHOLD = 0.90`；誤攔率與 ≤1% 常數、連續劣化 block/incident 皆找不到 | [TC-COMPLIANCE-07.md](TC-COMPLIANCE-07.md) |

已於前批走查、本 SC 沿用：[TC-WO-01](TC-WO-01.md)（一致）、[TC-NFR-REL-01](TC-NFR-REL-01.md)（部分實作）。

### SC-04（報價確認到工單成立，12 支，本批新走查 10 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-WO-02 | 部分實作 | 422 存在但 error_code 為 `ADDRESS_REQUIRED_FOR_CONVERT`，非 TC 寫的 `ADDRESS_REQUIRED`；地址檢查排第三順位 | [TC-WO-02.md](TC-WO-02.md) |
| TC-WO-03 | 部分實作 | gate 條件是 `quote.state == 'accepted'`，TC 寫的 `quote.customer_confirmed` 欄位在 schema 不存在；急件整段跳過 | [TC-WO-03.md](TC-WO-03.md) |
| TC-QUOTE-01 | 部分實作 | 實作狀態鏈為 `draft→pending_approval→approved→sent→accepted`，與 TC 的三個狀態名逐一不同 | [TC-QUOTE-01.md](TC-QUOTE-01.md) |
| TC-QUOTE-02 | 部分實作 | 403 `AI_FORBIDDEN_FINAL_QUOTE` 存在，但判定參數是 `actor_role` 非 `sender_role`；「範圍價」話術找不到 | [TC-QUOTE-02.md](TC-QUOTE-02.md) |
| TC-QUOTE-03 | 部分實作 | `AI_FORBIDDEN_WARRANTY_PROJECT` 僅以 `warranty_claims` 關聯判定，建案判定程式註解自述為遺留 | [TC-QUOTE-03.md](TC-QUOTE-03.md) |
| TC-QUOTE-04 | 部分實作 | `supersedes_quote_id` 唯一寫入點是技師 requote；客服建 v2 的 INSERT 欄位清單不含該欄 | [TC-QUOTE-04.md](TC-QUOTE-04.md) |
| TC-QUOTE-05 | **不一致** | 14 個 job 中無報價過期 job，過期為客戶點擊當下 lazy 寫入；有效期 7 天非 48h | [TC-QUOTE-05.md](TC-QUOTE-05.md) |
| TC-QUOTE-07 | 一致 | 客戶端硬編 `include_cost=False`，`unit_price` 只在 `if include_cost:` 時進 dict | [TC-QUOTE-07.md](TC-QUOTE-07.md) |
| TC-QUOTE-08 | 部分實作 | 兩個入口皆未掛 `idempotency_guard`；業務冪等分支所在函式實跑於 `:785` 拋 TypeError | [TC-QUOTE-08.md](TC-QUOTE-08.md) |
| TC-QUOTE-09 | 部分實作 | 五分支原始碼齊備、話術測試 8 項全過；實跑時 404／403 之後的四條分支未被執行到 | [TC-QUOTE-09.md](TC-QUOTE-09.md) |

已於前批走查、本 SC 沿用：[TC-CS-AI-06](TC-CS-AI-06.md)（部分實作）、[TC-WO-01](TC-WO-01.md)（一致）。

### SC-05（派工媒合到技師接單，12 支，本批新走查 10 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-DISPATCH-01 | **不一致** | `POST /technicians:match` 與 `dispatch.assigned` 零命中；實際為 `dispatch:auto-match` + `work_order.assigned`，狀態寫 `assigned` | [TC-DISPATCH-01.md](TC-DISPATCH-01.md) |
| TC-DISPATCH-02 | 部分實作 | 派工白名單為四種角色非僅 dispatcher；`assign_dispatch` 未傳 `actor_role`，該路徑 override 分支恆不成立 | [TC-DISPATCH-02.md](TC-DISPATCH-02.md) |
| TC-DISPATCH-04 | **不一致** | 「接單時限／逾時未接」在 api 零命中；只有 30 分 `dispatch_delay` 告警且動作僅 WS publish，無擴池、無通知客服 | [TC-DISPATCH-04.md](TC-DISPATCH-04.md) |
| TC-DISPATCH-05 | 部分實作 | 投影 10 欄 vs `work_orders` 51 欄，地址只有 `district`；但投影中找不到金額欄位 | [TC-DISPATCH-05.md](TC-DISPATCH-05.md) |
| TC-DISPATCH-06 | 部分實作 | fail-closed 分支存在，但由 `dispatch_policy.brand_auth_enforce` 控且預設 off | [TC-DISPATCH-06.md](TC-DISPATCH-06.md) |
| TC-DISPATCH-09 | 部分實作 | `dispatch_pending` 全 repo 零命中，空池回空候選清單；急件僅 5% score boost 非權重覆寫 | [TC-DISPATCH-09.md](TC-DISPATCH-09.md) |
| TC-EXC-06 | 部分實作 | 冪等鍵是 `event_id`，TC 指名的 `seq` 只在 `work_order_events` 且不在 Kafka payload | [TC-EXC-06.md](TC-EXC-06.md) |
| TC-PERF-03 | 無法靜態判定 | `loadtest/` 中 `300`／`match`／`dispatch` 皆零命中；門檻為 p95 500／1000ms 且標的為 API | [TC-PERF-03.md](TC-PERF-03.md) |
| TC-NFR-SLA-01 | 無法靜態判定 | `ARRIVAL_OVERDUE_MINUTES=120` 錨點為 `scheduled_at` 非派工時刻；retry queue／email fallback 零命中 | [TC-NFR-SLA-01.md](TC-NFR-SLA-01.md) |
| TC-NFR-SCAL-01 | 無法靜態判定 | 全域限流 config 自述「僅回 header 不真擋」；生效限流僅兩處 per-IP in-memory | [TC-NFR-SCAL-01.md](TC-NFR-SCAL-01.md) |

已於前批走查、本 SC 沿用：[TC-DISPATCH-03](TC-DISPATCH-03.md)（不一致）、[TC-NFR-PERF-01](TC-NFR-PERF-01.md)（無法靜態判定）。

### SC-06（現場作業與工單完工，15 支，本批新走查 9 支）

| TC | 判定 | 事實摘要 | 文件 |
|---|---|---|---|
| TC-WO-04 | 一致 | `error_code` / 422 / 照片門檻 3 皆有對應，門檻可由 M18 config 覆寫 | [TC-WO-04.md](TC-WO-04.md) |
| TC-WO-05 | 一致 | 簽名判定為「id 非空 AND `digital_signatures` 查得到 customer 列」雙條件 | [TC-WO-05.md](TC-WO-05.md) |
| TC-WO-06 | 一致 | `serial_required_categories` 預設 `["install"]`，repair 不在清單內故放行 | [TC-WO-06.md](TC-WO-06.md) |
| TC-WO-07 | 部分實作 | override 通過與技師 403 皆有；`COMPLETE_OVERRIDE` 載體為 `service_report` 文字與 `work_order_events` payload，`audit_events` 在完工路徑零寫入 | [TC-WO-07.md](TC-WO-07.md) |
| TC-WO-08 | 一致 | 409 `STATE_CONFLICT`，事件寫入在 UPDATE 之後；探針實測事件筆數 0→0 | [TC-WO-08.md](TC-WO-08.md) |
| TC-WO-14 | 一致 | 推播連結、重送 upsert、跨租戶 403+404、角色白名單、只存 `token_hash` 五項齊備 | [TC-WO-14.md](TC-WO-14.md) |
| TC-ONSITE-01 | 部分實作 | GPS 到場事件與 media purpose 分類齊備；TC 指名的工單狀態 `on_site` 零命中，`record_arrival` 不改 status | [TC-ONSITE-01.md](TC-ONSITE-01.md) |
| TC-ONSITE-05 | 部分實作 | service 層支援 liff/qr/paper 三值且非法值 422；兩個 HTTP 端點皆不傳該參數故恆為 liff | [TC-ONSITE-05.md](TC-ONSITE-05.md) |
| TC-ONSITE-06 | 部分實作 | 例外類型、分流、`high_risk_hold` 擋完工、取消存證皆齊；開立異常端點 RBAC 不含 technician | [TC-ONSITE-06.md](TC-ONSITE-06.md) |

已於前批走查、本 SC 沿用：[TC-CS-AI-06](TC-CS-AI-06.md)（部分實作）、[TC-DISPATCH-03](TC-DISPATCH-03.md)（不一致）、[TC-DISPATCH-05](TC-DISPATCH-05.md)（部分實作）、[TC-COMPLIANCE-06](TC-COMPLIANCE-06.md)、[TC-NFR-SLA-01](TC-NFR-SLA-01.md)。`TC-SETTLE-02` 見 SC-08。

### SC-07（現場加價與重新報價，7 支，本批新走查 6 支）

| TC | 判定 | 事實摘要 | 文件 |
|---|---|---|---|
| TC-ONSITE-02 | 部分實作 | ≤500 分級為 minor 且 `requires_supervisor=False` 成立；`record_scope_change` 對所有 tier 一律 `status='pending'`，無「三件套齊即通過」分支 | [TC-ONSITE-02.md](TC-ONSITE-02.md) |
| TC-ONSITE-03 | 部分實作 | quote v+1 與客戶 LIFF 確認鏈路存在，但入口是 requote command 且與金額無關；501–2000 觸發自動建 v+1 的分支找不到 | [TC-ONSITE-03.md](TC-ONSITE-03.md) |
| TC-ONSITE-04 | 部分實作 | >2000 主管強制存在於 quote `:send`（403 `REQUOTE_SUPERVISOR_REQUIRED`）；scope change 側無強制點，「影音+文字+before/after 照必齊」無對應閘門 | [TC-ONSITE-04.md](TC-ONSITE-04.md) |
| TC-ONSITE-06 | 部分實作 | 同 SC-06（本 TC 跨兩個 SC，只產一份） | [TC-ONSITE-06.md](TC-ONSITE-06.md) |
| TC-ONSITE-07 | 部分實作 | v+1 supersedes 串鏈與客戶 accept 齊備；`on_site→quoted` 狀態不存在，accept/decline 不回寫工單或 `requote_requests` | [TC-ONSITE-07.md](TC-ONSITE-07.md) |
| TC-DISPATCH-07 | 部分實作 | 四斷言中三項一致（不含金額的 command、非 assignee 403、同 `request_id` 冪等回放）；保固/建案 403 的 gate 在 quote `:send` 而非 command 入口 | [TC-DISPATCH-07.md](TC-DISPATCH-07.md) |

已於前批走查、本 SC 沿用：[TC-QUOTE-04](TC-QUOTE-04.md)（部分實作）。

### SC-08（結算與月結，11 支，本批新走查 10 支）

| TC | 判定 | 事實摘要 | 文件 |
|---|---|---|---|
| TC-WO-12 | 部分實作 | S1~S4 金額與 TC 相同；S5 的 `completed_ratio` 編排層未傳，實測為工項全額；audit payload 無 `initiator_role` | [TC-WO-12.md](TC-WO-12.md) |
| TC-SETTLE-02 | 部分實作 | 200／L1 tier／三維落庫皆符；核准僅 append `approval_chain` 不寫 `audit_events`；無 executor 執行路徑 | [TC-SETTLE-02.md](TC-SETTLE-02.md) |
| TC-SETTLE-03 | 一致 | header 層與 service 層同一實作，任二相同 403 `SOD_VIOLATION`，DB 兩條 CHECK backstop | [TC-SETTLE-03.md](TC-SETTLE-03.md) |
| TC-SETTLE-04 | **不一致** | 判定基準兩條（超限拒絕並升級、`min(requested, role_limit)`）皆無程式碼；`role_limit` 家族零命中 | [TC-SETTLE-04.md](TC-SETTLE-04.md) |
| TC-SETTLE-05 | 部分實作 | 24h TTL 冪等回放完整且退款端點全掛 guard；TC 指名的「退款執行」端點不存在，`status='executed'` 無寫入點 | [TC-SETTLE-05.md](TC-SETTLE-05.md) |
| TC-SETTLE-06 | 一致 | review→cosign 兩段雙簽、同人連簽 403 `SOD_VIOLATION`、未經 review 409 `DUAL_SIGN_REQUIRED`，DB CHECK backstop | [TC-SETTLE-06.md](TC-SETTLE-06.md) |
| TC-SEC-SOD-01 | 部分實作 | 退款走三維 header 兩變體皆攔；對帳與爭議走雙人 co-sign 無 executor 維度；「月結」有兩種讀法，月結批次模組無任何 SoD 比對 | [TC-SEC-SOD-01.md](TC-SEC-SOD-01.md) |
| TC-SEC-IDEM-01 | 一致 | `Idempotency-Key` 掛載 140 個端點，24h TTL 回放 | [TC-SEC-IDEM-01.md](TC-SEC-IDEM-01.md) |
| TC-PAYMENT-01 | 部分實作 | 驗簽 401／`provider_txn_id` 冪等＋唯一索引可靜態確認；`payment_service` 零 router 接線，無 payment→voucher 關聯 | [TC-PAYMENT-01.md](TC-PAYMENT-01.md) |
| TC-WEB-REPORT-01 | 部分實作 | 五條判定基準狀態各異（一致 1、不一致 1、部分實作 1、無法靜態判定 2），詳見文件逐條表 | [TC-WEB-REPORT-01.md](TC-WEB-REPORT-01.md) |

已於前批走查、本 SC 沿用：[TC-QUOTE-04](TC-QUOTE-04.md)（部分實作）。

### SC-09（對帳與報表，4 支，本批新走查 3 支）

| TC | 判定 | 事實摘要 | 文件 |
|---|---|---|---|
| TC-SETTLE-01 | 部分實作 | 唯一 monthly job 是技師對帳單 draft；月結批次無 cron 只有端點；`commission.accrued` 發自對帳核准而非月結 cron | [TC-SETTLE-01.md](TC-SETTLE-01.md) |
| TC-SETTLE-02 | 部分實作 | 同 SC-08（本 TC 跨三個 SC，只產一份） | [TC-SETTLE-02.md](TC-SETTLE-02.md) |
| TC-WEB-REPORT-01 | 部分實作 | 同 SC-08（本 TC 跨兩個 SC，只產一份） | [TC-WEB-REPORT-01.md](TC-WEB-REPORT-01.md) |

已於前批走查、本 SC 沿用：[TC-EXC-01](TC-EXC-01.md)（部分實作）。

### 末批：前綴分組（58 支）

SC-10～SC-19 剩餘者與 34 支無 SC 歸屬的橫切案例，改按 TC 前綴併為 6 組平行走查。SC-10 的 5 支全數已於前批涵蓋，無專屬案例。

#### A 組 — 合規與稽核（10 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-COMPLIANCE-01 | 部分實作 | 兩階段狀態機／cron／purge ledger 皆有落點；cron 呼叫 `hard_delete` 未傳必填的 `tenant_id`，`agent.*` 記憶不在 forget 涵蓋範圍 | [TC-COMPLIANCE-01.md](TC-COMPLIANCE-01.md) |
| TC-COMPLIANCE-02 | 部分實作 | 423 `LEGAL_HOLD_ACTIVE` 與 audit `gdpr_forget_blocked` 精確命中且有測試釘住；「7d 內客戶通知」只有欄位無發送程式碼 | [TC-COMPLIANCE-02.md](TC-COMPLIANCE-02.md) |
| TC-COMPLIANCE-03 | 部分實作 | 遮蔽工具與 65 處識別碼截斷存在；`scrub_text` 只掛 OTel span 與 audit payload，logging 管道無 filter | [TC-COMPLIANCE-03.md](TC-COMPLIANCE-03.md) |
| TC-COMPLIANCE-04 | 一致 | 過期軟刪、list 排除、RMA/保固 +3y、legal-hold 不刪四項全有落點，18 項既有測試全過 | [TC-COMPLIANCE-04.md](TC-COMPLIANCE-04.md) |
| TC-COMPLIANCE-05 | 部分實作 | adopt 硬 gate（425 `FAMILY_REVIEW_REQUIRED`）與 24h SLA cron 存在；覆核率報表與暫停 publish 無對應機制 | [TC-COMPLIANCE-05.md](TC-COMPLIANCE-05.md) |
| TC-COMPLIANCE-08 | 部分實作 | 語料軌 bronze-only／PDF 僅引 URL 機器可查核（`audit_corpus` 實跑通過，862 筆 facts）；TC 字面指名的 skills references 樹不在稽核範圍 | [TC-COMPLIANCE-08.md](TC-COMPLIANCE-08.md) |
| TC-NFR-AUD-01 | 部分實作 | actor／原因／hash／竄改偵測／匯出權限有落點；`trace_id` 與版本欄零命中，`audit_events` 無 `tenant_id` | [TC-NFR-AUD-01.md](TC-NFR-AUD-01.md) |
| TC-NFR-PRIV-01 | 部分實作 | 三套加密、遮罩、投影白名單、legal hold 阻刪皆有落點；撤回 consent 無專屬路徑，DEK 90d rotation 無對應 | [TC-NFR-PRIV-01.md](TC-NFR-PRIV-01.md) |
| TC-NFR-DQ-01 | 部分實作 | Python 覆寫以探針實測證實；「誤放率」三處零命中，NFR-DQ-004 門檻本身標 `[待確認]` | [TC-NFR-DQ-01.md](TC-NFR-DQ-01.md) |
| TC-NFR-SCH-01 | 部分實作 | 125 支 migration 冪等掃描 0 缺漏、drift-check 實跑偵測到幽靈列並 exit 1；forward-only 無程式化 gate | [TC-NFR-SCH-01.md](TC-NFR-SCH-01.md) |

#### B 組 — 安全（12 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-SEC-RBAC-01 | 部分實作 | technician/vendor 403 有實作與測試；授權矩陣為 7 角色（非 TC 的 12）且不參與端點放行 | [TC-SEC-RBAC-01.md](TC-SEC-RBAC-01.md) |
| TC-SEC-RBAC-02 | 部分實作 | 未列組合 deny-by-default 成立；「僅矩陣允許之組合通過」不成立——矩陣為 shadow log-only（`role_service.py:371`／`deps.py:347`） | [TC-SEC-RBAC-02.md](TC-SEC-RBAC-02.md) |
| TC-SEC-RBAC-03 | 一致 | router `role_required(*OPS_ROLES)` ＋ service `_assert_namespace_writable` 兩層，三種身分各有測試 | [TC-SEC-RBAC-03.md](TC-SEC-RBAC-03.md) |
| TC-SEC-RBAC-04 | 一致 | 403 `ACCOUNT_DISABLED` / 401 `TOKEN_STALE` 字面相符，重查掛在 `get_current_user` 單點 | [TC-SEC-RBAC-04.md](TC-SEC-RBAC-04.md) |
| TC-SEC-RBAC-05 | 一致 | logout 寫 `revoked_jti`、每請求 `is_jti_revoked` 命中回 401 `TOKEN_REVOKED` | [TC-SEC-RBAC-05.md](TC-SEC-RBAC-05.md) |
| TC-SEC-WEB-01 | 部分實作 | 後端 `role_required` 覆蓋 383/517、v2/legacy 稽核零不對稱；前端未登記路由為 allow-by-default（與 TC 的 deny-by-default 相反） | [TC-SEC-WEB-01.md](TC-SEC-WEB-01.md) |
| TC-SEC-WEB-02 | 部分實作 | `resolveTenantId()` 已導回登入（四站台皆同）；`auth.getTenantId()` 仍靜默 fallback 至預設租戶 | [TC-SEC-WEB-02.md](TC-SEC-WEB-02.md) |
| TC-SEC-INJ-01 | 無法靜態判定 | 攔截率需 live LLM；repo 內無 50 題注入語料，200 題禁區 corpus 七分類無 injection 類 | [TC-SEC-INJ-01.md](TC-SEC-INJ-01.md) |
| TC-SEC-INJ-02 | 無法靜態判定 | 誤攔率需 live LLM；repo 內無 100 題正常對話語料、無誤攔率計算函式 | [TC-SEC-INJ-02.md](TC-SEC-INJ-02.md) |
| TC-SEC-TENANT-01 | 部分實作 | 403/404 三層隔離與不洩存在性皆有落點；`cross_tenant_violation_attempted` 在 `api/` 零命中 | [TC-SEC-TENANT-01.md](TC-SEC-TENANT-01.md) |
| TC-SEC-PIPE-01 | 部分實作 | 檔案層 drift 阻斷已探針實測 exit 1；CI job 不帶任何 DB URI，TC 指名的 `schema_migrations` 對照段在 CI 中不執行 | [TC-SEC-PIPE-01.md](TC-SEC-PIPE-01.md) |
| TC-NFR-SEC-01 | 部分實作 | 認證／Output Guardrail／At-rest／Secrets 四項有落點；傳輸加密（HSTS 等）零命中，無 secret 掃描 | [TC-NFR-SEC-01.md](TC-NFR-SEC-01.md) |

#### C 組 — 工單、例外、結算尾數（9 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-WO-09 | 一致 | 冪等回放、不重複建單（業務層 + partial UNIQUE）、單號不重複三條各有兩層以上落點 | [TC-WO-09.md](TC-WO-09.md) |
| TC-WO-10 | 部分實作 | `notify_supervisor` / `PT2H` / `dispatched` 零命中；功能對應物 `arrival_overdue`（120 分鐘、`escalated_to=ops_manager`）完整存在 | [TC-WO-10.md](TC-WO-10.md) |
| TC-WO-11 | 部分實作 | `HIGH_RISK_HOLD` 422 掛在 assign 與 complete 兩路徑；`exception_type` 值域無 TC 指名的 `safety` | [TC-WO-11.md](TC-WO-11.md) |
| TC-EXC-02 | 一致 | sentinel `"[litellm error]"` 字面存在，攔截後回 `_FALLBACK_REPLY`，原文只進 log | [TC-EXC-02.md](TC-EXC-02.md) |
| TC-EXC-03 | 部分實作 | 罐頭回覆與轉真人有落點；配額耗盡的不重試分類因入口條件未滿足而不生效（`error_status_code` 未填） | [TC-EXC-03.md](TC-EXC-03.md) |
| TC-EXC-04 | 一致 | claims-only fail-open 與 fail-closed 白名單 20 端點兩半皆對上，另有反射式防漂移測試 | [TC-EXC-04.md](TC-EXC-04.md) |
| TC-EXC-05 | 部分實作 | 啟動守衛存在且訊息明確，但為 opt-in（`DB_URI_STRICT=1`）；`all`／`dispatch` 下 fallback 單庫 | [TC-EXC-05.md](TC-EXC-05.md) |
| TC-SETTLE-07 | 部分實作 | append-only 與 100 筆 hash 抽驗皆已實測通過；TC 指名的欄位名 `hash_self`／`hash_prev` 屬 `saas.voucher`，`audit_events` 用的是 `entry_hash`／`prev_hash` | [TC-SETTLE-07.md](TC-SETTLE-07.md) |
| TC-SETTLE-08 | 部分實作 | 成本欄位遮蔽完整；佣金／月結 statement 端點全為 `OPS_ROLES`，技師/vendor 是 403 而非「見自己 scope」 | [TC-SETTLE-08.md](TC-SETTLE-08.md) |

#### D 組 — 平台／技師／知識庫／Agent（12 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-PLT-PROV-01 | 部分實作 | 租戶登錄冪等且 License 模型齊備；License 寫入無 provisioning 完成度前置檢查，`provisioning` 全樹零命中 | [TC-PLT-PROV-01.md](TC-PLT-PROV-01.md) |
| TC-PLT-FLOW-01 | **不一致** | `flow_dsl`／`block_library`／`vertical_pack`／`workflow_definition`／`積木`／`DSL` 六識別碼在 api/web/SQL/agent/scripts 全數零命中 | [TC-PLT-FLOW-01.md](TC-PLT-FLOW-01.md) |
| TC-PLT-CFG-01 | 部分實作 | 保護層／rollback／audit 有落點；受保護 namespace 僅 `payment_gate`，SLO 檢查只回決策不真 halt | [TC-PLT-CFG-01.md](TC-PLT-CFG-01.md) |
| TC-PLT-SURFACE-01 | 一致 | 跨面 403、缺 portal claim 由 role 推導、平台獨立 guard 與獨立庫、拒絕早於業務查詢四項皆有落點，99 項既有測試全過 | [TC-PLT-SURFACE-01.md](TC-PLT-SURFACE-01.md) |
| TC-TEC-LIFE-01 | 部分實作 | 未核可者硬排除候選池成立；「重送冪等」實際回 409 `EMAIL_TAKEN`，`technician.registered` 零命中 | [TC-TEC-LIFE-01.md](TC-TEC-LIFE-01.md) |
| TC-TEC-REVOKE-01 | 部分實作 | 停權排除與復權守衛成立；撤銷「認證」不進派工判定，撤銷/停權路徑無通知程式碼 | [TC-TEC-REVOKE-01.md](TC-TEC-REVOKE-01.md) |
| TC-REF-INTAKE-01 | 部分實作 | refinery 側 gate／tenant default-deny／冪等／provenance 齊備；bronze-only 紅線 gate 位於 corpus 層而非 bronze 入口 | [TC-REF-INTAKE-01.md](TC-REF-INTAKE-01.md) |
| TC-REF-SPLIT-01 | 部分實作 | 兩軌分流、append-only、re-refine 皆成立；惡意覆寫 prompt 只有 system prompt 文字鐵律與 schema | [TC-REF-SPLIT-01.md](TC-REF-SPLIT-01.md) |
| TC-REF-PUBLISH-01 | 部分實作 | 未核可零落地與跨租戶阻擋成立；`publish_case_entry` 無 bronze 來源校驗（`knowledge-pipeline/refinery/` 內 `bronze` 零命中） | [TC-REF-PUBLISH-01.md](TC-REF-PUBLISH-01.md) |
| TC-AGT-CLARIFY-01 | **不一致** | `clarification_attempts` 與 `clarification_confirmed_at` 全樹零命中；正典自身於 `04_SRS.md:595` 與 ADR-033 記錄該行為已被 SOP 情境式紅線取代 | [TC-AGT-CLARIFY-01.md](TC-AGT-CLARIFY-01.md) |
| TC-AGT-URG-01 | 部分實作 | escalation spool 補送與問題卡 24h 冪等鍵成立；`emergency_class` 由客服後台標記（agent 側零命中），5 分鐘 SLA 無程式判定 | [TC-AGT-URG-01.md](TC-AGT-URG-01.md) |
| TC-AGT-RAG-01 | 部分實作 | tenant default-deny、閾值過濾、MCP timeout 降級皆成立；manual 檢索無相似度閾值，「LLM 是否編造」無法靜態判定 | [TC-AGT-RAG-01.md](TC-AGT-RAG-01.md) |

#### E 組 — Web 前端與無障礙（7 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-WEB-MEDIA-01 | 部分實作 | `AuthImage` 授權 fetch→Blob、失敗佔位、revoke、token 不外露皆有落點；TC 步驟列的三個畫面中對話頁沒有 lightbox | [TC-WEB-MEDIA-01.md](TC-WEB-MEDIA-01.md) |
| TC-WEB-OPS-01 | 部分實作 | 有姓名時顯示全名成立；後端把空姓名輸出為 `""`、前端兩層 `??` 不攔空字串，缺姓名走「尚未指派技師」而非註解宣稱的 shortId fallback | [TC-WEB-OPS-01.md](TC-WEB-OPS-01.md) |
| TC-WEB-SURFACE-01 | 部分實作 | 四 build 的實體路由裁剪＋`crossModeRedirect` 兩層機制齊備；登入後角色路由政策是 allow-by-default，導向全在 `useEffect` 內、四站皆無 middleware | [TC-WEB-SURFACE-01.md](TC-WEB-SURFACE-01.md) |
| TC-A11Y-01 | 無法靜態判定 | 判定基準是 NVDA/VoiceOver n=10 任務成功率；repo 內無 LIFF 前端，對應頁面是 brand-portal 四支 token 公開頁 | [TC-A11Y-01.md](TC-A11Y-01.md) |
| TC-A11Y-02 | 部分實作 | 對比在 token 層可算且 tech-portal 有既有檢核（門檻 4.5 非 7:1）；觸控目標與渲染後對比無法靜態判定 | [TC-A11Y-02.md](TC-A11Y-02.md) |
| TC-NFR-A11Y-01 | 部分實作 | 焦點兜底、skip link、不禁止縮放、mutation rollback 契約皆有落點；axe/keyboard fixture 零命中，無表單草稿保存 | [TC-NFR-A11Y-01.md](TC-NFR-A11Y-01.md) |
| TC-NFR-REP-01 | 部分實作 | 末段確定性與冪等成立且實跑三次數字相同；raw 層無阻擋、稽核不落檔、產出無 config 指紋 | [TC-NFR-REP-01.md](TC-NFR-REP-01.md) |

#### F 組 — 效能與運維 NFR（8 支）

| TC ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
| TC-PERF-02 | 部分實作 | 100 VU 壓測資產與 CI 觸發器存在；門檻常數是 500/1000ms、標的六 task 全為工單 API 不含 LINE AI 首回應 | [TC-PERF-02.md](TC-PERF-02.md) |
| TC-PERF-04 | 部分實作 | 罐頭回覆降級完整；全域限流 `enabled = false`、V2 派工/工單端點零限流，熔斷器實作存在卻因 `fallback_models = []` 未接上 | [TC-PERF-04.md](TC-PERF-04.md) |
| TC-PERF-05 | 部分實作 | p50/p95/p99 計算與 30s SLO 常數存在；樣本存 in-process deque，全體桶的 `slo_met` 讀的是 p95 而 NFR-Perf-009 的基準是 p99 | [TC-PERF-05.md](TC-PERF-05.md) |
| TC-NFR-AVAIL-01 | 部分實作 | 十項依賴中九項有明確中斷分支（fail-closed/fail-open 分流、DLQ、退單機、冪等鍵）；Refinery 一項無出向呼叫故無降級分支 | [TC-NFR-AVAIL-01.md](TC-NFR-AVAIL-01.md) |
| TC-NFR-DORA-01 | 部分實作 | release manifest 21 欄位、不可變 digest、rollback 指令自動生成、audit hash chain 皆到位；DORA 四指標的計算實作零命中 | [TC-NFR-DORA-01.md](TC-NFR-DORA-01.md) |
| TC-NFR-MAINT-01 | 部分實作 | typecheck/OpenAPI 結構/型別同步/v1 凍結/E2E 五道 gate 存在；coverage 在 20 支 workflow 零命中 | [TC-NFR-MAINT-01.md](TC-NFR-MAINT-01.md) |
| TC-NFR-OBS-01 | 部分實作 | PII scrub 雙防線完整，request/webhook/turn 三種 span 存在；LLM 層與背景 worker 無 OTel span、無 `traceparent` 傳遞 | [TC-NFR-OBS-01.md](TC-NFR-OBS-01.md) |
| TC-NFR-PUB-01 | 部分實作 | 未核可零落地與跨租戶 default deny 完整；append-only 在 revision 層成立但檔案層不成立；同源檢查腳本存在卻未接進任何 CI job | [TC-NFR-PUB-01.md](TC-NFR-PUB-01.md) |

## 本機測試資料庫

前四批（SC-01～SC-03）的 API 側測試因無資料庫而失敗，2026-08-03 建立本機 Docker 測試庫後重跑，數字如下節。**此環境僅供跑既有測試取得執行證據，未啟動任何應用服務，走查判定仍以原始碼為準。**

| 項目 | 內容 |
|---|---|
| 容器 | `smartlock-test-db`（`pgvector/pgvector:pg17`，host port 5433，拋棄式） |
| 品牌庫 | `lock_scratch_test`——82 張表（public schema）、124 支 migration 已登記、已套 `SQL/seeds/`（含 `problem_cards.sql`、`work_orders.sql`）與 `SQL/tech_authority/Schema_cqrs_projection.sql` |
| 技師庫／平台庫 | **未建，且測試不需要**。`TECH_POSTGRES_URI` 未設時走單庫 fallback（`api/core/db.py:244`），技師投影表落於品牌庫；既有測試取用的是品牌連線 `db_module._conn` |

建置過程中的三點環境事實（非程式缺陷）：

1. `scripts/db/make-test-db.sh` 預期的本機 UAT 庫容器 `lock-dispatch-locksmart-db-1` 不存在，「複製既有庫」路徑不可用，改為從 `SQL/` 從零建。
2. `SQL/` 根目錄有 11 支 base schema（非 3 支），需全部套用；主機未安裝 `psql`，改以轉發進容器的 shim 執行 `scripts/db/apply-schema-routed.sh`。
3. **Windows 預設的 ProactorEventLoop 不支援 psycopg async**（`api/db.py:60` 報 `Psycopg cannot use the 'ProactorEventLoop'`），而 `api/tests/conftest.py:47-50` 的 `event_loop_policy` fixture 回傳 `asyncio.DefaultEventLoopPolicy()`。實跑時以本機 pytest plugin（`-p winloop_plugin`，置於 scratchpad，未進 repo）切換為 Selector policy。
4. `SQL/` 根目錄的 11 支 base schema **不含** `SQL/tech_authority/Schema_cqrs_projection.sql`，該檔需另行套用，否則 `technician_workorder_projection`／`technician_commission_projection`／`event_consumer_dedup` 三表缺席。
5. `api/tests/test_cr_0193_lifecycle_events.py` 的 fixture 需要庫中**已有工單**才不 skip（`:46-49`），故需另套 `SQL/seeds/problem_cards.sql` 與 `SQL/seeds/work_orders.sql`。
6. `agent/tests/test_skill_sync.py` 6 項在本機失敗於 `agent/lockcore/agent/skill_sync.py:210` 的 `os.symlink`，錯誤為 `OSError: [WinError 1314] 用戶端沒有這項特殊權限`——Windows 建立 symlink 需 SeCreateSymbolicLinkPrivilege（開發者模式或系統管理員），屬主機權限限制。

## 本批測試執行摘要

```
cd agent && python -m pytest tests/test_skills_loaded.py tests/test_cr_0081_forbidden_eval.py \
  tests/test_reply_guard.py tests/test_cr_0074_redline.py tests/test_transfer_to_human.py \
  tests/test_photo_guide.py tests/test_memory.py tests/test_line_gateway.py \
  tests/test_e2e_mock_turn.py tests/test_tool_allowlist.py tests/test_mcp_allowlist_boundary.py \
  tests/test_fallback_reply_no_handoff.py tests/test_cr_0196_reply_latency.py \
  tests/test_webhook_idempotency.py -q -rs

1 failed, 170 passed, 3 skipped in 15.86s
```

- 失敗：`test_line_gateway.py::test_debouncer_serializes_fires_per_session`（單獨重跑 3 次皆通過，見 TC-CS-AI-08）
- Skip：`test_webhook_idempotency.py` 3 項，理由 `需 POSTGRES_URI`

### SC-02 批次

agent 側：

```
cd agent && python -m pytest tests/test_line_gateway.py tests/test_escalation_spool_durability.py \
  tests/test_spool_flush_bounded.py tests/test_sentiment.py \
  tests/test_fallback_reply_no_handoff.py tests/test_cr_0086_ai_intake_live.py -q -rs

116 passed, 2 skipped in 6.33s
```

API 側：

```
cd api && python -m pytest tests/test_internal_ingest.py tests/test_escalation_to_draft_pc.py \
  tests/test_pc_convert_to_wo.py tests/test_cr_0119_line_photo_ingest.py \
  tests/test_cr_0175_outbox_idempotency.py tests/test_cr_0172_tech_dispatch_outbox.py \
  tests/test_cr_0017_outbox_worker.py -q --tb=no -rf

22 failed, 25 passed in 5.36s
```

- Skip：`test_cr_0086_ai_intake_live.py` 2 項，理由「需 Vertex 憑證」
- 失敗的 22 項全部集中在需資料庫的四個檔案（`test_internal_ingest`、`test_escalation_to_draft_pc`、`test_pc_convert_to_wo`、`test_cr_0119_line_photo_ingest`），錯誤為 `503 DB_UNAVAILABLE` / `環境變數 POSTGRES_URI 未設定`。這些檔案無 skipif 守衛，故為 failed 而非 skipped
- 三個 outbox 測試檔全數通過，作為 TC-DISPATCH-03 與 TC-EXC-01 的執行證據

### SC-03 批次

```
cd agent && python -m pytest tests/test_transfer_to_human.py tests/test_sentiment.py \
  tests/test_cr_0074_redline.py -q -rs
21 passed in 3.09s

cd agent && python -m pytest tests/test_tool_allowlist.py tests/test_e2e_mock_turn.py -q -rs
5 passed in 3.48s

cd agent && python scripts/sentiment_eval.py --dry
✅ dry：corpus 120 題結構完整（負面 100）   RC=0

cd api && python -m pytest tests/test_cr_0129_retro_audit.py tests/test_cr_0128_quote_gate.py -q --tb=no -rf
16 failed, 2 passed in 0.48s
```

- API 側失敗同前批原因：`POSTGRES_URI` 未設定，無 skipif 守衛故為 failed 而非 skipped

### 建立測試庫後的實跑結果

| 批次 | 無資料庫 | 本機測試庫 |
|---|---|---|
| SC-02（7 檔） | 22 failed / 25 passed | **47 passed** |
| SC-03（2 檔） | 16 failed / 2 passed | **18 passed** |
| SC-04 報價批（9 檔） | 32 failed / 31 passed | **3 failed / 66 passed** |
| SC-05 派工批（9 檔） | 13 failed / 39 passed | **59 passed** |
| TC-WO-01 兩檔 | 19 skipped / 7 error | **26 passed** |
| agent 側 webhook 冪等 | 3 skipped | **3 passed** |

補齊投影 schema 與 seed 後，剩餘失敗只有一類：

- `test_cr_0095_quote_line_approval.py` 3 項——`api/services/quote_engine_service.py:785` 拋 `TypeError: 'coroutine' object is not subscriptable`（詳見 TC-QUOTE-08、TC-QUOTE-09）

agent 全套（`cd agent && pytest`）為 **7 failed / 338 passed / 2 skipped**（接庫前同一入口為 1 failed / 170 passed / 3 skipped——設了 `POSTGRES_URI` 後被啟用的測試變多）。失敗皆與資料庫無關，且**兩次執行的組成不同**：

| 執行 | 失敗組成 |
|---|---|
| 第一次 | `test_line_gateway.py::test_debouncer_serializes_fires_per_session` 1 項 + `test_skill_sync.py` 6 項 |
| 第二次 | `test_skill_sync.py` 7 項（debouncer 該輪通過） |

`test_skill_sync.py` 的失敗為前述 Windows symlink 權限限制。`test_debouncer_serializes_fires_per_session` 為時序敏感的間歇性測試——本批次執行中失敗一次、通過一次，先前單獨重跑 3 次亦皆通過（記錄於 TC-CS-AI-08）。此處僅陳述觀測到的執行差異，不裁定。

## 執行順序

1. ~~樣板 TC-WO-01~~（完成）
2. ~~SC-01（13 支）~~（完成）
3. ~~SC-02（12 支，新走查 9 支）~~（完成）
4. ~~SC-03（6 支，新走查 4 支）~~（完成）
5. ~~SC-04（12 支，新走查 10 支）~~（完成）
6. ~~SC-05（12 支，新走查 10 支）~~（完成）
7. ~~SC-06（15 支，新走查 9 支）~~（完成）
8. ~~SC-07（7 支，新走查 6 支）~~（完成）
9. ~~SC-08（11 支，新走查 10 支）~~（完成）
10. ~~SC-09（4 支，新走查 3 支）~~（完成）
11. ~~末批：SC-10～SC-19 剩餘者與 34 支無 SC 歸屬者，按 TC 前綴併為 A–F 六組平行走查（58 支）~~（完成）

**130 支全數走查完畢。**

> 已走查的 TC 若同時隸屬後續 SC（例：TC-CS-AI-06 亦屬 SC-04、SC-06），不重複產檔，於該 SC 的回報中引用既有文件。
