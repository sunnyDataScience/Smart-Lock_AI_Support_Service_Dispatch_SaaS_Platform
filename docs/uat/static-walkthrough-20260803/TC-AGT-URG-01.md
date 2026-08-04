# TC-AGT-URG-01 — 急件偵測強制轉真人：5 分鐘內可追溯、ingest 失敗重試只留一筆

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動 agent 與 API；實跑 agent 測試套件（330 passed / 5 failed / 12 skipped，5 項失敗為 Windows symlink 權限）與 API escalation/internal ingest 相關測試（見步驟 7）。TC 的「5 分鐘內」需 runtime 計時，無法由靜態走查判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `agent/lockcore/skills/locksmith-cs-sop/SKILL.md`、`agent/lockcore/agent/tools/transfer.py`、`agent/lockcore/agent/sentiment.py`、`agent/lockcore/channels/line_gateway.py:370-607`、`api/routers/internal_ingest.py`、`api/services/problem_card_service.py:936-1080`、`SQL/migrations/091-quote-before-dispatch.sql`、`SQL/migrations/101-emergency-class-check.sql` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | **急件四類**在 DB 有值域約束（`locked_out` / `trapped_inside` / `safety_risk` / `angry_high_risk`，`SQL/migrations/101-emergency-class-check.sql:29-32`），但**寫入者是客服經問題卡更新端點**（`api/services/problem_card_service.py:1318-1327`），agent 側對 `emergency_class` 零命中——即急件分類不由 agent 判定。**強制轉真人**在 SOP 層有規則（`locksmith-cs-sop/SKILL.md` Step 1 第 2、3 點），工具層有 deterministic 兜底（`line_gateway.py:609-648` 偵測「AI 承諾轉接但未呼叫工具」時補記 escalation）。**第一次 ingest 失敗不得假稱已派工**：agent 的 escalation 轉發是**旁路**，POST 失敗不改變已回覆客戶的內容（`line_gateway.py:601-606` 只落 spool + ERROR log）。**重試後只留一筆 escalation**：由 `problem_card_service.py:1026-1039` 的 sha256 冪等鍵 + 24h dedup 視窗保證同鍵回既有卡。**`urgency_detected_at` 欄位全樹零命中**。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：四種急件 intent 與 transfer API 故障 fixture
- 步驟：各送急件訊息；令第一次 ingest 失敗後重試
- 預期結果（判定基準）：5 分鐘內建立可追溯轉人紀錄；第一次失敗不得假稱已派工，重試後只留一筆 escalation
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-AGT-04｜屬於旅程腳本：—

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 急件四類值域 | `SQL/migrations/101-emergency-class-check.sql:29-32`、`SQL/migrations/091-quote-before-dispatch.sql:20-26` | 有（DB CHECK） |
| 應用層值域驗證 | `api/services/problem_card_service.py:1318-1327` | 有（`_VALID_EMERGENCY_CLASSES`） |
| agent 端偵測急件 intent | — | **找不到**：`emergency_class` 在 `agent/` 零命中 |
| 怒客 sentiment 偵測 | `agent/lockcore/agent/sentiment.py:20-40` | 有（LLM 判定 + 關鍵詞 fallback），未接 `emergency_class` |
| bypass 三層直接轉人 | `agent/lockcore/skills/locksmith-cs-sop/SKILL.md` Step 1 第 2、3 點 | 有（SOP prompt 層） |
| 轉人紀錄落檔 | `agent/lockcore/agent/tools/transfer.py:154-162` | 有（escalation_store） |
| 轉人紀錄旁路到 API | `agent/lockcore/channels/line_gateway.py:558-606`、`api/routers/internal_ingest.py:129-159` | 有 |
| deterministic 兜底（說了沒做） | `agent/lockcore/channels/line_gateway.py:609-648` | 有 |
| `urgency_detected_at` 寫入 | — | **找不到**：全樹零命中 |
| 5 分鐘內完成 | — | 無法靜態判定：無 timer／SLA 判定程式碼 |
| 第一次失敗不得假稱已派工 | `line_gateway.py:558-606`（旁路，失敗不改回覆） | 部分：回覆已送出，失敗只落 spool |
| 重試後只留一筆 escalation | `api/services/problem_card_service.py:1026-1039` | 有（冪等鍵 + 24h dedup） |
| 失敗補送 | `line_gateway.py:471-512`、`:598-606` | 有（spool + 下輪 flush） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | 送急件訊息（被鎖在外／受困／安全風險） | `UrgencyDetected` | 四類 intent | — | **找不到**：agent 無 `emergency_class` 判定；由 SOP 文字歸入「急迫派工／結構故障」紅線 |
| 客戶 | 怒客語句 | `NegativeSentimentDetected` | ≥90% 識別率 | `agent/lockcore/agent/sentiment.py:41-60` | 回 `SentimentResult(label, confidence, keywords, is_negative)`；寫庫由呼叫端負責 |
| agent | 呼叫 `transfer_to_human` | `EscalationLogged` | 唯一進線出口 | `agent/lockcore/agent/tools/transfer.py:154-162` | `escalation_store.log(tenant, user_id, reason, is_explicit, snapshot)`；失敗只 log，不阻擋回覆 |
| gateway | 旁路 POST escalation | `DraftProblemCardCreated` | AI 永不自轉工單 | `agent/lockcore/channels/line_gateway.py:601`、`api/routers/internal_ingest.py:143-151` | 呼 `escalation_to_draft_pc`，最多建 draft 卡 |
| gateway | 第一次 POST 5xx／逾時 | `EscalationSpooled` | 補送 | `line_gateway.py:601-606`、`:443-469` | `_post_escalation` 回 False → `_spool_append` 落 jsonl + `[ESCALATION_ALERT]` ERROR |
| gateway | 下一輪 turn | `SpoolFlushed` | 先補歷史再送本輪 | `line_gateway.py:598-600` | `await _flush_escalation_spool(base_url, token)` 於本輪 POST 之前 |
| API | 收到重試的同一 escalation | （不建第二張卡） | 冪等 | `api/services/problem_card_service.py:1026-1039` | 同 `idempotency_key` 且 24h 內 active → 回既有卡 `created=False, deduplicated=True` |
| LLM | 說「已為您安排師傅」卻未呼叫工具 | `EscalationBackfilled` | 案子不蒸發 | `line_gateway.py:609-648` | 偵測承諾話術 + 本輪 escalation 未新增 → 程式補一筆 |

