# CR-0192 — Plane 看板重新定位：從四書鏡像改為管理工具

- **日期**：2026-07-28
- **觸發**：業主檢視 `SPEC` 專案後指出三點——(a) work items 把太多性質不同的項目混在同一個看板；
  專案管理與客戶 issue 管理應是兩套切開的頁面 (b) WBS 缺多層次表達，實務上瀑布與 Scrum 都需要
  (c) Modules 混了「子系統」與「L1 分線」兩套語言，使用者不知該看哪個
- **觸發面向（CIA gate）**：Architecture boundary、Test plan、Domain model
- **上游**：CR-0190（Plane 借鏡架構優化）、`smartlock-docs/enterprise/規格統控整理/_plane/README.md`
- **實作分支**：未開（等 §8 裁決）
- **狀態**：🛑 等待業主裁決 §8

---

## §1 目標與不變式

**目標**：把 Plane 從「四書的鏡像」改造成「管理工具」。判準是單一句話——
**放上去的東西必須會改變狀態，且該狀態變化需要有人做決定**。不滿足此條件的內容留在文件。

**不變式（本 CR 不得破壞）**：

1. 四書（`28_Scenarios` / `04_SRS` / `05_NFR` / `20_Test_Cases`）與 `_relations/*.yaml`
   仍是唯一 SSOT，Plane 單向投影，不回寫規格。
2. `_validate_relations.py` 的 V6 不得違反——回寫只落 `status_snapshot.yaml`。
3. **追溯完整性的權威留在 xlsx**。Plane 不再承擔「171/171 需求全覆蓋」這個數字。
4. 四個狀態軸各有唯一 owner，不得互推（需求定版 SA／工程證據 RD／測試執行 QA／業務驗收 業主）。
5. Plane 不存在時四書照常 build（`snapshot.py` 的 fail-soft 設計不動）。
6. 不新增第五套編號。

---

## §2 AS-BUILT 盤點

### 2.1 現況

| 專案 | 內容 | 數量 |
|---|---|---|
| `SPEC`（`4acaa966…`） | SC 19 + FR 65 + NFR 106 + WBS 47 | 237 卡 |
| 同上 | 測試案例 + 資料夾 + 追溯連結 + TestRun | 130 / 40 / 273 / 19 |
| `LOCK`（`b8c33b48…`） | WBS 1.1.1–3.5.1、UAT-0720-\*、UAT-0723-\*、CR-\* 卡、M1–M3 卡 | 61 卡 |

### 2.2 缺陷清單

| # | 缺陷 | 證據 | 歸因 |
|---|---|---|---|
| **D1** | 171 張 FR/NFR 卡**永遠不轉狀態**。規格定版由 SA 在文件決定，卡片 state 恆為 Backlog | `spec_status` 自訂欄位已承載定版狀態；卡片 state 從未被使用 | 設計 |
| **D2** | WBS 47 張**完全扁平**，`parent` 一張都沒設；`Work Group`（`is_epic=true`）type 建了從未使用 | API 查證：`有 parent 的 WBS 卡: 0` | 實作 |
| **D3** | Module 兩套語言且成員互斥：`L1-*`(5) 只有 SC 19，`子系統 *`(7) 只有 FR 65，**NFR 106 + WBS 47 共 153 張無歸屬** | `attach_modules()` 只走 scenarios 與 requirements | 設計 |
| **D4** | Module 與 `value_line` / `subsystem` 自訂欄位**雙寫**同一份資訊，無一致性保證 | 兩者選項集合完全相同 | 設計 |
| **D5** | **M3.6 區塊欄位偏移，8 張卡標題誤植為狀態字串** | `WBS-3.6.1` 標題＝`3.6.1 ✅ 2026-07-27`，真正名稱「前端 mutation contract…」遺失 | 實作 |
| **D6** | `27_Product_Roadmap_WBS.md` 缺二層工作群列——47 項中 **42 項的二層母項不存在任何一列**，`1.1` 只活在編號的點號裡，沒有名字 | `三層項但無對應二層母項: 42` | 源檔 |
| **D7** | WBS 在 `SPEC` 與 `LOCK` **同號雙胞胎** | CR-0190 收尾時已記入 `_plane/README.md` | 設計 |
| **D8** | 軸②（工程證據）權威在 `LOCK`，但 `writeback.py` 讀 `SPEC`，等於回放規格文件自己的標記 | 同上 | 設計 |
| **D9** | FMA / RMA 借用硬體製造術語（FMEA＝失效模式分析，事前預防；RMA＝退貨授權），與實際語義（上線前缺陷逃逸／UAT 缺陷）不符 | 業主 2026-07-28 說明 | 命名 |

