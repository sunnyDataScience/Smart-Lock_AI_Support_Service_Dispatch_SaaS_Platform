---
title: 07 使用者旅程地圖（Journey Map）
version: 1.0
status: active
owner: 產品設計團隊
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P1/05_platform_architecture_L1.md
  - smartlock-docs/technician-platform/P1/05_architecture_and_design.md
  - smartlock-docs/web/P1/05_architecture_and_design.md
  - smartlock-docs/web/P4/08_project_structure_guide.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P006_四方RBAC模型_enforce.md
---

# 使用者旅程地圖 — Smart Lock AI 客服與派工 SaaS 平台

> 本文件描述四方角色（+ 潛在加盟品牌）從進入平台到達成目標的端到端旅程：各階段接觸點、情緒起伏、痛點與機會點、對應系統。
> 角色定義見 [06_UX_Research_Report](./06_UX_Research_Report.md)；任務級逐步流程（決策分支 / 例外路徑）見 [08_User_Flow](./08_User_Flow.md)。

---

## 1. 旅程總覽

平台主軸是一條跨角色的價值鏈：**進線 → 處理 → 派工 → 現場 → 結算 / 治理**。五條旅程沿這條主軸交織：

```
終端客戶(A)   LINE 報修 ──► AI 自助 ──► 報價確認 ──► 等待師傅 ──► 完工簽名 ──► 結案
                              │(必要時)      ▲                ▲
品牌營運(B)              真人接手 ──► 報價審核 ──► 派工媒合 ──► 工單追蹤 ──► 帳務/退款
                                                  │(OHS+事件)   ▲
簽約師傅(C)   註冊/認證 ──────────────────► 接單 ──► 現場6子流程 ──► 完工回報 ──► 對帳/佣金
                 ▲
平台管理員(D) 品牌申請審核 ── 師傅認證審核 ── 跨租戶治理/監看
                 ▲
加盟品牌(E)   導入行銷 ──► 品牌申請 ──► License 開通 ──► provisioning 上線
```

| 旅程 | 主角 | 進入點 | 目標達成 | 主要系統 |
|---|---|---|---|---|
| A | 終端客戶 | LINE Bot | 問題解決 / 完工滿意 | agent + token 公開頁 |
| B | 品牌營運（派工小編 / 租戶 Admin） | dispatch portal（:3000） | 案件全生命週期收斂 | web dispatch + api |
| C | 簽約師傅 | 獨立師傅 web（:3001） | 接單 → 完工 → 領錢 | technician-platform |
| D | 平台管理員（Super Admin） | 平台 console（:3003） | 跨租戶治理健康 | platform console + Casdoor |
| E | 潛在加盟品牌 | landing（:3002） | License 開通上線 | landing + Casdoor + provisioning |

---

## 2. 旅程 A｜終端客戶：LINE 報修 → AI 自助 → 報價確認 → 完工滿意

### 階段與接觸點

| 階段 | 客戶做什麼 | 接觸點 | 系統行為 | 情緒 |
|---|---|---|---|---|
| 1. 發現問題 | 鎖故障，焦慮中找求助管道 | 品牌 LINE 官方帳號 | — | 😟 焦慮（急件時 😡） |
| 2. 進線描述 | 打字 / 拍照描述問題 | LINE 對話（agent） | AI 認意圖（報修 / 諮詢 / 投訴 / 其他）；急件 4 類（鎖外 / 內困 / 安全風險 / 怒客）即刻偵測 | 😐 期待又怕被機器人繞圈 |
| 3. AI 自助 | 多輪對話、跟著引導拍照 | LINE 對話 | 三層解決（案例庫 → 手冊 RAG → 轉真人）；問題卡完整度 ≥ 0.85 才往下；clarify gate 主動確認「問題釐清了嗎」 | 🙂 5 秒內有回應則安心 |
| 4. 真人接手（必要時） | 等待客服回應 | LINE 對話（真人） | 急件 bypass 三層 5 分鐘內轉真人；資料連 3 次收不齊自動轉 | 😌 有人接手的踏實感 |
| 5. 報價確認 | 點開報價頁查看明細、勾選同意 | token 公開頁 `/quotes/[token]`、`/consent/[token]` | LINE 只告知「報價已備妥」+ 編號，金額一律在公開頁呈現；只顯示總額 / 實收，內部成本拆分不可見 | 🤔 金額透明則信任建立 |
| 6. 等待師傅 | 查看進度與師傅 ETA | token 公開頁 `/track/[token]` + LINE 通知 | 派工媒合完成後推播 ETA | 🙂 |
| 7. 現場服務 | 在場確認施工；如有加價依範圍變更頁同意 | 現場 + `/scope-change/[token]` | 加價三段分層（見 [08 §4](./08_User_Flow.md)）；客戶簽名 | 😬 加價是信任最脆弱點 |
| 8. 完工結案 | 簽名、按「已解決」或 48h 自動結案 | LINE + 現場簽名 | 結案 hard gate（地址 + 報價已確認）；7 天內重發訊息可重啟 | 😊 |