---

## 逐層走查

### 步驟 1 — 急件四類在程式碼中的位置

`SQL/migrations/101-emergency-class-check.sql:23-32`

```sql
        WHERE conname = 'chk_problem_cards_emergency_class'
    ...
            ADD CONSTRAINT chk_problem_cards_emergency_class
            ...
                emergency_class IS NULL
                OR emergency_class IN (
                    'locked_out', 'trapped_inside', 'safety_risk', 'angry_high_risk'
                )
```

欄位由 `SQL/migrations/091-quote-before-dispatch.sql:20-26` 引入：

```sql
    ADD COLUMN IF NOT EXISTS emergency_class VARCHAR(30);
                        -- 'locked_out'      : 門打不開被鎖在外
                        -- 'trapped_inside'  : 人被困屋內
                        -- 'safety_risk'     : 安全風險（瓦斯/幼童/醫療等）
```

寫入路徑 `api/services/problem_card_service.py:1318-1327`：

```python
    if emergency_class is not None:
        if emergency_class == "":
            sets.append("emergency_class = NULL")
        elif emergency_class in _VALID_EMERGENCY_CLASSES:
            sets.append("emergency_class = %s")
            args.append(emergency_class)
        else:
            raise ApiError(
                "VALIDATION_ERROR",
                f"emergency_class must be one of {sorted(_VALID_EMERGENCY_CLASSES)}（或空字串清除）",
                422,
            )
```

呼叫端為問題卡更新端點（`api/routers/problem_cards_v2.py:245`、`api/routers/problem_cards.py:203`），兩者皆為後台認證端點。

```
git grep -rn "emergency_class" -- agent/
（無輸出，exit=1）
```

TC 前置寫「四種急件 intent…fixture」、FR-AGT-04（`smartlock-docs/enterprise/04_SRS.md:279`）寫「Intent 階段判定急件 4 類（locked_out / trapped_inside / safety_risk / 怒客 sentiment）」／程式碼中 `emergency_class` 由客服在後台標記，agent 端無對應判定欄位。此處僅並陳，不裁定。

同一 SRS 檔 `:577` 記載業主裁決：「FR-AGT-04 急件 deterministic timer（業主 0721 裁決維持 SOP，非缺口）」。

### 步驟 2 — 急件的轉真人規則（SOP 層）

`agent/lockcore/skills/locksmith-cs-sop/SKILL.md` Step 1 第 2 點與第 3 點：

