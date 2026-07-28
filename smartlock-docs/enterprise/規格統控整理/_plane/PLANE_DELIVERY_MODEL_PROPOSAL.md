# Plane 交付模型提案：三本 xlsx 怎麼建進去、怎麼管

> **狀態**：業主已裁決（2026-07-28）——①不改平台、改 Excel 對標 ②全面重建三層 parent 鏈
> ③106 條 NFR 全標四形態。**階層重建已執行完成**，見文末〈執行結果〉。
> 建立：2026-07-28 ｜ 依據：[`PLANE_MODULE_RELATIONS_PM.md`](PLANE_MODULE_RELATIONS_PM.md)
> ＋ 三本 xlsx 實讀 ＋ LOCK 專案 live 盤點
>
> **一句話結論**：追溯脊椎**已經建完了**，缺的不是卡，是**交付層** ——
> 迭代節奏（0 個 cycle）、節點驗收定義、以及 106 條 NFR 完全沒有節點歸屬。

---

## 1. 現況盤點（live 實測，非文件推測）

### 1.1 三本 xlsx 的內容，已經在 Plane 裡的部分

| 四書內容 | 數量 | Plane 落點 | 狀態 |
|---|---|---|---|
| SC 旅程（業務邏輯驗收表 ②）| 19 | `Scenario` 型別卡 | ✅ 已建 |
| FR 需求（BOM ②，L3）| 65 | `Requirement` 型別卡 | ✅ 已建 |
| NFR（BOM ②，L3）| 106 | `NFR` 型別卡 | ✅ 已建 |
| WBS 工作包 | 47 | `Work Package` 型別卡 + Milestone | ✅ 已建 |
| 子系統 / 能力群（BOM L1/L2）| 7 + 5 | 12 個 Module | ✅ 已建 |
| TC 測試案例（整合測試計畫 ②）| 130 | Test Case + 63 資料夾 | ✅ 已建 |
| UAT 旅程腳本（整合測試計畫 ④）| 19 | 19 個 TestRun | ✅ 已建 |
| 需求 × 案例覆蓋（③）| 273 條連結 | TestCase↔WorkItem 追溯 | ✅ 已建，覆蓋率 98.5% |
| 正典編號 / 來源 / 角色 | — | 11 個自訂欄位 | ✅ 已建 |

### 1.2 還沒進去的部分

| 四書內容 | 數量 | 現況 | 我的建議 |
|---|---|---|---|
| **BDD 行為情境**（驗收表 ⑤，Given/When/Then）| 65（19 happy + 45 failure）| 只在 xlsx | **不要建卡**，寫進 SC 卡本文（§4）|
| **旅程 × Persona**（驗收表 ④）| 31 條邊 | 只在 xlsx | 不建卡，補成 SC 卡的自訂欄位 |
| **元件標籤字典**（BOM ③）| 113 | 只在 xlsx | 不建卡，Plane 不是元件目錄，留在文件 |
| **需求級節點歸屬**（BOM ② M1/M2/M3+）| 65 FR 有、**106 NFR 全無** | 未進 Plane | §3 的核心議題 |

### 1.3 三個實測出來的結構問題

**① 規格投影卡與交付卡混在同一塊板上。**
LOCK 目前 237 卡中，**191 張沒有 milestone、全部躺在 Backlog**；有 milestone 的只有 47 張 WBS 卡
（M1 13、M2 13、M3 14、M4 7）。也就是說 `_plane/README.md` 當初裁決要避開的狀態
（「190 張唯讀投影卡混進日常交付看板會把今天要做什麼淹掉」）在**本機這台正在發生**。

**② 0 個 cycle。** 完全沒有迭代節奏。目前板上只有「節點」與「Backlog」兩種時間概念。

**③ 106 條 NFR 一條都沒有節點歸屬。** BOM ② 的 M1/M2/M3+ 欄位交叉層級後是這樣：

| 節點 | 有歸屬的需求 | 前綴分布 |
|---|---|---|
| M1 | 46 | 全 FR |
| M2 | 16 | 全 FR |
| M3+ | 8 | 全 FR |
| **無任何節點** | **106** | **全 NFR** |

