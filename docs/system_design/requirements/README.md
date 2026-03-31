# 電子鎖智能客服與派工平台 — 開發前需求資料收集中心

> **最後更新:** 2026-03-31
> **管理者:** 產品經理
> **專案名稱:** Smart Lock AI Support & Service Dispatch SaaS Platform

---

## 這個資料夾是做什麼的

這裡存放所有**開發前**需要由各對口窗口提供的資料。
每個子資料夾對應一個主題，裡面的 `README.md` 會告訴你：
- 要準備什麼
- 為什麼需要
- 格式範本
- 截止日
- 給誰

所有資料圍繞**電子鎖 AI 智能客服**與**技師派工**兩大核心功能。

---

## 各資料夾一覽

| 資料夾 | 對口窗口 | 最晚交付日 | 狀態 |
| :--- | :--- | :--- | :--- |
| `01_domain_knowledge/` | 甲方資深技師 | Phase 1 啟動前 2 週 | 待收集 |
| `02_knowledge_base_seed_data/` | 甲方 + PM | Phase 1 W3 | 待收集 |
| `03_resolution_rules/` | 甲方 + PM | Phase 1 W4 | 待收集 |
| `04_problem_diagnosis_patterns/` | 甲方資深技師 | Phase 2 W3 | 待收集 |
| `05_technician_onboarding/` | 甲方營運 | Phase 2 W3 | 待收集 |
| `06_line_bot_templates/` | IT / 開發團隊 | Phase 1 W4 | 待收集 |
| `07_platform_accounts/` | IT / 開發團隊 | Phase 1 W4 | 待收集 |
| `08_business_metrics/` | 甲方營運 | Phase 2 W3 | 待收集 |

---

## 按窗口查看任務

### 甲方資深技師
- [ ] `01_domain_knowledge/` — 電子鎖產品目錄、客戶分群、業務術語表、現行維修流程
- [ ] `04_problem_diagnosis_patterns/` — 常見故障模式、診斷決策樹、品牌特殊問題、季節性故障

### 甲方 + PM
- [ ] `02_knowledge_base_seed_data/` — 歷史維修案例、產品手冊 PDF、FAQ 種子資料、案例分類體系
- [ ] `03_resolution_rules/` — L1 案例匹配規則、L2 RAG 管線規則、L3 轉派規則、信心度評分

### 甲方營運
- [ ] `05_technician_onboarding/` — 技師技能矩陣、服務區域劃分、Web App 操作指南、品質標準
- [ ] `08_business_metrics/` — 現況績效基準、目標 KPI、告警閾值、儀表板指標

### IT / 開發團隊
- [ ] `06_line_bot_templates/` — 對話範本、Flex Message 模板、Rich Menu 設計、錯誤回覆
- [ ] `07_platform_accounts/` — LINE OA 帳號、Google Cloud 設定、網域與 SSL、開發基礎設施

---

## 使用方式

1. 找到你負責的資料夾
2. 打開 `README.md` 看說明
3. 準備好的檔案直接放進該資料夾
4. 通知 PM 已備妥
5. PM 會安排確認會議
