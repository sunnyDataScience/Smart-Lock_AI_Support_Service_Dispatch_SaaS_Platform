# TC-COMPLIANCE-07 — 負面情緒 / 反諷識別率驗收

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **無法靜態判定** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；`sentiment_eval.py --dry`（僅驗語料結構、不打 LLM）可離線跑並通過；`--live`（實際量測識別率）需 LLM 憑證，本批未執行 |
| 走查時間 | 2026-08-03 18:02（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/scripts/sentiment_eval.py`、`agent/evals/sentiment_corpus.json`、`agent/lockcore/agent/sentiment.py`、`agent/scripts/forbidden_eval.py`、`agent/scripts/run_forbidden_gate.py`、`.github/workflows/forbidden-eval-gate.yml` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 三條門檻中只有「≥90% 識別」有對應常數（`sentiment_eval.py:27 THRESHOLD = 0.90`）；「誤攔 ≤1%」與「連續劣化觸發 block/incident」在程式碼中**找不到**任何常數或機制；實際識別率須實跑 LLM 量測，靜態走查不可得。 |

**TC 原文**｜前置：（空）｜步驟：labeled 100 題 + 反諷 20 題｜判定基準：識別 ≥ 90%、誤攔 ≤ 1%；連續劣化觸發 block/incident｜需求：FR-AGT-04、NFR-Comp-001｜旅程：SC-03

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 驗收者 | 跑 labeled 語料 | `EvalCorpusLoaded` | 100 題 + 反諷 20 題 | `agent/evals/sentiment_corpus.json`、`agent/scripts/sentiment_eval.py:31-49` | 語料 120 題（負面 100，其中 sarcasm group 20；另 neutral 12 / positive 8） |
| 系統 | 逐題判定情緒 | `SentimentClassified` | LLM 判定，反諷不得被表面字眼騙過 | `agent/lockcore/agent/sentiment.py:30-38`、`:65-80` | LLM 回 JSON label + confidence；解析失敗走關鍵詞 fallback |
| 系統 | 計算識別率 | `EvalScored(accuracy)` | ≥90% | `sentiment_eval.py:90-101` | 二元準確率（負面 vs 非負面）比對 `THRESHOLD = 0.90` |
| 系統 | 計算誤攔率 | `FalsePositiveRateScored` | ≤1% | — | **找不到** 誤攔率計算或 ≤1% 常數 |
| 系統 | 連續劣化處置 | `EvalDegradedBlocked` / `IncidentOpened` | 連續劣化 → block/incident | — | **找不到** 連續劣化判定；K8 禁區 gate 為單次 `<95%` block，非連續判定 |

---

## 走查紀錄

### 步驟 1 — 語料題數與反諷題配額

- **動作**：讀語料與結構驗證函式
- **預期**：labeled 100 題 + 反諷 20 題
- **實際**：語料共 120 題；標籤為負面者 100 題（`negative` 67 + `very_negative` 33），`group` 為 `sarcasm` 者 20 題，另有 `neutral` 12 / `positive` 8

```
python -c "..." 讀 agent/evals/sentiment_corpus.json
total 120
Counter({'negative': 67, 'very_negative': 33, 'neutral': 12, 'positive': 8})
Counter({'anger': 30, 'complaint': 30, 'mild': 20, 'sarcasm': 20, 'neutral': 12, 'positive': 8})
_meta = {"purpose": "K3' 負面情緒識別驗收（合約4.4a，≥90%）",
         "source": "CR-0166 R2 workflow-generated 2026-07-12", "total": 120}
```

`agent/scripts/sentiment_eval.py:36-49`

```python
def _validate(cases: list[dict]) -> list[str]:
    errs = []
    if len(cases) < 100:
        errs.append(f"corpus 題數 {len(cases)} < 100")
    labels = {"very_negative", "negative", "neutral", "positive"}
    for i, c in enumerate(cases):
        ...
    neg = sum(1 for c in cases if c.get("label") in _NEG)
    if neg < 90:
        errs.append(f"負面題數 {neg} < 90（K3 需 100 負面含 20 反諷）")
    return errs