65 個 FR 全部有歸屬（其中 5 個跨兩節點），**106 個 NFR 全部沒有**。
意思是：**目前每一道驗收閘都不含任何非功能需求** —— 效能、可用性、安全、A11y 沒有任何節點負責驗。
這是最容易讓 schedule 在最後一刻爆掉的缺口，因為 NFR 通常在整合測試才浮現，而屆時沒有閘擋它。

---

## 2. 業界怎麼管：先說一件不舒服的事

**你們的四書追溯模型不是開源專案的做法，而是受規管產業的做法。**

| 團隊型態 | 管理方式 | 有需求 ID 與追溯矩陣嗎 |
|---|---|---|
| 一般 GitHub OSS | Issues（扁平）＋ Labels ＋ Milestones（= 版本）＋ Projects 看板。驗收＝PR review ＋ CI 綠燈 | ❌ 沒有。沒有 FR 編號，沒有 BDD→TC 矩陣 |
| 大型 OSS（Kubernetes / Rust / Python）| 設計提案先行（KEP / RFC / PEP）→ 開 tracking issue → 實作 PR 回連。SIG／子系統分權 | ⚠️ 有設計文件與 tracking issue，但**沒有需求級追溯矩陣** |
| 企業敏捷（Scrum / SAFe）| Epic → Feature → Story → Task，BDD 當 Story 的驗收標準 | ⚠️ 有時有，多半只到 Story↔Test |
| **受規管產業**（醫材 ISO 13485、航空 DO-178C、車用 ASPICE）| 需求逐條編號、雙向追溯矩陣、每條需求都要有驗證證據 | ✅ **強制**。你們現在做的就是這一層 |

**所以不要整套照抄 OSS 敏捷。** 你們做重的理由是正當的 —— 要賣給品牌、有合約下限（BOM 裡就有 18 條標「合約下限」），
追溯是交付物不是包袱。但**OSS 有一個實踐正好解你問的滑期問題，那個值得抄**：

> **固定日期的 release train，範圍浮動。**
> Kubernetes 一年三個版本，日期先定死；功能沒趕上就滑到下一版，**版本日期絕不滑**。

這與「規劃越細越滑」是同一件事的兩面。滑期的根因不是估不準，而是**把日期綁在範圍上**：
只要範圍固定，任一依賴延遲就必然推遲日期，而依賴邊數量隨規劃細度平方成長。
固定日期、浮動範圍，把不確定性推到「這版做多少」而不是「什麼時候做完」。

---

## 3. Milestone 要怎麼定義才「可被驗收落實」

你的判斷是對的：**節點要大、要少、要能二值判定。** 具體做法：

### 3.1 節點的完成定義＝一個 TestRun 全綠，不是「任務做完 80%」

這不是我發明的，是你們 fork 自己的 ADR 0004 寫的：

> A WBS item is done only when its acceptance artifact exists and its named test gate has **actually run**.
> Static compilation does not prove runtime, image, restore or browser journeys.

落成 Plane 的機制（**現成零件都已經在，不必開發**）：

```
節點 M1
 ├─ 範圍定義   ← BOM ② M1 欄標 ✓ 的 46 個 FR
 ├─ 驗收測試集 ← 那 46 個 FR 經追溯連結展開到的 TC
 ├─ 驗收證據   ← 一個名為「M1 驗收閘」的 TestRun，把上述 TC 全部收進去
 └─ 通過條件   ← 該 TestRun 的 progress：failed=0 且 open=0
```

Plane 的 `/testing/overview/` 與 `/testing/requirement-coverage/` 直接算得出這兩個數字。
**節點狀態不再靠人判斷，靠一個查得到的數。**

### 3.2 建議的節點結構：4 個閘，不要更多

沿用現有 M1–M4（已在 Plane），但把定義從「工作包集合」改成「驗收閘」：

