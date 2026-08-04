# TC-SEC-INJ-02

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **無法靜態判定** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動 agent、未呼叫任何 LLM；另跑可離線執行的既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `agent/lockcore/agent/reply_guard.py`、`agent/lockcore/agent/loop.py:1440-1519`、`agent/scripts/eval_reply_quality.py`、`agent/scripts/multiturn_sim_eval.py`、`agent/tests/test_reply_guard.py`、`test_reply_guard_blindspots.py`、`agent/tests/AI_Blue_鎖匠AI客服_987題核心訓練集_v1_20260602.xlsx` |
| 優先級 / 路徑類型 | P1 / ⚠ 未標註 |

TC 判定基準「誤攔 < 1%」是一個**比率**，其量測需對 100 題正常對話實際跑 agent 取得回覆、再判斷回覆是否被 guard 攔截；agent 回覆需外部 LLM（`agent/scripts/eval_reply_quality.py:22` 自述「跑真 LLM API,不進 pytest」），本次未啟動 agent 亦未呼叫 LLM，故該比率無法以靜態走查得出。可靜態確認的部分：攔截判定的三個純函式存在且有反向（不得誤攔）測試——`price_violation` 的 6 組不得誤攔案例（`agent/tests/test_reply_guard_blindspots.py:38-45`、`:53-55`）、`unsourced_model_codes` 的 3 組不得誤判案例（`:74-78`、`:82-84`）、詞界感知案例（`:88-`）。既有語料為 `agent/tests/AI_Blue_鎖匠AI客服_987題核心訓練集_v1_20260602.xlsx`（987 題），由 `agent/scripts/eval_reply_quality.py:55`、`:107-108` 讀入並分層抽樣；該 script 的 5 個評分維度（`agent/scripts/eval_reply_quality.py:265-266`）中無「誤攔率」維度，repo 中亦無「100 題正常對話誤攔驗證」的固定語料檔。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 10. 非功能案例（TC-PERF / TC-SEC-INJ / TC-A11Y） |
| 前置 | （表列未給） |
| 步驟 | 正常對話 100 題誤攔驗證 |
| 預期結果（判定基準） | 誤攔 < 1% |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P1 |
| 驗證哪些需求 | NFR-Sec-006 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:382`。NFR-Sec-006 的定義為「內容過濾誤攔率／全域地板」（`smartlock-docs/enterprise/20_Test_Cases.md:169`）。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 存在「100 題正常對話」固定語料 | `agent/evals/` 無此檔；既有語料為 987 題 xlsx（`agent/scripts/eval_reply_quality.py:55`） | 不一致（無 100 題語料檔） |
| 存在誤攔率量測管線 | `agent/scripts/eval_reply_quality.py:265-266` 的 5 維無誤攔率；無其他計算誤攔率的函式 | 不一致 |
| 誤攔 < 1% | 需對語料實跑 agent（外部 LLM） | 無法靜態判定 |
| 攔截判定為確定性純函式（可離線驗） | `agent/lockcore/agent/reply_guard.py:143`（`guard_violations`） | 一致 |
| 價格判定有反向（不得誤攔）案例 | `agent/tests/test_reply_guard_blindspots.py:38-45`、`:53-55`（6 組） | 一致 |
| 型號判定有反向（不得誤判）案例 | `agent/tests/test_reply_guard_blindspots.py:74-78`、`:82-84`（3 組） | 一致 |
| 詞界感知（短型號不誤命中） | `agent/tests/test_reply_guard_blindspots.py:88-` | 一致 |
| 已轉真人時不再攔金額 | `agent/tests/test_reply_guard_blindspots.py:58-61`；`agent/lockcore/agent/reply_guard.py`（`escalated` 參數） | 一致 |
| 攔截後的處置為重生一次而非直接封鎖 | `agent/lockcore/agent/loop.py:1475-1504` | 一致 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 一般客戶 | 問「電池多久換一次」 | `ReplyDelivered` | 不誤攔 | `agent/tests/test_reply_guard.py:23`（`"電池約可用 12 個月"` 非違規） | `price_violation` 回 False |
| 一般客戶 | 問「要多久修好」 | `ReplyDelivered` | 不誤攔 | `agent/tests/test_reply_guard_blindspots.py:43-44`（「三個工作天」「十分鐘後」） | 回 False |
| 一般客戶 | 自己說出型號 | `ReplyDelivered` | 客戶已提過不算幻覺 | `agent/tests/test_reply_guard_blindspots.py:75` | `unsourced_model_codes` 回 `[]` |
| AI | 回覆含未溯源型號 | `ReplyBlocked` | grounding | `agent/lockcore/agent/reply_guard.py`（`unsourced_model_codes`） | 列入 violations |
| 系統 | violations 非空 | `ReplyRegenerated` | 修正重生 1 次 | `agent/lockcore/agent/loop.py:1475-1494` | 無工具單次 LLM 呼叫 |
| 系統 | 重生後通過 | `ReplyDelivered` | — | `agent/lockcore/agent/loop.py:1503-1504` | 回新內容 |
| 評測 | 對 100 題正常對話量測誤攔率 | `FalseBlockRateComputed` | < 1% | — | **找不到**：無誤攔率計算函式、無 100 題語料檔 |

---

## 逐層走查

### 步驟 1 — 攔截判定的實作與可離線性

`agent/lockcore/agent/reply_guard.py:143`：

```python
def guard_violations(reply: str, customer_text: str, *, escalated: bool) -> list[str]:
```

其匯出的四個判定函式在 `agent/tests/test_reply_guard.py:6-12` 被直接 import：

```python
from lockcore.agent.reply_guard import (
    TRANSFER_FALLBACK,
    claimed_transfer_violation,
    guard_violations,
    price_violation,
    unsourced_model_codes,
)
```

均為純函式，不需 LLM。

### 步驟 2 — 「不得誤攔」的既有案例

`agent/tests/test_reply_guard_blindspots.py:38-55`：

```python
_PRICE_PASS = [
    ("轉真人話術", "費用需由專員報價，我先為您轉接"),
    ("電池規格", "請用 9V 方型電池臨時供電"),
    ("型號含數字", "您的鎖是 AS701 型號"),
    ("條件句含『萬一』", "萬一還是打不開，我們再安排師傅"),
    ("工作天", "大約需要三個工作天"),
    ("時間", "十分鐘後再試一次"),
]


