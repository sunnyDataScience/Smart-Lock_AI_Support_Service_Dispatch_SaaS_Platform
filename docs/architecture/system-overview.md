<!-- 由 architecture/system-overview.html 自動轉出的 markdown 源（gen_docs_html.py）-->

<div class="wrap">

<div>

<div class="doc-id">

Smart Lock AI · Work-Order & Dispatch Platform

</div>

# 智慧鎖 AI 客服與派工平台 — 系統技術說明

工單全生命週期　·　師傅／廠商註冊與核准　·　報價 LINE 同意流程

</div>

<div class="toc">

<div class="toc-title">

目次

</div>

1.  [一、系統概述](#sec0)
2.  [二、工作流程](#sec1)
3.  [三、系統架構](#sec2)
4.  [四、功能模組圖](#sec3)
5.  [五、職責泳道圖](#sec4)
6.  [六、AI 客服的角色與決策範圍](#sec5)
7.  [七、完整流程對照表](#sec6)

</div>

## <span class="section-no">一、</span>系統概述

本平台為「智慧鎖售後 AI 客服與派工」之 SaaS
系統，將鎖具廠商轉型為外包仲介平台。客戶於 LINE 進線後，由 AI
客服判斷意圖；可自助回答之問題直接回覆，需現場處理者轉交真人並建立工單。一張工單依序歷經問題卡確認、開單、內部估價與外部報價、客戶
LINE
同意、派工、技師現場作業、完工與結案；師傅與廠商則經由獨立註冊與後台核准流程上架，唯有狀態為
active 之技師方可被派工。

系統由三個 Cloud Run 微服務構成：Agent Gateway 接收 LINE webhook
並執行客服決策；API 服務承載後台業務邏輯與資料持久化；Web
後台供客服操作。資料層採 Cloud SQL
PostgreSQL，以租戶識別碼貫穿隔離。對外 LINE 推送一律經由 outbox
佇列非同步送出，與業務邏輯解耦。

<div class="legend">

<div class="legend-row">

<span class="dot dot-human"></span>使用者／人（客戶、客服、技師）
<span class="dot dot-llm"></span>AI 客服／大型語言模型
<span class="dot dot-py"></span>確定性程式（API 服務、狀態機）
<span class="dot dot-data"></span>資料／儲存

</div>

</div>

<div class="note">

<span class="label">設計原則</span>AI
客服永不自行寫入業務狀態。進入後台系統的唯一入口為 `transfer_to_human`
工具；所有開單、報價、派工、結算皆由確定性程式以狀態機與硬閘控制。此一界線確保
AI 的不確定性不會污染營運資料。

</div>

## <span class="section-no">二、</span>工作流程

下圖呈現由 LINE
進線至結案的完整業務時序，並納入「師傅／廠商上架」前置流程。箭頭標籤描述兩節點之間傳遞的資料或觸發條件；粗線為通過驗證的主路徑，虛線為替代或退回路徑。

<div class="mermaid">

flowchart TD classDef human
fill:#ecfdf5,stroke:#047857,stroke-width:1.5px,color:#064e3b; classDef
py fill:#eef2fa,stroke:#1d4ed8,stroke-width:1.5px,color:#1e3a8a;
classDef llm
fill:#fdf6ec,stroke:#b45309,stroke-width:1.5px,color:#7c2d12; classDef
shared fill:#d1fae5,stroke:#047857,stroke-width:3px,color:#064e3b;
classDef isolated
fill:#fde9d2,stroke:#b45309,stroke-width:3px,color:#7c2d12; RT1\["師傅\
線上註冊"\]:::human RV1\["廠商\
線上註冊（公司名＋統編）"\]:::human RU\["共用身分表 users\
email＋角色 複合唯一"\]:::py R3\["後台審核"\]:::human R4\["技師
status＝active\
可被派工"\]:::py subgraph store\["資料歸屬"\]
RTP\["共用技師池　technicians\
無 tenant_id・全平台共享同一份"\]:::shared RVP\["獨立廠商庫　vendors\
tenant_id＋brand_partner_id・各廠商 fail-closed 隔離"\]:::isolated end
RT1 -- "姓名／電話／專長" --\> RU RV1 -- "公司名／統編 8 碼" --\> RU RU
== "role＝technician" ==\> RTP RU == "role＝vendor" ==\> RVP RTP --
"status＝pending_approval" --\> R3 R3 == "核准（onboard-approve）" ==\>
R4 R3 -. "拒絕" .-\> RX\["status＝rejected"\]:::py C1\["客戶\
LINE 發訊"\]:::human A1\["AI 客服\
意圖判斷"\]:::llm A2\["呼叫\
transfer_to_human"\]:::llm P1\["AI 草擬問題卡\
status＝incomplete"\]:::py H1\["客服補齊並確認"\]:::human P2\["開立工單\
公單號 TP-xxxxxx"\]:::py Q1\["建立報價\
內部估價→對客價"\]:::py Q2\["送出並推 LINE\
報價 Flex"\]:::py C2\["客戶 LINE\
同意／拒絕"\]:::human P3\["報價 state＝accepted"\]:::py D1\["派工\
指派技師"\]:::py T1\["技師接單"\]:::human T2\["到場 → 門檢"\]:::human
T3\["完工回報"\]:::human C3\["客戶確認結案\
評分"\]:::human C1 -- "文字訊息" --\> A1 A1 -. "可自助：直接回覆知識"
.-\> C1 A1 == "需真人／需派工" ==\> A2 A2 --
"escalation（原因＋脈絡快照）" --\> P1 P1 -- "draft（品牌／型號待補）"
--\> H1 H1 == "完整度 gate ≥ 0.8" ==\> P2 P2 -- "work_order_id" --\> Q1
Q1 -- "報價草稿" --\> Q2 Q2 -- "Flex（postback q:a｜／q:r｜）" --\> C2
C2 == "同意（postback）" ==\> P3 C2 -. "拒絕：改報價重送" .-\> Q1 P3 ==
"已同意報價（D2 硬擋）" ==\> D1 R4 -. "前置：需 active 技師" .-\> D1 D1
-- "technician_id" --\> T1 T1 -- "accept" --\> T2 T2 --
"arrival／door_check 事件" --\> T3 T3 == "完工硬閘：照片 ≥
3＋客戶簽名＋安裝序號" ==\> C3

</div>

<div class="figcap">

圖一　由 LINE 進線至結案之完整工作流程（含師傅上架前置）

</div>

<div class="note">

<span class="label">資料歸屬</span>師傅與廠商共用同一份身分表
`users`（電子郵件加角色為複合唯一鍵，同一人可兼具兩種身分）；但兩者落地的主檔截然不同——**師傅資料庫為通用**：`technicians`
表不含租戶識別碼，為全平台共享的單一技師池，任何發案方皆媒合同一份師傅資料（圖中粗綠框）。**廠商資料庫為獨立**：`vendors`
表帶租戶識別碼與 `brand_partner_id`，讀取一律經 `partner_scope_service`
失敗即拒（fail-closed）過濾，各廠商之間相互隔離，跨範圍存取回
`403`（圖中粗橘框）。

</div>

<div class="note">

<span class="label">關鍵閘門</span>全流程設有四道硬性驗證：問題卡完整度需達
`0.8`
方可開單；派工前工單須存在已同意之報價（`QUOTE_NOT_ACCEPTED`）且技師須為
active；完工需滿足照片、簽名、序號三項；過期報價視同未同意。主管角色可帶原因強制放行，並留稽核紀錄。

</div>

## <span class="section-no">三、</span>系統架構

系統依抽象層級由上而下分為四層：介面層接收外部請求，服務模組層承載業務邏輯，基礎設施層提供非同步與即時能力，儲存層持久化資料。本圖僅表達層級歸屬，上層使用下層，並不代表執行順序；實際執行順序請參見圖一。

<div class="arch-stack">

<div class="arch-layer">

<div class="arch-label">

介面層Interface

</div>

<div class="arch-modules">

<div class="arch-mod human">

LINE 官方帳號<span class="small">客戶進線通道</span>

</div>

<div class="arch-mod py">

Agent Gateway<span class="small">aiohttp · /callback</span>

</div>

<div class="arch-mod py">

Web 後台<span class="small">Next.js SSR</span>

</div>

</div>

</div>

<div class="arch-layer">

<div class="arch-label">

服務模組層Service Modules

</div>

<div class="arch-modules">

<div class="arch-mod llm">

LockCore 決策迴圈<span class="small">runner / loop</span>

</div>

<div class="arch-mod llm">

LiteLLM Provider<span class="small">多家模型路由</span>

</div>

<div class="arch-mod llm">

Builtin Skills × 2<span class="small">知識 + 決策 SOP</span>

</div>

<div class="arch-mod py">

work_order_service<span class="small">工單狀態機 + 硬閘</span>

</div>

<div class="arch-mod py">

quote_engine_service<span class="small">報價引擎</span>

</div>

<div class="arch-mod py">

problem_card_service<span class="small">問題卡</span>

</div>

<div class="arch-mod py">

technician_lifecycle_service<span class="small">技師核准狀態機</span>

</div>

<div class="arch-mod py">

auth_service<span class="small">註冊／登入</span>

</div>

<div class="arch-mod py">

internal_ingest<span class="small">LINE↔後台橋接</span>

</div>

</div>

</div>

<div class="arch-layer">

<div class="arch-label">

基礎設施層Infrastructure

</div>

<div class="arch-modules">

<div class="arch-mod py">

LINE Push Outbox Worker<span class="small">每 10 秒輪詢 + 重試</span>

</div>

<div class="arch-mod py">

Flex Builders<span class="small">訊息卡片渲染</span>

</div>

<div class="arch-mod py">

WebSocket Hub<span class="small">後台即時推送</span>

</div>

<div class="arch-mod llm">

Agent Memory<span class="small">per-user 記憶</span>

</div>

<div class="arch-mod py">

Cloud Run × 3<span class="small">容器化 + 自動擴展</span>

</div>

</div>

</div>

<div class="arch-layer">

<div class="arch-label">

儲存層Storage

</div>

<div class="arch-modules">

<div class="arch-mod data">

work_orders<span class="small">工單主表</span>

</div>

<div class="arch-mod data">

quote<span class="small">報價 + 快照</span>

</div>

<div class="arch-mod data">

problem_cards<span class="small">問題卡</span>

</div>

<div class="arch-mod data">

users<span class="small">共用身分表</span>

</div>

<div class="arch-mod shared">

technicians<span class="small">★ 通用 · 無 tenant_id · 全平台共享</span>

</div>

<div class="arch-mod isolated">

vendors<span class="small">★ 獨立 · tenant_id＋partner 隔離</span>

</div>

<div class="arch-mod data">

line_push_outbox<span class="small">外送佇列</span>

</div>

<div class="arch-mod data">

conversations<span class="small">對話紀錄</span>

</div>

<div class="arch-mod data">

technician_lifecycle_event<span class="small">核准稽核</span>

</div>

</div>

</div>

</div>

<div class="figcap">

圖二　分層系統架構（縱向抽象層級，非執行順序）

</div>

<div class="note">

<span class="label">租戶隔離</span>租戶識別碼貫穿 API、資料庫與 AI
記憶；per-user 記憶以「租戶＋使用者」為唯一鍵。機密（LINE 憑證、JWT
金鑰、內部權杖、資料庫連線字串）一律存於 GCP Secret
Manager，部署時注入，不入程式碼或映像檔。

</div>

## <span class="section-no">四、</span>功能模組圖

本圖呈現模組間的呼叫關係，箭頭由呼叫端指向被呼叫端；實線為直接呼叫，虛線為非同步推送（LINE
外送與 WebSocket 廣播）。資料形態與時序不在此圖表達，分別見圖一與圖五。

<div class="mermaid">

flowchart LR classDef py
fill:#eef2fa,stroke:#1d4ed8,stroke-width:1.5px,color:#1e3a8a; classDef
llm fill:#fdf6ec,stroke:#b45309,stroke-width:1.5px,color:#7c2d12;
classDef data fill:#f3f4f6,stroke:#9aa0a6,stroke-width:1.5px,color:#333;
subgraph entry\["入口"\] GW\["LINE Gateway\
aiohttp"\]:::py WEB\["Web 後台\
Next.js"\]:::py RT\["API Routers\
FastAPI"\]:::py end subgraph ai\["客服 AI 核心"\] LOOP\["LockCore
Loop"\]:::llm LLM\["LiteLLM Provider"\]:::llm SK\["Builtin
Skills"\]:::llm end subgraph svc\["業務服務"\]
ING\["internal_ingest"\]:::py PC\["problem_card_service"\]:::py
WO\["work_order_service"\]:::py QE\["quote_engine_service"\]:::py
TL\["technician_lifecycle_service"\]:::py AU\["auth_service"\]:::py end
subgraph infra\["外部介接"\] OBX\["Outbox Worker"\]:::py FX\["Flex
Builders"\]:::py HUB\["WS Hub"\]:::py end LINEAPI\["LINE Messaging
API"\]:::py DB\["PostgreSQL\
saas.\*"\]:::data GW --\> LOOP LOOP --\> LLM LOOP --\> SK GW --\> ING
WEB --\> RT RT --\> PC RT --\> WO RT --\> QE RT --\> TL RT --\> AU ING
--\> PC ING --\> QE WO --\> QE PC --\> DB WO --\> DB QE --\> DB TL --\>
DB AU --\> DB WO --\> OBX QE --\> OBX OBX --\> FX OBX -. "推送 Flex"
.-\> LINEAPI WO -. "事件廣播" .-\> HUB HUB -. "WS 推送" .-\> WEB

</div>

<div class="figcap">

圖三　功能模組呼叫關係（橫向依賴方向）

</div>

<div class="note">

<span class="label">關鍵節點</span>**work_order_service**
為派工與完工硬閘的匯流中樞；**Outbox Worker** 是所有 LINE
外送的單一出口；**internal_ingest** 是 LINE 對話與後台之間的唯一橋接；而
AI 端的 `transfer_to_human`
是進入後台系統的單一接點。此四者為未來擴充與權限收斂的關鍵改點。

</div>

## <span class="section-no">五、</span>職責泳道圖

本圖以一次完整工單執行為例，呈現各角色在時間軸上的互動。客服 AI
與後台業務拆為獨立泳道；對話持久化採射後不理（fire-and-forget）並行，LINE
外送由背景工作者輪詢推送。

<div class="mermaid">

sequenceDiagram autonumber participant C as 客戶（LINE） participant AI
as AI 客服 participant CS as 客服後台 participant QE as 報價引擎
participant T as 技師 participant SYS as 系統（API／DB／Outbox） Note
over T,SYS: 前置：技師須經後台核准，status＝active 方可被派工 C-\>\>AI:
LINE 文字訊息 AI-\>\>AI: 意圖判斷（決策樹） AI-\>\>SYS: 呼叫
transfer_to_human（escalation） par 並行（互不依賴） AI--\>\>C:
回覆「已為您轉接專員」 and SYS-\>\>CS: 建立 AI 草擬問題卡 end
CS-\>\>SYS: 補齊欄位並確認（完整度 ≥ 0.8） CS-\>\>SYS:
開立工單（公單號） CS-\>\>QE: 建立報價並送出 QE-\>\>SYS:
寫入外送佇列（quote_proposal） loop 背景輪詢（每 10 秒） SYS-\>\>C:
推送報價 Flex end C-\>\>SYS: postback 同意（q:a） SYS-\>\>QE: 驗擁有權 →
狀態轉 accepted QE-\>\>CS: 同步「客戶已同意」至對話管理 CS-\>\>SYS:
派工（檢查 accepted 報價＋active 技師） SYS-\>\>T: 通知新工單 T-\>\>SYS:
接單 → 到場 → 門檢 → 完工（硬閘） SYS-\>\>C: 通知工單已完工待確認
C-\>\>SYS: 確認結案並評分

</div>

<div class="figcap">

圖四　職責泳道圖（單次工單執行之跨角色時序）

</div>

## <span class="section-no">六、</span>AI 客服的角色與決策範圍

AI 客服由大型語言模型驅動，經 LiteLLM
以模型字串路由多家供應商。其職責嚴格限縮於「對話判斷與知識回覆」，並透過工具白名單限制可執行動作。以下分述其執行、未執行與失效情境。

### 執行（AI 負責）

- 意圖分類與紅線決策樹判斷（依
  <span class="pill llm">locksmith-cs-sop</span> 行為層 SOP）。
- 查詢產品知識並回覆可自助解決之問題（依
  <span class="pill llm">locksmith-product-knowledge</span> 事實層）。
- 判斷是否需轉交真人，並呼叫 `transfer_to_human` 寫入轉接紀錄。
- 維護 per-user 對話記憶（每輪結束抽取與寫入）。
- 可用工具白名單僅六項：`read_file`、`list_dir`、`find_files`、`grep`、`web_search`、`transfer_to_human`。

### 未執行（AI 不碰）

- 不自行開立工單、不寫入任何業務狀態。
- 不執行派工、不產生報價金額、不觸碰金流與結算。
- 報價同意與拒絕由 LINE postback 觸發確定性 API，非由 AI 判讀文字決定。
- 寫入、編輯、執行命令列、影像辨識等高風險工具均已自白名單移除。

### 失效情境（防護設計）

- 模型呼叫失敗時回傳哨兵值，閘道改以友善文字回覆，不外洩錯誤細節。
- 對話處於真人接管中（escalated）時，AI 暫停回覆，僅持久化訊息。
- 對話持久化與轉接通知採射後不理，逾時不阻塞客戶回覆路徑。

<div class="note">

<span class="label">鐵律</span>進入後台系統的唯一入口為
`transfer_to_human`。凡 AI
對客戶承諾「將為您安排」之情境，皆須實際呼叫此工具，否則訊息不會進入後台、不會生成問題卡。此設計杜絕「AI
說了卻沒做」的靜默失敗。

</div>

## <span class="section-no">七、</span>完整流程對照表

### 工單主流程

| 階段 | 執行者 | 工作內容 | 關鍵閘門／狀態 |
|----|----|----|----|
| 1 | 客戶 | LINE 發送文字訊息 | — |
| 2 | AI 客服 | 意圖判斷；可自助則直接回覆知識 | — |
| 3 | AI 客服 | 需真人／派工時呼叫 `transfer_to_human` | 進系統唯一入口 |
| 4 | 系統 | 建立 AI 草擬問題卡，對話轉真人接管 | status＝incomplete |
| 5 | 客服 | 補齊品牌／型號／地址等欄位並確認 | 完整度 gate ≥ 0.8 |
| 6 | 系統 | 開立工單，產生公單號 | created |
| 7 | 報價引擎 | 建立報價草稿、帶入對客價（內部成本遮蔽） | draft |
| 8 | 報價引擎 | 送出並推 LINE 報價卡，凍結價格快照 | sent（超門檻需先核准） |
| 9 | 客戶 | 於 LINE 點同意／拒絕（postback） | 擁有權驗證 403 |
| 10 | 系統 | 狀態轉 accepted／rejected，同步至對話管理 | D4 過期視同未同意 |
| 11 | 系統 | 派工：指派技師 | D2 須 accepted 報價＋active 技師 |
| 12 | 技師 | 接單 → 到場 → 門檢 | 門檢須先有到場事件 |
| 13 | 技師 | 完工回報（照片、簽名、序號） | 完工三道硬閘 |
| 14 | 客戶 | 確認結案並評分 | confirmed（終局） |

表一　工單由進線至結案之階段、執行者與工作內容

### 師傅／廠商上架流程

| 階段 | 執行者 | 工作內容 | 關鍵閘門／狀態 |
|----|----|----|----|
| 1 | 技師／廠商 | 線上註冊（廠商須填公司名與八碼統一編號） | email＋角色複合唯一 |
| 2 | 系統 | 建立帳號與檔案 | status＝pending_approval |
| 3 | 技師／廠商 | 待核准期間可登入取得權杖 | 登入不檢核狀態 |
| 4 | 後台（管理／派工） | 於列表檢視待核准清單，點「核准」按鈕 | 角色限 DISPATCH_ROLES |
| 5 | 系統 | 原子更新狀態並寫入稽核事件 | pending_approval → active |
| 6 | 系統 | 唯有 active 技師方可被排班與派工 | 派工前置條件 |
| — | 後台 | 另有拒絕、暫停、復權、終止四種狀態轉移（皆留稽核） | terminated 為不可逆終態 |

表二　師傅與廠商之註冊與核准生命週期

<div class="footer">

智慧鎖 AI 客服與派工平台 · 系統技術說明 · 內容依程式碼查證產出

</div>

</div>