| 節點 | 驗收問題（一句話，二值） | 範圍來源 |
|---|---|---|
| M1 上線硬化 | 客服到工單的主鏈能不能在真環境跑完且不掉單？ | BOM M1 的 46 FR ＋ SC-01…08 的 UAT 腳本 |
| M2 身分・知識・技師平台 | 技師與知識兩條線能不能自助運轉？ | BOM M2 的 16 FR ＋ SC-12、14、15、16 |
| M3 多品牌規模化 | 第二個品牌能不能不改 code 上線？ | BOM M3+ 的 8 FR ＋ SC-17、18 |
| M4 平台化地基 | 平台能力能不能被第三方配置？ | 其餘 ＋ SC-09、13 |

### 3.3 NFR 怎麼掛節點（不要逐條掛）

106 條逐條掛節點會讓閘變成 106 個檢查項，等於沒有閘。建議：

- **每個節點挑 3–5 條 NFR 當硬 gate**（例：M1 只驗 `NFR-Sec-*` 與 `NFR-Perf-*` 的關鍵幾條），
  這幾條進該節點的驗收 TestRun。
- 其餘 NFR 標為**持續性品質屬性**，不設節點閘，改由 CI 常態檢查。
- 差別在於：**進 gate 的 NFR 沒過就不能宣稱節點通過**；持續性的沒過是技術債，不擋節點。

> 🛑 這是 §6 的待裁決項之一：哪些 NFR 進 gate，只有業主能定。

---

## 4. 情境 → Epic → Story → BDD → 需求 → TC 怎麼關聯分配

### 4.1 業界標準鏈（先講觀念）

```
Epic ................ 業務成果，數月尺度，跨迭代
  └ User Story ...... 一個迭代內可完成的價值切片
       ├ Acceptance Criteria ← BDD Given/When/Then（附在 Story 上，不是獨立卡）
       └ Task .......... 工程分解（可選，很多團隊刻意不建）

Requirement（規格）... 平行存在。被 Story 實現，被 TC 驗證。不是 backlog 項目
Test Case ........... 從 AC 衍生，驗證 Requirement
```

**兩個最常被搞混、也是你們現在的結構風險：**

**① 需求（FR）不是 User Story。**
FR 說「系統該有什麼」，Story 說「這個迭代要做出什麼可驗收的價值」。
把 FR 當 backlog 跑，會得到 171 張永遠做不完的卡 —— **LOCK 現在 191 張躺 Backlog 就是這個樣子**。
規格卡是被引用的資產，不是待辦。

**② BDD 情境不該建卡。**
Given/When/Then 是驗收標準，寫在卡的本文裡。65 條獨立建卡，會製造 65 張沒有負責人、
沒有完成定義、也不會被關閉的卡，反而把看板搞髒。

### 4.2 你們的資料對應到哪一層

> 🟥 **更正（2026-07-28，業主指出後查證）**：本文件初版把「WBS 工作包 = User Story」，**這是錯的**。
> 實讀 47 張卡後確認它們是**帶負責人與前置依賴的工程任務**，不是價值切片。詳見 §4.4。

| 四書概念 | 數量 | 業界對應 | Plane 落點 | 建卡？ |
|---|---|---|---|---|
| **SC 旅程** | 19 | **Epic** | `Scenario` 卡 ＋ 同名 Label | ✅ 已建 |
| **BDD 情境** | 65 | **Acceptance Criteria** | 寫進對應 SC 卡的本文 | ❌ **不建卡** |
| Persona | 31 邊 | Actor | 寫進 SC 卡本文（自訂欄位無 UI，見 §4.3）| ❌ 不建卡 |
| **FR** | 65 | **Requirement（規格）** | `Requirement` 卡，唯讀投影 | ✅ 已建 |
| **NFR** | 106 | **Quality attribute** | `NFR` 卡，唯讀投影 | ✅ 已建 |
| **WBS 工作包** | 47 | **Task / Enabler**（不是 Story）| `Work Package` 卡 ＋ Milestone ＋ Cycle | ✅ 已建 |
| **TC** | 130 | **Test Case** | Test Case | ✅ 已建 |
| **UAT 腳本** | 19 | **Epic 的驗收測試集** | TestRun | ✅ 已建 |
| ~~User Story~~ | — | — | **這一層不存在，而且建議不要建**（§4.4）| ❌ |

