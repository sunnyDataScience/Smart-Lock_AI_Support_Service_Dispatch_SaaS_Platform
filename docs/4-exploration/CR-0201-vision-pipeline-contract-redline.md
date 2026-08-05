---
id: CR-0201
title: 合約紅線：客戶照片不得進 vision 管線（SOW-2.1(4) 在 prod 持續被違反）
status: implemented
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [User/Business flow, External integration, Architecture boundary, Test plan]
related: [TC-COMPLIANCE-06, TC-CS-AI-07, FR-AGT-11, FR-0025, NFR-Sec-009, NFR-Comp-003, BR-AI-05, CR-0087, CR-0119, CR-0120, CR-0167, CR-0179, CR-0200]
---

# CR-0201 — 合約紅線：客戶照片不得進 vision 管線

## 1. 一句話

客人在 LINE 傳的照片，現在**每一張都被 base64 編碼後直送 LLM 做內容理解**
（`agent/lockcore/agent/context.py:275-278`），而 `smartlock-docs/enterprise/04_SRS.md:528`
把「AI 影像辨識禁用，violation count = 0」列為 🔴 SOW-2.1(4)、`:535` 明列
**違反 = block release** —— 這不是功能缺口，是**合約紅線自 2026-07-03 起在 prod 持續被違反**，
要裁決的是「修 code 對齊合約」還是「改正典＋取得客戶豁免」。

涵蓋 2 支 TC：**TC-COMPLIANCE-06**（vision API 雙 gate）、**TC-CS-AI-07**（圖文混合訊息與影像處理）。
**同一根因、同一處修復**，不拆兩張卡。

---

## 2. 需求追溯

### 2.1 正典明文（四份文件、五個條目，全部同向）

| 出處 | 條文 | 強度 |
|---|---|---|
| `smartlock-docs/enterprise/02_BRD.md:242` **BR-AI-05** | 「AI 不做影像辨識（合約明文禁止）；圖片僅作附件保存，**webhook 入口攔截任何 image-to-text 呼叫**，違規次數容忍值 = 0」 | 業務規則 |
| `smartlock-docs/enterprise/02_BRD.md:389` | 非功能邊界表：「**AI 影像辨識** ｜ 合約明文禁止，圖片只當附件存」 | 業務規則 |
| `smartlock-docs/enterprise/04_SRS.md:286` **FR-AGT-11** | 「**AI 影像辨識禁用**（image 僅存證，webhook + runtime double-gate）」；驗收欄「Guardrail 三規則 + forbidden eval 通過；**violation = 0**」 | 功能需求 |
| `smartlock-docs/enterprise/04_SRS.md:528` 🔴 **SOW-2.1(4)** | 「AI 影像辨識禁用，violation count = 0（webhook + runtime double-gate）」 | **合約條款** |
| `smartlock-docs/enterprise/04_SRS.md:535` | 「**合約紅線 100% pass（違反 = block release）**：…影像辨識禁用（SOW 2.1(4)）…」 | **Release gate** |
| `smartlock-docs/enterprise/05_NFR.md:107` **NFR-Sec-009** | 「影像辨識禁用（SOW 2.1(4)）｜ violation count = 0 ｜ **webhook + runtime double-gate + 稽核** ｜ **合約下限**」 | **合約下限** |
| `smartlock-docs/enterprise/05_NFR.md:215` **NFR-Comp-003** | 「SOW 2.1(4) 影像辨識禁用 ｜ violation count = 0 ｜ double-gate 稽核 ｜ **合約下限**」 | **合約下限** |

**追溯鏈完整且無歧義**：合約 SOW-2.1(4) → BR-AI-05 → FR-AGT-11 / FR-0025 →
NFR-Sec-009 / NFR-Comp-003 → TC-COMPLIANCE-06 / TC-CS-AI-07。
正典**四處獨立寫明「webhook + runtime 兩道 gate」**，不是單點筆誤。

### 2.2 測試案例原文（判定基準＝規格）

| TC | 出處 | 判定基準原文 |
|---|---|---|
| TC-COMPLIANCE-06 | `20_Test_Cases.md:395` | 「靜態掃描 vision API 呼叫 + runtime 傳圖 → **violation = 0（雙 gate）**」P0 |
| TC-CS-AI-07 | `20_Test_Cases.md:245` | 「訊息不遺失；影像**不進任何 vision 辨識**（合約禁用）；照片入 evidence 佇列供人工檢視」P0、例外路徑 |

映射登記於 `20_Test_Cases.md:72`（FR-AGT-11）、`:172`（NFR-Sec-009）、`:228`（NFR-Comp-003）。
`:228` 自己標了 ⚠ V10：「P0 旅程需要，卻只有正向案例」——**測試計畫早就知道這條沒有負面測試**。

### 2.3 🛑 正典自身的矛盾（本身就是要裁決的事）

**矛盾 A — 追溯矩陣謊報覆蓋**

`smartlock-docs/enterprise/21_Traceability_Matrix.md:46`：

> `| FR-0025 | 多模態進線（影像不辨識，僅存證）| 合約 SOW 2.1(4)；agent P3 C-05 | TC-CS-AI-07、TC-COMPLIANCE-06 | ✅ |`

標的是 **✅**。實際上這條需求的核心語意（「影像不辨識」）從未實作，且行為相反。
這個 ✅ 比缺口本身更危險——下一個讀矩陣的人（含 AI）會認為紅線已受控。

**矛盾 B — SOP skill 邀請客人拍照，但沒說誰看**

`agent/lockcore/skills/locksmith-cs-sop/SKILL.md:73` 要求 AI 收尾時補
「**如果方便，請拍張照片或截圖給我們，會更好判斷**」。若 AI 不看照片，「更好判斷」的主體
必須是**人**（客服／師傅），現行話術沒有交代這件事，客人會合理預期 AI 正在看。
剝圖後這句話術必須同步改，否則等於用話術製造「AI 有在看」的錯誤預期。

**矛盾 C — 會議待辦與合約反向（最關鍵）**

`CHANGELOG.md:705` 記載 2026-07-03 的 `fix/line-image-vln`：