### 情緒曲線（定性）

焦慮高點在**階段 1-2**（急件時到頂）與**階段 7 現場加價**；信任建立點在**階段 3 首次有效回應**與**階段 5 金額透明**。量化情緒分數 `[待確認]`（待上線後 CSAT / sentiment 數據）。

### 痛點與機會點

| 痛點 | 機會點 | 對應設計 |
|---|---|---|
| 被反覆問資訊、講不清型號 | 拍照引導 + per-user 記憶記住設備 | agent 多模態 + user_memory |
| 急件被機器人擋在門外 | 急件 4 類即刻偵測、bypass 自助層 | 5 分鐘轉真人 SLA |
| 報價不透明、到場亂加價 | 金額只在簽章頁呈現、加價需客戶同意留痕 | token 公開頁 + 加價三段分層 |
| 「沒幫助」後被已讀不回 | 負面回饋 + 沉默 30 秒內 AI 主動 follow-up | 避免 silent failure 自動結案 |

---

## 3. 旅程 B｜品牌營運：進線監看 → 問題卡 → 報價審核 → 派工媒合 → 工單追蹤 → 帳務

### 階段與接觸點

| 階段 | 營運做什麼 | 接觸點（dispatch portal） | 情緒 |
|---|---|---|---|
| 1. 進線監看 | 監看 AI 對話與 escalation 佇列；必要時接手 | `conversations/`、`admin/cases/`、sentiment-alerts | 😐 高峰期認知負荷高 |
| 2. 問題卡處理 | 檢視 AI 草擬的問題卡，確認 / 補全 / 接手 | `problem-cards/[id]` | 🙂 資訊結構化則省力 |
| 3. 開單 | 補服務地址（AI 對話常缺）與聯絡資訊，最低門檻開工單；完整度不足需主管 override | 問題卡 → 開單 Modal | 😐 |
| 4. 報價審核 | 審 AI range → 定 final 明細 → 核准後送客戶確認 | `admin/quotes/`、`admin/quote-catalog/` | 🤔 金額責任感重 |
| 5. 派工媒合 | 系統經技師共享池 OHS API 取得候選技師（技能 / 地區 / 品牌授權 / 可用性排序），確認指派；必要時手動派工 | `admin/dispatch-queue/`、`admin/dispatch-manual/` | 🙂 候選排序可信則一鍵完成 |
| 6. 工單追蹤 | 看板 / 地圖 / 詳情追蹤現場進度；處理改期、叫料、範圍變更 | `work-orders/`（kanban / map / [id]）、`admin/material-requests/` | 😐 例外處理是主要工作 |
| 7. 帳務與退款 | 取消費分層計算（可覆寫留痕）、退款依金額分層核准（高額雙簽 SoD）、發票 / 月結 | `accounting/`（invoices / revenue / vouchers）、`admin/refunds/` | 😬 金流最怕出錯 |
| 8. 知識與治理 | SOP 草稿審核（knowledge-refinery 精煉產出）、Agent 調校（Agent Studio 客製層）、角色 / 帳號管理（租戶 Admin） | `knowledge-base/`、`admin/config-governance/`、`admin/roles/`、`admin/staff/` | 🙂 自主迭代不求人 |

### 痛點與機會點

