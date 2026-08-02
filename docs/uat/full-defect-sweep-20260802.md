# 全維度缺陷掃描記錄（2026-08-02）

- **觸發**：業主問「所有沒有掃到 Bug?」——答案是**沒有**，當時只掃了 24 節裡的 2 節、
  1551 個檔案裡的 4 個（涵蓋率 < 0.3%）
- **方法**：以 `.claude/skills/sunnydata-code-review/references/defect-patterns.md`
  為判準，8 個維度平行掃 `api/services` + `api/routers`，每個 finding 派 skeptic 對抗驗證
- **結果**：14 個 finding，**對抗驗證 0 個被駁回**，全部修復
- **commit**：`ab6be160`（前 5 個）、`2bb0d0f3`（其餘 9 個）

---

## 一、涵蓋率（誠實版）

| 範圍 | 檔案數 | 本次掃描 |
|---|---|---|
| `api/services` + `api/routers` | ~150 | ✅ 8 維度 |
| `web/` 四站台 | 565 tsx | ❌ 完全未掃 |
| `agent/` 自有 code | 59 py（另 103 為 lockcore vendor） | ❌ 完全未掃 |
| `SQL/` migration | 163 | ❌ 完全未掃 |

**所以這次仍不是「掃完了」**，只是把 api 那一塊掃過一輪。

## 二、修復清單

| # | 嚴重度 | 位置 | 缺陷 |
|---|---|---|---|
| 6 | **CRITICAL** | `services/public_token.py:89` | HMAC 金鑰靜默 fallback 到原始碼常數 |
| 1 | HIGH | `services/reconciliation_service.py:340` | reject 無列鎖 → 出款給已駁回的對帳單 |
| 2 | HIGH | `services/cancellation_service.py:391` | v2 取消從反方向繞過 CR-0199 的完工樂觀鎖 |
| 3 | HIGH | `routers/gdpr_forget_v2.py:167` | 可跨租戶讀取並**硬刪**他人使用者 PII |
| 4 | HIGH | `routers/brand_b2b_statement_v2.py:109` | statement 跨租戶讀金額並核准／標記已付款 |
| 5 | HIGH | `services/technician_statement_service.py:163` | 同上（三組 statement 皆同一模式） |
| 7 | HIGH | `main.py:526` | WS 工單頻道無租戶命名空間 → 跨租戶收未遮罩 PII |
| 8 | HIGH | `services/conversation_service.py:600` | 接管回覆推送失敗完全無痕跡，客服看到 201 |
| 9 | HIGH | `routers/platform_technicians.py:60` | phone 無格式驗證 → 髒資料炸整支列表 |
| 10 | HIGH | `services/report_export_service.py:270` | 匯出的 from/to 是死參數，實際匯全期間 |
| 11 | MEDIUM | `services/config_m18_service.py:587` | 可跨租戶回滾他人 config 版本 |
| 12 | MEDIUM | `services/refund_service.py:672` | 契約宣告必填但 DB nullable → 必定 500 |
| 13 | LOW | `services/work_order_service.py:2974` | 加價金額解析失敗被吞 → 分級誤判、客戶看到 0 元 |
| 14 | LOW | `services/technician_service.py:91` | availability/level 死參數 |

## 三、最重要的三個發現

### 1. #6 的 fallback 是「寫在原始碼裡的簽章金鑰」

```python
_DEV_SECRET = "dev-secret-do-not-use-in-prod"
def _get_secret():
    return (os.getenv("PUBLIC_TOKEN_HMAC_SECRET") or _DEV_SECRET).encode()
```

這把 13 個消費者端點的簽章打開了——不只唯讀，還包括
`POST /consumer/quotes/{token}`（代客戶接受報價）與
`POST /consumer/scope-changes/{token}`（代客戶核可加價）。
payload 是明文 base64，偽造只需要知道工單 UUID。

**repo 內找不到任何地方設定這個 env**（部署腳本、`.env.example`、compose 全都沒有）。