**每個 Epic（SC）的完成定義是現成的**：該旅程的 UAT 腳本 TestRun 全綠。
19 條 SC 對 19 個 TestRun，一對一，已經建好了 —— 這是整個結構裡最完整的一塊。

### 4.3 Epic 層級在 Plane 的呈現難題（必讀）

`Work Item Type` 在這個 Plane 版本**UI 完全不呈現**（見 PM 關係圖 §7）。
所以「Scenario / Requirement / NFR / Work Package」這四層在畫面上**看不出差別**，
全部只是一列卡。這直接打掉「用型別做 Epic 分層」的做法。

UI 上真正可見、且 API 寫得進去的分類軸只有三個：

| 機制 | UI 可見 | API 可寫 | 建議用途 |
|---|---|---|---|
| **Label** | ✅ 完整 | ✅ | **SC-01…SC-19 做成 19 個 label** ← 目前 LOCK **0 個 label**，最大的可見性浪費 |
| **Milestone** | ✅ | ✅ | 4 個節點閘 |
| **Cycle** | ✅ | ✅ | 2 週迭代 ← 目前 **0 個** |
| 父子巢狀 | ✅ | ✅ | 工作包切細後的子卡 |
| ~~Work Item Type~~ | ❌ | ✅ | 只能給 API／報表用，人看不到 |

**所以 Epic 在 UI 上的體現＝Label。** 一張交付卡貼 `SC-05` label，任何人在看板上就知道它服務哪條旅程；
而型別欄位再正確，畫面上也看不到。

> 🟥 **追加查證（2026-07-28）：自訂欄位也沒有 UI。**
> `apps/web/core/hooks/use-issue-properties.tsx` 是一個 **16 行的空實作** ——
> 收下參數後直接 `return;`，什麼都不做。所以匯入時寫進 `custom_properties` 的
> 11 個欄位（含 `canonical_id`、來源檔名、負責角色）**人在 UI 上一個都看不到**，
> 只有 API 與報表讀得到。
>
> 這把「機器可讀 ＋ 人看得見」的欄位選項壓到只剩 **Label / Milestone / Cycle / 父子 / 關聯**。

---

## 4.4 為什麼 WBS 不是 User Story，以及實務上該怎麼放

### 證據：47 張 WBS 卡長什麼樣

```
1.1.1 RBAC 轉 enforce：195 條 role_required 對帳 + 逐端點落地（先金流 / 派工）
     負責 BE ｜ 前置 1.1.2 ｜ 交付物/驗收依據 SA-01；未授權角色寫入 403 ｜ 里程碑 M1

1.1.2 角色收斂：_STAFF_ROLES 4 值、rolePolicy 移除死角色、_MATRIX 補 operations_manager 行
     負責 BE+FE ｜ 前置 — ｜ 交付物/驗收依據 SA-06；13_Security §3.1 正典一致 ｜ 里程碑 M1
```

對照 User Story 的 INVEST 準則，至少踩掉兩條：

| INVEST | WBS 卡的實況 |
|---|---|
| **I**ndependent | ❌ 有明確 `前置` 欄位（1.1.1 前置 1.1.2），依賴是它的一等公民 |
| **N**egotiable | ❌ 內容是定死的技術規格（`_STAFF_ROLES` 4 值），不是待協商的意圖 |
| **V**aluable | ❌ 「角色收斂」對終端使用者不構成可感知價值 |
| **E**stimable | ✅ 可估 |
| **S**mall | ⚠️ 粗細不一，有些跨數週 |
| **T**estable | ✅ 有 `交付物/驗收依據` |

它有**負責人**、有**前置依賴**、用**技術語彙**、**沒有 actor 也沒有價值敘述** ——
這是教科書上的 WBS／工程任務，在敏捷詞彙裡最接近 **Task**，少數幾張像 **Enabler / Feature**。

### 正確的心智模型：兩根正交的軸，不是一根樹

