---
status: superseded
superseded_by: "[[00-vision/project-brief-and-prd]]"
---

# (Superseded) 產品需求文件 (PRD) - 電子鎖智能客服與派工平台

> **This document has been superseded.** The canonical PRD is now at [[00-vision/project-brief-and-prd]] (v1.1).
> This file is kept for reference only. Do not update it.

---

**文件版本:** `v1.0`
**日期:** `2026-03-31`
**專案代號:** `SmartLock-SaaS`
**狀態:** Superseded
**SSOT:** [[00-vision/project-brief-and-prd]]

---

## 1. 產品定位 (Product Positioning)

打造一個整合型智慧平台，透過 AI 與自動化技術，徹底革新電子鎖售後服務與技師派工流程，將資深技師的專家知識系統化、可傳承，並消除從報修到結案的所有人工瓶頸。

---

## 2. 商業背景與痛點 (Business Background & Pain Points)

| 痛點 | 現況描述 | 影響程度 |
|:---|:---|:---|
| **知識不可擴展** | 客服能力完全依賴資深技師個人經驗，問題透過 LINE 文字、圖片、影片等非結構化方式湧入，知識無法保存、檢索與傳承，新進人員需數月才能上手 | 高 |
| **診斷效率低落** | 每次報修需人工逐步詢問品牌、型號、故障現象，再以腦中或紙本比對可能原因，重複性極高，品質因人而異 | 高 |
| **派工流程碎片化** | LINE 接到報修 → 紙本記錄 → 電話/LINE 聯繫技師 → Excel 記帳 → 銀行轉帳，全程手動，無法追蹤、無法稽核 | 高 |
| **帳務不透明** | 技師墊款、公司預付款項、完工結算等資金流向混亂，月底對帳耗時且爭議頻繁 | 中高 |
| **缺乏數據洞察** | 無法統計常見故障類型、地區分布、技師績效、客戶滿意度等關鍵營運數據，決策完全憑直覺 | 中 |

---

## 3. 目標使用者 (Target Users)

| 使用者類型 | 身份 | 互動介面 | 核心需求 |
|:---|:---|:---|:---|
| **消費者 (Consumer)** | 電子鎖終端使用者 | LINE Bot | 7x24 報修諮詢、自助排障、案件進度查詢 |
| **技師 (Technician)** | 簽約維修技師 | Web App (Next.js PWA) | 案件池瀏覽、一鍵接單、完工回報、帳務管理 |
| **審核員 (Reviewer)** | 知識庫審核人員 | Admin Panel (受限) | 對話紀錄唯讀、知識庫唯讀、SOP 審核（核准/退回） |
| **管理員 (Admin)** | 甲方營運人員 / 客服主管 | Admin Panel | 知識庫管理、對話監控、派工監控、帳務審核、客訴處理、營運儀表板 |

> **V2.0+ 預留角色**: Brand OEM（品牌原廠資料上傳）、Distributor（經銷商區域管理）、Community Manager（社區/建商批量管理）。RBAC 架構支援動態新增角色。

---

## 4. 消費者旅程 (Consumer Journey)

```
消費者在 LINE 描述電子鎖問題
    ↓
AI 智能客服意圖辨識（報修 / 諮詢 / 投訴 / 其他）
    ↓
多輪對話蒐集資訊 → 自動生成 ProblemCard（品牌/型號/症狀/位置）
    ↓
消費者確認 ProblemCard 內容（LINE Flex Message）
    ↓
三層解決引擎啟動：
  L1: 案例庫向量搜尋（相似度 >= 0.85）→ 命中則回覆解決方案
  L2: RAG + Gemini 2.5 Flash 推理 → 生成解決建議
  L3: 轉人工客服 / 建立派工單
    ↓
[V2.0] 智慧派工引擎自動匹配技師（技能 x 地區 x 評分 x 可用時段）
    ↓
技師接單 → 到場維修 → 提交完工報告（含照片 + 材料清單）
    ↓
[V2.0] 帳務結算（自動對帳、月結報表、記帳憑證）
```

