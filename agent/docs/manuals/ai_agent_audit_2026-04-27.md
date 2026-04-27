# AI 客服全面盤點報告

- **日期**：2026-04-27
- **盤點範圍**：Skill 層、Harness 層、Agent 核心、資料/狀態層、部署/設定、UX 風險
- **總計問題**：30 項（CRITICAL 3 / HIGH 11 / MEDIUM 11 / LOW 5）

---

## 嚴重度：CRITICAL

### 1. 跨 thread checkpoint 串線（GET /chat 預設 user_id）
- **位置**：`agent/app.py:209`
- **症狀**：所有從 `/chat?q=...`（沒帶 user_id）的測試請求共用 `test-cli` thread，先後請求的對話歷史會互相污染，eval 跑批時嚴重。
- **根因**：`user_id="test-cli"` 預設值沒有 per-call 隔離，checkpointer thread = `line_test-cli` 永遠同一條。
- **建議修法**：預設改用 `uuid4()` 或要求 caller 必填 user_id。

### 2. 多模態 octet-stream 與 buffer race（媒體先傳、文字緊接）
- **位置**：`agent/harness/debounce.py:792-826`、`agent/app.py:262-273`
- **症狀**：使用者連發圖+文，若媒體下載 >10s（`media_extra_wait`）會被當「處理超時」用佔位文字塞入，圖片實際內容遺失；若下載稍晚於佔位被取出但搶先 buffer pop，會丟棄該媒體。
- **根因**：佔位與替換用獨立 `add_message_to_buffer()` 呼叫，但 `process_and_reply` 取 buffer 後 user_buffers 被 del，下載晚到的 `replace_media_pending` 找不到 key → 媒體被丟到一個新的 buffer 並重新觸發 agent。
- **建議修法**：在 process_and_reply 取出 items 前 lock 該 user，或檢查到 media_pending 殘留時繼續等待真實到達。

### 3. Quick Reply 暫存遺失原始問題（pending → 未 pop 即覆蓋）
- **位置**：`agent/harness/debounce.py:606-616, 619-629`
- **症狀**：用戶 A 訊息 → 系統問品牌；A 在等回覆時又連送一則訊息（debounce buffer 觸發）→ 進入 `_quick_reply_intercept` 狀態 B，狀態 A 的 `_pending_messages` 會被覆寫成新內容，第一個原始問題永遠不會被回答。
- **根因**：`_pending_messages[user_id]` 為單槽，沒做佇列；連續啟動 quick reply 時前一筆被丟棄。
- **建議修法**：偵測已有 pending 時將新訊息 append（合併原文）而非覆蓋。

---

## 嚴重度：HIGH

### 4. data_correction 攔截不檢查邊界（`#資料修正` 為前綴匹配）
- **位置**：`agent/harness/data_correction.py:118-120`
- **症狀**：使用者寫「我要查 #資料修正流程」之類文字仍會 startswith 命中，吞掉訊息直接回模板。
- **根因**：用 `stripped.startswith(_keyword)` 而非要求單獨成行或前後有空白邊界。
- **建議修法**：改成 `stripped == keyword` 或要求 keyword 後接空白/EOL。

### 5. 安全閘門關鍵字嚴重不足
- **位置**：`agent/config.toml:48`
- **症狀**：dangerous_keywords 只有 4 個跟「破壞鎖具」相關的詞，完全沒涵蓋自殺、自傷、暴力、家暴、緊急醫療、未成年議題等高風險語意；遭遇高風險訊息只會走一般 LLM 回覆。
- **根因**：列表硬編碼為門鎖物理破壞，沒考慮被鎖在外的情緒崩潰與其他社群風險。
- **建議修法**：擴充自傷、緊急、暴力相關詞庫並提供求助資源回覆。

### 6. transfer_to_human guard 容易繞過
- **位置**：`agent/skills/tools.py:243-253, 26-31`
- **症狀**：使用者輸入「報價」「費用」「多少錢」會被認定為「明確轉接意圖」直接放行轉接 → 但這些是知識性問題，本應回知識庫；同時客戶說「請快點派師傅來」也會繞過 load_skill。
- **根因**：`_TRANSFER_KEYWORDS` 把金錢類問題、派工請求都當「明確轉接」放行。
- **建議修法**：拆分「明確轉真人」與「金錢/派工」兩類；後者需先 load skill 再決定。

