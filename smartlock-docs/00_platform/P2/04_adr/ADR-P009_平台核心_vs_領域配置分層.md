# ADR-P009: 平台核心 vs 領域配置分層（TRIZ 按系統層級分離）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state 理想態 v2）|
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）· 奠基性 |
| 關聯 | `06_platformization_strategy` §4-5 · [[ADR-P008]] · [[ADR-P010]] · [[ADR-P011]] |

## 1. 背景與問題

跨產業（同需工單 + 客服）是**近期真實需求**。核心矛盾（TRIZ 物理矛盾）：平台須**同時通用**（跨產業重用）**又專用**（藍領垂直做深）。業主擔心抽象化犧牲垂直整合。

## 2. 考量的選項

- **A：每產業 fork code** — 貼合但變 N 份分岔，違反重用。
- **B：一套超集寫死所有產業** — 複雜臃腫，垂直都做不深。
- **C：核心通用 + 領域配置分層**（TRIZ 按系統層級分離）——垂直深度活在**可組合配置**，非 fork code。

## 3. 決策

採 **選項 C**。以 TRIZ「按系統層級分離」化解矛盾：**核心層通用、配置層專用，兩層不在同一處競爭。**

### 3.1 可重用平台核心（FDE 永不動）
工單引擎（狀態機執行器）· 客服 agent runtime（LockCore）· 金流/對帳/結算軌 · 身分/RBAC/租戶/License（Casdoor）· 事件/即時骨幹（Kafka/Redis）· 可觀測性（SigNoz+OPIK）· 技師共享池 · 共用 UI 元件庫 · provisioning。

### 3.2 領域配置層（FDE 每產業 4 配置面）
| # | 配置面 | 承載 |
|---|---|---|
| ① | 診斷系統 | 知識核心 + model 編排（[[ADR-P008]]）+ api 調用效率 |
| ② | 知識精煉 | 產業事實語料 + skill 行為（[[ADR-P001]]/[[ADR-004]]）|
| ③ | 工單/金流 flow | flow DSL + 積木（[[ADR-P010]]）|
| ④ | 後台 UI 組裝 | 共用元件庫組裝畫面 + 自訂 panel |

### 3.3 三大地基（工單維運後台通用化）
- **領域模型**：通用核心欄 + JSONB 屬性 + `field_metadata`（產業欄位語義驅動表單/清單/驗證）。
- **後台呈現**：**分兩層**——欄位層配置驅動（`DynamicForm`/`DynamicTable` 吃 metadata）、畫面層元件組裝（+ 自訂 panel）。
- **產業配置打包**：**Vertical Pack 產業包**（`field_metadata` + flow DSL + catalog + knowledge + ui_composition + blocks，版本化）；品牌（租戶）從產業包實例化。

## 4. 後果

**正面**：新產業 = 裝一個 Vertical Pack + 輕組裝，核心零改碼 → 重用與垂直深度**不再 trade-off**（深度活在深積木裡）。
**負面/風險**：抽象化前置成本；配置層若做淺會退回「通用但不好用」→ 靠深度藍領積木 + 逃生艙緩解；FDE 每產業多一件「UI 組裝」（4 配置面）。
**影響範圍**：工單/金流/UI 全面重構為核心+配置分層；`07_workorder_platform_design.md` SDS 細化。
**重新評估觸發**：某產業需求根本超出核心原語 → 核心層擴充（而非 fork）。

## 5. 執行計畫
1. 抽取通用工單核心（core 欄 + JSONB + field_metadata），鎖領域欄位入配置。
2. 建共用 UI 元件庫（DynamicForm/Table/WorkOrderBoard/…）。
3. 定義 Vertical Pack manifest；以 locksmith 為首個產業包。
4. 細部設計於 SDS（`07`）。

## 6. 選用影響區段
- **架構**：核心 vs 配置雙層（TRIZ 按系統層級分離）。
- **資料**：通用核心 + JSONB + field_metadata。
- **配置/部署**：Vertical Pack 版本化、品牌實例化。