```
2. **明確要求真人 / 金錢相關(報價·費用·退費·發票·付款) / 急迫派工 / 連續不滿**
   → 呼叫 `transfer_to_human`,**不報價、不追問**。
3. **結構故障 / 電力·IC 異常 / 管理權限遺失**(門扇反弓、把手脫落、紅燈閃4次、換電池仍異常耗電、
   管理者密碼+卡片皆失、恢復原廠)→ **呼叫 `transfer_to_human`(派工也走此工具)**,再說明原因、不承諾時間費用。
```

同檔「單一進線鐵律」段：

```
> ⛔ **單一進線鐵律(先記)**:`transfer_to_human` 是**唯一**能把案子送進後台(問題卡→客服→工單→派師傅)
> 的工具。**轉真人與派工都走它。** 凡你告訴客戶「需師傅到場 / 專員會聯繫 / 已為您記錄 / 幫您安排」,
> 就**必須在同一輪實際呼叫 `transfer_to_human`** —— 只說不呼叫 = 案子蒸發。
```

### 步驟 3 — 轉人紀錄的產生與旁路

工具層 `agent/lockcore/agent/tools/transfer.py:154-167`：

```python
        if self._escalation_store:
            try:
                self._escalation_store.log(self._tenant, user_id, reason, is_explicit, snapshot)
                logger.info(
                    "transfer_to_human escalation user={} explicit={} reason={!r}",
                    user_id, is_explicit, reason,
                )
            except Exception:
                logger.exception("transfer_to_human: 寫 escalation 失敗(不阻擋回覆)")
```

gateway 旁路 `agent/lockcore/channels/line_gateway.py:558-577`：

```python
async def _forward_escalation_safe(
    esc: Any, tenant: str, user_id: str, before_id: int, user_text: str = ""
) -> None:
    """CR-0022:若本輪 agent 觸發了 transfer_to_human(escalation 變新),旁路 POST 給 API
    建 AI 草擬問題卡。env 未設 → 略過;失敗 fail-soft(只 log,不影響客人)。

    **AI 不自轉工單**:這裡只送 escalation,API 端最多建 draft PC;confirm/convert 走客服。
    """
    ...
    if not recs or recs[0].id <= before_id:
        return  # 本輪沒有新 escalation
```

API 端 `api/routers/internal_ingest.py:135-151`：

```python
async def ingest_escalation(
    body: EscalationIngestRequest,
    auth: ServicePrincipalContext = Depends(
        service_credential_required("escalations:write")
    ),
) -> dict:
    tenant_id = _resolve_tenant_id(body.tenant_id)
    assert_tenant_scope(auth, tenant_id)
    result = await problem_card_service.escalation_to_draft_pc(
```

### 步驟 4 — 第一次 ingest 失敗的處置

`agent/lockcore/channels/line_gateway.py:443-469`

```python
async def _post_escalation(base_url: str, token: str, payload: dict) -> bool:
    """單筆 escalation ingest。回 True=已送達（含 2xx），False=需重試。"""
    ...
        if resp.status_code < 400:
            return True
        # 4xx 多半是 payload 本身有問題，重試也不會好 → 不留 spool（避免無限累積）；
        # 5xx / 逾時才是「對方暫時不行」，值得補送。
        if 400 <= resp.status_code < 500:
            logger.error(
                "[ESCALATION_ALERT] escalation 遭拒（{}），payload 有問題不重試：{}",
                resp.status_code, resp.text[:200],
            )
            return True  # 視為終局，不再佔用 spool
        logger.warning("escalation 轉發回 {}:{}", resp.status_code, resp.text[:160])
        return False
    except Exception as e:  # noqa: BLE001
        logger.warning("escalation 轉發失敗（將落 spool 補送）: {!r}", e)
        return False
```

失敗落 spool 並告警，`agent/lockcore/channels/line_gateway.py:598-606`：

```python
    # 2026-08-02：先補送歷史失敗，再送本輪 —— 與對話持久化同一套耐久性
    # （原本這裡失敗只記一行 WARNING 就永久遺失，見 _flush_escalation_spool docstring）。
    await _flush_escalation_spool(base_url, token)
    if not await _post_escalation(base_url, token, payload):
        logger.error(
            "[ESCALATION_ALERT] 轉真人未送達，已落 spool 待補送 user={} path={}",
            user_id[:8], _ESCALATION_SPOOL_PATH,
        )
        await _spool_append(payload, _ESCALATION_SPOOL_PATH)
```