### 7. profile_updater 會把錯誤資訊寫死成 fact（無歷史回溯保護）
- **位置**：`agent/harness/profile_updater.py:191-197`
- **症狀**：LLM 在背景萃取 facts 失誤（如把客服範例電話「02-8601-9952」當成用戶電話）後直接 `update_fact` SCD Type 2 寫入；客戶下次轉接會看到錯的電話。
- **根因**：`extract_and_update` 對 phone/address 沒有 confidence check，也沒有將「客服訊息中提到的範例」排除。
- **建議修法**：限定只從 user message 萃取，加 regex 驗證 + 確認用戶第一人稱。

### 8. memory_manager 壓縮對 in-memory `_summaries` dict 在多 worker 下失效
- **位置**：`agent/harness/memory_manager.py:44, 165-172`
- **症狀**：Cloud Run min_instances=1, max_instances=3 → 不同 instance 的 `_summaries` 互不可見；第二個 instance 把同一 thread 拿去 ainvoke 時會缺前情提要（同時可能因 messages 沒被刪到而重複壓縮）。
- **根因**：summary 只存記憶體，沒寫到 checkpoint 或 DB。
- **建議修法**：將 summary 持久化到 user_facts 或 checkpoint metadata。

### 9. audit log 寫死假 model_name
- **位置**：`agent/harness/debounce.py:374, 384, 462-487`
- **症狀**：LLM interaction log 寫的 `model_name` 來自 `_config.get("model_name", "gemini-2.5-flash")`，而 config 中沒有此 key（config.toml 用的是 `[llm].model`），永遠紀錄 "gemini-2.5-flash" 假資料。
- **根因**：`_config["model_name"]` key 不存在，fallback 寫死 flash。
- **建議修法**：從 cfg.llm.model 傳入正確 model 字串，或改紀錄 from llm registry。

### 10. Output validator forbidden_phrases 高誤殺機率
- **位置**：`agent/config.toml:56-60`
- **症狀**：`"系統正在處理"` 屬正常服務語；`"工具呼叫"` 在客戶問「APP 怎麼呼叫客服」時 LLM 回覆會誤觸；validator 命中後會強制重跑 ReAct loop，造成回覆延遲翻倍 + 雙重計費。目前 enabled=false，但一旦開啟就出問題。
- **根因**：禁用詞太通用且未做上下文判斷。
- **建議修法**：縮窄為「載入技能」「load_skill」「請稍等我載入」這類明確內部術語。

### 11. infer_brand_from_text 與 update_user_info 競態 → 品牌髒資料
- **位置**：`agent/harness/debounce.py:282-296`、`agent/skills/tools.py:163-186`
- **症狀**：用戶說「我朋友的 AI-99 也壞了，但我這個 AS701 好像有問題」→ infer_brand_from_text 會 return 第一個匹配的型號（AI-99 / Chatlock），自動寫死 fact；客戶實際是 Dormakaba AS701。後續所有技能解鎖都錯。
- **根因**：infer_brand_from_text 是 first-match wins，沒做語境判斷或衝突偵測。
- **建議修法**：偵測到多個型號匹配時跳過自動推論，改用 quick reply 詢問。

### 12. `_common/troubleshoot` 路由表大量指向不存在的子技能
- **位置**：`agent/skills/data/_common/troubleshoot/SKILL.md:74, 77, 79, 81, 82`
- **症狀**：路由表寫「其他 → load_skill("ts-door-stuck-other")」「ts-verification-other」「ts-power-drain-other」，但實際沒有這些技能檔；當客戶為 3E、Waferlock、Milre、Philips、Kaadas 等品牌問門卡死/驗證/網路時，agent 會嘗試載入不存在的 skill → 走前綴比對 fallback → 給出無關的列表或空回覆。
- **根因**：troubleshoot SKILL.md 的路由表早於部分品牌子技能建立，內容過時。
- **建議修法**：更新路由表精準寫出每個品牌實際存在的子技能名；不存在則改載 product-knowledge。

### 13. `app-guide` 仍假設「客戶為 Chatlock」就引向 AI-99 子技能
- **位置**：`agent/skills/data/Chatlock/_all-models/app-guide/SKILL.md:43-57`
- **症狀**：警語只是文字提醒，但「功能索引」表仍以「load_skill("app-pairing")」等 AI-99 專屬 skill 為主；A90 用戶/AI-88 用戶若 LLM 漏看警語會直接跑下表，雖然已被 `load_skill` 型號 gate 攔住但會吐出「技能不適用」訊息給用戶，UX 退化。
- **根因**：型號 gate 的拒絕訊息會被 LLM 當 tool 結果直接 paraphrase。
- **建議修法**：將「型號分流」表設為強制第一步並在 gate rejection 時直接引導 product-knowledge。

