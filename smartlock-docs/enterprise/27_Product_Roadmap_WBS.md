---
title: 產品推進 Roadmap 與 WBS（瀑布式）— Smart Lock AI 客服與派工 SaaS 平台
version: 1.0
status: active
owner: PM
last-updated: 2026-07-07
upstream:
  - smartlock-docs/enterprise/02_BRD.md §9.3（技術分期 Phase 1-4）
  - smartlock-docs/enterprise/03_PRD.md §7-§10（FR 全集與優先級）
  - smartlock-docs/enterprise/04_SRS.md（FR-* 驗收基準）
  - smartlock-docs/00_platform/P1/07_workorder_platform_design.md §8-§9（平台化設計鎖定）
  - smartlock-docs/00_platform/P2/04_adr/ADR-P012（執行債清償排程）
---

# 27 產品推進 Roadmap 與 WBS（瀑布式開發）

> **業主裁決（2026-07-07）**：通用工單平台三大地基（§8 Vertical Pack / 兩層渲染 / field_metadata）與流程自動化護城河（§9 積木飛輪 / AI Onboarding Compiler / Flow 本體論）**全數劃入產品第二階段**。現行網站前端為鎖匠垂直設計——**階段一以鎖匠介面為主做深做穩，階段二才橫向展開**。
>
> 本文件是開發團隊的**單一進度基準**：階段 → 里程碑 → 工作包（WBS）→ 驗收依據（FR / TC / KPI）。瀑布式治理：需求已凍結為 baseline（見 §1），實作期間任何範圍變更一律走 CIA / ChangeRequest，不「順手加」。

---

## 1. 治理框架（瀑布式 Stage-Gate）

### 1.1 需求基線（已凍結）

**Baseline v1.0 = enterprise 文件集 00–26（2026-07-07）**，含本日六項業主裁決：報價先行＋現場修正輪、對話三方全量存檔（BR-CONV-03）、ADR-027 requote 邊界、急件補審引擎設計、角色目錄 4+保留（13_Security §3.1）、問題卡雙 gate（15_SDS §4.6）。

### 1.2 階段關卡（每個里程碑都走完整瀑布）

```
G0 需求基線 ✅ → 設計凍結（SDS 增補 + CIA 清零）→ 實作 → SIT（20_Test_Cases 對應 TC 全綠）
→ UAT（22 框架；合約紅線 K1/K3/K8 必過）→ Release（23 部署指南 + Release Note）
```

| 關卡 | 進入條件 | 產出 |
|---|---|---|
| **設計凍結** | 該里程碑全部工作包的 SDS 節次 / API 契約 / migration 草案完成，開放問題清零或明列 `[待確認]` | 設計基線 tag |
| **實作完成** | 全工作包 code complete + 單元測試 ≥ 80% 覆蓋 | 功能凍結（feature freeze）|
| **SIT 通過** | 對應 TC 全綠 + 回歸全綠 | SIT 報告 |
| **UAT 通過** | K1 ≥ 80%、K3 事件完整率 ≥ 95%、K8 ≥ 95%（違反 = block release）| UAT 報告（22）|
| **Release** | 部署 + smoke + rollback 演練 | Release Note + 監控基線 |

### 1.3 變更管理

範圍變更 → CIA（`docs/4-exploration/CR-NNNN`）→ 業主裁決 → 排入**當前里程碑之後**（瀑布原則：不打斷進行中的里程碑，急件例外由業主特批）。

---

## 2. 產品階段總覽（Roadmap）

```
產品階段一「鎖匠垂直深耕」（當前）                          產品階段二「平台化橫向展開」
┌─────────────┬──────────────┬──────────────┐   gate    ┌──────────────────────────┐
│ M1 上線硬化   │ M2 身分知識   │ M3 多品牌     │ ────────▶ │ M4 平台化地基 → M5 第2產業 │
│ 單品牌可上線  │ 技師平台成形  │ 規模化        │  階段閘   │ (=技術 Phase 4+)          │
│ (=Phase 1)   │ (=Phase 2)   │ (=Phase 3)   │           │                          │
└─────────────┴──────────────┴──────────────┘           └──────────────────────────┘
  T0+10 週        T0+22 週       T0+30 週                    階段閘通過後啟動
```