---

## 5. 核心模組 (Core Modules)

### V1.0 - AI 智能客服系統 (W1-W17)

| 子模組 | 說明 |
|:---|:---|
| **LINE Bot 接入** | Webhook 接收、簽章驗證、事件路由、Rich Menu、Flex Message |
| **對話管理** | 對話狀態機 (Idle → Collecting → Resolving → Resolved)、多輪上下文、Session 超時 30min |
| **問題診斷 (ProblemCard)** | 從自然語言提取結構化問題卡（品牌/型號/症狀/位置）、AI 輔助欄位推斷、缺失欄位追問 |
| **三層解決引擎** | L1 pgvector 語意搜尋 → L2 RAG + Gemini 推理 → L3 轉人工/建工單 |
| **知識庫管理** | 案例 CRUD、PDF 手冊上傳 → 分段 → Embedding、向量搜尋、增量更新 |
| **SOP 自動生成** | 監聽成功解決事件 → 分析對話 → AI 草擬 SOP → 提交審核佇列 |

**額外子模組：**

| 子模組 | 說明 |
|:---|:---|
| **安全防護** | Prompt Injection 攔截 (>= 95%)、內容過濾 (誤攔率 < 1%)、Output Guardrail |
| **情緒分流** | 負面情緒偵測 (識別率 >= 90%)、優先回應協議、管理員即時通知 |
| **Admin Panel V1.0** | 知識庫審核、對話紀錄查詢、SOP 上架、基礎營運儀表板 (Next.js 14 + shadcn/ui) |
| **LLM 閘道** | 統一 LLM 呼叫入口、Prompt 模板管理、Token 追蹤、Retry/Fallback |

### Agent Harness 框架與前端架構決策

| 項目 | 說明 |
|:---|:---|
| **Agent Harness 8 層框架** | AI 運行時基礎設施，位於 `harness/` 目錄。8 層架構：L1 Task Decomposition、L2 Context Assembly、L3 Governance Gate、L4 Feedback Loop、L5 Safety Boundary、L6 Observability Tap、L7 Human Escalation、L8 Entropy Tracker。Phase 0 骨架完成（全部 disabled），由 `config.toml` 14 區段集中驅動所有行為 |
| **前端統一決策** | Next.js 14 統一前端技術棧：V1.0 Admin Panel（取代原 Jinja2/HTMX 方案）+ V2.0 技師 Web App（PWA），共用 shadcn/ui + Tailwind CSS 元件庫 |
| **ProblemCard 領域無關設計** | 核心欄位（id, conversation_id, status, completeness_score, sentiment_label）保持領域無關；電子鎖特有欄位（brand, model, symptom, door_status 等）遷入 `domain_attributes` JSONB 欄位，為多垂直領域擴展預留架構彈性 |

### V2.0 - 技師派工與帳務平台 (W18-W31)

| 子模組 | 說明 |
|:---|:---|
| **智慧派工** | 技師匹配（技能 x 地區 x 評分 x 可用時段）、工單生命週期 (Created → Assigned → InProgress → Completed)、推播通知 |
| **報價引擎** | 計價規則（品牌 x 鎖型 x 難度）、自動報價、特殊加價（夜間/假日/遠程/高樓） |
| **帳務結算** | 墊款追蹤、月結報表、發票/請款單生成、技師佣金計算、記帳憑證 |
| **技師工作台** | 案件池、一鍵接單、進度回報、導航整合、個人帳務 (Next.js 14 + PWA) |
| **增強管理後台** | 派工監控儀表板、技師管理、帳務審核、案件全生命週期追蹤 (Next.js 14 + shadcn/ui) |
| **CRM 客訴管理** | 客訴生命週期管理、消費者滿意度調查（完工後 LINE 問卷）、技師績效評分模型、消費者統一歷史視圖 |
| **異常流程處理** | 派工異常（拒單/取消/改約）、現場異常（加價/材料短缺/無法維修）、財務異常（報價爭議/退費） |

