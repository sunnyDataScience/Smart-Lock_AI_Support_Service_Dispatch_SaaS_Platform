# Smart Lock 平台 — drawio 架構圖生成 prompt 集

> 對象:**Smart Lock AI 客服與派工 SaaS 平台**(正典文件 `smartlock-docs/enterprise/` 00–27)。
> 用途:每個子資料夾內的 `prompt.md` 是**自然語言生成 prompt**,可直接貼給 drawio AI(Help →「Generate diagram」/ draw.io Copilot)或當人工繪製規格;**實際產出以 `.drawio` 為準**(由 `_build_drawio.py` 程式化生成)。
> 讀法:**top-down**——從 `00_總覽` 的商業模式開始,逐層往下到 `04_流程圖`。

---

## 已生成的 .drawio(可直接匯入)

> 由 `_build_drawio.py` 依本規範自動產出;修改後執行 `python3 _build_drawio.py` 重生。**絕不手改 .drawio**(重生會覆蓋)。

- **`smartlock-platform-architecture.drawio`** — 單檔 **14 分頁**,一次匯入全部。分頁依**閱讀序**排列:主 deck(11 張關鍵-flow)在前、附錄(3 張戰略/能力)在後。
- **各子資料夾同名單張檔**(如 `03_執行層/03-1_container.drawio`)——需要單張時開這個。

**主 deck 閱讀序**:`00-1 商業心智 → 00-2 Context → 01-1 部署三分層 → 03-1 Container 主錨 → 03-2 agent 元件 → 03-3 api 元件 → 04-3 Sequence(工單全程)→ 03-4 State Machines → 04-2 跨系統資料流 → 04-4 知識精煉閉環 → 05-1 共用核心 Kernel`。
**附錄**:`A=01-2 平台核心 vs Vertical Pack(階段二)· B=02-1 知識能力分層 · C=02-2 AI 邊界紅線`。

版面檢查:`python3 _analyze_layout.py -v`(量測連線交叉+穿越節點)。

## 子資料夾(繪製順序)

| # | 子資料夾 | 圖(共 14 張)| 對應正典文件 |
|---|---|---|---|
| 00 | `00_總覽/` | 商業模式心智模型、System Context (C4 L1) | 00_Product_Strategy · 02_BRD §2/§5 · 12_SAD |
| 01 | `01_平台層/` | 部署三分層(bundle×共用×License 附加);**核心 vs Pack → 附錄A(階段二)** | 12_SAD §2 · ADR-001/002 |
| 02 | `02_能力資產層/` | **知識能力分層→附錄B、AI 邊界紅線→附錄C** | ADR-008/009/010/025 · 02_BRD §6.1 |
| 03 | `03_執行層/` | Container 主錨 (C4 L2)、agent 元件、api 元件、State Machines | 12_SAD · 15_SDS §4-§6 |
| 04 | `04_流程圖/` | 跨系統資料流 DAG、Sequence(工單全程)、知識精煉閉環 | 00_platform/P2/09 · 02_BRD §5.5/§5.6 |
| 05 | `05_共用核心/` | 平台共用核心 Kernel(工單引擎/身分/金流軌/可觀測/事件骨幹)| 15_SDS §3 · 13_Security |

---

## 全域視覺規範(所有圖共用)

### 配色(drawio 內建色票)

| 語意 | 填色 fill | 框線 stroke | 用在 |
|---|---|---|---|
| **即時客服熱路徑** | `#F8CECC` 紅 | `#B85450` | LINE 進線/agent/Turn/急件路徑 |
| **品牌後台營運** | `#DAE8FC` 藍 | `#6C8EBF` | web/api 營運面、工單域 |
| **平台共用服務** | `#D5E8D4` 綠 | `#82B366` | Casdoor/SigNoz/平台 console/守衛鏈 |
| **獨立子系統** | `#B0E3E6` 青 | `#0E8088` | technician-platform · knowledge-refinery |
| **知識/AI 能力資產** | `#FFE6CC` 橘 | `#D79B00` | Skill/RAG/記憶/Model Orchestration |
| **設計態 / DSL / Pack** | `#FFF2CC` 黃 | `#D6B656` | flow DSL/field_metadata/報價 BC/積木 |
| **外部實體 / actor** | `#F5F5F5` 灰 | `#666666` | LINE Platform/LLM 供應商/GCP/客戶/技師 |
| **Data Store** | `#E1D5E7` 紫 | `#9673A6` | 品牌庫/技師庫/平台庫/Redis/pgvector |

### 形狀

- 元件 / 程序 = **圓角矩形**;外部實體 / 系統 = **直角矩形**;人 / 角色 = **actor**;資料儲存 = **圓柱**;分層 / 部署區 / 子系統 = **container / swimlane**。

### 線型(語意化)

- **即時主資料鏈** = 粗實線(strokeWidth=2.5)、實心箭頭
- **同步呼叫 / 設計態發布** = 一般實線
- **學習態回流(知識/語料)** = 虛線
- **橫切支撐(共用服務→各區)** = 點線、淡色
- 狀態圖用正交圓角轉移線、時序圖用直線訊息;其餘連線走**直線散開**(不用正交,避免疊線)。
- 每張圖右下(或空白處)放**圖例**,列出該圖實際用到的配色與線型。

---

## 核心心法(每張圖都應傳達,避免畫歪)

1. **報價先行**:線上估價報價 → 客人確認 → 才開單派工;到府後不符走**現場報價修正輪**(quote v+1 再確認);急件 4 類 carve-out 事後補審。
2. **AI 永不自轉工單 / 永不 final quote**:AI 進後台唯一入口 = `transfer_to_human`;工單成立必經小編 1-click;AI 只給範圍價。
3. **邊界三分**:報價/定價 bounded context 在品牌 api;技師身分在跨租戶 technician-platform(工單只有唯讀投影,requote 只發 command——ADR-027);知識精煉是 License 附加(HITL 審核後才落地)。
4. **三庫物理隔離 = 租戶模型**(品牌庫/技師庫/平台庫,ADR-020);tenant_id 是輔助標記非主隔離。
5. **知識閉環資料前提** = LINE 對話三方(客戶/AI/真人接管)全量存檔(BR-CONV-03),缺一樣本失真。
6. **產品兩階段**:階段一單品牌鎖匠垂直(M1+M2);多品牌規模化與平台化(Vertical Pack/積木飛輪/AI Compiler)全在階段二——圖上一律標 🔜。