| 里程碑 | 一句話目標 | 對開發團隊的意義 | 週期（估）|
|---|---|---|---|
| **M1 上線硬化** | 單品牌（創始品牌）全鏈**正確、即時、可稽核**，具備收費上線條件 | 清安全債 + 補全業務流程硬閘 + 可觀測 | T0 → T0+10 週 `[待估校準]` |
| **M2 身分・知識・技師平台** | 統一身分、語義知識、技師共享池三大獨立能力成形 | 三條可平行的子系統線 | T0+10 → T0+22 週 |
| **M3 多品牌規模化** | 第 2 個品牌租戶以標準流程開站，事件骨幹上線 | 從「一套系統」到「可複製的 bundle」 | T0+22 → T0+30 週 |
| **階段閘（一→二）** | 見 §5 | — | — |
| **M4 平台化地基** | flow DSL 引擎產品化 + 兩層渲染 + Pack 打包機制 | 把鎖匠版「抽象成引擎」 | 階段二 T0 → +12 週 |
| **M5 第 2 產業落地** | 手工積木 bootstrap + FDE 4 配置面走通第 2 垂直 | 驗證飛輪，AI Compiler 隨後疊加 | +12 → +24 週 |

> 週期為規劃估值 `[待估校準]`——設計凍結時由各線 tech lead 回估修正；本文件只鎖**順序與驗收**，不鎖日曆日期。

---

## 3. 階段一 WBS（鎖匠垂直深耕）

> 編號規則：`M.工作群.工作包`。負責線：BE（api）/ FE（web）/ AG（agent）/ DT（data）/ OPS（DevOps）/ QA。
> 每個工作包的完整驗收細節以「驗收依據」欄指向的 FR / TC / SA 為準，本表不重複內文。

### M1 上線硬化（單品牌可收費上線）

| WBS | 工作包 | 負責 | 前置 | 交付物 / 驗收依據 |
|---|---|---|---|---|
| 1.1.1 | RBAC 轉 enforce：195 條 `role_required` 對帳 + 逐端點落地（先金流 / 派工）| BE | 1.1.2 | SA-01；未授權角色寫入 403（TC 權限類全綠）|
| 1.1.2 | 角色收斂：`_STAFF_ROLES` 4 值、`rolePolicy` 移除死角色、`_MATRIX` 補 `operations_manager` 行、Schema 註解同步 | BE+FE | — | SA-06；13_Security §3.1 正典一致 |
| 1.1.3 | fail-closed 白名單 + API_SURFACE 剔除清單測試 | BE | 1.1.1 | SA-03 / SA-05 |
| 1.2.1 | 工單狀態機對齊「報價先行＋現場修正輪」（flow gate + 轉移表）| BE | — | 02_BRD §5.7；TC-WO-*、TC-ONSITE-07 |
| 1.2.2 | 急件事後補審引擎（timer + 補審佇列 + 事後 LIFF/紙本 + 逾時升級）| BE+FE | 1.2.1 | FR-API-19；15_SDS §4.5；TC-DISPATCH-08；急件加價額 `[待確認]` 業主定案 |
| 1.2.3 | 問題卡雙 gate schema（CIA + migration：雙完整度 / 分流欄 / RMA spine / knowledge_ready / tenant_id）| BE+DT | CIA 裁決 | 15_SDS §4.6；18_DB §4.3 目標欄位 |
| 1.2.4 | 對話三方全量存檔驗證（接管期間零缺漏 + 寫入失敗告警）| AG+BE | — | FR-A11 / BR-CONV-03；FR-AGT-09 驗收 |
| 1.3.1 | 即時通道：WS hub 遷 Redis pub-sub + cron 分散式鎖 | BE+OPS | — | SA-02；多實例不遺失、cron 不重跑 |
| 1.4.1 | 可觀測性：SigNoz（metrics/logs/traces/alerts）+ OPIK（LLM 品質）基線 | OPS+AG | — | ADR-007；25_Monitoring_Spec |
| 1.5.1 | AI 禁區 200 題 Eval pipeline 常態化（每 deploy 跑，<95% block）| AG | — | FR-A10 / K8 |
| 1.6.1 | 基礎 CD：3 Cloud Run 自動部署 + migration drift-check CI | OPS | — | ADR-P012（G-12 / G-10）|
| 1.7.1 | SIT：M1 範圍 TC 全綠 + 回歸 | QA | 1.1–1.6 | SIT 報告 |
| 1.7.2 | UAT：合約紅線（K1 ≥ 80% / K3 ≥ 95% / K8 ≥ 95%）+ 業主驗收 | QA+PM | 1.7.1 | 22_UAT 報告；**M1 Release gate** |

