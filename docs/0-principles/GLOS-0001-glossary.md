---
title: Business Glossary — 業務術語 SSOT
tier: 0
status: active
last_updated: 2026-05-10
sources_merged:
  - "_pending-merge-customer-vocabulary.md (25 條口語 → 標準故障)"
  - "_pending-merge-technician-tiers.md (5 級師傅分級)"
  - "../2-contracts/master-data/{brand-model, fault-codes, fault-taxonomy, materials-catalog}.md (master data 概要)"
related:
  - "id-mapping-legacy.md"
  - "../2-contracts/master-data/"
---

# Business Glossary

> 本檔為業務術語 SSOT。任何開發 / AI / spec 文件提到 ambiguous 業務名詞時，先查此檔。
>
> **規則**：定義性質的詞彙在此；結構化資料（型號表、故障碼表）在 `2-contracts/master-data/`；資料量大的（手冊、對話庫）在專案根 `data/`。

---

## §1 Domain — 智能鎖客服與派工

### 角色

| 術語 | 定義 |
| :-- | :-- |
| Consumer (消費者) | 使用 LINE Bot 報修的最終使用者 |
| Technician (技師) | 接受派工出勤維修的師傅；分 5 級（見 §3）|
| Customer Service / Support Agent (客服) | 後台處理對話 / 工單 / 客訴的人員 |
| Dispatcher / Dispatch Officer (派工員) | V1.0 獨立角色；手動派工、改派、處理 SLA 警報。見 [Q1=A 拍板](../1-decisions/_pending-split-pm-alignment-Q1-Q10.md#2-q1) |
| Operations Manager (營運主管) | 工單覆核、爭議一級審核、退款 ≤ NT$10k |
| Operations Director (營運總監) | 爭議 / 退款終裁。Q2=A 新層級 |
| Tenant Admin (租戶管理員) | 同租戶內所有治理權限 |
| Super Admin (平台超管) | 跨租戶 L0 權限 |
| Auditor (稽核員) | 唯讀；不可寫 / 不可匯出原始 PII |

### 核心業務物件

| 術語 | 定義 |
| :-- | :-- |
| Conversation (對話) | LINE 通訊串；包含多 message；狀態機 idle → collecting → resolving → resolved |
| ProblemCard (PC, 問題卡) | AI 從對話自動產生的結構化問題；含分類、症狀、嚴重度、所需技能 |
| Work Order (WO, 工單) | 派工執行單位；16 個 state（見 [`2-contracts/state-machines/SM-0002-work-order-extensions.md`](../2-contracts/state-machines/SM-0002-work-order-extensions.md)）|
| Skill (技能 / SKILL.md) | Agent 可載入的 SOP 知識檔；存於 `agent/skills/data/` |
| Case Entry (案例) | 知識庫案例；可作為訓練資料與 SOP 草稿來源 |
| SOP Draft | AI 從歷史對話產生的 SOP 草稿；客服→主管雙層審核發布 |

### 流程術語

| 術語 | 定義 |
| :-- | :-- |
| Three-Layer Resolver | L1 知識庫直答 / L2 LLM 推理 / L3 升級人工 |
| Auto Dispatch | 派工演算法依區域、品牌、技能、SLA 自動指派技師 |
| Manual Dispatch | 派工員人工指派；繞過自動派工須留 audit log |
| Scope Change | 技師到場後變更維修範圍 / 加價；需消費者二次確認（Q9=B 拍板）|
| Reschedule | 改約；技師發起延遲 → LINE 推播消費者 |
| Escalation | 客服接管：AI confidence < 閾值或消費者要求 |
| Refund / 退款 | 雙簽流程；> NT$100k 自動雙簽（Q2=A 拍板）|
| Warranty Claim / 保固申訴 | 消費者→客服→技師複勘 ≤ 7d |
| Dispute / 爭議 | 對帳 / 結算爭議；月結 SLA 7 工作日（Q4=C）|
| SLA Soft Target | V1.0 所有 SLA 為 Soft（破線僅 dashboard 警報，無賠償；Q5=B 拍板）|

---

## §2 客戶口語對照表（25 條）

> **AI 用途**：當客戶說以下口語時，AI 必須轉換為標準故障分類後再查詢 SKILL.md。

| 客戶口語 | 標準故障分類 | 補充 |
| :-- | :-- | :-- |
| 鎖卡住了 | 鎖舌卡死 / 門扇卡澀 | 確認鎖體 vs 門扇 |
| 門打不開 | 開門故障（多種可能） | 確認方向（推 / 拉、室內 / 室外）|
| 門關不起來 | 關鎖失敗 / 鎖栓無法伸出 | 檢查受口片對位 |
| 鎖一直叫 | 未關門警報 / 關鎖失敗警報 | 確認叫聲模式（長鳴 vs 短嗶）|
| 密碼按了沒反應 | 面板無回應 / 電池耗盡 | 確認面板是否亮起 |
| 指紋感應不到 | 指紋辨識失敗 | 手指濕、髒、磨損 |
| 鎖沒電了 | 電池耗盡 | 引導緊急供電或鑰匙 |
| 電子鎖壞掉了 | 待診斷（泛稱） | 進一步問診 |
| 鎖一直嗶嗶叫 | 低電量警告 / 防盜警報 | 嗶聲頻率與次數 |
| 被鎖在外面 | 無法開門（緊急） | 優先處理；確認備用方式 |
| 鎖自己打開了 | 異常解鎖 / 鎖舌縮回 | 門扇反弓或感應器誤觸 |
| 把手轉不動 | 把手機構卡死 / 離合器故障 | 解鎖前 / 後判斷 |
| 感應卡刷不過 | 卡片驗證失敗 | 卡片是否已註冊 |
| APP 連不上 | Wi-Fi 模組斷線 | 路由器頻段（僅 2.4G）|
| 螢幕不亮 | 面板無回應 / 電池耗盡 | 先電池後排線 |
| 鎖會漏電 | 異常耗電 | 非真正漏電；確認電池與 Wi-Fi |
| 臉辨識不到 | 人臉辨識失敗 | 光線 / 防回頭機制 |
| 鎖很大聲 | 馬達異音 / 鎖栓撞框 | 正常 vs 異常聲 |
| 門會自己開 | 門扇反弓 (Rebound) | 非鎖具；調整門扇 / 鉸鏈 |
| 設定跑掉了 | 系統重置 / 設定遺失 | 電池拔除過久 / 主機板異常 |
| 鎖裝歪了 | 安裝品質問題 | 鎖體歪 vs 門扇下沉 |
| 密碼被改了 | 權限異常 / 管理者誤操作 | 管理者密碼是否仍有效 |
| 鎖進不去設定 | 管理者權限問題 | 區分管理者 vs 一般密碼 |
| 門縫很大 | 門扇下沉 / 鉸鏈鬆脫 | 非鎖具；調整門扇 |
| 鎖裝好還是關不了 | 安裝後關鎖失敗 | 受口片與鎖栓對位 |

---

## §3 師傅分級（5 級）

> 核心考核指標：**「解決問題能力」** + **「回修率」**

| 等級 | 稱號 | 特徵 | 派工優先權 |
| :-- | :-- | :-- | :-- |
| **S** | 資深高手 | 解決疑難雜症、安裝品質極佳、幾乎無客訴與回修 | 最高 |
| **A+** | 優秀師傅 | 安裝穩定、能處理多數現場狀況 | 高 |
| **A** | 一般師傅 | 基礎安裝能力、無重大失誤 | 中 |
| **新人** | 實習 / 新人 | 觀察期、未正式分級 | 低（搭配指導）|
| **B/C 不錄用** | 汰除名單 | 安裝後常需二次維修「擦屁股」 | **永不派工** |

派工演算法權重見 [`2-contracts/modules/dispatch-engine-weights.md`](../2-contracts/modules/dispatch-engine-weights.md)。

---

## §4 故障分類（簡表，詳見 master-data）

| 大類 | 例 | 標準處理 |
| :-- | :-- | :-- |
| 物理故障 | 門扇卡死、鎖舌卡澀 | 拉緊 / 推緊 → 解鎖 |
| 關鎖失敗 | 馬達空轉、未自動上鎖 | 受口片調整、檢查倒三角感應器 |
| 異常警報 | 嗶嗶叫、長鳴 | 確認電池、地震感應器、警報模式 |
| 驗證失敗 | 閃爍 6（dormakaba）| 重設指紋 / 卡片 / 密碼 |
| 權限混淆 | 管理者 vs 一般密碼 | 教導區分；找回管理者密碼 |
| 雙重驗證 | 密碼+卡片 | `* 8` 解除（dormakaba）|
| IoT 限制 | Wi-Fi 連不上 | 僅 2.4G；高階路由器降為 802.11b/g/n |

完整故障碼對照表：[`2-contracts/master-data/MDS-0003-fault-codes.md`](../2-contracts/master-data/MDS-0003-fault-codes.md)
完整故障體系：[`2-contracts/master-data/MDS-0004-fault-taxonomy.md`](../2-contracts/master-data/MDS-0004-fault-taxonomy.md)

---

## §5 品牌與型號（簡表）

V1.0 支援品牌（見 `2-contracts/master-data/MDS-0001-brand-model.md` 與 `agent/skills/data/`）：

- **Chatlock** (含 AI-99 等型號)
- **Dormakaba** (AS901, DP850, ML660, ...)
- **Milre** (6500F/S, 7150)
- **Philips** (7300, alpha, 702E, 9200, 9300)
- **Kaadas (凱迪仕)** (藍寶堅尼系列)
- **AiLock** (七合一旗艦款)

注：每品牌 SKILL.md 結構為 `agent/skills/data/{Brand}/{_all-models | Model}/`。`_common/` 為跨品牌通用知識。

---

## §6 IoT 限制（不可違反）

| 項目 | 規範 | 違反後果 |
| :-- | :-- | :-- |
| 電池 | 僅限 Panasonic 鹼性電池（金紅包裝） | 碳鋅 / 混用 → 異常警報 / 短壽命 |
| Wi-Fi 頻段 | 僅 2.4G；不支援 Wi-Fi 6/7 | 連不上 |
| 路由器 | 高階路由器降為 802.11b/g/n 混合 | 同上 |

理由：3-6 個月電池續航 → IoT 模組必須限制頻寬。

---

## §7 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 | MERGE 初版：customer-vocabulary + technician-tiers + brand/fault summary |