耐久性的成因記錄在 `agent/lockcore/channels/line_gateway.py:471-482`：

```python
async def _flush_escalation_spool(base_url: str, token: str) -> None:
    """補送 escalation spool。成功者移除、失敗者保留（下次再試）。

    2026-08-02：在此之前**轉真人轉發是唯一沒有耐久性的旁路** —— 對話持久化失敗會落
    spool、下次補送、發 [ARCHIVE_ALERT] ERROR；escalation 轉發失敗只有一行 WARNING，
    不重試、不落 spool、不告警，一次 5xx 或逾時就**永久遺失**。

    後果正是業主 2026-08-01 看到的畫面：訊息看得到（persist 成功）、AI 也說了
    「幫您轉接給真人專員」，但對話狀態沒翻成等待人工、後台也沒有問題卡
    —— 因為翻狀態與建卡都是 API 端收到 escalation 後的副作用，那個 POST 掉了就全沒了。
    """
```

TC 判定基準寫「第一次失敗**不得假稱已派工**」／程式碼的旁路發生在 agent 回覆之後（`_forward_escalation_safe` 為 turn 尾端旁路），失敗時客戶已收到 SOP 規定的轉接話術，補償手段為 spool + 下輪補送 + `[ESCALATION_ALERT]` ERROR；`transfer_to_human` 本身亦不因 escalation 寫入失敗而改變回傳內容（`transfer.py:161-162` 註解「不阻擋回覆」）。此處僅並陳，不裁定。

### 步驟 5 — 重試後只留一筆

`api/services/problem_card_service.py:1022-1039`

```python
    # TI-M03-06 / A06：sha256 冪等鍵 + 24h dedup 視窗（抵抗 DLQ/outbox retry 重複建卡）。
    # brand 在 AI 草擬卡多為空，鍵以 conv_id + 症狀 為主。命中 24h 內同鍵 → 回既有（冪等）。
    # CR-0096：只認「仍 active」的卡為 dedup 目標 —— 已轉工單/結案的舊卡不算，
    #          否則客人對已派工的舊問題再提同症狀會被誤 dedup 回舊卡、開不了新卡。
    idem_key = compute_pc_idempotency_key(conv_id, symptom_text, snapshot.get("brand"))
    kcur = await db_module._conn.execute(
        "SELECT id FROM problem_cards "
        "WHERE idempotency_key = %s AND created_at > NOW() - INTERVAL '24 hours' "
        "  AND status NOT IN ('resolved', 'escalated', 'dismissed') AND converted_at IS NULL "
        "ORDER BY created_at DESC LIMIT 1",
        (idem_key,),
    )
    krow = await kcur.fetchone()
    if krow:
        pc_id = str(krow[0])
        card = await get_card(tenant_id=tenant_id, pc_id=pc_id)
        return {"problem_card_id": pc_id, "conversation_id": conv_id,
                "created": False, "deduplicated": True, "card": card}
```

對話層亦冪等，`api/services/problem_card_service.py:964-980`：

```python
    conv, _ = await conversation_service.create_conversation(
        tenant_id=tenant_id,
        line_user_id=line_user_id,
        session_id=session_id,
        display_name=display_name,
    )
    conv_id = conv["id"]
    ...
    await db_module._conn.execute(
        "UPDATE conversations SET status = 'escalated', updated_at = NOW() "
        "WHERE id = %s::uuid AND status IS DISTINCT FROM 'escalated'",
        (conv_id,),
    )
```

`WHERE ... status IS DISTINCT FROM 'escalated'` 使重送不重複翻狀態。

補送迴圈本身也不會重複扣：`_flush_escalation_spool`（`line_gateway.py:495-503`）對每行呼 `_post_escalation`，成功才自 spool 移除。

### 步驟 6 — deterministic 兜底（說了沒做）

`agent/lockcore/channels/line_gateway.py:609-618`

```python
# CR-0097 方案 A 兜底：LLM tool-calling 不可靠 —— 會生成「已轉接/已安排師傅」話術卻
# 不呼叫 transfer_to_human，案子靜默蒸發（後台收不到問題卡）。偵測「AI 承諾轉接 + 本輪
# escalation 未新增（=沒呼叫工具）」→ 程式補一筆 escalation，讓既有 _forward_escalation
# 仍建問題卡。承諾話術用「完成式/指派式」字樣，降低純資訊提及的誤判。
# 完成式／已成事的承諾（一律視為真承諾，不受 hedge 影響）：出現＝案子已被交棒。
_DEFINITIVE_HANDOFF_MARKERS: tuple[str, ...] = (
    "已幫您轉接", "已為您轉接", "已轉接", "已為您轉接給",
    "已為您安排", "已幫您安排", "已安排專員", "已通報專員",
    "已登記", "已為您登記", "已為您記錄並轉", "已請師傅", "已派師傅",
)
```