### M2 身分・知識・技師平台（三線平行）

| WBS | 工作包 | 負責 | 前置 | 交付物 / 驗收依據 |
|---|---|---|---|---|
| 2.1.1 | Casdoor 統一 IdP：org（租戶）/ OIDC 授權碼流 / License 訂閱管理 | BE+OPS | M1 | ADR-004（Casdoor）；web token 改 httpOnly（ACT-01）|
| 2.1.2 | 租戶自助開帳：員工申請 tab + Admin 審核指派（4 角色）+ SoD 雙簽 | FE+BE | 2.1.1 | 13_Security §3.1 開通權矩陣 |
| 2.2.1 | RAG 語義層：`embed()` + pgvector 語料 + MCP server | AG+DT | — | agent ADR-004；FR-A03 / FR-AGT-07 |
| 2.2.2 | 語料灌注：型號事實 chunk 遷移 + Skill 重切（行為留 skill、事實入 RAG）| AG | 2.2.1 | RAG 引用率 ≥ 90% 品質 gate |
| 2.3.1 | knowledge-refinery 服務：診斷對話輸入汲取（吃 `knowledge_ready` 卡）+ 提煉分流 | DT | 1.2.3 / 1.2.4 | ADR-018；KR P1/05 |
| 2.3.2 | HITL 審核 UI（draft → 人審 diff → 核可落地 pgvector + skill）| FE+DT | 2.3.1 | ADR-018 §審核層 |
| 2.4.1 | technician-platform 獨立系統：技師庫 + tech-api + 師傅 web 拆出 | BE+FE | M1 | ADR-016；跨租戶單一身分 |
| 2.4.2 | 技師 KYC 註冊三層（登入/註冊分離 + 敏感 PII + 文件上傳）| BE+FE | 2.4.1 | CR-0115（七項設計裁決依 §8）|
| 2.4.3 | OHS requote command 通道（tenant 路由 + 冪等 + 降級）| BE | 2.4.1 / 1.2.1 | ADR-027；FR-TEC-07；TC-DISPATCH-07 |
| 2.5.1 | v1 API 收斂：凍結 → 遷移 ~42 caller → 移除（5-gate）| BE+FE | M1 | ADR-P012（G-09）|
| 2.6.1 | M2 SIT + UAT（含跨系統整合場景）| QA | 2.1–2.5 | **M2 Release gate** |

### M3 多品牌規模化

| WBS | 工作包 | 負責 | 前置 | 交付物 / 驗收依據 |
|---|---|---|---|---|
| 3.1.1 | Kafka 事件骨幹：`commission.accrued` / 工單投影事件上線（替換 outbox 輪詢）| BE+OPS | M2 | ADR-006 / ADR-017；17_AsyncAPI |
| 3.1.2 | 技師工作台改吃 CQRS 投影（跨品牌工單聚合）| BE+FE | 3.1.1 / 2.4.1 | FR-TEC-*；TC-DISPATCH-05 欄位最小化 |
| 3.2.1 | 期末對帳 reconcile 閘門（品牌計費 vs 平台結算對平）| BE+DT | 3.1.1 | BR-SETTLE-05；FR-E03 |
| 3.3.1 | License → provisioning 自動化（開站流程腳本化）| OPS | 2.1.1 | ADR-002（per-brand bundle）|
| 3.4.1 | 雲端拓撲對齊（tech / platform 面雲端部署 + 技師庫上雲）| OPS | 2.4.1 | 平台 L1 G-01 收斂 |
| 3.5.1 | 第 2 品牌租戶開站演練（全流程 dry-run：申請 → 核准 → 開站 → 綁 LINE）| PM+OPS | 3.3.1 | 開站 SOP 文件化；**M3 Release gate = 階段一完成** |

---

## 4. 階段二 WBS（平台化橫向展開——概要層級）

> 階段二在階段閘通過前**只做設計不動工**。以下為 PM 佈局粒度，設計凍結時再展開至工作包層級。

