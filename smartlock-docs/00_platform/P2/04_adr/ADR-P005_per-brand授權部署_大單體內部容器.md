# ADR-P005: per-brand 授權部署（大單體 + 內部容器化）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state / 理想態 v2）|
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）|
| 關聯缺口 | G-01（雲/本機拓撲不對稱）|

## 1. 背景與問題

現況 G-01：本機 5-bundle 多 surface，雲端只 3 個 Cloud Run（api `API_SURFACE=all` 單體），拓撲不對稱且未定義為刻意設計。業主澄清商業模式：**雲端部署、大單體架構、內部服務容器化；品牌商需我方授權（License）才能部署並綁定自己的 LINE 與設定**。

## 2. 考量的選項

- **選項 A：單一多租戶雲端部署（邏輯隔離 RLS）** — 資源共用，但與現況「一品牌一庫」物理隔離相悖，資料主權弱。
- **選項 B：per-brand 獨立部署（物理隔離）** — 每品牌一套授權部署，資料/LINE 隔離，對齊現況 CR-0110。
- **選項 C：混合（共用控制面 + per-brand 資料面）**。

## 3. 決策

採 **選項 B（含 C 的集中共用元件分層）**：

1. **部署單元 = per-brand bundle（可完整獨立部署）**：每品牌一套授權部署（**內部容器**：web(**僅品牌營運 dispatch**) / api / agent / 品牌 DB / Redis / MCP-RAG），**物理隔離**，對齊「一品牌一庫」（CR-0110）。**師傅端不在此 bundle**（屬技師平台 [[ADR-P004]]），故品牌不依賴任何共享元件即可獨立上線。
2. **大單體 + 內部容器**：單一部署邏輯內含容器化的內部服務，非分散式微服務網。
3. **License 開通 → provisioning**：品牌經 Casdoor subscription 授權（[[ADR-P003]]）→ provisioning 流程建置 bundle + 建庫 + **綁定該品牌 LINE channel 與設定**。
4. **集中共用元件（非 per-brand）**：Casdoor、SigNoz、**technician-platform（含獨立師傅 web，[[ADR-P004]]）**、平台維運 console、共享訊息 bus（Kafka [[ADR-P007]]）、**knowledge-refinery（License 附加系統，含獨立 web，[[ADR-P001]]）** 為**跨品牌集中部署**，各 per-brand bundle 串接之。**「開通哪些附加模組」由 License 決定**，整體架構圍繞此微調。

## 4. 後果

**正面**：物理隔離 → 資料主權/隔離/授權可控；符合品牌授權商業模式；集中元件避免每品牌重複。
**負面/風險**：per-brand 部署運維擴散（需 provisioning 自動化與升級策略）；集中元件成跨品牌單點需 HA；per-brand 與集中元件的網路/認證邊界需設計。
**影響範圍**：部署拓撲全面重畫（本機/雲端對齊）；`api/P2/14` 部署指南重寫；新增 provisioning 流程文件。
**重新評估觸發**：品牌數成長到 per-brand 運維不可持續 → 評估共用控制面 + namespace 隔離。

## 5. 執行計畫

1. 定義 per-brand bundle 組成與 provisioning 流程（License→部署→建庫→綁 LINE→健康檢查）。
2. 分層：集中共用元件（Casdoor/SigNoz/technician-platform/bus/refinery）vs per-brand 元件（api/agent/web/db）。
3. 雲端拓撲對齊（現況單體 → 目標 per-brand，或明確定義過渡）。
4. provisioning 自動化（IaC / 腳本）+ 升級/回滾策略。

## 6. 選用影響區段

- **架構/部署**：per-brand 物理隔離 + 集中共用元件雙層。
- **商業**：License 授權即部署開通閘門。
- **安全**：品牌資料/LINE 物理隔離；集中元件跨租戶邊界。
- **資料**：一品牌一庫（品牌庫）+ 集中技師/平台庫。