```

結構閘為 `>= 100 題` 與 `負面 >= 90 題`；反諷 20 題的配額在 `_validate` 中**找不到**對應斷言（反諷只在 `_live` 中另行統計，`sentiment_eval.py:82`）。

### 步驟 2 — 「識別 ≥ 90%」門檻常數

- **動作**：讀門檻與計分
- **預期**：程式碼中有 90% 常數
- **實際**：一致存在。門檻為 `0.90`，量測對象為「負面 vs 非負面」二元準確率

`agent/scripts/sentiment_eval.py:26-28`

```python
CORPUS = ROOT / "evals" / "sentiment_corpus.json"
THRESHOLD = 0.90
_NEG = {"very_negative", "negative"}
```

`agent/scripts/sentiment_eval.py:90-101`

```python
    acc = correct / len(cases) if cases else 0.0
    print(f"\nK3' 負面情緒 eval — model={cfg.model}  ({len(cases)} 題)")
    print(f"  二元準確率（負面 vs 非負面）: {acc:.2%}  threshold={THRESHOLD:.0%}")
    if sarcasm_total:
        print(f"  反諷類（最難）: {sarcasm_correct}/{sarcasm_total} = "
              f"{sarcasm_correct / sarcasm_total:.2%}")
    ...
    passed = acc >= THRESHOLD
```

反諷類單獨列印比率，但反諷比率本身**未**設門檻、不影響 `passed`。

### 步驟 3 — 「誤攔 ≤ 1%」門檻常數

- **動作**：全 repo 搜尋誤攔／false positive 相關門檻
- **預期**：程式碼中有誤攔率計算與 1% 常數
- **實際**：**找不到**

```
git grep -rn "誤攔|false_positive|fp_rate|誤判率" -- agent api
agent/tests/test_reply_guard_blindspots.py:53:def test_price_violation_no_false_positive(label, text):
agent/tests/test_reply_guard_blindspots.py:54:    assert price_violation(text, escalated=False) is False, f"[{label}] 誤攔非報價：{text}"
agent/tests/test_reply_guard_blindspots.py:83:def test_unsourced_model_no_false_positive(label, reply, cust):
```

命中的三處屬 `reply_guard` 的報價／型號攔截誤判單元測試（布林斷言，非比率門檻），與情緒識別誤攔率無關。`sentiment_eval.py` 的輸出僅有 `accuracy` / `sarcasm_acc` / `fails` 三項（`:102-106`），無正負類分開的 precision／false-positive 統計。

TC 判定基準要求「誤攔 ≤ 1%」，程式碼中沒有對應量測與常數。此處僅並陳，不裁定。

### 步驟 4 — 「連續劣化觸發 block/incident」

- **動作**：搜尋連續劣化判定與 CI gate
- **預期**：連續多次評測劣化 → block 或開 incident
- **實際**：**找不到**「連續」判定。存在的兩項相關機制皆為單次判定

搜尋結果：

```
git grep -rni "consecutive" -- agent api .github
api/realtime/sla_monitor.py:413:  "consecutive_overdue": 3,          （急件補審逾時，非情緒 eval）
agent/lockcore/providers/fallback_provider.py:169: circuit open after {} consecutive failures （provider 熔斷，非 eval）

git grep -rn "incident" -- agent .github
（無輸出）
```

情緒 eval 的執行方式為手動 CLI（`sentiment_eval.py:7-9` 的 usage），`.github/workflows/` 內**找不到**任何引用 `sentiment_eval` 的 workflow；`git grep -rn "sentiment_eval" -- .github` 無輸出。

程式碼中唯一與 eval 綁 CI block 的是 K8 禁區 gate，其門檻為單次 `<95%`：

`agent/scripts/forbidden_eval.py:22`

```python
FORBIDDEN_GATE_THRESHOLD = 0.95
```

`.github/workflows/forbidden-eval-gate.yml:3-6`

```yaml
# CR-0135 / FR-A10：AI 禁區 200 題 Eval——每 deploy/agent 變動跑 dry 結構守門
# （corpus 七分類配額齊備 + judge 純函式迴歸）。live 全量 nightly 排程
# （02:00 台北）實跑 agent 全 corpus：GEMINI_API_KEY secret 未配置時亮紅
# 提示（不假綠，CR-0038 教訓），配置後自動生效。<95% pass-rate block。
```

該 gate 針對禁區話術（K8），非本 TC 的情緒識別（K3'），且判定為單次 run 的 pass-rate，無跨 run 的連續劣化狀態。

### 步驟 5 — 執行可離線的部分

- **動作**：跑 `--dry` 結構驗證與 agent 側情緒單元測試
- **預期**：取得執行證據
- **實際**：`--dry` 通過（exit 0）；agent 側測試 21 passed

```
cd agent && python scripts/sentiment_eval.py --dry
✅ dry：corpus 120 題結構完整（負面 100）
---RC=0