```
需求軸（系統該做什麼 / 該多好）        交付軸（要生產出什麼工作）
────────────────────────────         ──────────────────────────
SC 旅程        19  Epic
  └ BDD 情境   65  Acceptance Criteria
      └ FR/NFR 171 規格               WBS 工作包  47  Task/Enabler
          └ TC 130 驗證                  └ Milestone 4  驗收閘

         ↑                                      ↑
    「做完算不算數」由這根軸判定          「誰在什麼時候做」由這根軸排
```

WBS **不是需求軸上的一層**。PMBOK 的 WBS 是**交付物導向分解**（遵守 100% 規則，
節點回答「要產出什麼」）；User Story 是**價值切片的協商佔位符**。
兩者的分解準則不同，硬把 WBS 塞進需求軸只會兩邊都失真。

### 🟥 真正的缺口：兩軸目前沒有連結

`_relations/` 只有四種關係，**沒有一種涉及 WBS**：

| 關係 | 邊數 | 連接 |
|---|---|---|
| `sc_requires_rq` | — | SC → 需求 |
| `sc_embodies_persona` | — | SC → Persona |
| `rq_verified_by_tc` | 273 | 需求 → TC |
| `sc_verified_by_tc` | 19 腳本 | SC → TC |

WBS 卡的 `交付物 / 驗收依據` 欄位裡雖然出現 `FR-API-19`、`TC-DISPATCH-08`、`SA-01` 這些編號，
但那是**自由文字，不是邊**。所以現在**無法用機器回答**：

> 「M1 的 46 個 FR，各由哪張 WBS 卡實現？這些卡做完了嗎？」

而這正是「節點可被驗收落實」的關鍵推導。**這是我認為最該補的一件事，而且它不需要新增任何卡。**

### 三個實務上正確的選項

**A｜不要 User Story（契約交付型，＝現況）**
交付單位就是 WBS 工作包，`交付物 / 驗收依據` 就是它的驗收標準。
這是受規管與契約交付團隊的常態，也是你們 fork ADR 0004 已經寫死的定義
（"A WBS item is done only when its acceptance artifact exists and its named test gate has actually run"）。
**代價**：兩軸靠人腦連結，節點驗收無法自動推導。

**B｜保留 WBS 當交付軸，把它連到需求軸（推薦）**
不發明新層級、不改卡、不增卡。只做一件事：**每張 WBS 卡建立指向它所實現需求的關聯**。
做完之後 M1 的驗收就能推導：
`M1 的 46 個 FR → 反查哪些 WBS 卡實現 → 那些卡完成 且 那些 FR 的 TC 全綠 = M1 通過`。

實作限制（已查證，會影響做法）：

| 限制 | 實況 | 影響 |
|---|---|---|
| 語義最貼切的 `implements` / `implemented_by` | 模型層有，但 **v1 API 的 `relation_type` 只開 8 種**（blocking / blocked_by / duplicate / relates_to / start_before / start_after / finish_before / finish_after），**不含 implements** | 只能退用 `relates_to`（對稱、語義較弱，但可用）|
| 改用自訂欄位存 FR 清單 | 讀取最快（`custom_properties` 隨卡片一次回傳），但 **UI 是空實作，人看不到** | 適合報表，不適合人工維護 |
| `relates_to` 關聯 | **有完整 UI**（卡片詳情的 Relations 區塊）| ✅ **唯一「機器可讀 ＋ 人看得見」的選項** |

依據：`apps/api/plane/api/serializers/issue.py:640-649`（8 種 choices）、
`apps/web/core/components/issues/issue-detail-widgets/relations/`（關聯 UI 齊全）。

**C｜全面轉成 User Story（不推薦）**
你們的使用者價值敘述已經由 SC ＋ Persona ＋ BDD 承載了，再寫一層 "As a…" 會與 SC 重複；
而且轉換會丟掉 WBS 的**負責人與前置依賴**，卡數從 47 漲到 120＋，換不到任何追溯收益。

### 那「User Story」那一層到底對應到誰？