---

## 6. 關鍵績效指標 (KPIs)

| 指標 | 目標值 | 量測方式 |
|:---|:---|:---|
| **AI 回答準確率** | >= 80% | 50 題標準測試集（甲方真實案例） |
| **AI 首次回應時間** | < 5 秒 | 系統日誌統計 |
| **自助解決率** | >= 60%（V1.0 上線 3 個月後） | 對話日誌分析（無需轉人工即解決） |
| **同時在線使用者** | V1.0 >= 50 / V2.0 >= 100 | 壓力測試 (k6 / Locust) |
| **系統可用性 (Uptime)** | V1.0 >= 95% / V2.0 >= 99.5%（月度） | 監控系統 |
| **案例庫搜尋延遲** | < 3 秒 | 系統日誌 |
| **RAG 回覆延遲** | < 8 秒 | 系統日誌 |
| **負面情緒識別率** | >= 90% | 測試集驗證 |
| **Prompt Injection 攔截率** | >= 95% | 安全測試集 |

---

## 7. 成功指標 (Success Metrics)

| 指標類型 | 指標描述 | 目標值 |
|:---|:---|:---|
| **主要指標** | AI 客服回答準確率 | >= 80% |
| **主要指標** | 系統同時服務使用者數 | V1.0 >= 50 / V2.0 >= 100 |
| **主要指標** | E2E 流程可走通（報修 → AI 診斷 → 派工 → 完工 → 結算） | End-to-End 測試通過 |
| **次要指標** | 上線後穩定運行天數 | >= 7 天（uptime, error rate） |
| **次要指標** | AI 首次回應時間 | < 5 秒 |
| **次要指標** | 自助解決率 | >= 60% |

---

## 8. 交付時程 (Release Roadmap)

### V1.0 - AI 智能客服系統 (W1-W17, 共 17 週)

| 階段 | 週次 | 說明 |
|:---|:---|:---|
| Phase 0 | W1-W2 | 需求確認與架構設計 |
| Phase 1 | W3-W7 | AI 客服 MVP（LINE Bot + 對話管理 + ProblemCard + L1 解決引擎） |
| Phase 2 | W8-W12 | 知識庫完善與三層引擎（L2 RAG + L3 轉接 + SOP 自動生成 + Admin Panel） |
| Phase 3 | W13-W15 | V1.0 UAT 使用者驗收測試 |
| Phase 4 | W16-W17 | V1.0 正式部署上線 |

### V2.0 - 技師派工與帳務平台 (W18-W31, 共 14 週)

| 階段 | 週次 | 說明 |
|:---|:---|:---|
| Phase 5 | W18-W19 | V2.0 需求分析與系統設計 |
| Phase 6 | W20-W24 | 派工系統 MVP（技師工作台 + 智慧派工 + 報價引擎） |
| Phase 7 | W25-W29 | 帳務系統與整合（帳務結算 + 增強 Admin Panel + 系統整合） |
| Phase 8 | W30-W31 | V2.0 UAT 與正式上線 |

---

## 9. 範圍外項目 (Out of Scope)

| 項目 | 排除原因 |
|:---|:---|
| 多語言支援 | V1.0/V2.0 僅支援繁體中文 |
| 消費者原生 App | 消費者端僅透過 LINE Bot 互動 |
| 線上金流整合 | 付款由線下處理 |
| 技師 GPS 即時追蹤 | 僅記錄出發/到達時間點 |
| 庫存管理系統 | 技師自行管理材料 |
| AI 影像辨識 | 合約 SOW 2.1(4) 明確排除，圖片僅作附件存儲 |
| 多租戶 (Multi-tenancy) | V1.0/V2.0 為單一甲方專用 |
| 語音對話 | 僅支援文字與圖片 |

---

*本文件為快速參考用途之濃縮版 PRD，完整需求請參閱 `docs/02_project_brief_and_prd.md`。*
