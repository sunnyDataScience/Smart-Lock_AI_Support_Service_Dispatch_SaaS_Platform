# TC-CS-AI-07 — 圖文混合訊息與影像處理

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **不一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務 |
| 走查時間 | 2026-08-03 15:14（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/channels/line_gateway.py`、`agent/lockcore/agent/context.py`、`agent/lockcore/agent/loop.py`；evidence 佇列另掃 `api/`、`web/`、`SQL/` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 判定基準三條中，「訊息不遺失」有對應實作；「影像不進任何 vision 辨識」與程式碼相反——照片以 base64 `image_url` 送進 LLM；「照片入 evidence 佇列」在 `api`／`agent`／`web`／`SQL` 全數搜尋零命中。 |

**TC 原文**｜前置：客戶傳照片 + 文字混合訊息｜步驟：連發圖片與文字｜判定基準：訊息不遺失；影像不進任何 vision 辨識（合約禁用）；照片入 evidence 佇列供人工檢視｜需求：FR-AGT-11｜旅程：SC-01

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | 連發圖片與文字 | `MessagesBuffered` | 訊息不遺失 | `agent/lockcore/channels/line_gateway.py:1117-1129` | debounce 合併，文字換行串接、media 路徑全數累加 |
| 系統 | 下載圖片 | `ImageStored` | 存檔備查 | `line_gateway.py:1254-1267` | Blob API 下載到 media dir，`media_paths=[img_path]` |
| 系統 | 組模型輸入 | （不應發生）`ImageSentToVision` | 影像不進任何 vision 辨識 | `agent/lockcore/agent/context.py:275-280` | 圖片轉 base64 後以 `image_url` 型別送入模型 |
| 系統 | 照片歸檔 | `EvidenceQueued` | 入 evidence 佇列供人工檢視 | — | **找不到**任何 evidence 佇列實作 |

---

## 走查紀錄

### 步驟 1 — 判定基準①「訊息不遺失」

- **動作**：讀 debounce 合併邏輯對文字與媒體的處理
- **預期**：連發的訊息與媒體都保留
- **實際**：文字以換行合併、媒體路徑全數串接

`agent/lockcore/channels/line_gateway.py:1117-1129`

```python
    async def _run_merged_turn(key: str, items: list[dict]) -> None:
        user_id = key.partition(":")[2] or key
        reply_token = items[-1].get("reply_token")
        merged_text = "\n".join(
            t for t in ((i.get("text") or "") for i in items) if t.strip()
        )
        all_media = [p for i in items for p in (i.get("media") or [])]
```

### 步驟 2 — 圖片的接收路徑

- **動作**：讀 LINE 圖片訊息的處理
- **預期**：取得圖片後的去向
- **實際**：下載到 media 目錄後放入 `InboundMessage.media`

`agent/lockcore/channels/line_gateway.py:1254-1260`

```python
                elif isinstance(event.message, ImageMessageContent):
                    blob_api = AsyncMessagingApiBlob(api_client)
                    img_path = await download_line_image(blob_api, event.message.id)
                    ...
                    user_text = ""  # LINE 圖片訊息無 caption;persist 用 [照片] 標記
                    media_paths = [img_path]
```

### 步驟 3 — 判定基準②「影像不進任何 vision 辨識」

- **動作**：追 `InboundMessage.media` 進入模型輸入的路徑
- **預期**：影像不送入任何 vision／多模態 API
- **實際**：影像被 base64 編碼後以 `image_url` 型別送入模型輸入

`agent/lockcore/agent/context.py:261-284`

```python
    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text

        images = []
        for path in media:
            ...
            b64 = base64.b64encode(raw).decode()
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
                "_meta": {"path": str(p)},
            })

        if not images:
            return text
        return images + [{"type": "text", "text": text}]
```

同一行為在通道檔頭以設計說明形式載明：

`agent/lockcore/channels/line_gateway.py:12-13`

```
  - 照片 → 以 Blob API 下載到 get_media_dir("line") → InboundMessage(media=[路徑])
    → context 既有 vision 管線(base64 image_url)交給 LLM 理解。
```

`git grep -n "image_url" -- agent` 命中 `context.py:277-278`、`loop.py:1600`、`line_gateway.py:13,992`。

TC 判定基準為「影像不進任何 vision 辨識（合約禁用）」，程式碼實際將影像送入模型。此處僅並陳，不裁定。

### 步驟 4 — 判定基準③「照片入 evidence 佇列」

- **動作**：搜尋 evidence 佇列的實作與資料表
- **預期**：存在供人工檢視的佇列
- **實際**：全數零命中

```
git grep -ln "evidence_queue\|evidence佇列\|evidence_review" -- api agent web SQL
（無輸出）

git grep -n "CREATE TABLE.*evidence" -- SQL
（無輸出）
```

照片在程式碼中的去向只有兩處：步驟 3 的模型輸入，以及持久化旁路 `_encode_media_for_persist`（`line_gateway.py:225-247`）送往 `/api/v1/internal/conversations/ingest`。

### 步驟 5 — 執行既有測試

- **動作**：跑相關測試取執行證據
- **預期**：取得證據
- **實際**：本 TC 的三條判定基準在 `agent/tests/` 中無對應測試檔；批次執行的 170 項通過中無一針對「影像不進 vision」或「evidence 佇列」。

---

## 觀測到的其他事實

- `agent/evals/forbidden_corpus.json` 有 `image_moderation` 分類（配額 20 題，`agent/scripts/forbidden_eval.py:17-20`），判定器標記表在 `agent/scripts/forbidden_eval.py:57`：

  ```python
  _VISION_CLAIM_MARKERS = ("照片中", "圖片中", "圖中", "照片顯示", "圖片顯示", "我看到", "從照片", "從圖片", "看起來是")
  ```

  該 eval 檢查的是「AI 是否聲稱看到影像內容」，屬回覆文字層；`agent/lockcore/agent/reply_guard.py:143-153` 的 runtime `guard_violations` 不含此項。
- 其他訊息型別（貼圖／語音／影片／檔案／位置）回友善話術，見 `line_gateway.py:14`。