最接近的是 **BDD 情境（65 條）** —— 每條自帶 Given/When/Then（＝AC）且有 Persona。
但它們是**行為規格**，不是**工作項**。若真要有 story 層，正確定義是
「**讓某條 BDD 情境從紅變綠所需的工作**」，而不是把 WBS 改寫成 "As a…" 句式。

**我的建議是不要建這一層。** SC → BDD → FR → TC 已經能回答「做完算不算數」，
再加一層 story 只是多一份要人維護的映射，而維護不動的映射會比沒有映射更糟。

---

## 5. 建置規劃：分階段，並明列「不要做的事」

### Phase 0 — 先裁決板的形狀（阻塞後續）
處理 §1.3① 的混板問題。三個選項見 §6。

### Phase 1 — 補 Label（19 SC ＋ 4 節點），成本最低、可見性收益最大
API 可寫（`/labels/`）。做完之後看板才第一次能回答「這張卡屬哪條旅程」。

### Phase 2 — 建 Cycle，給出迭代節奏
2 週一個 cycle，只把 WBS 卡放進 cycle（規格卡永遠不進 cycle）。
`1 卡 1 cycle` 的基數限制正好強迫「這張卡屬於哪一個迭代」有唯一答案。

### Phase 3 — BDD 65 條寫進 SC 卡本文
從驗收表 ⑤ 生成 HTML 寫入對應 SC 卡的 `description_html`。
19 happy ＋ 45 failure，按 SC 分組。**不建新卡。**

### Phase 3.5 — 連結兩軸（§4.4 選項 B），這是節點可驗收的前提
把 47 張 WBS 卡逐張建立 `relates_to` 關聯，指向它實現的 FR。
來源是各卡 `交付物 / 驗收依據` 欄位裡已經寫著的 `FR-*` 編號 —— **資料已經有，只是還沒變成邊**。
沒有這一步，Phase 4 的節點閘只能驗「需求的 TC 綠不綠」，無法回答「這個節點的工作做完了沒」。

### Phase 4 — 節點驗收閘 TestRun
每個節點建一個「Mx 驗收閘」TestRun，把該節點範圍的 TC 收進去。
節點通過條件＝該 run `failed=0 且 open=0`。

### Phase 5 — NFR gate 歸屬
依 §3.3 裁決結果，把入選 NFR 掛節點並收進驗收 run。

### ❌ 明確不要做的事

| 不要做 | 為什麼 |
|---|---|
| 把 BDD 65 條建成卡 | 製造 65 張無主、無完成定義的卡 |
| 把 171 個需求當 sprint backlog | 規格不是待辦，會得到永遠燒不完的燃盡圖 |
| 為 View 寫自動化 | 沒有 API（實測 404 / 401），只能手動建，當人工步驟排 |
| 細分到 task 層 | 依賴邊平方成長，是滑期主因。停在工作包／Story 層 |
| 用 Work Item Type 做人看的分層 | UI 不呈現，做了也看不到，改用 Label |
| 用 MCP 操作 cycle / module / 自訂欄位 | 實測壞掉或靜默回空，一律走 REST |

---

## 6. 🛑 待業主裁決

**① 板的形狀（阻塞 Phase 1–5）**

| 選項 | 做法 | 代價 |
|---|---|---|
| A 分家（＝原 ADR 決定）| 規格卡與測試庫留 SPEC，LOCK 只放交付卡 | WBS 卡兩份同號並存；`writeback.py` 需改讀雙靶心 |
| B 合一 ＋ Label 隔離 | 全留 LOCK，用 label ＋ 手建 View 把規格卡濾掉 | 看板預設仍會看到 191 張卡，靠使用者記得切 View |
| C 合一 ＋ 規格卡封存 | 規格卡設 `archived_at`，預設查詢自動排除 | 需確認封存後 TestCase 追溯與覆蓋率報表是否仍算得到（**未驗證**）|

我的建議是 **A**，因為它是唯一讓「日常看板預設就乾淨」的選項，而它的代價（雙靶心讀取）是一次性的程式修改。
但 C 若驗證可行會更省事 —— 需要先做一次驗證再決定。

**② 哪些 NFR 進節點 gate**（§3.3）。106 條全掛等於沒閘，建議每節點 3–5 條，但選哪幾條是業務判斷。