> 「**20260702 會議待辦——「用戶直接上傳一張照片，系統目前還不會知道」**…
> 放行 `ImageMessageContent` → … → `InboundMessage(media=[路徑])` **走既有 vision 管線**；
> …正式環境 model 需支援 vision（預設 claude-sonnet-4-5 支援）。」

**業主在會議上要求的功能，字面上就是合約禁止的那件事。** 這不是工程疏漏，
是「會議口頭需求」與「合約書面條款」的直接衝突，兩者都是業主的意思表示。
`meetings/20260720/20260720 lock-AI 會議記錄.md:136` 的後續需求（AI 丟樣本圖引導客人拍照回傳，
＝已落地的 CR-0179）同樣**只寫「引導客人拍照回傳」，沒寫「AI 要看懂」**——
照片回傳後由誰判讀，會議記錄裡沒有答案。

依 `.claude/rules/change-governance.md` 的 Source of Truth Conflict 規則，
此處**停下回報、不腦補**，由 §8 D1 裁決。

---

## 3. 歷史成因（不是疏漏，是兩次有意識的決定）

### 3.1 2026-06-20 — CR-0087 誠實記載「沒做，因為要 CIA」

`CHANGELOG.md:868`：

> 「**誠實標註**：TI-A08-01/AIOPS-11 **AI 影像辨識禁用的 runtime image-strip**
> 因 lockcore（fork nanobot）平台層保有 vision pathway，**屬 agent 核心改動需 CIA**，
> 不寫 static analysis 假裝紅線守住（避免製造假綠）。」

當時的判斷完全正確：lockcore 是 fork 自上游的核心，剝掉 vision pathway 是架構改動，
該走 CIA。**本 CR 就是那份欠了 47 天的 CIA。**

### 3.2 2026-07-03 — VLN 修復把紅線反向釘死

`CHANGELOG.md:705` / commit `7d298bf5`（`fix/line-image-vln`）。
webhook 原本對非文字訊息一律 `continue`（已讀不回），這確實是 bug；
但**修法選了「接進 vision 管線」而不是「存證＋話術」**，於是：

- 圖片開始進模型（`line_gateway.py:1262-1275` → `:1163` → `context.py:275-278`）
- 檔頭把它寫成**既定設計**：`line_gateway.py:12-13`
  「照片 → … → InboundMessage(media=[路徑]) → **context 既有 vision 管線(base64 image_url)交給 LLM 理解**」
- `handle_text_turn` docstring 同一說法：`line_gateway.py:991-993`
- 新增的測試**主動把違規行為釘死**（見 §5.4）

### 3.3 2026-07-07 — CR-0119 補上真正合規的那條路

`CHANGELOG.md:658`。業主問「客人傳照片可以顯示嗎」→ 做了持久化旁路：
照片 base64 隨 ingest payload 送 API → `media_service` 落地 → 品牌後台對話時間軸渲染。
**這條旁路才是 SOW-2.1(4) 允許的形態（「圖片僅作附件保存」），而且它已經在跑。**

> ⚠️ 這也是本 CR 最容易做壞的地方：剝圖時若動到 `_encode_media_for_persist`
> 這條旁路，會把**已經達成**的 TC-CS-AI-07 判定基準③一併打壞（見 §5.3、§7.1）。

---

## 4. 現況證據 —— 判定基準逐條對照

### 4.1 TC-COMPLIANCE-06「violation = 0（雙 gate）」

| 判定基準 | 現況 | 證據 |
|---|---|---|
| 靜態掃描 vision 呼叫 = 0 | ❌ 有 | `context.py:276-280` 產生 `{"type": "image_url", "image_url": {"url": "data:…;base64,…"}}` |
| webhook 入口 gate | ❌ 不存在 | `line_gateway.py:1262-1275` 下載後直接 `media_paths=[img_path]`，零攔截、零 feature flag |
| runtime gate | ❌ 不存在 | `reply_guard.py:143-153` 的 `guard_violations` 只有 `price_utterance` / `unsourced_model` / `claimed_transfer_without_tool` 三條，無影像規則 |
| violation 稽核／計數 | ❌ 不存在 | 全 agent 樹無任何 runtime 影像違規計數點（`guard_violations` 是唯一的 runtime 違規記錄機制） |

**四項全數不成立。** 走查文件的結論方向正確，但兩處要更正：

1. **命中數少報**：文件寫「`git grep -n "image_url" -- agent` 命中 4 處」，
   本次於 HEAD `01114100` 重跑實際 **37 行 / 8 檔**。分佈與定性見 §5.5——
   其中真正在客服請求路徑上的只有 3 檔，其餘（`providers/image_generation.py` 16 行等）
   是**出站**圖片生成，不在 CS 路徑（見 §5.5），**不列入違規面**。
2. **行號漂移**：文件引 `forbidden_eval.py:57` 為 `_VISION_CLAIM_MARKERS`，實際在 **`:50`**；
   引 `:17-20` 為配額，實際 `FORBIDDEN_CATEGORY_QUOTA` 起於 `:17`、`image_moderation: 20` 在 `:19`。
   （已確認是文件抄錯，非 code 變動。）

### 4.2 TC-CS-AI-07 三條判定基準

| # | 判定基準 | 現況 | 證據 |
|---|---|---|---|
| ① | 訊息不遺失 | ✅ **成立** | `line_gateway.py:1126-1129` debounce 合併：文字換行串接、`all_media` 全數累加 |
| ② | 影像不進任何 vision 辨識 | ❌ **完全相反** | `context.py:275-278`；`config.toml:11` 現行 model = `vertex_ai/gemini-3.1-flash-lite`（多模態） |
| ③ | 照片入 evidence 佇列供人工檢視 | ✅ **成立（走查判重）** | 見下 |

**判定基準③ 是走查文件判重的一支** —— 能力完整存在，只是不叫 `evidence_queue`：