另有未完成式語彙（`:622-628`）、條件語氣排除（`:632-636`）、否定排除（`:639-641`）與徵詢問句排除（`:642-644`）。

生成後 guard 亦有對應判定，`agent/lockcore/agent/reply_guard.py:72-88`：

```python
# 聲稱轉接/專員將聯繫的「確定式宣告」語彙（CR-0166 R0，K8 warranty_free say-do gap）：
# 嘴上說已轉接/會有專員聯繫，本 turn 卻沒呼叫 transfer_to_human = 案子蒸發。
```

### 步驟 7 — 執行既有測試

```
cd agent && python -m pytest tests/ -q
5 failed, 330 passed, 12 skipped in 8.24s
```

5 項失敗全在 `tests/test_skill_sync.py`，成因為 Windows 建立 symlink 需 `SeCreateSymbolicLinkPrivilege`（`OSError: [WinError 1314]`，落在 `agent/lockcore/agent/skill_sync.py:210` 的 `os.symlink`），屬執行環境限制。

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest -p winloop_plugin \
  tests/test_skills_v2_endpoint.py tests/test_escalation_to_draft_pc.py \
  tests/test_internal_ingest.py tests/test_config_m18.py -q
58 passed, 3 skipped in 6.09s
```

---

## 既有測試證據

- `api/tests/test_escalation_to_draft_pc.py`、`api/tests/test_internal_ingest.py`：與其他兩檔合跑 58 passed / 3 skipped（步驟 7）。
- agent 測試套件 330 passed（步驟 7）。
- 無對應既有測試涵蓋「5 分鐘 SLA」與「四種急件 intent 各送一次」——`git grep -rni "emergency_class\|5 分鐘\|5min" -- agent/tests` 零命中。

---

## 觀測到的其他事實

1. **`urgency_detected_at` 全樹零命中**：

```
git grep -rn "urgency_detected_at" -- api/ agent/ SQL/ web/
（無輸出，exit=1）
```

FR-AGT-04（`smartlock-docs/enterprise/04_SRS.md:279`）的驗收欄為「TransferEvent 落檔 + `urgency_detected_at` 寫入」。落檔部分對應 escalation store（`transfer.py:156`）與 draft 問題卡（`internal_ingest.py:143`）。此處僅並陳，不裁定。

2. **急件的下游效果在報價 gate，不在派工速度**：`api/services/work_order_service.py:583-586`

```python
    #     急件 carve-out（pc.emergency_class 四類）跳過報價直接開單、事後補審（4h timer＝1.2.2）。
    if pc_emergency_class is None:
```

補審查詢在 `api/services/work_order_service.py:1494-1510`（`AND pc.emergency_class IS NOT NULL`）。

3. **spool 有上限與丟棄告警**：`agent/lockcore/channels/line_gateway.py:388-393`

```python
            if len(lines) > _PERSIST_SPOOL_MAX:
                dropped = len(lines) - _PERSIST_SPOOL_MAX
                logger.error("[ARCHIVE_ALERT] spool 超限,丟棄最舊 {} 筆(上限 {})",
                             dropped, _PERSIST_SPOOL_MAX)
```

spool 路徑可由 `ESCALATION_SPOOL_PATH` 覆寫，預設 `data/escalation_spool.jsonl`（`:374-376`），為容器本機檔案。

4. **4xx 被視為終局不重試**：`line_gateway.py:457-462` 的 `return True  # 視為終局，不再佔用 spool`。即 API 端回 4xx（例如 tenant 解析失敗，`internal_ingest.py:54-58` 回 400）時該筆 escalation 不會被補送。

5. **情緒偵測與急件分類未連線**：`agent/lockcore/agent/sentiment.py:1-8` 自述用途為「①後台 sentiment_alerts 告警 ②K3' ≥90% 驗收」，並明示「寫庫/通知由呼叫端（gateway bridge → api internal endpoint）負責，維持 architecture lock（agent 不直接寫庫）」；`git grep -n "emergency" -- agent/lockcore/agent/sentiment.py` 零命中。
</content>