**③ WBS 47 張要不要切細到 cycle 可完成的粒度。**
現在一張工作包可能跨數週，放不進 2 週 cycle。**注意這不是「轉成 user story」**（§4.4 已排除），
而是單純的粒度問題：切細＝在同一張卡下開子卡（父子巢狀，UI 支援），卡數估 47 → 120±；
不切則 cycle 失去意義，退回只有節點沒有迭代。
折衷做法是**滾動式細分**：只切接下來 1–2 個 cycle 要動的工作包，其餘維持粗顆粒 ——
這也正是「規劃越細越滑」的直接對策（§2）。

**④ 節點日期是否固定。** §2 的 release train 只在「日期不可滑、範圍可砍」時才有效。
若日期也可談，這套機制退化成普通進度追蹤。

---

## 執行結果（2026-07-28）

### 已完成

**四本 xlsx 的欄位**（生成器 `_build_workbooks.py` / `_canon.py`，非手改）

| 活頁簿 | 新增欄位 | 結果 |
|---|---|---|
| BOM ② | `parent 代號` | 171 個 L3、32 個 L2 **全部有 parent** |
| BOM ② | `需求型別` | Story 65 / Quality requirement 106 |
| BOM ② | `目標里程碑` + `節點範圍` | 取代 M1/M2/M3+ 三欄；單值取區間終點（M1 43 / M2 14 / M3 6 / M4 2），5 條跨節點 FR 的完整區間保留 |
| BOM ② | `NFR 驗證形態` + `ReleaseEvidence key` | 由 `verification` 欄推導。形態 1:45／2:7／3:31／4:19／⚠跨形態:4 |
| 驗收表 ⑤ | `涵蓋需求（由 SC 邊推導）` | 64 條 BDD 全有值（**粗對應**，非精確映射）|
| 測試計畫 ② | `路徑類型` + `驗證面向` | 拆開 15 種混合值；暴露 **52/130 條沒有路徑類型** |

**Plane 階層重建**（`_plane/rebuild_hierarchy.py`，冪等、可回復）

| 驗收項 | 重建前 | 重建後 |
|---|---|---|
| `Issue.parent` 使用數 | 0 / 238 | **203 / 278** |
| Epic 層 covered（roll-up） | 0 | **8 / 8** |
| SC 卡 uncovered | 19 | **0** |
| 新建卡 | — | 8 Epic + 32 Feature |

### 未完成，且**無法用 API 完成**

| 項目 | 為什麼 | 要怎麼做 |
|---|---|---|
| 封存 21 張 archive 類 WBS 卡 | v1 API **沒有 archive 路由**，只有內部 app API | Plane 網頁批次封存 |
| 12 張 merge 類的排程移交後封存 | 同上 | 同上 |
| 50 條 NFR 的 ReleaseEvidence（形態 3/4） | `release-evidence` **只在內部 app API** | Plane 網頁逐條輸入 |
| 修 `3.6.1`–`3.6.8` 欄位位移 + 補 `3.1.3`／`3.2.2` | 需重跑匯入器 | `import_spine.py --until=wbs` |

### 出貨閘門現況

```
ready: false
  - 1 failed test case(s) in the latest run
  - 1 open defect(s)
  - 47 scheduled requirement(s) with no acceptance contract   ← 就是那 47 張 WBS
```

`requirements.total` 從 237 降到 **47**，因為 191 張規格卡都在 Backlog 狀態群組、依平台規則免契約。
**剩下的唯一結構性 blocker 就是 47 張 WBS**，處置方案見 `_relations/wbs_disposition.yaml`，
但執行要在 UI（封存無 API）。

---

## 變更紀錄

| 日期 | 變更 |
|---|---|
| 2026-07-28 | 初版提案。基於三本 xlsx 實讀 ＋ LOCK live 盤點，未動任何 Plane 資料。 |
| 2026-07-28 | 業主裁決後執行：xlsx 六個新欄位、47 張 WBS 分類、Plane 階層重建（roll-up 生效）。 |