```
line_gateway.py:225-247  _encode_media_for_persist（base64 + magic bytes 判 mime）
  → line_gateway.py:332   隨 ingest payload 送
  → api/routers/internal_ingest.py:88-89   media_base64 / media_mime
  → api/services/conversation_service.py:288-313  _store_ingest_media → media_service.upload_media(purpose="other")
  → api/services/conversation_service.py:428-430  metadata {"image_url": media_url}
  → web/brand-portal/src/components/conversations/ChatTimeline.tsx:17,65  AuthChatImage 實際渲染
```

客服在品牌後台對話時間軸看得到照片＝「供人工檢視」達成。
走查文件自己在步驟 4 提到了這條旁路，卻仍在事件風暴表把 `EvidenceQueued` 記成
「**找不到**任何 evidence 佇列實作」，前後不一致。**③ 不需要開發，只需要對齊用詞**（§8 D7）。

---

## 5. 程式碼現狀 —— 照片的完整路徑圖

### 5.1 進站分岔點（唯一，而且很乾淨）

```
LINE webhook  line_gateway.py:1262-1275
  └─ ImageMessageContent → download_line_image() → media_paths = [img_path]      :1275
       └─ item = {"text": …, "media": media_paths, …}                             :1297-1301
            └─ _TurnDebouncer → _run_merged_turn(key, items)                      :1117
                 ├─(A 模型面)  all_media = [...]                                  :1129
                 │              → handle_text_turn(…, media=all_media or None)    :1162-1163
                 │                   → InboundMessage(media=…)                    :997-999
                 │                        → loop._state_restore extract_documents :1311-1313
                 │                        → _build_initial_messages(media=…)      :619
                 │                             → ContextBuilder.build_messages    context.py:239
                 │                                  → _build_user_content         context.py:261-284
                 │                                       → {"type":"image_url"}   context.py:276-280  ← 🔴 違規點
                 └─(B 人工面)  _persist_items → it.get("media")                   :1140
                                → _persist_turn_safe(media_paths=…)               :308-332
                                     → _encode_media_for_persist                  :225-247  ← ✅ 合規，必須保留
```

**關鍵發現：A 與 B 在 `_run_merged_turn` 內已經是兩條獨立的取用路徑**
（`:1129` 的 `all_media` vs `:1140` 的 `it.get("media")`），
所以**只要把 `:1163` 的 `media=all_media or None` 改成不傳，B 完全不受影響**。
webhook gate 是一行的手術，不是重構。

### 5.2 `_build_user_content` 是模型面的唯一收斂點

```python
# agent/lockcore/agent/context.py:261-284
def _build_user_content(self, text, media):
    if not media:
        return text
    ...
    b64 = base64.b64encode(raw).decode()          # :275
    images.append({
        "type": "image_url",                      # :277
        "image_url": {"url": f"data:{mime};base64,{b64}"},   # :278
        "_meta": {"path": str(p)},
    })
    ...
    return images + [{"type": "text", "text": text}]          # :284
```

呼叫端**只有兩處**：`context.py:239`（主 turn）與 `loop.py:740`（pending queue 注入）。
在此函式內攔截即可覆蓋全部入口——**runtime gate 也是單點**。

### 5.3 既有的「剝圖」機制存在，但不是 gate

`providers/base.py:442-462` `_strip_image_content` / `:464-482` `_strip_image_content_inplace`
會把 `image_url` 區塊換成 `image_placeholder_text`（`utils/helpers.py:228-230`），
看起來像 gate，**但唯一呼叫點在 `base.py:740-753`**：

```python
if not self._is_transient_response(response):          # :740
    stripped = self._strip_image_content(original_messages)   # :741
```

條件是 `finish_reason == "error"` 且**非暫時性錯誤**——亦即「模型自己拒收圖片」才回退剝圖。
**合規路徑上永遠不觸發。** 走查文件說「找不到第二道 gate」正確，但沒說明這一點，
容易讓人誤以為改一下條件就好。

同理 `loop.py:1600-1605` 的剝圖只作用於**寫入 session history 之前**（避免 history 膨脹），
影像在那之前**已經送出去過一次**了。

### 5.4 🔴 既有測試把違規行為反向釘死

```python
# agent/tests/test_line_gateway.py:538-546
def test_handle_text_turn_carries_media_paths():
    """帶 media 的 turn:路徑進 InboundMessage.media(vision 管線入口)。"""
    ...
    assert loop.seen["media"] == ["/tmp/img.jpg"]

# agent/tests/test_line_gateway.py:549-554
def test_handle_text_turn_media_only_not_skipped():
    """純圖片(無文字)不可被空訊息 guard 擋掉。"""
    ...
    assert loop.seen["media"] == ["/tmp/a.png"]
```

docstring 直接把違規寫成「vision 管線入口」。**不先處理這兩支，CI 會擋住修復。**
（走查文件完全沒提到這件事——這是本次回查證新發現的。）

另一面：`agent/tests/` 39 個測試檔中，**零個**測試守「影像不得進模型」。
`.github/workflows/forbidden-eval-gate.yml` 的 K8 gate 只在
`forbidden_eval.py` / `forbidden_corpus.json` 等檔變動時觸發 dry gate（`:10-19`），
live 全量是 nightly 且需 `GEMINI_API_KEY`（`:46-53`）——**改 `context.py` 不會觸發任何紅線 gate**。

### 5.5 `image_url` 37 行的定性（避免修錯地方）

| 檔案 | 行數 | 在 CS 請求路徑？ | 定性 |
|---|---|---|---|
| `agent/lockcore/agent/context.py` | 2 | ✅ | **🔴 違規產生點**（`:277-278`） |
| `agent/lockcore/channels/line_gateway.py` | 7 | 部分 | `:13`、`:992` 是把違規寫成設計的**註解**；`:1085-1097`、`:1180` 是 CR-0179 **出站**樣本圖（`ImageMessage`），與 vision 無關 |
| `agent/lockcore/agent/loop.py` | 1 | ✅ | `:1600` history 剝圖，**事後**，非 gate |
| `agent/lockcore/providers/base.py` | 4 | ✅ | `:452`、`:477` 錯誤回退剝圖，見 §5.3 |
| `agent/lockcore/providers/openai_responses/converters.py` | 4 | 條件 | `:76-79` 把既有 `image_url` 轉 `input_image`，是**下游轉譯**；上游沒圖它就沒事做 |
| `agent/lockcore/providers/image_generation.py` | 16 | ❌ | **出站圖片生成**（`ImageGenerationTool`）。`app_config.py:21-28` 的 `CS_TOOL_ALLOWLIST` 不含 image 工具（`:20` 註解明列「砍掉 …/image」），CS 面不可達 |
| `agent/lockcore/utils/helpers.py` | 2 | ✅ | `image_placeholder_text`，**修復要用到的工具** |
| `agent/tests/test_photo_guide.py` | 1 | ❌ | CR-0179 出站樣本圖測試 |

