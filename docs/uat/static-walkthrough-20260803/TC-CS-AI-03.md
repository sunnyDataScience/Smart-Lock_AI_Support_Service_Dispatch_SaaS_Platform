# TC-CS-AI-03 — 純知識問題不建草擬卡

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務 |
| 走查時間 | 2026-08-03 15:02（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/agent/skills.py`、`context.py`、`channels/line_gateway.py`、`agent/loop.py` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | skill references 回答路徑存在；建卡判斷以「本輪 escalation 表是否新增」為準，共三條寫入路徑，其中「話術兜底關鍵字比對」與「reply_guard 違規」兩條不屬於 TC 所述的「明確要真人／派工」。 |

**TC 原文**｜前置：知識 skill 已載入｜步驟：問「Yale 怎麼換電池」（純知識問題）｜判定基準：AI 以 skill references 回答；不建草擬卡（僅明確要真人/派工才建卡）｜需求：FR-AGT-03、FR-AGT-07、FR-DAT-04｜旅程：SC-01、SC-15

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | 問純知識問題 | `KnowledgeAnswered` | 以 skill references 作答 | `agent/lockcore/agent/skills.py:94-109` | 載入 skill markdown 併入 system prompt |
| 系統 | 判斷是否建卡 | （不應發生）`ProblemCardDrafted` | 僅明確要真人／派工才建卡 | `agent/lockcore/channels/line_gateway.py:573-577` | 比對本輪前後最新 escalation id，無新增即 return |
| AI | 呼叫 transfer_to_human | `EscalationLogged` | 明確要真人／派工 | `agent/lockcore/agent/tools/transfer.py:154-156` | 寫入 escalation |
| 系統 | 話術兜底 | `EscalationLogged` | （TC 未列此條件） | `agent/lockcore/channels/line_gateway.py:801-806` | AI 回覆含承諾轉接字樣但未呼叫工具 → 補寫 escalation |
| 系統 | reply_guard 違規 | `EscalationLogged` | （TC 未列此條件） | `agent/lockcore/agent/loop.py:1508-1516` | 重生後仍違規 → 寫 escalation |

---

## 走查紀錄

### 步驟 1 — skill references 作答路徑

- **動作**：確認 skill 內容如何進入模型輸入
- **預期**：知識問題由 skill references 作答
- **實際**：`load_skills_for_context` 讀 skill markdown 並串接，由 `ContextBuilder.build_system_prompt`（`agent/lockcore/agent/context.py:250`）併入 system prompt

`agent/lockcore/agent/skills.py:94-101`

```python
def load_skills_for_context(self, skill_names: list[str]) -> str:
    ...
    parts = [
        f"### Skill: {name}\n\n{self._strip_frontmatter(markdown)}"
        for name in skill_names
        if (markdown := self.load_skill(name))
    ]
    return "\n\n---\n\n".join(parts)
```

### 步驟 2 — 建卡的判斷依據

- **動作**：找「是否建草擬卡」的判斷邏輯
- **預期**：僅在明確要真人／派工時建卡
- **實際**：判斷依據不是意圖分類或關鍵字，而是「本輪 escalation 表是否新增一筆」

`agent/lockcore/channels/line_gateway.py:572-577`

```python
    try:
        recs = esc.list_for_user(tenant, user_id, limit=1)
    except Exception:  # noqa: BLE001
        return
    if not recs or recs[0].id <= before_id:
        return  # 本輪沒有新 escalation
```

### 步驟 3 — 列舉 escalation 的所有寫入路徑

- **動作**：找出所有會寫 escalation 的地方
- **預期**：只有「明確要真人／派工」一種
- **實際**：三條路徑，其中兩條不對應 TC 所述條件

路徑 (a) 工具呼叫 — `agent/lockcore/agent/tools/transfer.py:154-156`

```python
        if self._escalation_store:
            try:
                self._escalation_store.log(self._tenant, user_id, reason, is_explicit, snapshot)
```

路徑 (b) 話術兜底（比對 AI 自己的回覆字樣）— `agent/lockcore/channels/line_gateway.py:801-806`

```python
    if esc is None or not (reply or "").strip():
        return
    if _latest_escalation_id(esc, tenant, user_id) > before_id:
        return  # 本輪 AI 已正常呼叫工具 → 不重複補
    if not _promised_handoff(reply):
        return  # AI 沒承諾轉接 → 不兜底
```

路徑 (c) reply_guard 重生後仍違規 — `agent/lockcore/agent/loop.py:1508-1513`

```python
        if self._escalation_store is not None and ctx.msg.sender_id:
            try:
                self._escalation_store.log(
                    self._memory_tenant, ctx.msg.sender_id,
                    "reply_guard:" + ";".join(violations), False,
                    {"turn_id": ctx.turn_id},
                )
```

TC 判定基準寫「僅明確要真人/派工才建卡」，程式碼實際有三條寫入路徑。此處僅並陳，不裁定。

### 步驟 4 — 執行既有測試

- **動作**：跑 skill 載入與兜底不誤建卡的測試
- **預期**：取得執行證據
- **實際**：全數通過（含於下方批次執行）

```
cd agent && python -m pytest tests/test_skills_loaded.py tests/test_fallback_reply_no_handoff.py ... -q
1 failed, 170 passed, 3 skipped in 15.86s
```

（唯一失敗為 `test_line_gateway.py::test_debouncer_serializes_fires_per_session`，屬 TC-CS-AI-08 範圍，見該份文件。）

---

## 觀測到的其他事實

- `agent/lockcore/channels/line_gateway.py:798-799` 的註解說明兜底路徑刻意採「寧可多建」立場。
- 兜底比對的標記表定義於 `line_gateway.py:614-644`（`_DEFINITIVE_HANDOFF_MARKERS`／`_SOFT_HANDOFF_MARKERS`），判斷函式 `_promised_handoff` 在 `line_gateway.py:669-701`。