| WBS | 工作群 | 內容 | 對應決策 |
|---|---|---|---|
| 4.1 | flow DSL 引擎產品化 | 從鎖匠 pack 抽出引擎（DSL-first 鐵律：引擎先於 UI）；積木契約 + 匯入靜態驗證 | ADR-013；15_SDS §3.3-3.5 |
| 4.2 | 兩層渲染 | `field_metadata` 配置驅動（DynamicForm/Table）+ `ui_composition` 元件組裝；**現行鎖匠前端漸進遷移，不 big-bang 重寫** | ADR-001；07_workorder §8.1 |
| 4.3 | Vertical Pack 打包 | pack@version + 租戶覆寫 + 向後相容檢查；鎖匠版收斂為第一個正式 pack | 07_workorder §4 |
| 4.4 | 積木庫 bootstrap | 頭 2-3 產業積木**手工建**（誠實面對冷啟動）| ADR-014 鐵律 2 |
| 4.5 | FlowEditor 拖拉 | 薄編輯器，只產出/編修 DSL | FR-F07 |
| 4.6 | AI Onboarding Compiler | SOP/訪談 → Block Ontology → draft DSL → **HITL 人審**（金流/派工/同意書必過人審）；與 knowledge-refinery 共用審核 UI 骨架 | ADR-014 / FR-F08 |
| 4.7 | 第 2 產業落地 | FDE 4 配置面走通（診斷 / 知識精煉 / flow / UI 組裝），驗證飛輪 | 07_workorder §8.2 |

---

## 5. 階段閘：階段一 → 階段二 的啟動條件

全部滿足才啟動 M4（缺一則繼續深耕鎖匠垂直）：

1. **M3 Release gate 通過**（含第 2 品牌開站演練成功）。
2. **商業驗證**：≥ 2 個付費品牌租戶穩定營運 ≥ 1 個月，K1/K5/K7 全達標 `[待確認：業主定案具體租戶數與月數]`。
3. **技術前提**：Kafka 事件骨幹穩定（C4 hash mismatch = 0）、工單引擎經 flow gate 驗證（1.2.1 的狀態機已由 DSL 定義驅動）。
4. **業主裁決確認啟動**（階段二為投資決策，不自動觸發）。

---

## 6. 里程碑燃盡與回報節奏

| 節奏 | 內容 |
|---|---|
| 週報 | WBS 工作包狀態（未開始 / 進行中 / 完成 / 阻塞）+ 阻塞升級 |
| 里程碑關卡會 | 設計凍結 / SIT / UAT 三個 gate 各開一次，業主出席 UAT gate |
| 變更看板 | CIA / CR 佇列與裁決狀態（等業主 §8 者標紅）|
| KPI 儀表 | K1 / K3 / K5 / K8 + counter-metrics（C1 / C2 / C4），上線後常態監控 |

## 7. 風險登記（roadmap 層級）

| 風險 | 影響 | 緩解 |
|---|---|---|
| RBAC enforce 灰度誤傷（M1）| 上線期 403 誤擋營運 | shadow 對帳先行（1.1.1 前置於矩陣對帳）+ 金流/派工先行灰度 + 快速回退開關 |
| `operations_manager` 矩陣缺行未補即 enforce | 租戶最依賴角色全鎖 | 1.1.2 強制排在 1.1.1 之前（WBS 已定序）|
| 三線平行（M2）整合風險 | SIT 後期大爆炸 | 2.6.1 前每線各自 mini-SIT；OHS 契約（ADR-027）先凍結 |
| Kafka 引入運維複雜度（M3）| 事件遺失 / 重複消費 | outbox 保底 + reconcile 閘門把關金流正確性 |
| 階段二過早啟動 | 鎖匠垂直未站穩即分兵 | §5 階段閘含業主裁決,不自動觸發 |
| 瀑布式需求凍結 vs 現場回饋 | 需求漂移累積 | CIA/CR 全記錄,批次排入下一里程碑,不插隊 |

---

## 8. 追溯

| 本文件 | 上游 | 下游 |
|---|---|---|
| §2 階段對映 | 02_BRD §9.3（Phase 1-4）、業主裁決 2026-07-07 | 各系統 P1/16 WBS（依本文件重排）|
| §3 M1 安全群 | 13_Security §8 Phase 1 行動項（SA-*）| 20_Test_Cases 權限類 TC |
| §3 M2 三線 | ADR-004/016/018/027、CR-0115 | 各系統 SDS |
| §4 階段二 | 07_workorder_platform_design §8-§9、ADR-013/014 | 設計凍結時展開 |
| §5 階段閘 | 業主裁決（平台化列第二階段）| Release 計畫 |

---

*27_Product_Roadmap_WBS v1.0 — 2026-07-07*