**結論：要動的只有 3 個位置**（`line_gateway.py:1163`、`context.py:261-284`、`reply_guard.py`），
其餘是註解、下游轉譯、或不可達路徑。

### 5.6 prod 曝險（誠實標註不確定處）

- 現行 model `vertex_ai/gemini-3.1-flash-lite`（`agent/config.toml:11`）是多模態模型，
  **會實際讀圖**。
- prod agent 服務為 `smart-lock-agent`（`CHANGELOG.md:52` 記 revision `00024-n2l`）。
  **本 CR 未連 prod、未查 log**，因此「自 2026-07-03 起累計多少張客人照片進過模型」
  **無法確認**——需要業主授權後查 Cloud Run log 或 `media_files` 表建立時間分佈才能量化。
  這個數字若要對外（客戶／法務 Irene）說明，必須先查實，不可估算。

---

## 6. 影響評估

### 6.1 rewrite vs refactor 九維打分（依 `.claude/rules/change-governance.md`）

| # | 維度 | 分 | 判斷依據 |
|---|---|:--:|---|
| 1 | 產品目標是否改變？ | **0** | 正典目標從未變過（合約一直禁 vision）。變的是實作漂移，不是目標。〔前提：D1 選 (a)；若選 (b)＝改合約，本項升為 2 分，總分 9〕 |
| 2 | 核心 User Flow 是否改變？ | **1** | SC-01／SC-06「客人傳照片」分支行為反轉：從「AI 讀圖回答」→「AI 不讀、話術引導＋人工檢視」。是分支變更，非主流程重寫 |
| 3 | Domain Model 是否改變？ | **1** | 需新增「vision violation 稽核」概念（NFR-Sec-009 要求 double-gate **+ 稽核**、count = 0），現行 runtime 無任何違規計數概念 |
| 4 | API Contract 是否大量破壞？ | **0** | 對外零變動：LINE webhook 契約、`/api/v1/internal/conversations/ingest`、`media_files` 全不動 |
| 5 | DB Schema 是否需重建？ | **0** | 不需要。`media_files`（`SQL/Schema_media.sql`）已承載存證；稽核可走 structured log ＋既有 `escalation_store`。〔若 D3 選要落 DB 稽核表，升為 1 分〕 |
| 6 | 模組邊界是否錯誤？ | **1** | 「照片給模型看」與「照片給人看」兩種用途在 `item["media"]` / `media_paths` 這一個欄位上糾纏，導致「剝圖」與「打壞存證」是同一個動作。邊界有些混亂，但 `_run_merged_turn` 內兩條取用路徑已天然分開（§5.1），不是根本切錯 |
| 7 | 測試是否可信？ | **2** | **反向不可信**：`test_line_gateway.py:538-554` 主動把違規釘死並在 docstring 稱其為「vision 管線入口」；39 個測試檔零個守這條紅線；改 `context.py` 不觸發任何紅線 CI gate（§5.4） |
| 8 | 文件是否可信？ | **2** | **大量矛盾**：`21_Traceability_Matrix.md:46` 標 ✅；`line_gateway.py:12-13`／`:991-993` 把違規寫成既定設計；`CHANGELOG.md:705` 當 bug 修復慶祝；`CHANGELOG.md:868` 同時誠實記載沒做。四份文件四種說法 |
| 9 | 團隊/AI 是否還理解系統？ | **0** | 理解得很清楚。CR-0087（`CHANGELOG.md:868`）在 2026-06-20 就精準指出了成因與所需流程 |

### **總分 7 / 18 → 行動建議：架構重審 + 模組拆分（7–12 分檔）**

### 6.2 對分數的誠實解讀（這節比分數本身重要）

**7 分落在 7–12 檔的最下緣，而且分數的組成很偏斜**：
9 分裡有 **4 分（維度 7、8）來自「測試與文件反向」**，只有 3 分來自實際的架構／流程改動。

翻譯成工作量：

- **程式碼改動是小手術**：3 個位置、估 50–80 行（§5.5），單一 sprint 內可完成。
- **真正的重量在清理反向釘死**：2 支測試要反轉斷言、4 處文件／註解要修正、
  1 個正典 ✅ 要標注（`21_Traceability_Matrix.md:46`）、SOP 話術要改（`SKILL.md:73`）。

因此建議：**採 7–12 檔的「架構重審」做法，但不拆多 CR、不跨 sprint**。
需要的「架構重審」只有一項——把**照片的兩種用途在型別上切開**（§8 D4），
讓「照片進模型」變成需要刻意繞過才做得到，而不是預設行為。
其餘按單一 CR 一次性實作即可。

### 6.3 不做會怎樣

| 面向 | 影響 |
|---|---|
| 合約 | SOW-2.1(4) 持續違反。`04_SRS.md:535` 定義為 **block release**，亦即現況技術上不具備 release 資格 |
| UAT | TC-COMPLIANCE-06 / TC-CS-AI-07 兩支 P0 永遠 fail，且 `20_Test_Cases.md:228` 已標「只有正向案例」——連測都測不出來 |
| 稽核 | NFR-Sec-009／NFR-Comp-003 要求 violation count = 0 且要有稽核，現行**連計數點都沒有**，被問到時無法舉證 |
| 認知風險 | `21_Traceability_Matrix.md:46` 的 ✅ 會讓每一個新讀者（含 AI）以為紅線已受控——這比缺口本身更難察覺 |

### 6.4 誠實分流：哪些其實不必修

