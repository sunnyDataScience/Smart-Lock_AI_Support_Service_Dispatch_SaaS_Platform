# TC-CS-AI-11 — Chatlock 專屬拍照樣本圖

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務 |
| 走查時間 | 2026-08-03 15:26（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/channels/line_gateway.py:250-285`、`agent/config.toml:39-49`、`skills/locksmith-cs-sop/SKILL.md` |
| 優先級 / 路徑類型 | P0 / happy＋例外 |
| 事實結論 | 「未知 key 與被截斷標記只剝除不外洩、文字回覆不中斷」有 runtime 實作；「只有已確認 Chatlock 才附樣本圖」的品牌判斷只存在於 prompt／SOP 層，gateway 端只查 key 是否在映射表中，不驗品牌。 |

**TC 原文**｜前置：Chatlock 與非 Chatlock 品牌各一對話，photo guide key 已配置｜步驟：兩組客戶都要求拍照引導；另送未知 key 與被截斷標記｜判定基準：只有已確認 Chatlock 回覆附核准樣本圖；其他品牌純文字；未知/殘缺標記只剝除不外洩，文字回覆不中斷｜需求：FR-AGT-01｜旅程：SC-01

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| AI | 對 Chatlock 客戶輸出標記 | `PhotoGuideAttached` | 僅 Chatlock 附圖 | `skills/locksmith-cs-sop/SKILL.md:41-44`、`:77-81` | prompt 層規則，要求「僅在已確認為 Chatlock 時」輸出標記 |
| 系統 | 解析標記 | `PhotoGuideAttached` | 品牌檢查 | `line_gateway.py:270-278` | 只查 key 是否在 `guide_map`，**無品牌判斷** |
| AI | 對非 Chatlock 客戶輸出標記 | （不應附圖） | 其他品牌純文字 | `line_gateway.py:272-275` | key 存在即夾圖，不因品牌而拒 |
| 系統 | 收到未知 key | `PhotoGuideStripped` | 只剝除不外洩 | `line_gateway.py:276-278` | 記 WARNING，替換為空字串 |
| 系統 | 收到被截斷標記 | `PhotoGuideStripped` | 剝除殘尾 | `line_gateway.py:254`、`:281` | `_PHOTO_GUIDE_PARTIAL_RE` 剝掉行尾殘缺標記 |
| 系統 | 送出回覆 | `ReplySent` | 文字回覆不中斷 | `line_gateway.py:280-285` | 剝除後回傳 cleaned 文字，照常送出 |

---

## 走查紀錄

### 步驟 1 — 品牌判斷位於哪一層

- **動作**：搜尋 runtime 的 Chatlock 品牌檢查
- **預期**：gateway 或 loop 中有品牌條件
- **實際**：只在 SKILL.md（prompt 層）

`agent/lockcore/skills/locksmith-cs-sop/SKILL.md:41-44`

```
4. **預約安裝 / 維修**→ 依 `references/booking.md` 收必抓資訊(安裝要**明說「請提供照片」**;
   **僅在已確認客戶的鎖為 Chatlock 品牌時**,可在文末附 `[[photo-guide:chatlock-pre-install]]`
   讓系統夾發 Chatlock 施工前測量示範圖;**其他品牌尚無專屬測量圖 → 一律純文字引導拍照,不附標記**
   (量測部位因品牌而異,丟錯品牌的圖會誤導客戶量錯);
```

### 步驟 2 — gateway 端的實際判斷條件

- **動作**：讀標記解析函式
- **預期**：驗證品牌後才夾圖
- **實際**：只查 key 是否在映射表中

`agent/lockcore/channels/line_gateway.py:258-285`

```python
def _extract_photo_guides(
    text: str, guide_map: dict[str, str] | None
) -> tuple[str, list[str]]:
    """CR-0179：剝除回覆中的 [[photo-guide:key]] 標記，解析為樣本圖 URL 清單。

    未知 key／未配置映射：只剝不夾圖（fail-soft，標記文字絕不外洩給客人）。
    回 (乾淨文字, 圖 URL 去重保序、上限 4)。
    """
    if not text or "[[photo-guide:" not in text:
        return text, []
    urls: list[str] = []

    def _swap(m: re.Match) -> str:
        key = m.group(1)
        url = (guide_map or {}).get(key)
        if url:
            if url not in urls:
                urls.append(url)
        else:
            logger.warning("photo-guide 標記 key 未配置(僅剝除): {}", key)
        return ""
```

TC 判定基準為「只有已確認 Chatlock 回覆附核准樣本圖」，runtime 層無此檢查；若模型對非 Chatlock 客戶輸出該 key，gateway 會夾圖。此處僅並陳，不裁定。

### 步驟 3 — 未知 key 的處理

- **動作**：確認未知 key 是否外洩、是否中斷回覆
- **預期**：只剝除、文字照常送出
- **實際**：一致（`_swap` 回空字串並記 WARNING，cleaned 文字續行）

### 步驟 4 — 被截斷標記的處理

- **動作**：讀殘缺標記的剝除規則
- **預期**：剝掉殘尾防外洩
- **實際**：一致

`agent/lockcore/channels/line_gateway.py:252-255`、`:280-281`

```python
_PHOTO_GUIDE_RE = re.compile(r"\[\[photo-guide:([a-z0-9-]+)\]\]")
# handle_text_turn 先截 4900 再回：標記若恰被腰斬，剝掉殘尾防外洩。
_PHOTO_GUIDE_PARTIAL_RE = re.compile(r"\[\[photo-guide:[a-z0-9-]*$")
_PHOTO_GUIDE_MAX = 4  # LINE reply/push 上限 5 則，扣 1 則文字
...
    cleaned = _PHOTO_GUIDE_RE.sub(_swap, text)
    cleaned = _PHOTO_GUIDE_PARTIAL_RE.sub("", cleaned)
```

### 步驟 5 — key 的配置來源

- **動作**：找 `guide_map` 的來源
- **預期**：核准樣本圖清單可配置
- **實際**：`agent/config.toml:39-49` 定義 `chatlock-pre-install` URL，經 `app_config.py:50-52, 97-98` 載入、`scripts/line_gateway.py:115-116` 注入

### 步驟 6 — 執行既有測試

- **動作**：跑 `tests/test_photo_guide.py`
- **預期**：通過
- **實際**：通過（含於批次 170 passed）

```
cd agent && python -m pytest tests/test_photo_guide.py ... -q
1 failed, 170 passed, 3 skipped in 15.86s
```

（唯一失敗屬 TC-CS-AI-08 範圍。）

---

## 觀測到的其他事實

- SKILL.md:78 規定「一則回覆至多一個標記」，runtime 的上限為 4 張（`_PHOTO_GUIDE_MAX = 4`，`line_gateway.py:255`）。
- 標記剝除發生在送出、持久化、兜底三個下游之前（`line_gateway.py:1168-1169`）。
- 剝除後會做空白收斂（`line_gateway.py:282-284`）。
