---
title: 規格正統語言化 — Persona 節點化 + BDD 生成視圖
cr_id: CR-0185
status: draft
created: 2026-07-27
owner: PM / BA / SA / QA
targets:
  - smartlock-docs/enterprise/規格統控整理/_canon.py
  - smartlock-docs/enterprise/規格統控整理/_validate_relations.py
  - smartlock-docs/enterprise/規格統控整理/_build_workbooks.py
  - smartlock-docs/enterprise/規格統控整理/_relations/*.yaml
  - smartlock-docs/enterprise/06_UX_Research_Report.md
  - smartlock-docs/enterprise/28_Scenarios.md
---

# CR-0185 · 規格正統語言化（Persona 節點 + BDD 生成視圖）

## 1. 背景與動機（WHY）

現行 `規格統控整理` 走的是 **ISO/IEC/IEEE 29148（SRS）＋ use-case scenario ＋ V-model 追溯**
學派：脊椎 = `SC-*`，三條互不推導的邊（SC→RQ、RQ→TC、SC→TC）＋ V2–V10 機器檢查。
這是對合約級 B2B2C 派工平台最合適的正統，且 V9 覆蓋缺口機制比多數 BDD 團隊更嚴謹。

業主提出的需求鏈（Persona → Epic → User Story → AC → BDD → Test Case）是
**Agile／BDD 學派**。兩者都是正統，只是不同傳統。盤點後，現行文件其實已具備該鏈
絕大多數層級，真正缺口只有兩個半：

| Agile/BDD 層 | 現況節點正典 | 狀態 |
|:---|:---|:---|
| Persona | `06_UX §3` Persona 卡（林太太／小美／阿宏／維運者）| 已是正統寫法，但**只是散文，未進追溯圖** |
| Epic | `28_Scenarios §1` 五分線 L1-CUS/OPS/TEC/KNW/PLT | 實質即 Epic，只差標籤 |
| User Story | `SC-01…19`（旅程粒度）| use-case，非 atomic story（**刻意，保留**）|
| Acceptance Criteria | `SC.完成判定` + `FR.後置與驗收` | 已有 |
| BDD Scenario | 僅 `SC` 散文 + `TC` 步驟持有素材 | **缺 Gherkin 形式化** |
| Test Case | `TC-*` | 強 |

本 CR 目標：以**外科手術式銜接**補齊「Persona 未進圖」與「缺 BDD 形式化」，
**不動既有 SC 脊椎與三邊模型**。

## 2. 觸發面向（為何需要 CIA）

命中 change-governance 的：**Domain model**（規格 meta-model 新增 PER 節點型別）、
**Test plan**（新增 BDD 生成視圖與可能的 V11 檢查）、**Architecture boundary**（新增第四條
宣告邊與一支生成器）。因此走 CIA gate，停在 §8 等業主裁決後才動 canon。

## 3. 目標設計（WHAT）

### 3.1 Persona 節點 `PER-*`

- 新增 Persona 節點正典（家由 §8-D1 裁決）。欄位對齊現有 06_UX 卡：
  `PER-ID / 名稱 / 對應角色 / 情境 / 目標 / 痛點 / 成功定義`。
- ID 方案（建議）：主要 4 個 `PER-CUS-01`（林太太）、`PER-OPS-01`（小美）、
  `PER-TEC-01`（阿宏師傅）、`PER-PLT-01`（維運者）；次要角色（DPO／Domain Expert／
  租戶 Admin／Family Reviewer／加盟品牌）視 §8-D4 決定是否一併節點化。
- `_canon.py` 新增 `Persona` dataclass 與 `load_personas()`，與 SC/FR/TC 同級。

### 3.2 `SC ──體現──► Persona` 宣告邊

- SC.Actor 常為複合（`終端客戶 × 派工小編`）→ 一條 SC 體現 1–2 個 Persona，天生 M:N。
- 真相源 `_relations/sc_embodies_persona.yaml`，欄位 `{scenario, persona, role}`
  （`role ∈ {primary, secondary}`，語義同 sc_rq 的 essential/supporting）。
- 與現行「宣告不推導」哲學一致：**不由 Actor 字串命名相似度推 Persona**（V2 精神）。
- `Relations` 加 `sc_per` 欄與 `personas_of(sc)` / `scenarios_of_persona(per)` 派生視圖。

### 3.3 BDD 生成視圖（Given/When/Then）

- **是 SC 的生成視圖，不是新節點、不是第五套編號**——比照 `19_Test_Plan §1.1` 與
  `20_Test_Cases §2.1` 的 `BEGIN/END GENERATED` 生成塊哲學。手改上游 SC，重跑生成器。
- 映射規則（全部從既有欄位取，零手抄）：
  - `Feature` ← SC：`作為 <PER.名稱>，我想要 <SC.名稱>，以便 <PER.成功定義>`
  - `Scenario（happy）` ← `SC.觸發`（Given/When）+ `SC.主要步驟`（When）+ `SC.完成判定`（Then）
  - `Scenario（failure/recovery）` ← `SC.失敗與例外` 逐條拆，並對齊
    `rq_verified_by_tc.yaml` 既有 `kind ∈ {happy|boundary|failure|recovery}` → 每條情境
    尾標可驗證它的 `TC-*`。
  - Gherkin 語言由 §8-D3 裁決（繁中 功能/情境/假設/當/那麼 或 英文關鍵字）。
- 產出位置由 §8-D2 裁決。

### 3.4 Epic 標籤（輕量，非新 ID）

- 不鑄 `EPIC-*`。在四書與 BDD Feature 標題沿用既有 5 分線作 Epic/Theme 標籤即可。
  純顯示層，無新真相源、無 CIA 額外面向。

## 4. 影響面（IMPACT）

| 檔 | 變更 | 破壞性 |
|:---|:---|:---|
| `_canon.py` | +Persona dataclass / load_personas / Relations.sc_per | 無（純新增，向後相容）|
| `_validate_relations.py` | +V11 Persona 孤兒檢查（finding，不擋生成）| 無 |
| `_relations/sc_embodies_persona.yaml` | 新檔（第四條邊）| 無 |
| Persona 正典檔（D1 決定）| 新增或升級 | 視 D1 |
| `28_Scenarios.md` | 不改脊椎；BDD 若選內嵌則加 GENERATED 塊 | 視 D2 |
| `_build_workbooks.py` / 新 `_render_bdd.py` | BDD 生成器；驗收控制表可增「體現 Persona」欄 | 無 |
| 四書 xlsx | 重生快照 | 無（生成物）|

追溯鏈補完後：`PER → SC → {FR/NFR} → TC`，「誰」端閉合，V9 覆蓋機制不受影響。

## 5. 風險與反模式防護

- **不得**把 SC 砍成 atomic User Story（會重新打碎跨角色旅程、破壞 M:N SC↔RQ）。本 CR 保留 SC。
- **不得**逼 NFR 進「作為…我想要…」句型（NFR 是全域地板，見四書指南 §4）。BDD 只生成自 SC。
- **不得**讓 BDD 變手維護第四份檔（違反四書指南 §1「同一旅程寫多次」根因）。強制生成視圖。
- **不得**由 Actor 字串推 Persona 邊（違反 V2「不用命名慣例偽裝關聯」）。宣告邊。

## 6. 驗證計畫

- `_validate_relations.py` 通過（含新 V11 finding 清單）。
- `_build_workbooks.py` 重生四書 + BDD 視圖無 error。
- 抽驗 3 條 P0 SC 的 BDD happy+failure 情境，人工確認每條 Then 對得到 TC。
- BDD 視圖 diff 應可由「改 SC → 重生」完全再現（生成物特性）。

## 7. 追溯矩陣影響

`21_Traceability_Matrix.md` 增列 Persona 維度（PER × SC 覆蓋）；四書指南 §2/§3/§4 補
Persona 節點與第四條邊的定位；新增 Agile/BDD ↔ 29148 術語對照表（業主原始需求）。

## 8. Human Decisions Required 🛑

> 以下為無法由 code/現有文件推定、需業主裁決的設計分岔。裁決後才進 §9 實作。

- **D1 — Persona 節點的家**
  - (A1) 新增 `29_Personas.md` 作 PER 節點正典（**建議**：一型一檔，與 28_Scenarios 對稱；
    06_UX 保留研究敘事並反指）
  - (A2) 直接把 `06_UX §3` 升為 PER 正典（省一個檔，但研究報告混入節點正典職責）
- **D2 — BDD 視圖產出位置**
  - (B1) 獨立 `smartlock-docs/enterprise/bdd/*.feature`（**建議**：標準 Gherkin 工具/IDE 可讀）
  - (B2) `28_Scenarios.md` 內每卡 `BEGIN/END GENERATED` 塊（與脊椎同檔，閱讀連貫）
  - (B3) 四書某 xlsx 新分頁（業務可在 Excel 看，但脫離版本 diff）
- **D3 — Gherkin 語言**：繁中（功能/情境/假設/當/那麼，與業主範例一致）或英文標準關鍵字
- **D4 — 次要角色是否節點化**：只建 4 個主要 Persona，或連 DPO／Domain Expert／租戶 Admin／
  Family Reviewer／加盟品牌一併建 `PER-*`
- **D5 — SC→Persona 邊 vs 映射表**：宣告邊 `sc_embodies_persona.yaml`（**建議**，與三邊模型一致、
  可帶 primary/secondary）或 `_spec_data.py` 的 `ACTOR_TO_PERSONA` dict（更輕，但不進關聯健康檢查）

## 9. Suggested Implementation Order（裁決後）

- **S1** 建 Persona 正典（D1）+ 4–9 張 PER 卡（源自 06_UX §3，零虛構）
- **S2** `_canon.py`：Persona dataclass + load_personas + Relations.sc_per + 派生視圖
- **S3** `sc_embodies_persona.yaml`（D5）逐條宣告 19 SC 的 Persona 邊 + `_validate_relations.py` V11
- **S4** BDD 生成器（D2/D3）：SC+relations → Gherkin；四書指南補術語對照表 + Persona 定位
- **S5** 重跑 `_validate_relations.py` + `_build_workbooks.py`，抽驗 P0，更新 21_Traceability_Matrix
- 每步完成回寫本 CR §進度 + CHANGELOG `[Unreleased]`

## 業主裁決（2026-07-27）

- **D1** = 升級 `06_UX §3` 為 PER 正典（不另開 29 檔）
- **D2** = 三個輸出都要：`bdd/*.feature` ＋ `28_Scenarios.md` 內嵌生成塊 ＋ 四書 xlsx 分頁（全同源）
- **D3** = 英文標準 Gherkin 關鍵字（Feature/Scenario/Given/When/Then），內文繁中
- **D4** = 建齊所有在 SC 出現的 Actor 對應 Persona（4 主要 + 6 次要）
- **D5** = 宣告邊 `_relations/sc_embodies_persona.yaml`

## 進度

- ✅ **S1** done：`06_UX §3` 升為 PER 節點正典——4 主要卡加 `PER-*` ID + §3.5 六張次要角色卡（源自 §2／§內部次要角色，零虛構）
- ✅ **S2** done：`_canon.py` +`Persona` dataclass / `load_personas()`（解析 §3 兩種格式）/ `Relations.sc_per` + `personas_of` / `scenarios_of_persona`
- ✅ **S3** done：`sc_embodies_persona.yaml` 30 條邊（每條帶 note）+ `_validate_relations.py` V11；`python3 _validate_relations.py` 全綠（SC 19 · Persona 10 · SC×Persona 30）
- ⏳ **S4** BDD 生成器（3 輸出 + 四書指南術語對照表）
- ⏳ **S5** 重跑四書 + 21_Traceability_Matrix Persona 維度