> ⚠️ **prod 是否真的漏設，本次未能證實**。我第一次的查證用了
> `gcloud ... | grep ... || echo "未設"`——**gcloud 失敗時也會走到 `||` 分支**，
> 而當時 token 已過期。這是與「183 個端點回 400 就當守衛擋下」同一類的方法學錯誤：
> 沒有對照組。要確認需先 `gcloud auth login` 再查。

修法刻意**不做啟動失敗**：若 prod 確實漏設，fail-fast 會直接變 outage；
改用 process 啟動時隨機金鑰 + `logger.critical`，只讓既有公開連結失效
（那些連結若真是用已知金鑰簽的，本來就該失效）。

### 2. #2 是我自己修正的洞

CR-0199 加在 `work_order_service` 的完工樂觀鎖，被 v2 六階段取消**從反方向繞過**——
因為 `cancellation_service` 不經 `work_order_service.cancel_order`
（該檔的 CR-0193 註解自己寫明了這件事，我當時沒讀到）。

**教訓**：修一個狀態的併發保護時，要問「還有誰會寫這個欄位」，
而不只是「這個函式的競態修好了嗎」。

### 3. #8 的 except 是死碼

```python
try:
    await line_push_service.push_text(...)      # docstring: "Never raises"
except Exception:
    logger.warning(...)                          # ← 永遠不會執行
```

`push_text` 明文保證不拋例外、回 bool，而那個 bool 被丟棄。
所以推送失敗**完全無痕跡**，客服卻收到 201「已送出」。

**教訓**：`try/except` 看起來像有處理錯誤，但如果被呼叫方的契約是「回傳值表示失敗」，
那個 except 就是裝飾品。看到 fail-soft 的 try/except 要順手確認被呼叫方到底怎麼報錯。

## 四、驗證

| 項目 | 結果 |
|---|---|
| 全套測試 | **20 failed / 2305 passed**（基線 20 / 2284） |
| 逐條比對 | `comm -13` **零新增失敗** |
| 反向驗證 | worktree 退回 `cf62c3e2`，本批測試 **6 紅 3 綠**，修正後全綠 |
| 新增測試 | 9 個（public_token 金鑰 6、取消競態 3） |

### 未寫測試的部分（誠實標注）

- **#1 `reject_reconciliation`**：跨連線的 approve/reject 並發需要兩條真實連線，
  現有 `FakeConn` 夾具模擬不出。修法本身與同檔 `approve_reconciliation`
  對稱（`transaction()` + `FOR UPDATE OF r`），但**沒有回歸保護**。
- **#3 #4 #5 #7 #11 的跨租戶擋人**：只驗了既有測試沒被打壞，
  沒有新增「用 B 租戶的 id 打 A 租戶端點應得 404」的負向測試。
- **#10 #12 #13 #14**：靠既有測試涵蓋，無新增。

## 五、對抗驗證 0 駁回的說明

上一輪（CR-0199）的對抗驗證駁回了 5/16，這次 0/14。這個落差值得記錄：

- 這次的 prompt 明確要求 **precision > recall** 且**每個維度最多報 2 個**，
  所以 finder 自己先篩過一輪
- skeptic 並非照單全收——**主動下修了 5 個嚴重度**
  （#1 CRITICAL→HIGH、#3 CRITICAL→HIGH、#5 CRITICAL→HIGH、#6 CRITICAL→HIGH、
  #11 HIGH→MEDIUM、#12 HIGH→MEDIUM、#13 HIGH→LOW、#14 HIGH→LOW）
- 但 0 駁回仍應視為**可能偏鬆**的訊號，而不是「finding 品質完美」的證明

## 六、後續

1. **確認 prod 的 `PUBLIC_TOKEN_HMAC_SECRET`**（需 `gcloud auth login`）——
   若確實未設，部署本修正會讓既有公開連結失效，屬營運影響，需先告知
2. 部署前決定要不要先在 Secret Manager 建好這個 secret 並掛上
3. `web/` 565 個 tsx、`agent/` 59 個 py、`SQL/` 163 個 migration **仍未掃**
4. #1 的並發測試待有跨連線夾具時補
