# 資料修正功能使用指南

本文件說明 `#資料修正` 關鍵字攔截功能的使用方式與管理工具。

---

## 1. 功能概述

當 LINE 使用者在對話中輸入 `#資料修正`，系統會：

1. **跳過 AI Agent** — 不進入 LLM 推理流程
2. **擷取當前上下文** — 對話歷史（checkpoint 中的 user/ai messages）+ 用戶資料（brand/model/phone/address）
3. **寫入資料庫** — 存入 `data_corrections` 表，狀態為 `pending`
4. **回覆確認訊息** — 告知使用者已收到回報

使用者在發送 `#資料修正` 後可繼續正常對話，不會影響 AI 的對話上下文。

---

## 2. 使用者端操作

### 基本用法

在 LINE 對話中直接輸入：

```
#資料修正
```

### 附帶補充說明

`#資料修正` 後方的文字會作為補充說明存入 `note` 欄位：

```
#資料修正 品牌應該是Dormakaba不是Chatlock
```

```
#資料修正 剛才說的步驟做了沒效果
```

### 使用時機

- AI 回答了錯誤的故障排除步驟
- AI 辨識了錯誤的品牌或型號
- AI 提供的資訊與實際情況不符
- 任何需要人工審查的對話場景

---

## 3. 系統行為

### 攔截位置

```
LINE 訊息 → debounce buffer → process_and_reply()
  → H6 安全閘門
  → H_DC #資料修正 攔截 ← 在這裡
  → H_QR Quick Reply
  → run_agent()
```

### 不影響對話的原因

`#資料修正` 訊息在 `agent_and_reply()` 中被攔截，**不會執行 `run_agent()`**，因此：
- 不會寫入 LangGraph checkpoint
- 不會出現在後續對話歷史中
- 不會觸發記憶壓縮或輪廓萃取

### 限制

- 僅在 **LINE webhook** 路徑觸發（`POST /webhook`）
- `/chat` 測試端點不經過 `agent_and_reply()`，因此不會攔截
- 匹配方式為**前綴匹配**（`text.startswith("#資料修正")`）

---

## 4. 資料庫結構

### data_corrections 表

| 欄位 | 類型 | 說明 |
|------|------|------|
| `id` | BIGSERIAL | 主鍵 |
| `user_id` | TEXT | LINE 使用者 ID |
| `note` | TEXT | `#資料修正` 後方的補充說明 |
| `conversation_context` | TEXT | 擷取的對話歷史（純文字格式） |
| `user_facts` | JSONB | 擷取時的用戶資料快照 |
| `status` | VARCHAR(20) | `pending`（預設）/ `resolved` |
| `created_at` | TIMESTAMP | 建立時間 |

表在 server 啟動時由 `data_correction.init_db()` 自動建立（`CREATE TABLE IF NOT EXISTS`）。

---

## 5. 管理工具

### 查看修正紀錄

```bash
cd agent

# 顯示所有 pending 紀錄
python scripts/view_corrections.py

# 顯示全部紀錄（含已處理）
python scripts/view_corrections.py --all

# 查看特定使用者
python scripts/view_corrections.py --user U3bc4ff5b50486278d25d00d0c168fa02

# 匯出為 JSON（預設檔名 data_corrections.json）
python scripts/view_corrections.py --export

# 匯出至指定檔案
python scripts/view_corrections.py --export corrections_20260424.json

# 清空全部紀錄（會要求確認）
python scripts/view_corrections.py --clear
```

### 輸出範例

```
==============================================
  Data Corrections — Pending 紀錄
==============================================

  #1  |  PENDING  |  2026-04-24 09:31:03
  User: U3bc4ff5b...
  Facts: device_brand=Chatlock, device_model=A90
  Note: 品牌應該是Dormakaba
  ──────────────────────────────────
    用戶: 我的鎖打不開
    客服: [已參考技能: troubleshoot]
    客服: 好的，門打不開的情況...
  ──────────────────────────────────
```

### 查詢 Cloud SQL 資料

本機 `view_corrections.py` 預設讀 `.env` 的 `POSTGRES_URI`（本機 DB）。若要查 Cloud Run 上的資料，需透過 Cloud SQL Proxy：

```bash
# Terminal 1: 啟動 Cloud SQL Proxy
cloud-sql-proxy cedar-scope-489604-g3:asia-east1:lock-ai --port 5433

# Terminal 2: 查詢（.env 的 POSTGRES_URI 需指向 localhost:5433）
python scripts/view_corrections.py
```

### 手動更新狀態

處理完畢後，可透過 SQL 將狀態改為 `resolved`：

```sql
UPDATE data_corrections SET status = 'resolved' WHERE id = 1;
```

---

## 6. 設定

在 `agent/config.toml` 中的 `[data_correction]` section：

```toml
[data_correction]
enabled          = true              # 開關
keyword          = "#資料修正"        # 觸發關鍵字
reply            = "已收到您的回報，我們會盡快處理，謝謝您！"  # 回覆訊息
postgres_uri_env = "POSTGRES_URI"    # DB 連線環境變數名稱
```

設為 `enabled = false` 即可停用，`#資料修正` 訊息會正常進入 Agent。

---

## 7. 相關檔案

| 檔案 | 用途 |
|------|------|
| `agent/harness/data_correction.py` | 攔截模組（init_db / check_and_save / close_db） |
| `agent/harness/debounce.py` | 攔截呼叫點（agent_and_reply 內） |
| `agent/config.toml` | `[data_correction]` 設定區段 |
| `agent/scripts/view_corrections.py` | 查看/匯出修正紀錄的 CLI 工具 |