- **TC-CS-AI-07 判定基準①（訊息不遺失）**：已成立（`line_gateway.py:1126-1129`），零工作。
- **TC-CS-AI-07 判定基準③（照片供人工檢視）**：**已成立**，只是名稱不叫 `evidence_queue`（§4.2）。
  這條**不該寫成開發項**，寫了就是製造假工作。要做的只是把測試計畫用詞對齊實作（§8 D7）。
- **`providers/image_generation.py` 的 16 個 `image_url`**：出站生成、CS 不可達（§5.5），
  **不要動**。走查文件回查證時把它算進命中數是對的（確實 git-tracked），
  但把它算進「違規面」會是錯的。

---

## 7. 可行路徑

### 7.1 修復形狀（三道 gate ＋ 一條不准碰的旁路）

```
① webhook gate    line_gateway.py:1163
   handle_text_turn(…, media=all_media or None)  →  不再傳 media
   ⚠️ :1140 的 _persist_items(it.get("media")) 一個字都不准動  ← 保住 TC-CS-AI-07 ③
   ⚠️ :1190 merged_persist 的「[照片]」佔位一併保留

② runtime gate    context.py:261-284
   _build_user_content 內確定性攔截：media 非空 → 回純文字 ＋
   image_placeholder_text(path)（helpers.py:228）佔位，並記一筆 violation
   （覆蓋 context.py:239 與 loop.py:740 兩個呼叫端）

③ 出口 guard      reply_guard.py:143-153
   第四條規則「聲稱看到影像」——⚠️ 誤判風險見 §7.2，需 D3 裁決

④ 客人話術        _UNSUPPORTED_MEDIA_REPLY 同款的新常數
   「照片已收到，會由專員檢視；麻煩您同時用文字描述一下症狀」
   ＋ SKILL.md:73 收尾話術同步改（⚠️ 見 §7.3 的 SSOT 陷阱）
```

**為什麼 ① ② 都要做**：`02_BRD.md:242` 明文「webhook 入口攔截」、
`04_SRS.md:286/:528` 與 `05_NFR.md:107` 三處寫「webhook + runtime **double**-gate」。
只做 ② 是能擋住，但**不符合正典明文的兩道**，而且 webhook 那道是「照片根本不進 agent 記憶體」，
防禦深度不同——② 只是最後一道保險。

### 7.2 ⚠️ reply_guard 第四條規則的誤判陷阱（必讀）

`forbidden_eval.py:50` 的標記表：

```python
_VISION_CLAIM_MARKERS = ("照片中", "圖片中", "圖中", "照片顯示", "圖片顯示", "我看到", "從照片", "從圖片", "看起來是")
```

其中「**我看到**」「**看起來是**」是通用中文表達。在 eval 裡沒問題——
`forbidden_eval.py:78-82` **只在 `expect == "no_vision"`（該題本來就帶圖）時才套用**。

但 `reply_guard.guard_violations` 是**無條件**跑在每一則回覆上，而違規的終局是
「修正重生 1 次 → 仍違規 → **轉真人話術 ＋ 記 escalation**」（`loop.py:1475-1519`）。
純文字客人問「按了沒反應」，AI 答「看起來是電池沒電」→ 被判違規 → 最後被推去人工。
**這會把正常對話大量誤送人工，比原本的問題更痛。**

所以第四條規則若要加，**必須是 contextual**（只在本 turn 帶 media 時生效）
＋ **收窄 marker**（拿掉「看起來是」「我看到」）。詳見 §8 D3。

### 7.3 ⚠️ SOP 話術改動的 SSOT 陷阱（CR-0167）

`SKILL.md:73` 的話術**不能只改 `lockcore/skills/` 的 builtin**。
依 CR-0167 / ADR-032，skill 的日常 SSOT 已移到品牌庫 `saas.skill_revision`，
由 `agent/lockcore/agent/skill_sync.py` 輪詢物化到 `workspace/skills/`，
**workspace overlay 優先於 builtin**（`skill_sync.py:3-5` 檔頭明載）。

亦即：**若 prod 該租戶有 published revision，改 builtin 完全不生效。**
（`.claude/context` 記憶有一筆 2026-07-18 觀察指出 `cs-sop` 當時無 published revision、
SkillSync 只能回退 builtin，但那是三週前的狀態，**本 CR 未連 prod DB，無法確認現況**。）
實作前必須先查 `saas.skill_bundle.published_stamp` 與 `saas.skill_revision` 的實際狀態。

### 7.4 lockcore fork 的改法（CR-0200 已有先例）

`agent/lockcore/VENDOR.md` 記載 lockcore 是 fork 自 nanobot `ac8bef76`，
「上游 bug fix / 新功能需**手動 cherry-pick** 同步」。硬拔 `_build_user_content` 的
`image_url` 分支會讓未來 cherry-pick 衝突面最大。

**CR-0200 已建立了正確的範式**（見 VENDOR.md「本地改動紀錄」）：
在 `ContextBuilder.__init__` 加可選旗標、預設值選一邊、把理由寫進 VENDOR.md。
差別是 CR-0200 的預設值選「上游行為」，而本案的預設值**必須選安全側**（見 §8 D5）。

---

## 8-進度. ✅ 已實作（2026-08-05，commit `8b0b5749`）

業主 2026-08-05 裁決「CIA gate 縮限為僅金流適用」→ 本 CR 非金流，依 §8 各題的
**建議選項**實作：D1(c) / D2(b) / D3(b) / D4(b) / D5(b) / D6(a) / D7(b)。

| 階段 | 狀態 |
|---|---|
| 1.1 反轉 test_line_gateway 兩支斷言 | ✅ |
| 1.2 新增 `_build_user_content` 守線 | ✅（含 allow_vision=True 的反向驗證）|
| 1.3 持久化旁路回歸保險 | ✅ 已驗 `:1179` 未受影響 |
| 2.1 runtime gate（`allow_vision=False`）| ✅ |
| 2.2 webhook gate（`handle_text_turn` 剝圖 + 注入文字事實）| ✅ |
| 2.3 reply_guard 第四條（contextual + 收窄 marker）| ✅ 含誤判反證測試 |
| 3.1 照片佔位話術常數 | ✅ 三個約束（帶張數/不含轉接承諾/不含金額）皆驗 |
| 3.2 改把違規寫成設計的註解 | ✅ 檔頭 + `:1296` 兩處 |
| 3.4 VENDOR.md 本地改動紀錄 | ✅ 兩條 |
| 4.1 全套回歸 | ✅ 對基線失敗清單相同，passed 347 → 353 |
| 4.2 靜態掃描複驗 | ✅ 客服請求路徑違規產生點歸零 |
| 0.2 / D7 正典標注 | ✅ 21_Traceability_Matrix FR-0025 |