**D5 的根因值得記下**：`import_wbs()` 以固定索引 `row[1] row[2] row[3]…` 取值，而源檔的
M3.6 表格比其他區塊多一個優先級欄。**位置取值遇到不齊的表格就會靜默錯位**——不報錯、不驗證，
只是把錯的字串當標題寫進去。修法不是調整索引（下一個新表格又會錯），而是改為**依表頭名稱取值**。

### 2.3 外部參考結論

| 來源 | 結論 |
|---|---|
| [Plane 官方](https://plane.so/blog/epic-vs-feature-vs-user-story-vs-task-understanding-the-differences) | 建議 **Epic → Feature → User Story → Task** 四層，上接 Initiative（跨專案）、Cycle（sprint）、Module（分組） |
| [Atlassian](https://www.atlassian.com/agile/project-management/epics-stories-themes) | `story < epic < initiative < theme`；Initiative 跨季度、跨團隊 |
| [垂直切片](https://monday.com/blog/rnd/vertical-slice/)／[Educative](https://www.educative.io/courses/more-effective-agile-a-roadmap-for-software-leaders/key-principle-deliver-in-vertical-slices) | 按功能端到端切，不按層切；週期時間可降約 40% |
| [看板衛生](https://www.breeze.pm/articles/signs-your-project-management-tool-is-complicated) | 「移除你不用的欄位。選一個真相源。」沒人用的欄位只製造猶豫與誤選 |

### 2.4 系統能力實測（2026-07-28，於 `SPEC` 建臨時卡驗證後刪除）

| 能力 | 結果 |
|---|---|
| `parent` 巢狀 5 層 | ✅ 未撞深度上限 |
| Epic 掛 Epic 底下 | ✅ |
| 階層查詢 | ✅ `pql='childOf("SPEC-12")'` |
| Cycle（sprint） | ✅ 原語完整；`SPEC` 目前 `cycle_view=false` 只是沒開 |
| 故事點 | ✅ work item 有 `point` / `estimate_point`，專案層有 estimate 定義 API |

**結論：多層 WBS 與 Scrum 系統都做得到，D2 是實作缺口不是能力限制。**
唯一未驗證項：UI 把巢狀渲染成樹狀或僅卡內 sub-issues 清單——需業主在畫面確認。

---

## §3 影響分析

### 3.1 Flow / UX

看板使用者的動線由「瀏覽 237 張卡」變為「Milestone → Epic → Work Package」三層下鑽。
規格內容改以卡片內文 reference（如 `04_SRS.md §3.1`）呈現，不再是可點擊的卡。

### 3.2 API Contract

**無影響**。本 CR 只動 `_plane/` 投影層與 Plane 內的資料形狀，不觸及 `api/openapi.yaml`
或任何產品端點。

### 3.3 Domain model

`_plane/README.md §3` 的整張對映表重寫。受影響的對映：

| 來源 | 現行 Plane 原語 | 提議 |
|---|---|---|
| `FR-*` / `NFR-*` | work item（Requirement / NFR type） | **不投影**，改內文 reference |
| `SC-*` | work item（Scenario type） | **Epic**（垂直切片單位） |
| WBS 三層項 | work item（Work Package，扁平） | Work Package，掛在二層 Epic 下 |
| WBS 二層群 | 不存在 | **Epic**（需先在源檔命名，見 §5） |
| `sc_requires_rq` | `essential_for` / `supporting_for` 欄位 + relation | 隨 FR/NFR 卡移除而消失，權威回歸 `_relations/*.yaml` |
| `rq_verified_by_tc`（273） | TestCaseWorkItemLink → RQ 卡 | 改掛 `sc_verified_by_tc`（19 腳本 / 145 refs）→ SC Epic |

### 3.4 DB schema

**無影響**。不動本平台任何資料庫。

### 3.5 External integration

Plane 實例（`lock-ai` @ ngrok）內的資料重整，含刪除。**Plane 無批次刪除**，
清理走既有 `rollback_target.py`。

### 3.6 Test plan

**這是本 CR 最需要業主注意的影響面**：

- 測試庫 130 案**保留**，但看板呈現層級由「130 個案例各自狀態」上收為「19 條 SC 驗收腳本通過率」。
- `TestCaseWorkItemLink.clean()` 強制測試案例與需求卡同專案。FR/NFR 卡移除後，
  **273 條 `rq_verified_by_tc` 在 Plane 失去掛載對象**，改掛 SC Epic（粒度由需求級變旅程級）。
- **`requirement-coverage` 的 171/171 數字在 Plane 消失**，該指標退回 xlsx（`_build_workbooks.py`
  本就以 `_relations/rq_verified_by_tc.yaml` 計算，不依賴 Plane）。
- `writeback.py` 的軸③ 由 `axis3_req`（依需求）縮為 `axis3_case` + `axis3_script`。
  `snapshot.py` 的 `req_execution_of()` 與四書「整合測試計畫 ②測試案例主表」的
  `Plane 執行結果` 欄需同步調整。

### 3.7 Architecture boundary

由「一個 Plane 專案承載全部」改為多專案分責。專案數與邊界見 §6，屬 §8 待裁決項。

---

## §4 風險與回復

| 風險 | 影響 | 對策 |
|---|---|---|
| 刪除 171 張規格卡後反悔 | 需重跑匯入 | `id_map` 完整記錄，`import_spine.py --until=requirements` 可重建；**但 sequence_id 會改變**，任何外部引用（截圖、會議紀錄裡的 `SPEC-45`）失效 |
| 追溯粒度降級後才發現需要需求級 | 273 條連結要重建 | 連結來源 `_relations/rq_verified_by_tc.yaml` 未動，重建是重跑而非重編 |
| 二層工作群命名改到源檔後，既有 CR/ADR 的 WBS 引用失效 | 文件交叉引用斷裂 | **只新增二層列、不改動三層編號**，`1.1.1` 等既有引用全數保持有效 |
| 多專案後 writeback 需跨專案讀取 | 軸②/軸③/軸④ 分散 | 已知（D8），本 CR 一併處理，見 §9 |
| 重整期間業主正在使用看板 | 看到半成品 | 於 `SPEC` 完成後再切換，`LOCK` 全程不動 |

**回復路徑**：`rollback_target.py --dry-run` 先驗，再實刪；`id_map` per-target，
不影響其他靶心。

---

## §5 WBS 二層工作群命名草案（🛑 請逐條核）

依據＝該群底下三層項的實際內容。**只新增二層列，不改三層編號**，既有引用不受影響。

| 二層 | 提議名稱 | 底下的三層項（依據） |
|---|---|---|
| 1.1 | 權限系統硬化 | 1.1.1 RBAC 轉 enforce／1.1.2 角色收斂／1.1.3 fail-closed 白名單 |
| 1.2 | 核心業務流程對齊 | 1.2.1 工單狀態機／1.2.2 急件補審引擎／1.2.3 問題卡雙 gate／1.2.4 對話存檔驗證 |
| 1.3 | 即時通道基礎設施 | 1.3.1 WS hub 遷 Redis pub-sub |
| 1.4 | 可觀測性基線 | 1.4.1 SigNoz + OPIK |
| 1.5 | AI 品質防線 | 1.5.1 禁區 200 題 Eval pipeline |
| 1.6 | 持續部署基礎 | 1.6.1 3 Cloud Run 自動部署 + migration drift-check |
| 1.7 | M1 驗收 | 1.7.1 SIT／1.7.2 UAT 合約紅線 |
| 2.1 | 統一身分與租戶開帳 | 2.1.1 Casdoor IdP／2.1.2 自助開帳 SoD 雙簽 |
| 2.2 | RAG 語義層與語料 | 2.2.1 embed + pgvector + MCP／2.2.2 語料灌注與 Skill 重切 |
| 2.3 | 知識精煉與熱更新 | 2.3.1 knowledge-refinery／2.3.2 HITL 審核 UI／2.3.3 LiveSkill 熱更新 |
| 2.4 | 技師平台獨立化 | 2.4.1 technician-platform 拆出／2.4.2 KYC 三層／2.4.3 OHS requote 通道／2.4.4 技師觸達 |
| 2.5 | v1 API 收斂 | 2.5.1 凍結→遷移→移除（5-gate） |
| 2.6 | M2 驗收 | 2.6.1 M2 SIT + UAT |
| 3.1 | 跨品牌工單聚合與派工 | 3.1.1 Kafka 事件骨幹／3.1.2 CQRS 投影／3.1.3 混合派工 |
| 3.2 | ⚠️ **見下方異常** | 3.2.1 期末對帳閘門／3.2.2 refinery intake 受控 API |
| 3.3 | 開站自動化 | 3.3.1 License → provisioning |
| 3.4 | 雲端拓撲對齊 | 3.4.1 tech/platform 上雲 + 技師庫上雲 |
| 3.5 | 多品牌開站驗證 | 3.5.1 第 2 品牌開站演練 |
| 3.6 | Plane 借鏡架構優化 | 3.6.1–3.6.8（源檔已有此群名） |

**兩個異常，我不自行決定**：

1. **3.2 底下兩項不同源**：3.2.1 是計費對帳閘門（財務），3.2.2 是 refinery 資料進入受控 API
   （資料治理，ADR-042）。硬湊一個群名（如「對帳與資料治理」）會製造一個沒有內聚性的節點。
   建議把 3.2.2 移到別群或另開 3.7，但這動到三層編號，屬業主決定。
2. **4.1–4.7 本身就是二層**（M4/M5「概要層級」，無三層細項）。是要維持概要、
   還是趁此展開成三層，屬規劃深度問題。

---

## §6 提議的目標拓樸（🛑 待裁決）

| 內容 | 落點 | 理由 |
|---|---|---|
| FR 65 / NFR 106 | **不進 Plane**，卡片內文 reference `04_SRS.md §3.1` | 業主 2026-07-28 已裁決 |
| SC 19 旅程 | **Epic**（垂直切片單位） | SC 本身即端到端旅程 |
| WBS 47 + 新增二層群 | Milestone → Epic → Work Package（→ Task 視需要） | 對齊 Plane 官方四層建議 |
| 測試案例 130 | 測試庫保留；看板只呈現 19 條 SC 驗收腳本通過率 | 管理看的是「這條旅程能否驗收」 |
| 上線前缺陷 / UAT 缺陷 | 獨立 issue 專案（命名見 §8-D5） | 生命週期與節奏不同 |
| Module | 收斂為單一軸 | 消除 D3/D4 |

**Module 收斂的補充**：業主已選「只留子系統一套」，但需注意兩點——
(a) 子系統 AGT/API/WEB/DAT 是**水平分層**，與「垂直切片追蹤」的取向相反；
(b) NFR 在 canon 中**只有 `category`（Perf/Sec/…）沒有子系統屬性**，無法歸入子系統。
FR/NFR 卡若依 §6 移除，此矛盾自動消失（Module 只需服務 WBS 與 SC），故列為 §8-D3 重新確認項。

---

## §7 Traceability

| 追溯邊 | 現行載體 | 變更後 |
|---|---|---|
| `sc_embodies_persona`（30） | `personas` multi_select | 隨 SC 卡保留 |
| `sc_requires_rq`（132） | `essential_for`/`supporting_for` + relation | **僅存 `_relations/` 與 xlsx** |
| `rq_verified_by_tc`（273） | TestCaseWorkItemLink → RQ | **僅存 `_relations/` 與 xlsx** |
| `sc_verified_by_tc`（19/145） | TestRun | TestCaseWorkItemLink → SC Epic + TestRun |

**四書 xlsx 的追溯矩陣完整性不變**——上述四條邊的真相源 `_relations/*.yaml` 全程不動。

---

## §8 Human Decisions Required 🛑

> 以下未填寫前不動 code。

| # | 決策項 | 選項 | 業主裁決 |
|---|---|---|---|
| **D1** | §5 二層工作群命名 19 條逐條核 | 接受／逐條修改 | |
| **D2** | 3.2 群異常：3.2.2 refinery intake 是否移出（動三層編號） | 維持現狀硬湊群名／移到 3.7／移入 2.x | |
| **D3** | 4.1–4.7 維持概要二層，或展開三層 | 維持／展開 | |
| **D4** | Module 單一軸取哪個（見 §6 補充的兩點矛盾） | 子系統／L1 分線／全拆改用自訂欄位 | |
| **D5** | issue 專案的命名與範圍（業主指出 FMA 用詞不精確，RMA 尚無規劃） | 上線前缺陷 + UAT 缺陷兩類／合併一類分 type／沿用 FMA-RMA | |
| **D6** | 專案數：3 個（SPEC／DELIVERY／ISSUE）或 2 個（SPEC／LOCK 內分 type） | 3／2 | |
| **D7** | 是否啟用 Cycle（sprint）與故事點 | 啟用走 Scrum／不啟用走瀑布 WBS | |
| **D8** | 既有 `SPEC` 的 237 卡：原地改造或砍掉重建 | 原地（保 sequence_id）／重建（號碼會變） | |
| **D9** | D5 欄位偏移造成的 8 張錯誤卡：是否連同 `_canon.py` 改為依表頭取值 | 是／只修卡片 | |

---

## §9 Implementation Order（待 §8 裁決後生效）

1. **S0** 修 D5：`_canon.load_wbs()` 改依表頭名稱取值，加不齊表格的驗證；重建錯誤的 8 張卡。
2. **S1** 依 §8-D1/D2/D3 修 `27_Product_Roadmap_WBS.md`，新增二層工作群列；`_canon.py` 解析同步。
3. **S2** `import_spine.py`：WBS 建立時帶 `parent`，二層用 `Work Group`（`is_epic`），三層用 `Work Package`。
4. **S3** 依 §8-D6 建立目標專案；`rollback_target.py` 清理不再需要的內容。
5. **S4** 移除 FR/NFR 投影；`_upsert` 的 description 加入 source_doc reference 連結。
6. **S5** 追溯改掛 `sc_verified_by_tc`；`writeback.py` 軸③ 調整；`snapshot.py` 與 xlsx 欄位同步。
7. **S6** Module 依 §8-D4 收斂。
8. **S7** issue 專案依 §8-D5 建立，`LOCK` 的 UAT-\* 卡遷移。
9. **S8** 重寫 `_plane/README.md §3` 對映表；更新 `四書關係與產出指南.md`；CHANGELOG。
10. **S9** 全鏈路驗證：`_validate_relations.py` 全綠、四書 build、writeback 四軸、Plane UI 目視確認階層渲染。

## §10 進度

- ✅ **S0 已提前單獨執行**（2026-07-28，業主指示「單獨修」，等同裁決 §8-D9＝「是，
  連同 `_canon.py` 改為依表頭取值」）。`load_wbs()` 改依表頭名稱取值並在缺必要欄時
  拋錯；`WBS_STATE` 由 3 種記號補到 6 種（🟨→In Progress、🛑→Backlog、空→Backlog），
  未知記號改為出聲警告而非靜默套 Todo；`_html()` 改輸出與 Plane 儲存形式一致的 HTML
  （`quote=False` + `<br>`），使日後漂移檢查不再被轉義差異灌滿假陽性。
  Plane 側修正 18 張卡（8 張 3.6.x 名稱／狀態／內文、7 張 4.x 狀態、3 張因源檔更新），
  補建 `3.1.3`／`3.2.2`（`ec2fea0d` 新增），WBS 卡數 47 → 49，逐張對帳 **0 差異**。
  軸② 49 筆、覆蓋率 171/239，`_validate_relations.py` 全綠。
- 🛑 等待業主裁決 §8 其餘 8 項（D1–D8）。