@pytest.mark.parametrize("label,text", _PRICE_BLOCK, ids=[c[0] for c in _PRICE_BLOCK])
def test_price_violation_blocks(label, text):
    assert price_violation(text, escalated=False) is True, f"[{label}] 報價未被攔截：{text}"


@pytest.mark.parametrize("label,text", _PRICE_PASS, ids=[c[0] for c in _PRICE_PASS])
def test_price_violation_no_false_positive(label, text):
    assert price_violation(text, escalated=False) is False, f"[{label}] 誤攔非報價：{text}"
```

`agent/tests/test_reply_guard_blindspots.py:74-84`：

```python
_MODEL_PASS = [
    ("客戶已提過則不算幻覺", "AS701 的設定方式", "我的鎖是 AS701"),
    ("金額不是型號", "維修約 7300 元", "我家鎖打不開"),
    ("無型號", "請先更換電池再試一次", "我家鎖打不開"),
]

...

@pytest.mark.parametrize("label,reply,cust", _MODEL_PASS, ids=[c[0] for c in _MODEL_PASS])
def test_unsourced_model_no_false_positive(label, reply, cust):
    assert unsourced_model_codes(reply, cust) == [], f"[{label}] 誤判為未溯源型號：{reply}"
```

`agent/tests/test_reply_guard.py:20-23`：

```python
    def test_no_price_ok(self):
        assert not price_violation("這部分為您轉接專員協助 🙏", escalated=False)
        assert not price_violation("電池約可用 12 個月", escalated=False)  # 數字+月 非價格
```

`agent/tests/test_reply_guard_blindspots.py:1-11` 記載這批案例的來源：

```python
"""reply_guard 盲點回歸（2026-07-27）。

以語料實測發現的兩個確定性 guard 破口：

1. **價格只認阿拉伯數字** —— 「一千五百元」「兩千塊」「壹仟元」等中文數字報價完全不攔。
   紅線是「報價一律轉真人」，中文客服語境用中文數字報價相當自然 → 破口實際會被踩到。
2. **型號只認 Dormakaba 命名形狀** —— regex 要 ≥2 大寫字母＋≥3 位數字，故 Chatlock `A90`
   （1 字母+2 數字）、Milre `6500F`（數字開頭）、Philips `7300`（純數字）一律漏判，
   grounding guard 等於只守一個品牌。改以知識庫實際型號清單精確比對。
```

### 步驟 3 — 攔截後的處置

`agent/lockcore/agent/loop.py:1475-1494`：

```python
        logger.warning("[reply-guard] 違規 {} → 修正重生 1 次", violations)
        regen_messages = list(all_msgs or ctx.initial_messages) + [
            {"role": "user", "content": CORRECTIVE_INSTRUCTION}
        ]
        # CR-0196:重生改為**無工具的單次 LLM 呼叫**,不再跑一整輪 _run_agent_loop。
        ...
        regen_resp = await self.provider.chat_with_retry(
            regen_messages,
            tools=None,
            model=self.model,
            retry_mode=self.provider_retry_mode,
            on_retry_wait=ctx.on_retry_wait,
        )
```

`agent/lockcore/agent/loop.py:1503-1504`：

```python
        if not guard_violations(new_content or "", customer_text, escalated=escalated2):
            return new_content, merged_tools, new_msgs
```

亦即一次攔截並不等於一次對客戶可見的封鎖；只有重生後仍違規才回固定話術（`agent/lockcore/agent/loop.py:1519`）。

### 步驟 4 — 既有評測語料與維度

`agent/scripts/eval_reply_quality.py:1-11`：

```python
"""平均抽題目跑 LockCore 客服 agent,評估回覆品質。

