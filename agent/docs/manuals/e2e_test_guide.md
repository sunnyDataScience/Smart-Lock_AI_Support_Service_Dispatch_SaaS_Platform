# E2E 模擬測試指南 (E2E Simulation Test Guide)

本文件說明如何使用 `scripts/simulate_e2e.py` 進行全系統端到端 (E2E) 模擬測試。這套工具旨在模擬真實上線（如部署於 Cloud Run）後，使用者透過 LINE 進行互動的各種真實情境。

---

## 1. 為什麼需要 E2E 模擬？

在開發階段，單純的 Unit Test 或 CLI 測試無法完全覆蓋以下真實行為：
- **LINE Webhook 行為**：包含 HMAC 簽名驗證與非同步處理。
- **訊息防抖 (Debounce)**：使用者在 1 秒內連發多則訊息時的合併邏輯。
- **多模態延遲**：圖片下載與背景處理的時序問題。
- **狀態機流程**：Quick Reply 追問品牌與型號的連續對話狀態。
- **雲端環境限制**：模擬在高延遲或超時設定下的系統反應。

---

## 2. 測試矩陣 (Test Matrix)

模擬器支援以下五大核心場景：

| 場景名稱 | 參數 `--scenario` | 測試重點 |
| :--- | :--- | :--- |
| **防抖合併** | `debounce` | 模擬使用者連傳三則訊息，確認 AI 只會產生一個合併回覆。 |
| **Quick Reply** | `quick_reply` | 模擬「提問 -> 追問品牌 -> 答品牌 -> 追問型號 -> 解答」的完整流程。 |
| **上下文記憶** | `context` | 測試 AI 是否能透過對話歷史理解代名詞（如「那要去哪裡買？」）。 |
| **多模態識別** | `multimodal` | 模擬使用者傳送圖片並緊接著傳送文字描述的時序處理。 |
| **安全閘門** | `safety` | 驗證系統是否能正確攔截超出服務範圍或具攻擊性的問題。 |

---

## 3. 使用方式

### 前置需求
確保已安裝依賴並設定好 `.env`（雖然腳本會 mock LINE Token，但仍需 LLM API Key）：
```bash
pip install -r requirements.txt
```

### 執行測試
你可以執行全部測試，或針對特定場景進行測試：

```bash
# 執行所有場景
python scripts/simulate_e2e.py --scenario all

# 只測試 Quick Reply 流程
python scripts/simulate_e2e.py --scenario quick_reply

# 只測試圖片識別功能
python scripts/simulate_e2e.py --scenario multimodal
```

---

## 4. 運作原理

`scripts/simulate_e2e.py` 透過以下技術達成「免連線」的真實模擬：

1.  **FastAPI TestClient**：直接啟動應用程式實例，並呼叫 `/webhook` 端點，這會觸發 `app.py` 中的完整生命週期。
2.  **Signature Mocking**：自動計算符合 LINE 規範的 `X-Line-Signature`，通過安全性檢查。
3.  **Dependency Interception**：
    *   攔截 `core.line_bot.send_response`：將 AI 的回覆直接輸出至終端機，而非發往 LINE 伺服器。
    *   攔截 `multimodal.download_and_store_media`：模擬圖片下載流程，避免依賴 LINE Content API。
4.  **Asyncio Control**：精確控制 `sleep` 時間，以觸發或重設 `harness/debounce.py` 中的計時器。

---

## 5. 擴充測試案例

若要新增測試場景，請在 `scripts/simulate_e2e.py` 中新增一個 `async def scenario_xxx(client)` 函式，並使用 `send_webhook` 輔助函式發送模擬訊息：

```python
async def scenario_my_test(client):
    print("\n[場景] 我的新測試")
    # 發送訊息
    send_webhook(client, TEST_USER_ID, "你好")
    # 等待系統反應
    await asyncio.sleep(5)
```

---

## 6. 與 Quality Check 的差異

| 特性 | `quality_check.py` | `simulate_e2e.py` |
| :--- | :--- | :--- |
| **目的** | 知識庫 (SOP) 準確率驗證 | 系統流程與中介層 (Harness) 穩定性 |
| **輸入** | 純文字題目 (JSON) | 模擬 Webhook Payload |
| **重點** | 回答內容是否包含關鍵字 | 防抖、狀態、超時、多模態處理 |
| **頻率** | 每次修改 SOP 後執行 | 每次修改核心邏輯或部署前執行 |
