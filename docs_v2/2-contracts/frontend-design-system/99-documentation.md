# 99_Documentation — 電子鎖智能客服與派工平台 治理、交付、變更管理

> 設計系統如果沒有治理，只會越來越胖、越來越亂，最後死掉。
> 本文件定義 Admin Panel、Technician PWA、LINE Bot 三端的設計治理規範。

---

## 目錄

1. [Do / Don't 規範](#1-do--dont-規範)
2. [元件貢獻規範](#2-元件貢獻規範)
3. [Handoff Spec（交付規格）](#3-handoff-spec交付規格)
4. [Design QA Checklist](#4-design-qa-checklist)
5. [Change Log](#5-change-log)
6. [Version 策略](#6-version-策略)
7. [Ownership & Review](#7-ownership--review)
8. [Deprecation 流程](#8-deprecation-流程)
9. [Design ↔ Dev 同步機制](#9-design--dev-同步機制)

---

## 1. Do / Don't 規範

### 1.1 全域規則（適用所有元件、所有平台）

| ✅ Do | ❌ Don't |
|-------|---------|
| 使用 Design Token，不寫 magic number | 直接寫 `#2563EB` 或 `padding: 13px` |
| 遵循 Spacing Scale（4px 倍數） | 用 5px、7px、13px 這種非系統值 |
| 每個互動元素都有 hover + focus + active + disabled 狀態 | 只做 default 狀態就交付 |
| 空狀態、錯誤狀態、Loading 都要設計 | 只設計 happy path |
| 一頁只有一個 Primary CTA | 放 3 個 Primary Button 搶注意力 |
| 使用語意色（status.pending / status.danger） | 用品牌色 #2563EB 表示錯誤 |
| Icon + Text 配對（非 icon-only 優先） | 只用 icon 沒有任何文字提示 |
| 圖片有 alt text / aria-label | 純裝飾圖片佔用 screen reader |
| 遵守 prefers-reduced-motion | 強制所有使用者看動畫 |

### 1.2 工單狀態規則

| ✅ Do | ❌ Don't |
|-------|---------|
| 使用工單狀態語意色（6 色系）表示所有工單狀態指示 | 自創新顏色表示工單狀態 |
| 每個狀態同時用「顏色 + 文字標籤 + icon」三重傳達 | 僅靠顏色區分工單狀態（色盲無法辨識） |
| SLA 倒數計時用 3 階段視覺：綠（>50%）、琥珀（20%–50%）、紅（<20%） | SLA 只顯示數字不顯示視覺提示 |
| SLA 逾期時用 pulse 動畫吸引注意 | SLA 逾期無任何視覺區分 |
| Kanban 卡片左側使用 3px status stripe | Kanban 卡片無狀態指示 |
| 工單狀態變更時用動效過渡（200ms） | 狀態變更直接跳變無過渡 |
| 13 個工單狀態都有對應的視覺表達 | 遺漏某些工單狀態的視覺設計 |

### 1.3 地圖互動規則

| ✅ Do | ❌ Don't |
|-------|---------|
| 所有地圖互動支援鍵盤操作（Tab 切換 pin、Enter 開啟詳情） | 只能用滑鼠/觸控操作地圖 |
| 地圖 pin 搭配狀態色 + 數字/icon 雙重資訊 | pin 只有顏色沒有任何標示 |
| 地圖載入時顯示 skeleton + 載入進度 | 地圖區域空白等載入完成 |
| 地圖控制按鈕有 `shadow.map-control` 確保可見度 | 控制按鈕與地圖底色融合看不清 |
| 地圖 cluster 顯示數量標示 | cluster 沒有數量提示 |

### 1.4 Admin Panel 規則

| ✅ Do | ❌ Don't |
|-------|---------|
| Desktop-first 設計，向下適配 Tablet/Mobile | Mobile-first 再放大到 Desktop |
| Sidebar 收合/展開都能正常操作 | Sidebar 收合後功能遺失 |
| Table 在 mobile 轉為 Card List | Table 在 mobile 橫向捲動 |
| Form 在 Desktop 雙欄、Mobile 單欄 | Form 在所有尺寸都單欄 |
| Kanban 看板在 tablet 改為 2 欄 | Kanban 在 tablet 仍強制水平捲動 |
| Dashboard KPI 用 `text.kpi` token（36px/700/tabular-nums） | KPI 數字用一般 body 文字 |
| 使用 Recharts 的統一配色方案 | 圖表每個頁面不同配色 |

### 1.5 Technician PWA 規則

| ✅ Do | ❌ Don't |
|-------|---------|
| 所有觸控目標最小 44×44px | 觸控按鈕小於 44px |
| 關鍵資料離線快取（Service Worker） | 離線時整個 APP 不能用 |
| Bottom Sheet 三段式 snap（peek/half/full） | Bottom Sheet 只有開/關兩態 |
| 按鈕用 `active` / `touch` 回饋，不用 `hover` | 依賴 hover 互動（mobile 無 hover） |
| 下拉重新整理手勢更新工單資料 | 只有按鈕能觸發重新整理 |
| 離線時顯示離線 banner + 最後同步時間 | 離線時無任何提示 |
| GPS 權限拒絕時有 fallback UI（手動選地址） | GPS 被拒絕後功能死掉 |
| E-signature 畫布支援 touch + pressure | E-signature 只支援滑鼠 |
| 照片上傳支援相機直拍 + 相簿選取 | 只能從相簿選取 |

### 1.6 LINE Bot 規則

| ✅ Do | ❌ Don't |
|-------|---------|
| 使用 LINE 原生 UI 元件（Flex Message、Quick Reply） | 發送純文字模擬 UI |
| Quick Reply 最多 13 個選項 | Quick Reply 超過上限 |
| Flex Message 圖片使用 HTTPS URL | Flex Message 用 HTTP 圖片 |
| 對話流程最多 3 步完成主要操作 | 對話流程超過 5 步才能完成 |

---

## 2. 元件貢獻規範

### 2.1 新增元件流程

```
Step 1: 提案
  ├── 填寫「元件提案表」（見下方）
  ├── 確認不與現有 shadcn/ui 元件重複
  ├── 確認不與現有自定義元件重複
  └── 確認至少有 2 個以上使用場景

Step 2: 設計
  ├── 遵循命名規範（01_components_spec.md §6）
  ├── 完成所有 variants × states × sizes
  ├── Admin Panel + Tech PWA 兩端視覺（如適用）
  ├── 撰寫 Do / Don't
  └── 使用 Foundation tokens（不造新 token）

Step 3: 審核
  ├── Design review（設計負責人）
  ├── Dev review（工程確認 shadcn/ui 可擴展或需自建）
  ├── Accessibility check（對比度、鍵盤操作、screen reader）
  └── 效能 check（Tech PWA 離線可用？）

Step 4: 發布
  ├── 加入 Figma Component Library
  ├── 更新 Component Inventory
  ├── 撰寫 Change Log
  ├── 更新 Storybook（若有）
  └── 通知相關人員（Slack / LINE 群組）
```

### 2.2 元件提案表

```markdown
## 元件提案

**元件名稱**：
**類別**：（Action / Input / Data Display / Feedback / Navigation / Map / WorkOrder）
**適用平台**：（Admin / Tech PWA / Both）
**提案人**：
**日期**：
**關聯模組**：（M1–M13 哪些模組會使用）

### 為什麼需要？
（描述使用場景，至少 2 個）

### 與現有元件的差異
（為什麼不能用 shadcn/ui 現有元件解決？）

### 初步規格
- Variants：
- States：
- Sizes：
- 離線支援：（是/否，Tech PWA 必填）

### 參考
（Figma link / Screenshot / 競品參考）
```

### 2.3 Breaking Changes 規則

```
Breaking Change 定義：
  - 刪除元件
  - 刪除 variant / prop
  - 改變預設行為
  - 改變 token 名稱
  - 改變元件 API（prop 名稱、type）
  - 改變工單狀態色對應

Breaking Change 處理：
  1. 標記為 @deprecated（至少 1 個版本週期）
  2. 提供遷移指引
  3. 在 Change Log 中標記 [BREAKING]
  4. 主動通知受影響的模組 Owner（M1–M13）
  5. Admin Panel 和 Tech PWA 同時處理（不能只改一端）
```

---

## 3. Handoff Spec（交付規格）

### 3.1 通用交付清單

每個設計交付時必須包含：

```
✅ 基本規格
  □ 所有尺寸使用 Design Token（不是 pixel 值）
  □ 間距使用 Spacing Token
  □ 色彩使用 Color Token（含狀態語意色）
  □ 字型使用 Typography Token
  □ 圓角使用 Radius Token
  □ 陰影使用 Shadow Token

✅ 狀態覆蓋
  □ Default 狀態
  □ Hover 狀態（Admin only）
  □ Focus 狀態（鍵盤導航必須）
  □ Active / Pressed 狀態
  □ Disabled 狀態
  □ Loading 狀態
  □ Error 狀態
  □ Empty 狀態
  □ Success 狀態（若適用）
  □ Offline 狀態（Tech PWA 必須）

✅ RWD 行為（Admin Panel）
  □ Desktop 版面（>= 1024px）
  □ Tablet 版面（768px–1023px）
  □ Mobile 版面（< 768px）
  □ 斷點轉換行為描述

✅ 互動與動效
  □ 動效 trigger（什麼操作觸發）
  □ Duration + Easing（使用 Motion Token）
  □ 動效方向（from where to where）

✅ 文案
  □ 所有文案已定稿（繁體中文為主，英文術語保留）
  □ 錯誤訊息已定義
  □ 空狀態文案已定義
  □ Loading 文案已定義（若需要）
  □ 確認訊息已定義（刪除/取消等破壞性操作）

✅ 可及性
  □ 對比度檢查通過（AA 標準）
  □ Focus 順序已標示
  □ ARIA labels 已標示（icon-only buttons、images）
  □ 表單 error 關聯已標示（aria-describedby）
  □ 狀態資訊不只靠顏色傳達
```

### 3.2 工單相關交付額外清單

```
✅ 工單狀態
  □ 全部 13 個工單狀態都有視覺表達（參照 00_foundations §2.2.1）
  □ 每個狀態有 Badge（main + bg + text 三色組合）
  □ Kanban 卡片左側 status stripe 色彩正確
  □ 狀態轉換動效已定義

✅ SLA 倒數計時
  □ SLA 計時器正確顯示剩餘時間（格式：HH:MM:SS 或 X小時Y分鐘）
  □ SLA 三階段視覺已實現（綠 >50% / 琥珀 20%–50% / 紅 <20%）
  □ SLA 逾期 pulse 動畫已設計
  □ SLA 計時器 tabular-nums 對齊

✅ 地圖
  □ 地圖 pin 顏色與工單狀態色一致
  □ 地圖 cluster 有數量標示
  □ 地圖 pin 點擊 → 工單詳情卡正確
  □ 地圖載入 skeleton 已設計
  □ 地圖鍵盤操作可用
  □ 技師即時位置 pin 有區分（與工單 pin 不同形狀）

✅ Kanban 看板
  □ 拖曳預覽（ghost）已設計
  □ 拖曳中 shadow.kanban 效果正確
  □ 放置區高亮效果已設計
  □ 跨欄拖曳動效已定義
  □ 拖曳失敗回彈動效已定義
  □ 鍵盤拖曳（Space + Arrow）已設計

✅ 離線模式（Tech PWA 必須）
  □ 離線 banner 已設計（顯示最後同步時間）
  □ 離線時可瀏覽已快取的工單
  □ 離線時表單可填寫並暫存
  □ 重新連線後同步 UI 已設計
  □ 離線照片上傳佇列 UI 已設計

✅ E-Signature（電子簽名）
  □ 簽名畫布在 touch 裝置上流暢
  □ 畫布支援 undo / redo / clear
  □ 簽名預覽確認 UI 已設計
  □ 簽名儲存 loading 狀態已設計
```

### 3.3 Handoff 交付格式

```
推薦工具：
  - Figma Dev Mode（內建）
  - Figma MCP Server（AI 讀取 → 直接生成 shadcn/ui 程式碼）
  - Storybook（元件視覺驗證）

Figma 標註規範：
  - 使用 Auto Layout（不要用絕對定位）
  - 使用 Variables（不要用 hard-coded 值）
  - Frame 命名有語意（不要用 Frame 432）
  - 元件使用 Library instances（不要 detach）
  - Admin 和 Tech PWA 的頁面放在不同 Figma Page
  - 工單狀態使用 Component Set 的 variant property
```

---

## 4. Design QA Checklist

### 4.1 Admin Panel QA

| # | 檢查項 | 優先級 | 通過 |
|---|--------|--------|------|
| 1 | Desktop Chrome 視覺正確 | P0 | ☐ |
| 2 | Desktop Firefox 視覺正確 | P1 | ☐ |
| 3 | Desktop Safari 視覺正確 | P2 | ☐ |
| 4 | Tablet (768px) RWD 正確 — Sidebar 收合、Grid 8 欄 | P0 | ☐ |
| 5 | Mobile (< 768px) RWD 正確 — Sidebar 隱藏、單欄 | P1 | ☐ |
| 6 | Wide (1440px) Container 鎖寬正確 | P0 | ☐ |
| 7 | 所有 Token 使用正確（無 hard-coded 值） | P0 | ☐ |
| 8 | Dashboard KPI 數字使用 `text.kpi` + tabular-nums | P0 | ☐ |
| 9 | Kanban 拖曳：drag shadow 正確 | P0 | ☐ |
| 10 | Kanban 拖曳：drop zone 高亮正確 | P0 | ☐ |
| 11 | Kanban 拖曳：鍵盤操作可用 | P1 | ☐ |
| 12 | 工單狀態 Badge：13 態全部正確顯示 | P0 | ☐ |
| 13 | SLA 倒數：3 階段色彩正確 | P0 | ☐ |
| 14 | SLA 逾期 pulse 動畫正確 | P1 | ☐ |
| 15 | 地圖載入 + pin 渲染正確 | P0 | ☐ |
| 16 | 地圖鍵盤操作可用 | P1 | ☐ |
| 17 | Table 排序/篩選正常 | P0 | ☐ |
| 18 | Table mobile 轉 Card List 正確 | P1 | ☐ |
| 19 | Modal 在 mobile 改 Bottom Sheet 正確 | P1 | ☐ |
| 20 | 對比度 WCAG AA 通過（axe-core） | P0 | ☐ |
| 21 | Focus 順序合理（Tab 鍵導航） | P0 | ☐ |
| 22 | 鍵盤快捷鍵可用（若有定義） | P2 | ☐ |
| 23 | Recharts 圖表配色一致 | P1 | ☐ |
| 24 | Sidebar 展開/收合過渡動效正確 | P1 | ☐ |
| 25 | Empty/Error/Loading 狀態齊全 | P0 | ☐ |
| 26 | 效能：LCP < 2.5s | P0 | ☐ |
| 27 | 效能：CLS < 0.1 | P0 | ☐ |
| 28 | 效能：FID < 100ms | P1 | ☐ |

### 4.2 Technician PWA QA

| # | 檢查項 | 優先級 | 通過 |
|---|--------|--------|------|
| 1 | Mobile Safari (iOS) 視覺正確 | P0 | ☐ |
| 2 | Mobile Chrome (Android) 視覺正確 | P0 | ☐ |
| 3 | PWA 安裝後 Standalone 模式正確 | P0 | ☐ |
| 4 | Bottom Nav 正確顯示 + safe area padding | P0 | ☐ |
| 5 | 所有觸控目標 >= 44×44px | P0 | ☐ |
| 6 | 下拉重新整理手勢正常 | P0 | ☐ |
| 7 | Bottom Sheet 三段式 snap 正常 | P0 | ☐ |
| 8 | Bottom Sheet 拖曳手勢流暢 | P0 | ☐ |
| 9 | 地圖全螢幕顯示正確（扣除 Top Bar + Bottom Nav） | P0 | ☐ |
| 10 | 地圖 pin 點擊 → Bottom Sheet 工單詳情 | P0 | ☐ |
| 11 | GPS 權限允許：定位功能正常 | P0 | ☐ |
| 12 | GPS 權限拒絕：fallback UI 正常（手動選地址） | P0 | ☐ |
| 13 | 離線模式：離線 banner 顯示 | P0 | ☐ |
| 14 | 離線模式：已快取工單可瀏覽 | P0 | ☐ |
| 15 | 離線模式：表單可填寫並暫存 | P0 | ☐ |
| 16 | 離線模式：重新連線後資料同步 | P0 | ☐ |
| 17 | 離線模式：照片上傳佇列正確 | P1 | ☐ |
| 18 | E-Signature 觸控簽名流暢 | P0 | ☐ |
| 19 | E-Signature undo/redo/clear 正常 | P1 | ☐ |
| 20 | 照片上傳：相機直拍正常 | P0 | ☐ |
| 21 | 照片上傳：相簿選取正常 | P0 | ☐ |
| 22 | 工單狀態 Badge 13 態正確顯示 | P0 | ☐ |
| 23 | 工單狀態切換操作正確（滑動手勢） | P0 | ☐ |
| 24 | 推播通知接收正確 | P0 | ☐ |
| 25 | 不使用 hover-dependent 互動 | P0 | ☐ |
| 26 | safe-area-inset 在 iOS 劉海機正確 | P0 | ☐ |
| 27 | 深色模式預留（V2.0 不測但不能 break） | P2 | ☐ |
| 28 | 效能：TTI < 3.5s（含 Service Worker） | P0 | ☐ |

### 4.3 跨平台 QA

| # | 檢查項 | 優先級 | 通過 |
|---|--------|--------|------|
| 1 | 工單狀態在 Admin 和 Tech PWA 視覺一致 | P0 | ☐ |
| 2 | 工單狀態即時同步（WebSocket 推送後兩端 UI 更新） | P0 | ☐ |
| 3 | WebSocket 斷線 → 自動重連 → UI 恢復 | P0 | ☐ |
| 4 | WebSocket 重連後資料補齊（無遺漏狀態更新） | P0 | ☐ |
| 5 | Admin 拖曳更新狀態 → Tech PWA 即時反映 | P0 | ☐ |
| 6 | Tech PWA 更新工單 → Admin Kanban 即時反映 | P0 | ☐ |
| 7 | 同一工單被兩人同時操作 → 衝突 UI 處理 | P0 | ☐ |
| 8 | LINE Bot 發送通知 → Admin/Tech 有對應顯示 | P1 | ☐ |
| 9 | 時區一致（全部 Asia/Taipei） | P0 | ☐ |
| 10 | 工單編號格式一致（WO-YYYYMMDD-NNN） | P0 | ☐ |

### 4.4 新元件 QA

| # | 檢查項 | 通過 |
|---|--------|------|
| 1 | 所有 variants 完整 | ☐ |
| 2 | 所有 states 完整（default/hover/focus/active/disabled/loading/error） | ☐ |
| 3 | 所有 sizes 完整 | ☐ |
| 4 | Token 使用正確（無 hard-coded 值） | ☐ |
| 5 | Auto Layout 設定正確（拉伸不爆版） | ☐ |
| 6 | 命名符合規範（Category / Name / Variant） | ☐ |
| 7 | Accessibility 對比度 >= 4.5:1（一般文字） | ☐ |
| 8 | Focus state 有 visible focus ring（`shadow.focus-ring`） | ☐ |
| 9 | Do / Don't 已撰寫 | ☐ |
| 10 | 已加入 Component Library | ☐ |
| 11 | Admin + Tech PWA 兩端都有設計（若兩端都使用） | ☐ |
| 12 | 離線模式行為已定義（Tech PWA 元件必須） | ☐ |

---

## 5. Change Log

### 格式規範

```markdown
## [vX.Y.Z] - YYYY-MM-DD

### Added
- 新增 XXX 元件（描述功能、適用平台）

### Changed
- XXX: 具體描述變更內容

### Fixed
- XXX: 修正 XXX 問題

### Deprecated
- XXX → 請改用 YYY（將在 vN.0 移除）

### Breaking ⚠️
- [BREAKING] 具體描述
  - 遷移：步驟說明
  - 影響範圍：受影響的模組/頁面
  - 影響平台：Admin / Tech PWA / Both
```

### 變更紀錄

```markdown
## [v1.0.0] - 2026-04-21

### Added — 初始發布

#### Foundations（00_foundations_spec.md）
- 建立 Admin Panel Grid System（1440px/12col/24px gutter）
- 建立 Technician PWA Grid System（480px/1col/16px padding）
- 定義 Brand Colors：Primary #2563EB / Accent #F59E0B / Secondary #1E293B
- 定義 Work Order Status Colors 6 色系（Pending/Assigned/Active/Warning/Success/Danger）
- 建立 13 態工單狀態 → 色系對應表
- 定義 Typography 階梯（Inter + Noto Sans TC + JetBrains Mono）
- 新增 `text.kpi` token（36px/700/tabular-nums）
- 定義 Spacing Scale（4px 基數） + 平台專用 token
- 定義 Shadow System 含 `shadow.kanban` 和 `shadow.bottomsheet`
- 定義 Z-Index 11 層級（含 Kanban Drag / BottomSheet / Map Controls）
- 定義 Iconography（Lucide + 自定義 Lock/Battery/Connectivity/Technician 圖示）
- 定義 Motion System（含 SLA Pulse / Kanban Drag / BottomSheet Slide / Map Pin Pulse / Sidebar Toggle）
- 建立 Design Token 命名規範（含平台前綴）
- 定義 Token Mode（Light default + Dark V2.0 + 白標品牌 Yale/Gateman/Samsung）

#### Documentation（99_documentation_spec.md）
- 建立 Do / Don't 規範（全域 + 工單狀態 + 地圖 + Admin + Tech PWA + LINE Bot）
- 建立元件貢獻規範（提案 → 設計 → 審核 → 發布）
- 建立 Handoff Spec（通用 + 工單專用 + 地圖 + Kanban + 離線 + E-Signature）
- 建立 Design QA Checklist：Admin Panel 28 項 / Tech PWA 28 項 / 跨平台 10 項 / 新元件 12 項
- 定義 Version 策略（SemVer）
- 定義 Ownership（按模組 M1–M13 映射）
- 定義 Deprecation 流程
- 定義 Design ↔ Dev 同步機制（Token Studio + Style Dictionary + shadcn/ui + Figma MCP）
```

### 紀錄規則

```
1. 每次發布都寫 Change Log（不管多小）
2. 按 Added / Changed / Fixed / Deprecated / Breaking 分類
3. Breaking changes 必須有遷移指引 + 影響平台
4. 標注影響範圍（M1–M13 哪些模組受影響）
5. Change Log 保持時間倒序（最新在最上）
6. Admin 和 Tech PWA 的變更分別標注
```

---

## 6. Version 策略

### Semantic Versioning

```
v{MAJOR}.{MINOR}.{PATCH}

MAJOR：Breaking changes（token 改名、元件刪除、API 改變、狀態色對應改變）
MINOR：新增功能（新元件、新 variant、新 pattern、新模組 UI）
PATCH：修復（Bug fix、微調、文案修正、對比度修正）

範例：
  v1.0.0 → 初始發布（本次）
  v1.1.0 → 新增 DateRangePicker 元件
  v1.1.1 → 修正 DateRangePicker 在 Safari 的 bug
  v1.2.0 → 新增 M7 庫存管理頁面
  v2.0.0 → Dark Mode 上線 + Token 重構
  v2.1.0 → 新增白標品牌切換功能
```

### 發布節奏

```
PATCH：隨時（修復即發布）
MINOR：每 2 週一次（Sprint 結束時）
MAJOR：每季一次（需要遷移計畫，需通知所有模組 Owner）

里程碑：
  v1.0 — 基礎系統 + 核心模組 UI（M1–M6）
  v1.x — 擴展模組 UI（M7–M13）
  v2.0 — Dark Mode + 高對比模式 + 白標品牌
  v3.0 — 設計系統重構（若有需要）
```

---

## 7. Ownership & Review

### 7.1 角色定義

| 角色 | 職責 |
|------|------|
| Design System Lead | 整體方向、Breaking changes 審核、版本策略、跨平台一致性把關 |
| Admin Panel Design Owner | 負責 Admin Panel 元件與頁面設計 |
| Tech PWA Design Owner | 負責 Technician PWA 元件與頁面設計 |
| Token Owner | 維護 Foundation tokens、確保 Light/Dark/Brand mode 一致性 |
| Documentation Owner | 維護文件、Change Log、Do/Don't |
| Engineering Liaison | 確保設計 ↔ 工程同步（shadcn/ui 擴展、Tailwind config） |

### 7.2 模組 Ownership 映射

| 模組 | 名稱 | 主要平台 | Design Owner | 備註 |
|------|------|---------|--------------|------|
| M1 | 認證授權 | Both | Admin Owner + Tech Owner | 登入/SSO |
| M2 | 使用者管理 | Admin | Admin Owner | 管理員/技師帳號 |
| M3 | 智能客服（LINE Bot） | LINE Bot | Design System Lead | LINE 原生 UI |
| M4 | 工單管理 | Both | Admin Owner（Kanban）+ Tech Owner（Card List） | 核心模組 |
| M5 | 派工引擎 | Admin | Admin Owner | 地圖 + 演算法 UI |
| M6 | 即時通訊 | Both | Admin Owner + Tech Owner | WebSocket 聊天 |
| M7 | 庫存管理 | Admin | Admin Owner | 零件追蹤 |
| M8 | 知識庫 | Both | Admin Owner | FAQ/故障排除 |
| M9 | 報表分析 | Admin | Admin Owner | Recharts 圖表 |
| M10 | 計費帳務 | Admin | Admin Owner | 金額 tabular-nums |
| M11 | 通知中心 | Both | Admin Owner + Tech Owner | 推播/WebSocket |
| M12 | 系統設定 | Admin | Admin Owner | 設定頁 |
| M13 | 品牌白標 | Admin | Design System Lead | Token Mode 切換 |

### 7.3 Review 流程

```
新元件 / Breaking Change：
  → Component Owner 提案
  → Design System Lead 審核
  → Engineering Liaison 確認可行性（shadcn/ui 可擴展？需自建？）
  → Design QA（Admin + Tech PWA 兩端）
  → 發布

Minor Change（新 variant、修正）：
  → Component Owner 直接修改
  → Peer review（另一位 designer / 另一端 owner）
  → 發布

Patch（Bug fix）：
  → 直接修復
  → 記錄在 Change Log
  → 通知相關模組 Owner

跨平台變更（影響 Admin + Tech PWA）：
  → 兩端 Owner 共同討論
  → Design System Lead 審核
  → 同時發布（不能一端先上另一端後上）
```

---

## 8. Deprecation 流程

```
Step 1: 標記 @deprecated
  - 在 Figma 元件加上 [DEPRECATED] prefix
  - 在文件中標記 Deprecated 並說明替代方案
  - 在 Storybook 中標記 deprecated（若有）

Step 2: 通知
  - 在 Change Log 中記錄
  - 通知受影響的模組 Owner（依 M1–M13 映射表）
  - 在 Slack/LINE 開發群組發佈公告

Step 3: 緩衝期
  - 至少保留 1 個 MINOR 版本週期（2 週）
  - 大範圍影響的（如 Token 改名）：保留 1 個 MAJOR 版本週期（1 季）
  - 緩衝期內新舊並行可用

Step 4: 移除
  - 在下一個 MAJOR 版本中移除
  - 確認所有使用方已遷移
  - Admin Panel 和 Tech PWA 同時移除
```

---

## 9. Design ↔ Dev 同步機制

### 9.1 同步工具鏈

```
Token 同步：
  Figma Variables
    ↓ Tokens Studio (plugin) export
  tokens.json (W3C Design Token 格式)
    ↓ Style Dictionary transform
  ├── CSS Variables (globals.css)
  ├── Tailwind Config (tailwind.config.ts → theme.extend)
  └── TypeScript Constants (design-tokens.ts)
    ↓ Git PR → Code Review → Merge
  Admin Panel + Tech PWA 自動生效

元件同步：
  Figma Component（設計）
    ↓ Figma MCP Server
  AI 讀取設計結構
    ↓ Claude Code
  shadcn/ui Extended Component（程式碼）
    ↓ Storybook
  視覺驗證

Code Connect（Figma 官方）：
  Figma Node ↔ shadcn/ui Component 建立 mapping
    → 在 Figma Dev Mode 中直接顯示對應的 React 程式碼

技術堆疊同步：
  ├── Next.js 14 + React 19：shadcn/ui component library
  ├── Tailwind 3.4：theme.extend 引用 CSS Variables
  ├── TanStack Query：data fetching layer（不影響 UI token）
  ├── Zustand：client state（不影響 UI token）
  ├── Recharts：圖表使用 color token
  ├── @vis.gl/react-google-maps：地圖使用 pin color token
  └── @dnd-kit/core：Kanban 拖曳使用 shadow.kanban + z.kanban-drag
```

### 9.2 同步頻率

| 內容 | 頻率 | 方式 | 負責人 |
|------|------|------|--------|
| Token 變更 | 即時 | Token Studio auto-sync → Git PR | Token Owner |
| 新元件 | Sprint 結束（2 週） | PR + Code Review + Storybook | Component Owner |
| Pattern 更新 | 月度 | Design Review Meeting | Design System Lead |
| Breaking Changes | 季度 | Migration Plan + 全團隊通知 | Design System Lead |
| QA 驗收 | 每次部署前 | Checklist review | QA + Design Owner |

### 9.3 衝突解決

```
設計領先（設計好了，工程還沒做）：
  → 記錄在 Backlog，標記模組（M1–M13）與優先級
  → 工程在下個 Sprint 追上
  → 暫時提供 Figma Dev Mode 標註供工程參考

工程領先（工程改了 shadcn/ui，設計沒更新）：
  → Code-to-Canvas（Figma MCP）同步回 Figma
  → 設計審核後更新 Library
  → 記錄在 Change Log

Token 衝突（設計改了 token，工程用舊值）：
  → Token pipeline 自動偵測 diff（Style Dictionary build 失敗）
  → CI 警告 + PR review
  → Token Owner 仲裁

跨平台衝突（Admin 和 Tech PWA 設計不一致）：
  → Design System Lead 仲裁
  → 確認是否應該一致（有時兩端有合理差異，如 hover vs touch）
  → 決議後同時更新兩端
```

---

## Figma 結構建議

```
📁 99_Documentation（Figma Page）
├── 📄 Do / Don't
│   ├── 全域規則
│   ├── 工單狀態規則
│   ├── 地圖互動規則
│   ├── Admin Panel 規則
│   ├── Tech PWA 規則
│   ├── LINE Bot 規則
│   └── 元件級（每個自定義元件）
├── 📄 Contribution Guide
│   ├── 新增元件流程圖
│   ├── 提案表模板
│   └── Naming Convention 速查
├── 📄 Handoff Spec
│   ├── 通用 Handoff Checklist
│   ├── 工單專用 Handoff Checklist
│   ├── 標註範例（Admin + Tech PWA）
│   └── 離線模式交付規格
├── 📄 QA Checklist
│   ├── Admin Panel QA（28 項）
│   ├── Tech PWA QA（28 項）
│   ├── 跨平台 QA（10 項）
│   └── 新元件 QA（12 項）
├── 📄 Change Log
│   └── 按版本倒序排列
└── 📄 Governance
    ├── Ownership 表（角色 + M1–M13 映射）
    ├── Review 流程
    ├── Deprecation 流程
    └── Version 策略
```

---

**版本**：v1.0
**最後更新**：2026-04-21
**平台**：Admin Panel (Next.js 14) / Technician PWA / LINE Bot
**相關文件**：`00_foundations_spec.md`（基礎系統規格）、`01_components_spec.md`（元件規格）、`02_patterns_spec.md`（模式規格）