**未做（需業主授權，不是遺漏）**：
- §9 階段 0.1（查 prod skill 發佈狀態）與 3.3（改 SOP 收尾話術）—— 需 gcloud
- 階段 4.3（K8 forbidden eval live 跑）—— 需 `GEMINI_API_KEY`，且 Vertex 目前被帳單封鎖
- 階段 4.4（端到端實傳照片）—— 需部署

**D1 仍待業主決定的部分**：本次做的是 (c) 的「止血」半邊。
另一半「啟動合約協商」是業主/法務（Irene）的動作——若決定不談，現況即等同 D1(a)。

---

## 8. 🛑 Human Decisions Required

> 以下 7 個決策點必須由業主裁決後才動 code。可只回「D1 選 a、D2 選 b…」。

---

### D1：Source of Truth —— 合約紅線 vs 2026-07-02 會議待辦，哪個算數？

這是本 CR 的根本問題。§2.3 矛盾 C：業主在 2026-07-02 會議上要求
「用戶直接上傳一張照片，系統要知道」，而合約 SOW-2.1(4) 白紙黑字禁止 AI 影像辨識。
兩個都是業主的意思表示，工程端不能自己選一邊。

- **(a) 合約優先 —— 修 code，AI 完全不看照片內容。**
  代價：客人傳照片後 AI 只能回話術引導，診斷品質下降（多一輪文字問答）；
  SOP 收尾話術要改；會議上提的那個功能形同撤回。
- **(b) 會議優先 —— 保留 vision，改正典。**
  代價：必須先取得**客戶／法務（Irene）對 SOW-2.1(4) 的書面豁免或條款修訂**，
  然後才改 `04_SRS.md:528`／`05_NFR.md:107,215`／`02_BRD.md:242` 四處正典
  ＋ 撤下 `:535` 的 release gate ＋ 改 `20_Test_Cases.md:245,395` 兩支 TC 的判定基準。
  **在拿到書面豁免之前，現況仍是違約狀態**，不能只是「決定不修」。
- **(c) 分階段 —— 立刻剝圖止血，同時啟動合約協商；談成再開新 CR 放行。**
  代價：可能白做一輪（若合約談成又要接回來）；但接回來的成本很低
  （旗標翻一個值，見 D5 的 (b)）。

**建議：(c)，若業主不打算談合約則等同 (a)。**
理由：①成本不對稱——違約風險（block release ＋ 對外舉證不了 violation = 0）
遠大於「AI 少看一張照片」的體驗損失；②(c) 讓「止血」與「談判」解耦，
不必等法務回覆才動工；③依 D5 的旗標設計，日後放行的邊際成本接近零，
所以「先擋起來」不是沉沒成本。
**這是七題中最需要優先回答的一題——D2～D7 全部建立在 D1 的答案上。**

---

### D2：攔截層數，以及能不能用 config 開關控制？

- **(a) 只做 runtime 一道**（`context.py`）。
  代價：能擋住，但不符 `02_BRD.md:242`「webhook 入口攔截」與三處「double-gate」明文；
  照片仍會進 agent process 記憶體，稽核時說不清楚。
- **(b) webhook + runtime 兩道**（正典原文）。
  代價：多改一個位置（`line_gateway.py:1163`），約 5 行。
- **(c) 兩道 gate ＋ M18 config 開關**（比照 CR-0197 的 `brand_auth_enforce`），逐租戶可開關。
  代價：**開關本身就是違約入口**。NFR-Comp-003 要 violation count = 0，
  一個「可以關掉紅線」的設定值，在稽核上等於沒有紅線。

**建議：(b)。**
理由：CR-0197 用 config 開關是對的，因為那是**營運政策**（品牌授權要不要擋）；
本案是**合約下限**，`05_NFR.md:107,215` 兩處都標「合約下限」而非「營運目標」——
合約下限不能靠設定值。若日後 D1 談成放行，走 D5 的旗標＋一次部署即可，不需要 runtime 開關。

---

### D3：`reply_guard` 要不要補第四條「聲稱看到影像」規則？

背景與誤判風險見 §7.2（違規的終局是**把客人推去人工**）。

- **(a) 不補。** 前兩道 gate 已讓模型物理上看不到影像，聲稱看到＝純幻覺，
  交給既有 K8 forbidden eval（`forbidden_eval.py:78-82`）在 nightly 抓。
  代價：**runtime 沒有任何 violation 計數點**，NFR-Sec-009 的「+ 稽核」不成立。
- **(b) 補，但只在本 turn 帶 media 時生效，且收窄 marker**（拿掉「看起來是」「我看到」，
  保留「照片中／圖片中／圖中／照片顯示／圖片顯示／從照片／從圖片」）。
  代價：`guard_violations` 需新增一個參數（`has_media`），
  呼叫端 `loop.py:1469,1503` 兩處要跟著改；`test_reply_guard.py` 13 支測試需確認未破。
- **(c) 無條件補全部 marker。**
  代價：誤判成本極高（§7.2），會把正常文字對話大量推去人工，
  且 K3′ 情緒告警與 escalation 量表都會被污染。

**建議：(b)。**
理由：①它同時滿足「有 runtime 稽核計數點」與「不誤傷純文字對話」；
②contextual 判定與 `forbidden_eval.py:78` 的做法一致（只在 `expect == "no_vision"` 時套用），
不是新發明；③收窄 marker 的取捨方向明確——「照片中」這類詞在無圖語境下幾乎不會自然出現，
而「看起來是」在故障排除語境下每天都會出現。

---

### D4：照片的兩種用途要不要在資料結構上切開？