cd agent && python -m pytest tests/test_transfer_to_human.py tests/test_sentiment.py \
  tests/test_cr_0074_redline.py -q -rs
21 passed in 3.09s
```

`--dry` 只驗語料結構與欄位合法性，**不呼叫 LLM、不產生識別率數字**（`sentiment_eval.py:52-62`）。

---

## 為何無法靜態判定

- 「識別 ≥ 90%」是對 120 題語料逐題呼叫 `classify_sentiment(provider, text, model)` 後統計的比率（`sentiment_eval.py:77-90`）。判定值由 LLM 逐題回應決定，程式碼本身只有門檻常數，沒有可靜態推得的準確率。
- `classify_sentiment` 在 LLM 不可用或 JSON 解析失敗時會落到關鍵詞 fallback（`agent/lockcore/agent/sentiment.py:53-59`），該 fallback 對 `_ESCALATION_KEYWORDS`（`:23-28`）命中即回 `negative`。同一份語料在「LLM 正常」與「fallback」兩種執行期狀態下的準確率不同，靜態無從得知實際落在哪一條路徑。
- 「誤攔 ≤ 1%」與「連續劣化觸發 block/incident」在程式碼中沒有實作載體（見步驟 3、步驟 4），既無門檻常數也無量測輸出，即使實跑本專案現有腳本也不會產生對應數字。

## 判定所需的前置條件

1. LLM 憑證與路由可用：`agent/config.toml` 的 `[llm] model` 指向可呼叫的供應商（`sentiment_eval.py:7-8` 註明需 Vertex 憑證或 `model = vertex_ai/`；`.github/workflows/forbidden-eval-gate.yml:60-75` 另示範以 `GEMINI_API_KEY` + `gemini/gemini-2.5-flash` 的 CI 路由）。
2. 執行 `cd agent && uv run python scripts/sentiment_eval.py`（非 `--dry`），取得 `agent/evals/sentiment_eval_result.json` 內的 `accuracy` / `sarcasm_acc` / `fails`（`sentiment_eval.py:102-106`）。
3. 「誤攔 ≤ 1%」需先有量測定義與實作（目前語料非負面題僅 20 題：neutral 12 + positive 8），以及對應的門檻常數。
4. 「連續劣化 → block/incident」需先有跨 run 結果留存與比較機制，以及 block 或 incident 的觸發載體。

---

## 觀測到的其他事實

- `classify_sentiment` 的 system prompt 明文要求反諷判為 negative（`agent/lockcore/agent/sentiment.py:30-38`），與語料 `sarcasm` group 對應。
- 情緒判定結果的下游落點為 `api` 的 `sentiment_alerts`：agent 於 turn 內判定 → `EscalationIngestRequest.sentiment_label / sentiment_confidence / sentiment_keywords`（`api/models/internal.py:40-45`）→ `api/routers/internal_ingest.py:90-92`；後台端點在 `api/routers/sentiment_alerts_v2.py:38-96`。
- `agent/lockcore/agent/sentiment.py` 為純函式模組，docstring 明載「無 I/O 副作用；寫庫/通知由呼叫端負責，維持 architecture lock（agent 不直接寫庫）」（`:7-8`）。
- 語料 `_meta.purpose` 記為「K3' 負面情緒識別驗收（合約4.4a，≥90%）」，未提及誤攔率或連續劣化。