### 14. system-settings 內容對跨品牌引導模糊
- **位置**：`agent/skills/data/Chatlock/_all-models/system-settings/SKILL.md:17`
- **症狀**：system-settings 屬於 Chatlock brand-wide skill，但內文要求 Dormakaba 用戶「呼叫 ss-dormakaba」；雖然品牌過濾會排除非 Chatlock 用戶看到本 skill，但 description 中描述跨品牌選擇會誤導 LLM。
- **建議修法**：description 限定本品牌；跨品牌引導交給上層（system prompt 或 product-knowledge）。

---

## 嚴重度：MEDIUM

### 15. SCD Type 2 update_fact 在新增同值時不會 expire 舊值（race window）
- **位置**：`agent/profiles/manager.py:135-148`
- **症狀**：兩個 concurrent request 同時更新 `device_brand=Chatlock`，CTE 內 `is_current=TRUE AND attr_val != %s` 對相同新值不 expire，但 `NOT EXISTS` 對首次寫入會競爭；可能短暫出現兩筆 is_current=TRUE 同一 attr_key。
- **建議修法**：加上 unique partial index `(user_id, attr_key) WHERE is_current=TRUE`。

### 16. ContextVar 在背景 task 中可能被洩漏到下一請求
- **位置**：`agent/skills/tools.py:19-23`、`agent/harness/debounce.py:760`
- **症狀**：pending 流程跨請求保留，但 ContextVar 重設靠 `run_agent` 入口；其他工具如 `_extract_facts` 不重設。
- **建議修法**：在 `agent_and_reply` 入口無條件 set_current_user_id。

### 17. Quick Reply pending 中圖片 buffer_items 過 5 分鐘 TTL 會丟，但媒體 GCS 物件不清
- **位置**：`agent/harness/debounce.py:43, 893-900`
- **症狀**：pending 過期後使用者重發，但 GCS 物件仍存活，無回收策略。
- **建議修法**：cleanup_stale_buffers 增加 GCS 過期物件刪除（lifecycle policy）。

### 18. config.toml `request_timeout` 240s 與 LINE 90s reply_token 衝突
- **位置**：`agent/config.toml:10`
- **症狀**：LINE reply_token 約 1 分鐘有效；agent 等到 240s 才 timeout，最終只能走 push fallback；用戶體驗極差且可能違反 LINE TOS（連續 push）。
- **建議修法**：把 request_timeout 降到 ~60s，超時改 push fallback 模板。

### 19. `.env.example` 與實際使用脫鉤
- **位置**：`.env.example:5`
- **症狀**：`.env.example` 列 `GEMINI_API_KEY`、`ORDER_API_URL` 等過時 key，缺 `GCS_MEDIA_BUCKET`；新人 setup 易誤填。
- **建議修法**：對齊 deploy.sh secrets 與實際使用。

### 20. infer_brand_from_text 對「Chainlock」（品牌別名）不處理
- **位置**：`agent/harness/line_ui_factory.py:106-124`
- **症狀**：system.md 寫客戶可能用「Chainlock」稱呼 Chatlock，但 _brand_items 沒有 Chainlock 別名，infer 會回 None。
- **建議修法**：config.toml 加 brand aliases 欄位。

### 21. ts-power-drain-chatlock 內嵌 AI-99/A90 緊急開鎖 SOP，無 model gate
- **位置**：`agent/skills/data/Chatlock/_all-models/ts-power-drain-chatlock/SKILL.md:96-117`
- **症狀**：雖然有警語，但 SOP 內文整段照寫 AI-99/A90 步驟；AI-88 用戶若 LLM 漏看警語會被引導錯誤緊急開鎖步驟（按錯位置）。
- **建議修法**：警語保留，但 AI-99/A90 段落標題上加更醒目的型號標記。

### 22. Dormakaba `ts-alarm` 內 cross-load `ts-verification-dormakaba` 未經 gate
- **位置**：`agent/skills/data/Dormakaba/_all-models/ts-alarm-dormakaba/SKILL.md:30`
- **症狀**：跨技能 load 在 SKILL.md 中為純文字提示，不是工具 gate；當品牌變更（用戶切換）時可能出現一致性問題。
- **建議修法**：SKILL.md 內 cross-load 應該標註「先確認品牌仍為 Dormakaba」。