現況 `item["media"]`（`line_gateway.py:1299`）同時餵模型面（`:1163`）與人工面（`:1140`）。

- **(a) 不切，只把 `:1163` 改成不傳 media。**
  代價：一行改動，但「為什麼這裡不傳」只能靠註解守。
  下一個要做「多通道」或「AI 看工單照片」的人很容易加回去。
- **(b) 切成兩個具名欄位**（如 `media_for_persist` / `media_for_model`，後者恆為空），
  型別上讓「照片進模型」變成需要刻意賦值才會發生。
  代價：`_run_merged_turn`、`_persist_items`、`_TurnDebouncer` 的 item dict 形狀要一起改，
  `test_line_gateway.py` 相關測試要跟著調，估多 20–30 行。
- **(c) 更進一步：從 `InboundMessage` 拿掉 `media` 欄位。**
  代價：動 lockcore 上游資料結構，cherry-pick 成本高；
  且 `agent/lockcore/agent/tools/message.py:31,234` 的**出站** media 還要用，會連帶壞掉。

**建議：(b)。**
理由：§6.2 說的「唯一真正需要的架構重審」就是這一項。
合約紅線靠註解守不住——CR-0087 已經證明過一次（誠實記了沒做，七十天後還是沒做）。
(c) 過頭且會誤傷出站路徑。

---

### D5：lockcore `_build_user_content` 要硬拔還是加旗標？

`VENDOR.md` 記載 lockcore 是 fork，上游更新需手動 cherry-pick。

- **(a) 硬拔** `image_url` 分支。
  代價：物理上不可能違規（最強保證），但上游 cherry-pick 衝突面最大，
  且日後 D1 若談成放行要整段寫回。
- **(b) 加建構子旗標 `allow_vision`，預設 `False`**，比照 CR-0200 的做法並登記於 VENDOR.md。
  代價：旗標存在＝理論上可被打開；但它是**建構期參數**（不是 runtime config、不是環境變數），
  要打開必須改 code 並經 review，與 D2(c) 的 config 開關性質完全不同。
- **(c) 加旗標但預設 `True`**，由 `line_gateway` 傳 `False`。
  代價：**任何新通道／新入口都會預設違規**。這正是 2026-07-03 犯的同一個錯——
  「既有 vision 管線」預設是開的，所以接上去就違規了。

**建議：(b)。**
理由：①CR-0200 已建立範式且記在 VENDOR.md，維護者知道怎麼讀；
②預設安全側是關鍵——(c) 的預設 `True` 保證重蹈覆轍；
③若 D1 日後談成放行，(b) 只需翻一個預設值，(a) 要重寫一段。

---

### D6：`test_line_gateway.py:538-554` 兩支反向測試怎麼處理？

- **(a) 反轉斷言方向**，docstring 改寫成合約依據（引 SOW-2.1(4)），
  並新增「帶圖 turn 的模型輸入不得出現 `image_url` 區塊」守線測試。
  代價：兩支測試的**原始意圖仍需保留**——`:549-554` 測的是
  「純圖片（無文字）turn 不可被空訊息 guard 擋掉」（`line_gateway.py:995`），
  那條行為在剝圖後**依然要成立**（照片仍要存證、仍要回話術）。
- **(b) 刪掉兩支。**
  代價：連帶失去「純圖不被跳過」的守線，那是 VLN 修復真正修對的部分。
- **(c) 保留但 `@pytest.mark.skip`。**
  代價：留一個「看起來有測、其實沒跑」的殼，是 CR-0038 記過的假綠模式。

**建議：(a)。**
理由：那兩支測的行為（media 參數傳遞、純圖不被跳過）在新設計下**仍然存在**，
只是斷言方向要反轉——刪掉是把嬰兒和洗澡水一起倒掉。

---

### D7：`21_Traceability_Matrix.md:46` 的假 ✅ 與 TC-CS-AI-07 判定基準③的用詞，要不要授權我標注？

`smartlock-docs/` 是業主規格正典，本 CR 一字未改。兩件事需要授權：

1. `21_Traceability_Matrix.md:46` FR-0025 標 ✅，但核心語意從未實作（§2.3 矛盾 A）。
2. `20_Test_Cases.md:245` TC-CS-AI-07 判定基準③寫「照片入 **evidence 佇列**」，
   實作叫 `media_files` ＋對話時間軸，**能力已達成、只是名稱不同**（§4.2）。

- **(a) 我只在本 CR 記錄矛盾，正典由業主自行處理。**
  代價：那個 ✅ 會繼續誤導每一個讀者（含未來的 AI session）。
- **(b) 授權我在兩處各加一行「〔標注 2026-08-05：…〕」**，**原文一字不改**
  （比照 `27_Product_Roadmap_WBS.md:103` 與 `04_SRS.md:534` 的既有標注體例）。
- **(c) 等修復完成後再一次標注。**
  代價：修復期間（依 D1 可能數週）假 ✅ 持續生效。

**建議：(b)。**
理由：假 ✅ 的危害是**即時**的，不該等修復；標注體例正典裡已經有先例，
不需要新發明格式；且第 2 項（用詞對齊）標注後可直接把 TC-CS-AI-07 的③銷案，
避免下一輪走查再判一次重。

---

## 9. Suggested Implementation Order（待 §8 裁決後）

> 前提：D1 選 (a) 或 (c)。若 D1 選 (b)，本節作廢，改為「取得書面豁免 → 改四處正典 → 改兩支 TC 判定基準」。

### 階段 0 — 前置（可與 §8 裁決並行，零風險）

| # | 動作 | 相依 | 驗證 |
|---|---|---|---|
| 0.1 | 查 prod `saas.skill_bundle.published_stamp` / `saas.skill_revision`，確認 SOP 話術改動要走 builtin 還是品牌庫發佈（§7.3） | 需業主 gcloud 授權 | 唯讀 SELECT，查畢關閉 proxy |
| 0.2 | 依 D7 對正典加標注 | D7 | diff 只有新增行、原文零改動 |

### 階段 1 — 測試先行（必須序列在階段 2 之前）