| 痛點 | 機會點 | 對應設計 |
|---|---|---|
| 不知道哪些對話該接手 | escalation 佇列 + 情緒警示集中呈現 | HITL 轉換鏈（AI 標注信心與缺欄位） |
| 派工靠人腦記師傅名單 | 共享池媒合排序（評分 / 距離 / 工作量） | OHS `POST /technicians:match`（🔜 Kafka 事件骨幹規劃中） |
| 取消費 / 退款規則靠記憶 | 系統依工單狀態自動算，特殊情境可覆寫 | 取消費 5+1 階段 + 退款 L1–L5 SoD |
| AI 回答品質要等原廠調 | 品牌自服務調校（受保護層之上的客製層） | Agent Configuration Studio（ADR-P013） |

---

## 4. 旅程 C｜簽約師傅：註冊認證 → 接單 → 現場 → 完工 → 對帳

> 師傅端全程在 **technician-platform 獨立師傅 web**（跨品牌一套，不屬任何品牌後台）。詳細序列圖見 `../technician-platform/P1/05_architecture_and_design.md` §7。

### 階段與接觸點

| 階段 | 師傅做什麼 | 接觸點（師傅 web） | 系統行為 | 情緒 |
|---|---|---|---|---|
| 1. 上線註冊 | 建立跨租戶技師身分、填基本資料 / 技能 / 欲服務品牌 | `tech-register`（KYC 註冊） | Casdoor OIDC 建立跨租戶身分（role=technician）；發 `technician.registered` 事件（🔜 Kafka 規劃中） | 🤔 文件多但一次搞定 |
| 2. 認證准入 | 上傳 KYC + 證照 | 註冊流程內 | 敏感欄位 app 層加密（Fernet）；人工審核通過 → 認證生效 + 品牌授權，才進入派工候選集 | 😐 等待審核 |
| 3. 接單 | 收到派工推播（指派）或在搶單池搶單 | `home`（工作台）、`pool`（搶單池，即時推播） | 派工指派事件 → WS 推播「新派工到手」；師傅接單 / 拒單回饋品牌工單狀態 | 🙂 推播即時則搶得到 |
| 4. 出發到場 | 查看案件詳情、回報 ETA、到場簽到 | `my-orders/[id]` | ETA 經 LINE 通知客戶 | 😐 |
| 5. 現場 6 子流程 | 依現場狀況觸發：延遲回報 / 門況檢查 / 叫料 / 改期 / 範圍變更（加價） / 客戶簽名 | `my-orders/[id]/{delay, door-check, material-request, reschedule, scope-change, signature}` | 範圍變更依金額三段分層；簽名唯客戶本人（法律效力） | 😬 現場變數最多 |
| 6. 完工回報 | 拍照上傳、完工報告 | `my-orders/[id]` | 結案 gate 檢查（地址 + 報價確認） | 🙂 |
| 7. 對帳 / 佣金 | 查排班、對帳單、佣金明細 | `account/{schedule, statements, commission-statements}` | 佣金 per-job 計費在品牌側，跨品牌結算 / statement / payout 由技師平台彙總（ADR-P014 Billing / Settlement 分離） | 😊 跨品牌一份對帳單 |

### 痛點與機會點

| 痛點 | 機會點 | 對應設計 |
|---|---|---|
| 每個品牌一套系統一組帳號 | 一個跨租戶身分服務所有簽約品牌 | Casdoor 技師身分 + 技師共享池單一真相 |
| 到場資訊錯誤（帶錯料 / 判錯保固） | 開單完整度 gate 擋垃圾工單 | 問題卡完整度 ≥ 0.85 + 主管 override 留痕 |
| 加價爭議收不到錢 | 三段分層 + 客戶簽名確認 + 留痕 | scope-change 子流程 |
| 月底對帳吵不完 | 事件驅動的結算主體集中在技師平台 | `commission.accrued` 事件 → 跨品牌 statement（🔜 規劃中） |

---

## 5. 旅程 D｜平台管理員：品牌申請審核 → 師傅認證審核 → 跨租戶治理

### 階段與接觸點

