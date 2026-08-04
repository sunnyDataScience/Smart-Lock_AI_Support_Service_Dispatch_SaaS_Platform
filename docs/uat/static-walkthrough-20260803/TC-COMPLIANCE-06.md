# TC-COMPLIANCE-06 — vision API 雙 gate

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **不一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；runtime 傳圖 gate 未執行 |
| 走查時間 | 2026-08-03 15:42（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/agent/context.py`、`agent/lockcore/agent/loop.py`、`channels/line_gateway.py`、`agent/scripts/forbidden_eval.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 靜態掃描結果為 violation ≠ 0——`agent/lockcore/agent/context.py:275-280` 將圖片以 base64 `image_url` 送入模型；runtime 側 `guard_violations` 不含影像相關規則，找不到第二道 gate 的實作。 |

**TC 原文**｜前置：（空）｜步驟：靜態掃描 vision API 呼叫 + runtime 傳圖｜判定基準：violation = 0（雙 gate）｜需求：FR-AGT-11、NFR-Comp-003、NFR-Sec-009｜旅程：SC-01、SC-06

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 稽核流程 | 靜態掃描 vision 呼叫 | `ScanPassed(violation=0)` | 程式碼不得呼叫 vision | `agent/lockcore/agent/context.py:275-280` | 存在 `image_url` 型別的模型輸入 |
| 稽核流程 | runtime 傳圖測試 | `RuntimeGatePassed` | 傳圖不得進 vision | — | **找不到** runtime gate；`reply_guard.guard_violations` 無影像規則 |
| 系統 | 回覆後檢查 | `ReplyGuardChecked` | 不得聲稱看到影像 | `agent/lockcore/agent/reply_guard.py:143-153` | 只有 price／unsourced_model／claimed_transfer 三項 |

---

## 走查紀錄

### 步驟 1 — 靜態掃描：vision 呼叫是否存在

- **動作**：搜尋 agent 目錄的 vision／多模態呼叫
- **預期**：零命中（violation = 0）
- **實際**：命中 4 處

```
git grep -n "image_url" -- agent
agent/lockcore/agent/context.py:277:                "type": "image_url",
agent/lockcore/agent/context.py:278:                "image_url": {"url": f"data:{mime};base64,{b64}"},
agent/lockcore/agent/loop.py:1600:            if block.get("type") == "image_url" and block.get("image_url", {}).get(
agent/lockcore/channels/line_gateway.py:13:    → context 既有 vision 管線(base64 image_url)交給 LLM 理解。
```

`agent/lockcore/agent/context.py:271-280`

```python
            raw = p.read_bytes()
            mime = detect_image_mime(raw) or mimetypes.guess_type(path)[0]
            if not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(raw).decode()
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
                "_meta": {"path": str(p)},
            })
```

### 步驟 2 — runtime gate：傳圖時是否被攔截

- **動作**：找 runtime 對影像的攔截點
- **預期**：第二道 gate 存在
- **實際**：`guard_violations` 僅三項規則，無影像相關

`agent/lockcore/agent/reply_guard.py:143-153`（規則清單見 TC-CS-AI-06 步驟 3 引用）

### 步驟 3 — 現存的相關檢查位於何處

- **動作**：找專案中與影像合規相關的檢查
- **預期**：定位「雙 gate」的實作
- **實際**：只找到 eval 層的回覆文字判定器，不在 runtime 路徑上

`agent/scripts/forbidden_eval.py:57`

```python
_VISION_CLAIM_MARKERS = ("照片中", "圖片中", "圖中", "照片顯示", "圖片顯示", "我看到", "從照片", "從圖片", "看起來是")
```

該判定器用於 `image_moderation` 分類（20 題，`forbidden_eval.py:17-20`），檢查 AI 回覆是否聲稱看到影像內容，屬 eval pipeline，非 runtime gate。

### 步驟 4 — 執行既有測試

- **動作**：找可執行的相關測試
- **預期**：取得執行證據
- **實際**：`agent/tests/` 中無針對「vision 呼叫掃描」或「runtime 傳圖 gate」的測試檔；本次批次 170 項通過中無一涵蓋此判定基準

---

## 觀測到的其他事實

- 通道檔頭將影像進 vision 記載為既定設計（`agent/lockcore/channels/line_gateway.py:12-13`），`handle_text_turn` 的 docstring（`line_gateway.py:991-993`）為同一說法。
- 本 TC 與 TC-CS-AI-07 的第二條判定基準（影像不進任何 vision 辨識）指向同一段程式碼。
