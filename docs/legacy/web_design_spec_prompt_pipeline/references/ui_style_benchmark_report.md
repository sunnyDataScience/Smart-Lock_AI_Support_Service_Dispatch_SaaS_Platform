# 電子鎖智能客服與派工平台 — UI 風格參考報告

> **版本:** v1.0 | **日期:** 2026-04-21
> **關聯文件:** `global/01_sunny_brand_system.md`, `global/BASE_DESIGN_SYSTEM.md`, `docs/01-define/E3x--module-breakdown.md`
> **用途:** 提供國內外成功案例作為 Figma UI 設計的風格參考依據

---

## 一、五大設計風格分類

根據國內外成功案例，派工/工單 SaaS 的 UI 風格可歸納為五類：

### 風格 A：Card-Based KPI Dashboard（卡片式儀表板）

> 關鍵詞：資訊優先、數據驅動、SMB 友善

| 平台 | 市場 | 特色 |
|------|------|------|
| **Housecall Pro** | 美國 | 白底/藍色調，首頁即今日工單+營收+待處理報價，卡片式佈局 |
| **Jobber** | 加拿大 | 青綠色系，大卡片+圖標，日曆條+報價漏斗，學習曲線極低 |
| **Kintone (Cybozu)** | 日本 | 粉彩色、圓角、友善排版，每條記錄內建討論串+工作流 |
| **NewDate (揪棒)** | 台灣 | 乾淨極簡，工單卡片+狀態色標，LINE 整合通知 |

**適合場景**：Admin Panel 首頁 — 展示今日派工數、待處理工單、技師在線數等 KPI。

---

### 風格 B：Kanban Dispatch Board（看板式派工板）

> 關鍵詞：拖拉指派、狀態流轉、即時可視

| 平台 | 市場 | 特色 |
|------|------|------|
| **FieldPulse** | 美國 | 水平泳道（每排=一位技師），拖拉派工，藍灰色調 |
| **Zuper** | 美國 | 垂直看板欄（未指派→排程→進行中→完成），紫白色，SLA 倒數計時 |
| **Jobdone** | 台灣 | 跨公司 PMIS，角色切換視角，時間軸+甘特派工 |

**適合場景**：派工調度頁 — dispatch 模組的核心 UI，讓管理者一眼掌握全局。

---

### 風格 C：Map-Centric View（地圖中心視圖）

> 關鍵詞：地理定位、路線優化、IoT 設備分佈

| 平台 | 市場 | 特色 |
|------|------|------|
| **ServiceM8** | 澳洲 | 地圖即主 UI，點擊圖釘開工單卡，白綠色調，行動優先 |
| **MS Dynamics 365 FS** | 全球 | Bing Maps 嵌入，技師位置+車程半徑+IoT 警報疊加層 |
| **ThingsBoard** | 開源 | 600+ Widget，即時遙測+地圖疊加+告警表格，暗色主題 |
| **Tuya IoT** | 中國/全球 | 設備狀態面板+地圖+批次控制，支援明暗主題切換 |

**適合場景**：系統已整合 Google Maps API — 可做技師即時定位+客戶地點+路線規劃的 split view。

---

### 風格 D：Enterprise Gantt + Timeline（企業級甘特/時間軸）

> 關鍵詞：大量工單、多技師排程、高資訊密度

| 平台 | 市場 | 特色 |
|------|------|------|
| **Salesforce Field Service** | 全球 | 上半甘特時間軸+下半未指派工單列表，Lightning 設計系統 |
| **SAP FSM** | 全球 | Fiori 設計語言，甘特+列表混合，水平藍色調 |
| **IFS PSO** | 全球 | 全甘特拖拉調整，支撐 10,000+ 工單，深色側欄+白畫布 |

**適合場景**：V2.0 規模化後，若單日派工量超過 50 單，可考慮此模式。MVP 階段偏重。

---

### 風格 E：Smart Lock / IoT Device Dashboard（智慧鎖設備面板）

> 關鍵詞：設備狀態、電量監控、遠端操作、活動日誌

| 平台 | 市場 | 特色 |
|------|------|------|
| **TTLock** | 中國/全球 | 藍色主色，物業管理多門鎖視圖，租戶權限管理+活動日誌+遠端密碼派發 |
| **Kaa IoT Cloud** | 全球 | 模板驅動，內建智慧鎖方案（電量/連線/事件時間軸元件） |
| **RON Design Lab** | 設計案例 | 漸層品牌+玻璃擬態卡片+生物辨識微互動，行動優先大觸控區 |

**適合場景**：系統核心是電子鎖 — 可在工單詳情中嵌入鎖具狀態面板（電量、連線、操作紀錄）。

---

## 二、2024-2026 設計趨勢

| 趨勢 | 說明 | 本系統如何應用 |
|------|------|--------------|
| **AI 輔助排程可視化** | AI 建議以紫色/特殊 Badge 標記，非隱藏在設定中 | LLM Gateway 建議可直接嵌入派工板 |
| **角色預設儀表板** | 不同角色登入看到不同首頁 | Admin/Technician/Consumer 三端本身就是分離的 |
| **對話式 UI** | Chat-based 建單與狀態查詢 | 已有 LINE Bot，Admin Panel 可加內部 chatbot |
| **即時設備狀態面板** | 電量/連線/告警的即時顯示 | 直接對應電子鎖設備監控需求 |
| **Dark Mode** | ServiceTitan、Zuper 已支援 | 技師夜間作業友善 |
| **微互動** | Kanban 卡片狀態轉換動畫 | 提升派工板操作手感 |