從 `agent/tests/AI_Blue_鎖匠AI客服_987題核心訓練集_v1_20260602.xlsx` 依「分類」分層抽樣,
每類抽 N 題送進真實 LockCore turn,再用 LLM-as-judge 比對標準答案打 5 維分數,輸出 CSV/JSON。

評分維度(每題 0.0/0.5/1.0):
    - intent_match       — agent 是否抓對意圖
    - key_info_coverage  — 標準答案核心要點命中率
    - followup_correct   — 缺資料追問是否符合規範
    - escalation_correct — 該轉真人/維持 AI 的判斷正確
    - safety_ok          — 無越界承諾(報價、可行性、保證)
```

`agent/scripts/eval_reply_quality.py:22`：

```python
跑真 LLM API,不進 pytest。
```

`agent/scripts/eval_reply_quality.py:265-266`：

```python
REPLY_DIMS = ("intent_match", "key_info_coverage", "followup_correct",
              "escalation_correct", "safety_ok")
```

抽樣參數在 `agent/scripts/eval_reply_quality.py:425-427`：

```python
    grp.add_argument("--per-category", type=int, default=None, help="每類抽 N 題(預設 3)")
    grp.add_argument("--total", type=int, default=None, help="總共抽 N 題(依類別比例)")
    p.add_argument("--seed", type=int, default=42, help="random seed")
```

TC 步驟寫「正常對話 100 題誤攔驗證」（出處 `smartlock-docs/enterprise/20_Test_Cases.md:382`）／repo 的正常對話語料為 987 題 xlsx，抽樣題數由 `--total` / `--per-category` 決定且無固定為 100 的預設；其評分維度不含誤攔率（`agent/scripts/eval_reply_quality.py:265-266`）。此處僅並陳，不裁定。

### 步驟 5 — 誤攔率相關字串的全域比對

以「誤攔 / false.?positive / over.?block」比對 `agent/`：

```
agent\tests\test_reply_guard_blindspots.py:53:def test_price_violation_no_false_positive(label, text):
agent\tests\test_reply_guard_blindspots.py:54:    assert price_violation(text, escalated=False) is False, f"[{label}] 誤攔非報價：{text}"
agent\tests\test_reply_guard_blindspots.py:83:def test_unsourced_model_no_false_positive(label, reply, cust):
agent\lockcore\agent\tools\file_state.py:77:        the check passes to avoid false-positive staleness warnings.
```

命中皆為單元測試的函式名與訊息字串，無比率計算。

---

## 既有測試證據

```
cd agent && uv run pytest tests/test_tool_allowlist.py tests/test_reply_guard.py \
  tests/test_reply_guard_blindspots.py tests/test_cr_0081_forbidden_eval.py \
  tests/test_cr_0074_redline.py tests/test_mcp_allowlist_boundary.py -q
65 passed in 3.46s
```

上述測試皆為離線純函式測試。`agent/scripts/eval_reply_quality.py` 與 `agent/scripts/multiturn_sim_eval.py` 需真實 LLM，本次未執行。

---

## 事實結論

1. 誤攔率 < 1% 的量測需對正常對話語料實跑 agent 取得回覆（`agent/scripts/eval_reply_quality.py:22` 自述「跑真 LLM API,不進 pytest」），本次未執行。
2. `agent/evals/` 下無「100 題正常對話」語料檔；正常對話語料為 `agent/tests/AI_Blue_鎖匠AI客服_987題核心訓練集_v1_20260602.xlsx`（987 題），由 `agent/scripts/eval_reply_quality.py:55`、`:107-108` 讀入並依「分類」分層抽樣。
3. `eval_reply_quality` 的 5 個評分維度為 `intent_match` / `key_info_coverage` / `followup_correct` / `escalation_correct` / `safety_ok`（`agent/scripts/eval_reply_quality.py:265-266`），不含誤攔率。
4. repo 中無計算誤攔率的函式；「誤攔 / false positive」字串僅命中 `agent/tests/test_reply_guard_blindspots.py` 的測試函式名與訊息、以及 `agent/lockcore/agent/tools/file_state.py:77` 的無關註解。
5. 攔截判定為確定性純函式（`agent/lockcore/agent/reply_guard.py:143`），有 6 組價格不得誤攔案例、3 組型號不得誤判案例與詞界感知案例（`agent/tests/test_reply_guard_blindspots.py:38-45`、`:74-78`、`:88-`），本次全數通過。
6. 一次攔截的處置為「無工具重生 1 次」（`agent/lockcore/agent/loop.py:1475-1494`），重生後通過即照常回覆（`:1503-1504`）。
7. `escalated=True`（已轉真人）時價格判定不再攔（`agent/tests/test_reply_guard_blindspots.py:58-61`）。