### 23. trigger_keywords「APP」「手機」「應用程式」過於通用
- **位置**：`agent/skills/data/Chatlock/_all-models/app-guide/SKILL.md:5-7`
- **症狀**：用戶問「我手機掉了能不能找回鎖的密碼」會誤觸 app-guide router，繞開 dispatch-guide / ts-verification 路徑。
- **建議修法**：trigger 加更具體上下文（「APP 配對」「APP 連線」）。

### 24. _audit_agent_result 中 `args_summary[:200]` 可能截斷 JSON 含敏感欄位
- **位置**：`agent/harness/debounce.py:471`
- **症狀**：tool args 超 200 字會截斷且 PII masking 在 storage 層才做；中間 print log 是原文未 mask。
- **建議修法**：所有寫入路徑統一在源頭 mask。

### 25. data_correction 不關閉 _pending_messages → 修正後 quick reply 流程仍卡住
- **位置**：`agent/harness/data_correction.py:118-147`、`agent/harness/debounce.py:686-692`
- **症狀**：用戶發 `#資料修正 我之前選錯品牌`，data_correction 回確認訊息後 return，但 `_pending_messages` 中可能還暫存上次未回的問題；下次用戶輸入會被當品牌選擇，造成奇怪流程。
- **建議修法**：data_correction 命中時清空該 user 的 _pending_messages。

---

## 嚴重度：LOW

### 26. memory compression 切割點往後找 human 而 cut_index 越界回 None（無摘要）
- **位置**：`agent/harness/memory_manager.py:103-110`
- **症狀**：若 retention_pair × 2 之後到結尾沒有任何 human message，壓縮直接放棄；訊息會無限累積。
- **建議修法**：若找不到 human，往前找最近 human 而非往後。

### 27. Dockerfile 沒有 non-root user
- **位置**：`agent/Dockerfile:1-26`
- **症狀**：容器以 root 執行，違反 least privilege。
- **建議修法**：加 `USER appuser`。

### 28. `set_current_user_input` 在 multimodal 時 join text blocks 用單空白
- **位置**：`agent/harness/debounce.py:262-263`
- **症狀**：使用者圖+多段 text 拼成「a b c」，TRANSFER_KEYWORDS 完整字串若被切到不同 block 不會被偵測。
- **建議修法**：多 block 用換行 join 並做完整匹配。

### 29. `_TRANSFER_KEYWORDS` 中「報價」風險偏低
- **症狀**：客服話術不會誤觸，僅 user input 才會匹配，影響有限。

### 30. trigger_keywords「快取」「清除」過通用
- **位置**：`Chatlock/_all-models/app-cache/SKILL.md:5-7`
- **症狀**：客戶問「清除卡片」可能誤觸 app-cache。
- **建議修法**：trigger 改為「APP 緩存」「APP 卡頓」更具體。

---

## 分類統計

| 嚴重度 | 數量 |
|---|---|
| CRITICAL | 3 |
| HIGH | 11 |
| MEDIUM | 11 |
| LOW | 5 |
| **合計** | **30** |

---

## 建議修復優先順序

### Phase 1（必修，影響資料正確性與安全）
1. **#1** `/chat` 預設 user_id 串線
2. **#5** safety_gate 關鍵字擴充（自殺、家暴、緊急）
3. **#11** infer_brand first-match wins → 髒資料
4. **#7** profile_updater 寫錯 PII

### Phase 2（高 UX 影響）
5. **#3** Quick Reply pending 覆蓋
6. **#6** transfer_to_human guard 漏洞
7. **#12** troubleshoot 路由表 dangling
8. **#18** request_timeout 240s vs LINE 90s

### Phase 3（穩定性與一致性）
9. **#2** 多模態 buffer race
10. **#8** memory _summaries 多 worker 失效
11. **#9** audit log 假 model_name
12. **#15** SCD Type 2 race

### Phase 4（清理與強化）
13. **#4 #25** data_correction 邊界與 pending 清理
14. **#10 #13 #14** SKILL.md 一致性強化
15. **#19 #27** 部署設定與安全性
16. 其餘 LOW 項目

---

## 備註

- 本盤點未實際執行任何程式碼變更，僅做靜態分析。
- 建議在 Phase 1-2 修復前先增補 quality_check 測試案例覆蓋上述高風險場景，避免回歸。
- 與前一輪修復（commits `5509d36` `a744185` `79ff660`）共同構成「品牌/型號錯配」防線；本輪識別的多數問題屬於「邊界條件」與「狀態管理」類，需要分階段處理。