---

## 三、對照桑尼品牌系統的風格建議

根據 `global/01_sunny_brand_system.md` 設計原則：

| 桑尼設計原則 | 最匹配的風格 | 推薦參考 |
|-------------|-------------|---------|
| **資訊優先**（砍動畫保可讀性） | 風格 A + B 混合 | Housecall Pro + Zuper |
| **學習友善**（低認知負擔） | 風格 A 卡片式 | Jobber（業界最低學習曲線） |
| **數據驅動**（用數據而非形容詞） | 風格 A KPI 卡 | ServiceTitan 的 KPI Dashboard |
| **鼓勵探索**（空狀態引導行動） | Jobber 的空狀態設計 | 「還沒有派工任務，立即建立」 |

### 推薦組合方案

```
Admin Panel
├── 首頁 → 風格 A（KPI 卡片儀表板）
├── 派工板 → 風格 B（Kanban 看板）+ 風格 C（地圖 toggle）
├── 工單詳情 → 風格 E（嵌入鎖具狀態面板）
└── 報表 → 風格 D（時間軸/甘特，V2.0）

Technician PWA
├── 首頁 → 風格 C（地圖優先，ServiceM8 模式）
├── 工單卡 → 風格 A（大卡片+滑動完成）
└── 鎖具操作 → 風格 E（TTLock 風格設備面板）

Consumer LINE Bot
└── 已有 LINE 原生 UI，補 Quick Reply + Flex Message
```

---

## 四、台灣 / 亞太市場補充參考

| 平台 | 市場 | 類型 | 設計特色 |
|------|------|------|---------|
| **Ragic** | 台灣 | No-code 雲端資料庫 | 列表/表單雙視圖，白底藍色調，使用者自建工單流程 |
| **Jobdone (揪棒)** | 台灣 | 營建/設備維修 PMIS | 跨組織協作，時間軸派工，角色切換視角 |
| **NewDate** | 台灣 | 清潔/維修/物管派工 | 極簡風，LINE 整合，卡片式工單+狀態色標 |
| **孟華科技** | 台灣 | 派工維修管理 | 多維度統計儀表板，維修 KPI 視覺化 |
| **鼎新電腦** | 台灣 | ERP 大廠 | 傳統企業 UI，功能密集導航，近年雲端化轉型 |
| **Kintone (Cybozu)** | 日本 | No-code 工作平台 | 粉彩色+圓角+友善排版，記錄內討論串+工作流 |
| **Tuya IoT** | 中國/全球 | 智慧設備管理 | 即時設備面板+地圖+批次控制，明暗主題 |
| **TTLock** | 中國/全球 | 智慧鎖管理 | 物業多鎖視圖，租戶權限+活動日誌+遠端密碼 |

---

## 五、Figma / 設計資源推薦

| 資源 | 用途 |
|------|------|
| [AiDEA Smart SaaS Dashboard UI Kit (Figma Community)](https://www.figma.com/community/file/1532723729743223601) | SaaS Dashboard 基礎元件 |
| Figma Community 搜 **"Kanban Board UI"** | 派工看板拖拉元件 |
| Figma Community 搜 **"CRM Dashboard"** | 客戶/工單管理模式 |
| [SaaSFrame](https://www.saasframe.io/categories/dashboard) | 166 個真實 SaaS Dashboard 截圖參考 |
| Dribbble 搜 **"smart-lock"**、**"field-service"**、**"iot-dashboard"** | 視覺靈感 |
| [Musemind Agency (Behance)](https://www.behance.net/musemindagency) | 企業級但乾淨的 Dashboard 佈局 |
| [RON Design Lab SmartLock Case](https://rondesignlab.com/cases/smartlock-branding-smart-home-ux-ui-design) | 智慧鎖品牌+UI 設計案例 |
| [ThingsBoard](https://thingsboard.io/) | 開源 IoT Dashboard 元件參考 |
| [Kaa IoT Dashboards](https://www.kaaiot.com/iot-dashboards) | IoT 智慧鎖模板參考 |
| [2026 SaaS UI Trends](https://www.saasui.design/blog/7-saas-ui-design-trends-2026) | 設計趨勢文章 |

---

## 六、下一步行動建議

1. **確認風格方向** — 從五大風格中選定主風格組合（建議：A+B+E）
2. **建立 Design Token** — 基於 `BASE_DESIGN_SYSTEM.md` 模板，填入派工平台專用的色彩/排版/元件 Token
3. **Figma 原型** — 使用 AiDEA UI Kit 作為基底，搭配 Kanban + Map 元件組裝 Admin Panel 原型
4. **Pencil 快速迭代** — 用 Pencil + Claude Code 快速生成各頁面的 React 元件
5. **Design Review** — 對照本報告的參考案例進行設計走查