| 階段 | 管理員做什麼 | 接觸點 | 情緒 |
|---|---|---|---|
| 1. 品牌申請審核 | 審核 landing 進來的品牌申請、確認資質 | platform console `platform/brand-applications` | 😐 |
| 2. License 開通 | 核准後在 Casdoor 開通 org + License 訂閱（決定開通哪些模組，如 knowledge-refinery 附加系統） | Casdoor 管理面 | 🙂 |
| 3. Provisioning | 觸發 per-brand bundle 部署（web dispatch / api / agent / 品牌庫 / Redis / MCP-RAG）+ 綁定該品牌 LINE channel | provisioning 流程（🔜 自動化規劃中） | 😬 手動期步驟多 |
| 4. 師傅認證審核 | 審核技師 KYC / 證照，核發品牌授權 | `platform/technician-approvals` | 😐 佇列作業 |
| 5. 跨租戶治理 / 監看 | 跨租戶健康監控、配置治理、稽核 | platform console 儀表板 + SigNoz（🔜 規劃中） | 🙂 |

### 治理面補充

- **知識治理**：各品牌知識精煉（診斷 + 素材 → 事實 / 行為）由 knowledge-refinery 承載，平台管理員治理其 License 開通與精煉服務健康；審核操作本身在品牌側（旅程 B 階段 8）。
- **配置治理**：品牌自服務調校（Agent Studio）之受保護層（escalation / domain-safety / 租戶邊界）由平台鎖定，品牌不可 override；工單流程配置以 Flow DSL 宣告式狀態機為權威（ADR-P010 / ADR-P013）。
- platform console 部分頁面完成度 `[待確認]`（審核佇列以外的治理儀表板仍在迭代）。

---

## 6. 旅程 E｜潛在加盟品牌：導入行銷 → 申請 → License 開通上線

| 階段 | 品牌做什麼 | 接觸點 | 系統行為 |
|---|---|---|---|
| 1. 認識平台 | 瀏覽導入行銷頁 | landing（:3002），雙 CTA：「品牌申請導入」/「師傅加入」 | — |
| 2. 提交申請 | 填品牌申請表 | landing → `platform/apply` 公開申請頁 | 申請進入平台審核佇列 |
| 3. 等待審核 | 補件 / 溝通 | Email / 平台聯繫 | 平台管理員於 `platform/brand-applications` 審核（旅程 D） |
| 4. License 開通 | 簽約、取得授權 | Casdoor subscription | License 決定開通模組集（基礎 bundle + 附加模組） |
| 5. 上線 | 綁定自己的 LINE channel、租戶 Admin 自助開帳給團隊 | per-brand bundle（provisioning，🔜 自動化規劃中） | 品牌獨立部署一套物理隔離 bundle，即刻可營運 |

**機會點**：從申請到上線的 lead time 是加盟轉換率關鍵指標，目標值 `[待確認]`；provisioning 自動化（License → 部署 → 建庫 → 綁 LINE → 健康檢查）是縮短它的核心投資。

---

## 7. 旅程交會點（跨角色時刻）

| 交會時刻 | 角色 | 品質要求 |
|---|---|---|
| AI → 真人接手 | 客戶 × 營運 | 急件 5 分鐘 SLA；接手時完整對話脈絡與問題卡到位 |
| 報價送出 → 客戶確認 | 營運 × 客戶 | 金額只在簽章頁呈現；確認前工單不得建立（急件例外） |
| 派工指派 → 師傅接單 | 營運 × 師傅 | 指派事件 → 師傅推播 < 2 秒（🔜 Kafka + WS 規劃中）；拒單自動回佇列 |
| 現場加價 → 客戶同意 | 師傅 × 客戶（× 營運） | 依金額分層：小額師傅留痕 / 中額客戶簽章同意 / 大額營運覆核 |
| 完工 → 結算 | 師傅 × 營運 × 平台 | 品牌算 per-job 佣金、技師平台出跨品牌 statement，期末對帳閘門 |

---

*相關文件：[06_UX_Research_Report](./06_UX_Research_Report.md) · [08_User_Flow](./08_User_Flow.md) · [09_IA](./09_IA.md) · 深度參考 `../technician-platform/P1/05_architecture_and_design.md` §7、`../web/P1/05_architecture_and_design.md` §8*