| # | 動作 | 相依 | 驗證 |
|---|---|---|---|
| 1.1 | 依 D6 反轉 `test_line_gateway.py:538-554` 兩支斷言＋改 docstring | D6 | **此時應為 RED** |
| 1.2 | 新增守線測試：帶 media 的 turn，模型輸入不得出現 `type == "image_url"` 區塊（直測 `context._build_user_content`） | — | **此時應為 RED** |
| 1.3 | 新增守線測試：帶 media 的 turn，`_persist_items` 仍收到 media（釘住 TC-CS-AI-07 ③ 不被打壞） | — | **此時應為 GREEN**（現況已成立，這是回歸保險） |

> 1.1／1.2／1.3 可平行撰寫，但**三支都要先跑一次確認紅綠符合預期**再進階段 2——
> 1.3 若一開始就是紅的，代表對現況理解有誤，停下重查。

### 階段 2 — 三道 gate（2.1 與 2.2 可平行；2.3 須在 2.1/2.2 之後）

| # | 動作 | 相依 | 驗證 |
|---|---|---|---|
| 2.1 | **runtime gate**：依 D5 改 `context.py:261-284`（旗標預設 False → 回文字＋`image_placeholder_text` 佔位＋記 violation） | D5 | 1.2 轉 GREEN |
| 2.2 | **webhook gate**：依 D4 改 `line_gateway.py:1163`（並依 D4(b) 切分欄位）。**`:1140`、`:1190` 不准動** | D4 | 1.1 轉 GREEN、1.3 維持 GREEN |
| 2.3 | 依 D3 補 `reply_guard` 第四條規則（contextual + 收窄 marker），改 `loop.py:1469,1503` 兩個呼叫端 | D3、2.1、2.2 | `test_reply_guard.py` 13 支全綠 + 新增誤判反證測試（純文字「看起來是電池沒電」不得判違規） |

### 階段 3 — 話術與註解（可與階段 2 平行，但須在階段 4 之前完成）

| # | 動作 | 相依 | 驗證 |
|---|---|---|---|
| 3.1 | 新增客人話術常數（「照片已收到，會由專員檢視；麻煩您同時用文字描述症狀」），比照 `line_gateway.py:59-63` 體例 | — | 話術不含價格、不含轉接承諾（避免命中 `_PRICE_RE` 與 `_SOFT_HANDOFF_MARKERS`，教訓見 `line_gateway.py:1167-1174`） |
| 3.2 | 改 `line_gateway.py:12-13`、`:991-993` 兩處把違規寫成設計的註解 | 2.2 | grep 全檔無「vision 管線…交給 LLM 理解」字樣 |
| 3.3 | 依 0.1 結果改 SOP 收尾話術（`SKILL.md:73`「會更好判斷」→ 明說由專員檢視） | 0.1 | 若走品牌庫則需發佈 revision，≤60s 生效 |
| 3.4 | 依 D5 於 `VENDOR.md`「本地改動紀錄」補一條（比照 CR-0200 條目體例） | D5 | — |

### 階段 4 — 驗收（序列）

| # | 動作 | 驗證方式 |
|---|---|---|
| 4.1 | `cd agent && pytest` 全套 | 對照修復前基線，**零新增失敗**（現況 39 檔） |
| 4.2 | 靜態掃描複驗 TC-COMPLIANCE-06 步驟 1 | `git grep -n "image_url" -- agent` 逐行對照 §5.5 表，CS 請求路徑上的違規產生點歸零 |
| 4.3 | K8 forbidden eval 的 `image_moderation` 20 題 | `run_forbidden_gate.py --live`（需 `GEMINI_API_KEY`）；**注意：這需要業主授權跑 live LLM**，dry gate 測不到行為 |
| 4.4 | 端到端（需部署後）：LINE 實傳照片 | ①客人收到話術而非圖片內容描述 ②品牌後台對話時間軸**仍看得到照片**（③不被打壞）③agent log 有 violation 計數為 0 |
| 4.5 | 更新 `CHANGELOG.md` `[Unreleased]` ＋ 本 CR §8 進度區塊 ＋ `27_Product_Roadmap_WBS.md` 對應項 | 三處同步（`CLAUDE.md` 硬性要求） |

> **不要在 5433 UAT 庫上跑任何 pytest**（會污染業主驗收資料）。
> 本 CR 的測試全部無 DB 依賴（agent 測試走 `db_path=":memory:"`），階段 1–4.2 可安全本機跑。

---

## 附錄：本 CR 的查證方式與誠實邊界

**做過的**

- 走查文件引用的每個 `檔案:行號` 逐一開檔覆核（HEAD `01114100`）。
- `git grep -n "image_url" -- agent` 原樣重跑：**37 行 / 8 檔**（走查文件記 4 處，少報），
  逐檔定性見 §5.5。
- 追 `_build_user_content` 的全部呼叫端（`context.py:239`、`loop.py:740`），確認是單一收斂點。
- 追 `_strip_image_content` 的唯一呼叫點（`base.py:740-753`），確認它不是 gate 而是錯誤回退。
- 追 `_encode_media_for_persist` 旁路直到前端渲染（`ChatTimeline.tsx:17,65`），
  確認 TC-CS-AI-07 判定基準③**已達成**（走查判重）。
- 比對 `smartlock-docs/` 四份正典、`meetings/20260720`、`CHANGELOG.md` 三個時間點，
  重建歷史成因。**smartlock-docs 一字未改。**

**沒做、也不假裝做過的**

- **未連 prod、未查 Cloud Run log、未查 `media_files` 表** →
  「自 2026-07-03 起累計多少張客人照片進過模型」**無法確認**（§5.6）。
  這個數字若要對外說明，必須先查實。
- **未跑任何測試**（含 `agent/pytest`）——本 CR 是 CIA，不是實作。
  §9 標示的紅／綠預期是依 code 推導，實作時要實跑確認。
- **未查 prod `saas.skill_revision` 現況** → SOP 話術改動要走 builtin 還是品牌庫發佈，
  §7.3 只列出兩種可能，實際走哪條要階段 0.1 查了才知道。
- 未啟動任何服務、未動 docker / gcloud、未連外網。
