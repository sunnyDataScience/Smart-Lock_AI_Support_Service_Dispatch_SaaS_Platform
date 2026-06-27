<!-- 由 _audit/owner-spec-compliance-and-pending-decisions-20260627.html 自動轉出的 markdown 源（gen_docs_html.py）-->

<div class="wrap">

# 🔒 智慧鎖 AI 派工 SaaS — 系統就緒度 × 待業主拍板工項 × 近期實作測試盤點報告

<div class="sub">

給主管（Irene／Johnson）回報用 · 對齊「接單從客服一路串到工單 →
鎖匠多租戶上線」三角色情境

</div>

<div class="meta">

產出日期：2026-06-27 ｜ 撰寫：啟恆 + Claude（對 code / migration /
測試實查，非文件自評）\
來源規格：`20260617資料/01-workorder-erp-final-spec-20260520.xlsx`（M01–M20
模組地圖 + Q&A 決策庫 + 業務規則庫 +
權限角色矩陣）、`20260617資料/02-phased-test-plan-alpha-beta-rc-ga-20260617.xlsx`（四階段測試矩陣
194 項）、`20260617 lock-AI 會議記錄.md`（工作順序拍板）\
盤點底稿：`docs/_audit/module-completion-audit-M01-M20-20260624.md`（40-agent
對抗式驗證）、`docs/5-views/test-plan-coverage-report-20260620.md`（測試覆蓋）、`docs/4-exploration/CR-0104~0107`（近期實作）

</div>

<div class="toc">

<div>

一、[執行摘要（一頁看懂）](#s1)

</div>

<div>

二、[業主拍板工作順序 7 步 — 現況對照](#s2)

</div>

<div>

三、[三類租戶 / 三個角色對齊狀況](#s3)

</div>

<div>

四、[M01–M20 模組完成度（對規格）](#s4)

</div>

<div>

五、[核心目標：接單→工單→鎖匠 端到端盤點](#s5)

</div>

<div>

六、[⭐ 待業主／人員拍板的工項清單](#s6)

</div>

<div>

七、[這幾天的實作 × 手動測試紀錄](#s7)

</div>

<div>

八、[測試覆蓋現況（對齊測試計畫 excel）](#s8)

</div>

<div>

九、[需要你補的「技術細節定義」清單](#s9)

</div>

<div>

十、[給主管的回報重點 + 下一步](#s10)

</div>

</div>

## 一、執行摘要（一頁看懂）

<div class="cards">

<div class="card blue">

<div class="n">

~45%

</div>

<div class="l">

M01–M20 平均端到端完成度（對完整規格）

</div>

</div>

<div class="card green">

<div class="n">

5/7

</div>

<div class="l">

會議拍板工作順序步驟 已就緒

</div>

</div>

<div class="card amber">

<div class="n">

2/14

</div>

<div class="l">

Phase I「Build-Now」模組完全就緒（M05、M08）

</div>

</div>

<div class="card blue">

<div class="n">

194 / 96.4%

</div>

<div class="l">

測試計畫項數 / 已實作功能加權覆蓋率

</div>

</div>

<div class="card green">

<div class="n">

1034+

</div>

<div class="l">

pytest 通過（api 914 + agent 120，0 fail）

</div>

</div>

<div class="card red">

<div class="n">

19

</div>

<div class="l">

待你（業主）拍板的工項（§六）

</div>

</div>

</div>

<div class="note">

**三句話結論：**

1.  **主線「客服 → 工單 → 報價 → 派工 → 完工」的 happy path
    已可端到端跑通並實機驗證**（CR-0095 報價 LINE 同意 + 派工硬閘 + LINE
    推送斷鏈修復已上線 prod），這正是「接單能順利串起來」的核心訴求。
2.  **但對照業主完整規格（M01–M20），平均端到端完成度約 45%**——檔案 /
    端點 /
    migration「都在」，大量功能卡在部分完成、假資料、或缺業務規則。**測試覆蓋率
    96.4%
    衡量的是「已實作功能」，不是「規格完成度」**（兩個維度，會議已警示「AI
    100% 覆蓋率不可信」，本報告分開呈現，見 §八）。
3.  **剩下要往前推的卡點，大多不是工程量，是「待你拍板的業務規則」**（急件
    / 夜間定義、師傅核准標準、班別、扣款項目…）——AI
    不可腦補（治理紅線），§六 + §九 列齊待你定義的項目。

</div>

## 二、業主拍板工作順序 7 步 — 現況對照

依 `20260617 會議記錄 §七` 拍板的順序逐步盤點（Lite 版 =
第一階段：多租戶骨架 + 註冊，不做金流 / 不做自動媒合）。

| \# | 會議拍板步驟 | 狀態 | 現況證據（這幾天做到哪） |
|----|----|----|----|
| 1 | 補公單系統欄位（對 Irene esales PDF / Johnson 紙本） | <span class="b b-ok">✅ 就緒</span> | 派工單 6 模組 24 欄補完（CR-0026/0043）+ 前端 `DispatchOrderView` 內嵌編輯（CR-0091）+ 工單詳情對話逐字稿。成本明細只在後台、客戶端只看最終價（符合會議決議 §10.4）。 |
| 2 | 對 Excel 跑功能盤點（Ultra Code workflow） | <span class="b b-ok">✅ 就緒</span> | 已產出 **M01–M20 完成度盤點**（40-agent 對抗式，06-24）+ **四階段測試覆蓋報告**（06-20）。本報告 §四 / §八 即其彙整。 |
| 3 | 加廠商 / 師傅註冊系統（發案者 / 接案者兩路由，資料庫分開） | <span class="b b-ok">✅ 就緒</span> | 師傅註冊→**pending_approval→後台核准→active**（CR-0103 補核准入口 + 修核准 404）；廠商註冊 + 統一編號 8 碼（CR-0089）；同一 email 可兼任技師+廠商（CR-0090）；技師端響應式 + 登入儀表板（CR-0088）。師傅=共用人才池、廠商=各自隔離。 |
| 4 | 補登入 / 忘記密碼 / 5 種角色權限隔離 | <span class="b b-ok">✅ 就緒</span> | 自助忘記密碼 email 重設（CR-0025）；**80 個敏感寫入端點補角色檢查**（原本任何登入者可寫金流 / 設定，CR-0092 硬化）；**完整 5 角色系統 + 後台建非-admin 帳號**（CR-0094，解「只有 admin」）。 |
| 5 | 派工模式切換（租戶手動派 / 平台代派 / 自動媒合） | <span class="b b-part">🟡 部分</span> | **後端切換 API 已做**（CR-0030：`manual / platform_paid / auto_match` 三檔可設 + 稽核）；**手動派工可動**。但**「自動媒合」引擎本身仍是 stub**（`auto_dispatch_attempts` 回 `[]`）＝第二階段；前端「租戶派/平台代派」切換開關的營運 UI 待確認補齊。 |
| 6 | Alpha + Beta 測試 | <span class="b b-part">🟡 進行中</span> | **Alpha（內部）**：pytest 1034+ 全綠 + 測試計畫就緒（§八）。**Beta（Irene/Johnson 真人點測）**：點測腳本已備、待實際進系統 + LINE 點測。會議定調 Lite 版只需測到 Beta。 |
| 7 | （下一輪）Multi-tenant 三類租戶骨架 + 自動媒合 | <span class="b b-def">⏸️ 第二階段</span> | 會議定調「v1 仍 single-tenant by Chairlock，先補齊 + Beta 通過再轉 multi-tenant」（§10.11）。三類租戶 Agent/DB 隔離設計 + LINE Token 分發機制屬下一輪。 |

<div class="note">

✅ **會議交辦的 13 個 Action Item**，與工程相關的（#1 公單欄位、#3
註冊、#4 密碼權限、#5 SOP ID 洩漏、#6 LINE 公單回傳斷鏈、#7
派工模式）**大多已落地**——其中會議當場打臉的三個洞（LINE 公單回傳斷鏈 /
知識庫洩漏內部 ID / 5 角色只有 admin）**都已修復**（CR-0095 /
fix-kb-cases / CR-0094）。

</div>

## 三、三類租戶 / 三個角色對齊狀況

對齊昨天與 Johnson / Irene 開會的三角色情境（接案方 / 派案方 /
使用者）。

<table>
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th width="120">角色（會議用語）</th>
<th>對應實體</th>
<th width="80">狀態</th>
<th>已做 / 缺口</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>接案方</strong><br />
（鎖匠 / 師傅）</td>
<td>各地獨立鎖匠，來平台註冊進案件池接單</td>
<td><span class="b b-ok">✅ 就緒</span></td>
<td>註冊 + 核准 + 生命週期（暫停/復權/終止）+ 技師端決策屏 +
詳情頁（可用狀態/等級/認證/佣金/獎懲全轉真）。<strong>全平台共用人才池</strong>（<code>technicians</code>
無租戶欄，可被不同品牌派）。</td>
</tr>
<tr>
<td><strong>派案方</strong><br />
（品牌商 / 鎖店 / 經銷商）</td>
<td>賣鎖、客戶來修但自己沒師傅，把案件丟進平台</td>
<td><span class="b b-part">🟡 部分</span></td>
<td>廠商註冊 + 統編 + 廠商專區頁 + <strong>跨範圍存取一律擋（fail-closed
403）各廠商隔離</strong>。缺口：Partner Portal 自助發案 / 對帳屬
<strong>Phase III</strong>（會議 §11 明示延後）。</td>
</tr>
<tr>
<td><strong>使用者</strong><br />
（用戶 / 客戶）</td>
<td>LINE 進線報修的終端客戶</td>
<td><span class="b b-part">🟡 部分</span></td>
<td>LINE 進線 → AI 問題卡 → 工單 → 報價 LINE 同意可動；Customer 主檔 v2
CRUD + 歷史聚合。缺口：<strong>M01 入口僅 LINE 單一渠道</strong>（規格要
8 渠道：電話/web/品牌/鎖店/經銷/建商/推薦），完成度 12%；Device
設備主檔、Site Group 社區案未建。</td>
</tr>
<tr>
<td><strong>平台 multi-tenant 本身</strong></td>
<td>承接「外包仲介」角色（類比 Uber / 外勞仲介）</td>
<td><span class="b b-def">⏸️ 第二階段</span></td>
<td>v1 仍 single-tenant by Chairlock。三類租戶骨架（Agent skill / 報價 /
客戶資料獨立，公單池 / 師傅池共享）+ LINE Webhook URL/Token 分發 =
下一輪（Beta 後）。</td>
</tr>
</tbody>
</table>

## 四、M01–M20 模組完成度（對規格）

來源：40-agent
對抗式盤點（2026-06-24），以「端到端可動率」而非「檔案存在率」評定。**M07
師傅**於 06-24 後再經 CR-0103/0104/0106/0107
大幅補強（詳情頁全轉真），實際已高於下表 48%。

<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 18px;margin:12px 0">

<div class="modrow">

<div class="modname">

M01 客戶入口 Intake <span class="modn">D1</span>

</div>

<div class="bar">

<div class="seg cov" style="width:12%">

</div>

</div>

<div class="modpct">

12%

</div>

</div>

<div class="modrow">

<div class="modname">

M02 客戶/地址/設備主檔 <span class="modn">D1</span>

</div>

<div class="bar">

<div class="seg cov" style="width:42%">

</div>

</div>

<div class="modpct">

42%

</div>

</div>

<div class="modrow">

<div class="modname">

M03 AI 分診/ProblemCard <span class="modn">D2</span>

</div>

<div class="bar">

<div class="seg cov" style="width:48%">

</div>

</div>

<div class="modpct">

48%

</div>

</div>

<div class="modrow">

<div class="modname">

M04 報價/價格/核准 <span class="modn">D2</span>

</div>

<div class="bar">

<div class="seg cov" style="width:55%">

</div>

</div>

<div class="modpct">

55%

</div>

</div>

<div class="modrow">

<div class="modname">

M05 WorkOrder 狀態機 <span class="modn">D2</span>

</div>

<div class="bar">

<div class="seg cov" style="width:78%">

</div>

</div>

<div class="modpct">

78%

</div>

</div>

<div class="modrow">

<div class="modname">

M06 派工/媒合/排程 <span class="modn">D2</span>

</div>

<div class="bar">

<div class="seg cov" style="width:36%">

</div>

</div>

<div class="modpct">

36%

</div>

</div>

<div class="modrow">

<div class="modname">

M07 師傅人力管理 <span class="modn">D3</span>

</div>

<div class="bar">

<div class="seg cov" style="width:48%">

</div>

</div>

<div class="modpct">

48%↑

</div>

</div>

<div class="modrow">

<div class="modname">

M08 現場施工/行動 <span class="modn">D2</span>

</div>

<div class="bar">

<div class="seg cov" style="width:75%">

</div>

</div>

<div class="modpct">

75%

</div>

</div>

<div class="modrow">

<div class="modname">

M09 照片/證據鏈 <span class="modn">D6</span>

</div>

<div class="bar">

<div class="seg cov" style="width:55%">

</div>

</div>

<div class="modpct">

55%

</div>

</div>

<div class="modrow">

<div class="modname">

M10 品牌/商品/BOM/庫存 <span class="modn">D3</span>

</div>

<div class="bar">

<div class="seg cov" style="width:36%">

</div>

</div>

<div class="modpct">

36%

</div>

</div>

<div class="modrow">

<div class="modname">

M11 付款/應收 AR/退款 <span class="modn">D4</span>

</div>

<div class="bar">

<div class="seg cov" style="width:36%">

</div>

</div>

<div class="modpct">

36%

</div>

</div>

<div class="modrow">

<div class="modname">

M12 師傅/品牌月結 AP <span class="modn">D4</span>

</div>

<div class="bar">

<div class="seg cov" style="width:52%">

</div>

</div>

<div class="modpct">

52%

</div>

</div>

<div class="modrow">

<div class="modname">

M13 客訴/保固/RMA <span class="modn">D5</span>

</div>

<div class="bar">

<div class="seg cov" style="width:20%">

</div>

</div>

<div class="modpct">

20%

</div>

</div>

<div class="modrow">

<div class="modname">

M14 Partner Portal <span class="modn">D1 · Phase III</span>

</div>

<div class="bar">

<div class="seg cov" style="width:10%">

</div>

</div>

<div class="modpct">

10%

</div>

</div>

<div class="modrow">

<div class="modname">

M15 異常/核准/風控 <span class="modn">D2</span>

</div>

<div class="bar">

<div class="seg cov" style="width:56%">

</div>

</div>

<div class="modpct">

56%

</div>

</div>

<div class="modrow">

<div class="modname">

M16 聊天/通知/溝通 <span class="modn">D6</span>

</div>

<div class="bar">

<div class="seg cov" style="width:42%">

</div>

</div>

<div class="modpct">

42%

</div>

</div>

<div class="modrow">

<div class="modname">

M17 權限/安全/稽核 RBAC <span class="modn">D6</span>

</div>

<div class="bar">

<div class="seg cov" style="width:64%">

</div>

</div>

<div class="modpct">

64%

</div>

</div>

<div class="modrow">

<div class="modname">

M18 系統設定/主檔配置 <span class="modn">D6</span>

</div>

<div class="bar">

<div class="seg cov" style="width:52%">

</div>

</div>

<div class="modpct">

52%

</div>

</div>

<div class="modrow">

<div class="modname">

M19 報表/BI/KPI <span class="modn">D6</span>

</div>

<div class="bar">

<div class="seg cov" style="width:56%">

</div>

</div>

<div class="modpct">

56%

</div>

</div>

<div class="modrow">

<div class="modname">

M20 AI 營運/知識庫治理 <span class="modn">D6</span>

</div>

<div class="bar">

<div class="seg cov" style="width:22%">

</div>

</div>

<div class="modpct">

22%

</div>

</div>

</div>

<div class="warn">

⚠️ **對抗驗證揪出 77 個「假綠」旗標**（散佈 18/20
模組），四類系統性問題：① mock 主檔未轉正、② 金額/規則
hardcode（違反規格「金額/比例必須 configurable」紅線）、③
軟閘偽裝硬閘（有 DEFAULT 無 NOT NULL/CHECK）、④ 測試假綠（FakeConn mock
DB）。**近兩週開發的主軸正是逐一消滅這些假綠**（如 CR-0104
把師傅可用狀態/等級的硬補常數接成真值）。

</div>

## 五、核心目標：接單→工單→鎖匠 端到端盤點

這是昨天 Johnson / Irene
開會的核心訴求：「確保接單可以順利，從客服一路串到工單，然後鎖匠可以上線多租戶」。

### 5.1 主線 happy path（已可端到端，實機驗證過）

<div class="flow">

客人(LINE) ── 進線詢問 ──▶ <span class="green">AI 草擬問題卡</span> ──▶
客服確認 ──▶ <span class="green">開單(工單 created)</span> ──▶ 內部估價
→ 外部報價(草稿→送審→核准) ──▶ <span class="green">推 LINE 報價
Flex</span> ──▶ 客戶點「同意」 ──▶ <span class="amber">報價
accepted（硬閘：沒同意報價派不了工）</span> ──▶ 派工 assign ──▶
師傅技師端接單 accept ──▶ 到場 → 開工檢查 ──▶
<span class="amber">完工回報（硬閘：照片≥3 + 客戶簽名）</span> ──▶
確認結案 confirmed(終態)

</div>

<div class="note">

這條鏈在 **CR-0095（06-22）**打通並上線 prod：報價 LINE 同意（真
postback + 網頁 fallback）、派工硬閘（無 accepted
報價→409）、完工硬閘（照片≥3 + 簽名）、以及修掉「LINE
推送從沒送達」的真根因（outbox worker
ImportError）。**「接單順利串起來」這個訴求，主線已成立。**

</div>

### 5.2 對「完整規格」的 8 站，仍有缺口（Phase I Exit 尚未全綠）

| 流程站 | 模組 | 就緒 | 主要卡關點 |
|----|----|----|----|
| 入口建案 Intake | M01 12% | <span class="b b-no">❌</span> | 無全渠道 Case 實體，僅 LINE；缺 8 渠道來源、缺「報價前先建 Case」gate、缺首次回應 SLA 計時 |
| AI 分診 | M03 48% | <span class="b b-no">❌</span> | 規格 5-state（Need Photo/Need Human/Closed Remote）未實作；五向分診無結構化輸出；升級靠 LLM 自律非硬閘 |
| 報價 Quote | M04 55% | <span class="b b-no">❌</span> | 內部成本未拆維度（只有單一 unit_price，缺工資/材料/車馬/毛利分科） |
| 付款閘 Payment | M11 36% | <span class="b b-no">❌</span> | 金流 service 寫齊但**無 router 註冊（API 不可達）**；三軌支付待 provider 選型——屬第二階段 |
| 工單 WorkOrder | M05 78% | <span class="b b-ok">✅</span> | 狀態機可動；缺集中式 transition matrix（8 組散落集合） |
| 派工 Dispatch | M06 36% | <span class="b b-no">❌</span> | **搶單池**（FOR UPDATE 防重領 / low-risk 分類 / 車程過濾）MISSING；自動媒合 stub——屬第二階段 |
| 現場施工 Onsite | M08 75% | <span class="b b-ok">✅</span> | 可動；客戶簽名仍技師同機 canvas，非客戶 LIFF 獨立簽收 |
| 證據 Evidence | M09 55% | <span class="b b-no">❌</span> | legal_hold 有欄位 + cron，但無 API/UI 設定保固/爭議保存緩衝 |

<div class="note">

**怎麼解讀「主線可動」vs「8 站只 2 站就緒」的落差**：主線 happy
path（5.1）是**把已實作的環節串成一條可示範的路**；8 站的 %
是**對照完整規格**（8 渠道、成本分科、金流 provider、搶單池…）。給 Beta
點測「跑一張單」沒問題；要宣稱「規格 Phase I
全做完」則還沒到。金流（M11）與自動媒合（M06）兩個大缺口，**會議本就定調第二階段**，不阻擋
Lite 版 Beta。

</div>

## 六、⭐ 待業主／人員拍板的工項清單

這是「前幾天有說需要人員確認」的工項彙整。核心原則：**這些缺的不是工程量，是業主必須拍板的業務規則；AI
不可腦補**（change-governance 紅線；ERP spec Q121 明令「師傅扣款不能交給
AI 或工程師自行假設」）。

### A. 阻擋性業務規則（不定義就只能腦補 / 算不了真錢）

| ID | 項目 | 來源 | 現況 | 待你 |
|----|----|----|----|----|
| <span class="q">Q-09</span> | 師傅分潤公式（依服務/區域/材料/合約拆分） | ERP「13 待決策」原標待回答 | <span class="b b-ok">已裁決</span> 核准草稿費率上線 | —（已解；CR-0106 落地） |
| <span class="q">Q-03</span> | 急件觸發條件 | ERP Q&A 待回答 | <span class="b b-part">加成 OFF</span> | ⛔ 定義「什麼算急件」 |
| <span class="q">Q-04</span> | 夜間時段定義 | ERP Q&A 待回答 | <span class="b b-part">加成 OFF</span> | ⛔ 定義夜間起訖時段 |
| <span class="q">Q121</span> | 師傅各扣款項目 + 金額（未繳現金/未退料/客訴/返工…） | ERP spec 明令不可 AI 假設 | <span class="b b-part">改主管手動登錄</span> | ⛔ 逐項拍板金額/觸發 |
| — | S 級費率 | 「19 鎖匠等級」只定 A/B/C | <span class="b b-part">S 暫映 LV-A</span> | ⛔ 補 S 級拆帳數值 |

### B. 流程決策點（可以這樣也可以那樣，需你定方向）

出自 `今晚報告底稿-20260623 §四`，這幾天測試陸續測出。

| \# | 決策點 | 現況 / 已先修一版 | 待你確認 |
|----|----|----|----|
| 1 | 同一客人多個問題怎麼分單 | 已修：舊卡「已轉工單/已結案」→ 開新卡；處理中 → 併入（CR-0096） | 這個界線 OK？還是「客服一確認就鎖卡」更符實務？ |
| 2 | 誰能「接單」（代接權限） | 後台目前可越權接單；已盤點待收斂 | 主管代接權限給到哪層（只主管？派工員也行？） |
| 3 | 客戶 LINE 同意報價後要不要「自動排單」 | 同意只解開派工硬閘，仍後台手動指派（自動媒合是 stub） | A 維持手動（可控）／ B 同意後自動進排單佇列（要定排單規則） |
| 4 | 師傅核准的審核標準 | 後台人工核准，無明文標準 | 核准要看哪些條件（證照？保證金？面試？）還是先維持人工把關 |
| 5 | 對話訊息串是否跟問題分開 | 問題卡/工單已能分開，但同客多卡仍共用同一條 LINE 對話串 | 要完全分需「每問題開新對話」＝較大改動，建議排後續 |

### C. 待規則才能動工的模組（缺來源未定義的業務規則）

<table>
<colgroup>
<col style="width: 50%" />
<col style="width: 50%" />
</colgroup>
<thead>
<tr>
<th width="160">模組</th>
<th>缺什麼定義</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>本週排班</strong><br />
（師傅詳情頁主區，唯一仍示意的區塊）</td>
<td>① 班別定義（早/晚/值班各自起訖時間）② 排班來源（人事預排 roster vs
工單/休假反推，資料模型完全不同）③ 週起始 + 時區 ④「值班」語意（on-call
vs 出勤）⑤ 誰能排班 ⑥ admin 在他人詳情頁的權限邊界</td>
</tr>
<tr>
<td><strong>師傅等級「自動計算」</strong><br />
（現為手動指派，可選升級）</td>
<td>升降級門檻（完成單數 / 平均評分 / 年資 + 各級數值）、計算時點（即時
vs 月結重算）、彙總規則</td>
</tr>
</tbody>
</table>

### D. 工程假設待你確認（非財務規則、可動態調整、一行可改）

| 假設                 | 目前採值                               |
|----------------------|----------------------------------------|
| 新師傅等級預設值     | `C`（入門級），admin 可調升 S/A/B/C    |
| 認證「即將到期」門檻 | 到期前 **30 天** 內標示                |
| 認證維護方式         | admin 後台登錄（非技師自助上傳憑證檔） |

### E. 階段順序（你已部分裁決，列出供主管知悉）

- **佣金 / 獎懲**：原屬第二階段（Beta 後），你 06-27
  裁決「**提前到本階段**」並核准草稿費率 → 已落地（CR-0106/0107）。
- **金流代收代付（M11）/ 自動媒合（M06）/ Multi-tenant
  三類租戶**：會議定調**維持第二階段（Beta 後）**——若要提前需另行裁決。

## 七、這幾天的實作 × 手動測試紀錄

06-21～06-27
與你一起逐頁實測、發現問題、修正的完整清單（每一項都附「怎麼手動測的」）。多數為你逐頁實測時當場回報
→ 我修 → Playwright / curl / live LINE 驗證。

<table>
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th width="80">CR / 日期</th>
<th>做了什麼（業主回報 → 修正）</th>
<th>手動測試方式</th>
<th width="80">狀態</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>CR-0088</strong><br />
06-21</td>
<td>技師端響應式版型（原桌面固定 480px 置中）+
登入後決策屏儀表板（收入/上線大鈕/今日行程/熱力圖）。順手修 2
個假綠：my-orders / 對帳單用錯 ID 過濾，技師永遠查無自己的單。</td>
<td>tsc 0 + docker build + 5 角度對抗審查 + 實機 register→login→打端點全
200；2 端點 dashboard-summary / heatmap 200。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0089</strong><br />
06-21</td>
<td>廠商註冊 404 修復（路徑缺 <code>/api/v1</code>）+ 台灣 B2B 統一編號
8 碼必填。</td>
<td>test_cr_0089 9/9；實機帶統編 201 落庫、缺統編/非 8 碼 422。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0090</strong><br />
06-21</td>
<td>同一人可兼接案(技師)+發案(廠商)：email
由全域唯一改「每角色唯一」。</td>
<td>test_cr_0090 4/4 + 267 unit；實機技師 201→同 email 廠商 201→同 email
技師再註冊 409。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0091<br />
/0092</strong><br />
06-21</td>
<td><strong>權限硬化</strong>：80
個敏感寫入只檢查登入沒檢查角色（任何人可寫金流/設定）→ 補
<code>role_required</code>。<strong>派工單視圖</strong>：work_orders 有
PDF 6 模組欄但前端零編輯 UI → 新 DispatchOrderView。+ 補 66 個 i18n 缺
key。</td>
<td>test_cr_0091 5/5 + test_cr_0092 角色隔離 + <strong>全套件 1386
passed / 0 回歸</strong> + tsc 0 + API smoke 401。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0093<br />
/0094</strong><br />
06-21</td>
<td><strong>完整 5 角色系統</strong>（解「只有 admin」）：新
create_staff_user + 後台 /admin/staff 建 5 種角色帳號 + reviewer
對齊。技師完工頁改打正規硬閘端點（原撞 403 完工流程壞掉）。報價→發票動作
+ config 治理 UI。</td>
<td>test_cr_0029/0094 + <strong>全套件 1396 passed / 0 回歸</strong> +
tsc 0。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0095</strong><br />
06-22</td>
<td><strong>報價 LINE 同意流程貫通</strong> + 派工硬閘（無 accepted
報價→409）+ <strong>揪出 LINE 推送斷鏈真根因</strong>（outbox worker
ImportError，所有 LINE 推送從沒送達）+ SOP 補強 + 技師核准按鈕。</td>
<td>test_cr_0095 10/10 + 技師 v2 9/9 + quote 42/0 回歸 + agent 120 + tsc
0。<strong>api+web 已部署 Cloud Run</strong>（image dfdebdd8）。</td>
<td><span class="b b-ok">✅ 已上線</span></td>
</tr>
<tr>
<td><strong>CR-0096</strong><br />
06-23</td>
<td>同一 LINE 客人不同問題各自獨立成卡（原全寫在第一張卡）。migration
077 部分唯一索引。</td>
<td>test_cr_0096 3/3 + 轉工單/escalation/convert 回歸 64/0。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0097</strong><br />
06-23</td>
<td>AI 說了「已轉接真人」卻沒呼叫工具 → 問題卡靜默蒸發。channel 層兜底補
escalation。</td>
<td>test_line_gateway +6 + agent 126 passed；live LINE 重現→修復。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0101</strong><br />
06-23~25</td>
<td>報價頁建報價改「選工單」免貼 UUID（公單號可搜）+ 報價列表 scoped
到選定工單（解工單/報價混淆）+「示意資料」誤標移除 + sidebar
依開單流程重排。</td>
<td>test_wo_keyword 2/2 + 回歸 24/0 + Playwright 多案例 + tsc 0。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0102</strong><br />
06-26</td>
<td>LINE 進線講的電話自動帶入工單 customer_phone（regex
抽台灣手機，只空白時填）。</td>
<td>agent test +5 / API test +3 / convert 回歸 22 全綠 + live E2E（POST
帶 0922-371-211 → users.phone 落庫）。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td>工單電話<br />
亂碼修<br />
06-26</td>
<td>工單詳情「客戶資訊」電話顯示亂碼 → 根因把 LINE ID 當電話佔位。改綁真
customer_phone + LINE ID 獨立列。</td>
<td>Playwright 驗證面板顯「未提供 / LINE ID U3bc… / 台北市」+ tsc
0。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0103</strong><br />
06-26</td>
<td>技師詳情頁「編輯/停權/復權」是 disabled
佔位鈕（假綠：後端早能用前端沒接）→ 接線 + admin 編輯端點。<strong>+
修核准 404</strong>（後台新增技師沒建 user → 全核准不了）。</td>
<td>test_technicians_v2 38→39 passed + Playwright 編輯/停權/復權
round-trip + live 建技師→核准 200→active。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0104</strong><br />
06-27</td>
<td>師傅詳情頁假資料轉真：可用狀態（接真 online_state）+
等級（手動指派）+ 技能認證矩陣（建完整模組）。</td>
<td>技師相關 83 passed + 1 skip + Playwright（認證 modal
新增即顯「有效」、等級 PATCH=A、可用狀態真值；測試資料已清）。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0106</strong><br />
06-27</td>
<td>師傅佣金摘要轉真：發現 mock 模型錯了（抽成制 vs 實際固定工資制）→
照固定工資制重建月結引擎，讀業主核准的拆帳費率。</td>
<td>test_technician_commission 4/4 + 技師 51 passed + live E2E（丁啟恆
level=B + 完工單 → 卡片顯「本月工資 NT$1,100」）。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
<tr>
<td><strong>CR-0107</strong><br />
06-27</td>
<td>師傅獎懲紀錄轉真：mock 4 筆規則來源完全沒有（捏造）→ 改後台手動登錄
ledger + 自動帶取消失約扣款（唯一規則明確者）。守 Q121 紅線。</td>
<td>test_technician_penalty_bonus 4/4 + 技師 38 passed + live E2E（POST
手動獎金+300 + DB 取消罰 500 → 卡片顯「取消失約扣款 −500【自動】不可刪 +
高評價獎金 +300 可刪」）。</td>
<td><span class="b b-ok">待部署</span></td>
</tr>
</tbody>
</table>

<div class="note">

📦 **未部署的累積**：上表多數標「待部署」——CR-0095
之後的修正（CR-0096~0107，含 migration 077~083）**都還在
`feat/technician-detail-real-fields` 等分支、未推上 prod**。Beta
點測前需安排一次 api+web 部署把這批帶上去。

</div>

## 八、測試覆蓋現況（對齊測試計畫 excel）

這就是你之前帶我產的「測試 excel」對應的覆蓋盤點。**來源
excel**：`20260617資料/02-phased-test-plan-alpha-beta-rc-ga-20260617.xlsx`（四階段測試矩陣
194
項）。**我標注「哪些測了」的報告**：`docs/5-views/test-plan-coverage-report-20260620.{md,html}`（preview
圖：根目錄 `test-plan-report-preview.png`）。

<div class="cards">

<div class="card blue">

<div class="n">

194

</div>

<div class="l">

TI 測試項（功能）

</div>

</div>

<div class="card green">

<div class="n">

180

</div>

<div class="l">

✅ 已覆蓋

</div>

</div>

<div class="card amber">

<div class="n">

14

</div>

<div class="l">

🟡 部分覆蓋

</div>

</div>

<div class="card red">

<div class="n">

0

</div>

<div class="l">

🔴 完全缺口

</div>

</div>

<div class="card blue">

<div class="n">

96.4%

</div>

<div class="l">

加權覆蓋率

</div>

</div>

</div>

<div class="warn">

⚠️ **這個 96.4% 要怎麼跟主管講（很重要，避免重蹈會議「100%
不可信」覆轍）：**

- **96.4% =
  對「已實作功能」的測試覆蓋率**——即「有做出來的東西，有沒有測」。這個數字是**對齊真實
  pytest 執行**（api 914 + agent 120 = 1034 passed / 0
  fail）算出來的，不是 AI 自評。
- **≠ 規格完成度**。對照業主完整規格的功能完成度約 **45%**（§四
  M01–M20）。**沒做出來的功能（如金流、搶單池、8 渠道）不在這 194
  項裡，所以不會拉低覆蓋率**——這正是會議當時「100%
  覆蓋率」陷阱的本質：覆蓋率只算「測試項清單內」的東西。
- **正確說法**：「**已實作功能的測試覆蓋率 96.4%、pytest 1034
  項全綠；但對照完整規格仍有約 55%
  功能未做或部分完成，多數是待業主定義業務規則或第二階段項目。**」

</div>

### 8.1 四階段測試定義（你教的 RD 四階段）+ 本案目標

| 階段 | 誰來測 | 本案狀態 | 說明 |
|----|----|----|----|
| **Alpha** | 內部團隊（QA / 開發 / 營運） | <span class="b b-ok">大致達標</span> | pytest 1034+ 全綠 + 測試計畫人工 review 過。內部把基本 bug / 功能先測出來。 |
| **Beta** | 外部真實使用者（Irene + Johnson 點測） | <span class="b b-part">待執行</span> | 點測腳本就緒；需把這批未部署 CR 上 prod 後，Irene/Johnson 真人進系統 + LINE 點測。**Lite 版目標到此即可。** |
| RC | UAT 簽核者 | <span class="b b-def">不需（Lite）</span> | 會議拍板 Lite 版不需 RC。 |
| GA | 全體 + 壓測 | <span class="b b-def">第二階段</span> | 正式發佈 + 灰度 + 監控，留到完整版。 |

### 8.2 各模組測試覆蓋（節錄，完整見 5-views 報告）

多數模組測試覆蓋 100%（M02-M10, M12-M18），少數部分覆蓋：A05/A08/A10
75%、A12 50%、M01 92%、M11
87%。**注意**：此處「覆蓋」指測試項有對應自動化測試，與
§四「功能完成度」是兩條軸。

## 九、需要你補的「技術細節定義」清單

你問「我需要再補哪些技術細節的定義」——以下是**卡住開發、需要你（或你帶會計
/ Johnson）給定義**的清單，按優先序。給了定義我就能往下做。

| 領域 | 需要你定義的技術細節 | 卡住什麼 |
|----|----|----|
| **派工** | ① 急件觸發條件（Q-03）② 夜間時段起訖（Q-04）③ 同意報價後是否自動排單 + 排單規則 ④ 主管代接權限給到哪層 | 佣金加成、派工自動化、接單權限收斂 |
| **師傅費率** | ⑤ S 級拆帳費率（來源只有 A/B/C）⑥ 夜間/急件加成率定案（目前 0.2/0.15 是草稿）⑦ 佣金分科科目（維修/安裝/客製料 各對應哪些 service_code） | 佣金月結金額正確性 |
| **師傅管理** | ⑧ 師傅核准審核標準（證照/保證金/面試？）⑨ 班別定義（早/晚/值班起訖 + 排班來源）⑩ 等級升降門檻（若要自動計算） | 核准把關、本週排班、等級自動化 |
| **獎懲扣款** | ⑪ 各扣款/獎金項目 + 金額 + 觸發（Q121 須主管逐項拍板，不可 AI 假設） | 獎懲自動入帳 |
| **客戶入口** | ⑫ 8 渠道來源定義（電話/web/品牌/鎖店/經銷/建商/推薦如何進案）⑬ Device 設備主檔欄位 ⑭ Site Group 社區/建案案 | M01 Intake、保固起算、批次派工 |
| **流程界線** | ⑮ 同客多問題分單界線 ⑯ 對話串是否跟問題分離（較大改動） | 問題卡/對話資料整潔度 |

## 十、給主管的回報重點 + 下一步

### 回報重點（三句話版）

1.  **主線通了**：客服 → 工單 → 報價 → LINE 同意 → 派工 → 完工的 happy
    path 已端到端跑通並上線（CR-0095），會議當場打臉的三個洞（LINE 斷鏈
    / 內部 ID 洩漏 / 只有 admin）都修了。
2.  **進度誠實**：對齊真實規格的功能完成度約 45%，測試覆蓋率
    96.4%（衡量「已做功能」非「規格」）；金流 / 自動媒合 / multi-tenant
    三大塊會議本就定調第二階段。
3.  **卡點在規則不在工程**：往下推的卡點大多是「待你拍板的業務規則」（§六
    19 項 + §九 16 個技術細節定義），不是寫不出來。

### 建議下一步

- **A. 安排一次部署**：CR-0096~0107（含 migration 077~083）都還沒上
  prod，Beta 點測前需 api+web 部署一次帶上去（等你「授權部署」）。
- **B. 你回我 §九
  的技術細節定義**（哪怕先給急件/夜間/班別這三個最常被卡的），我就能繼續往下做。
- **C. 啟動 Beta 點測**：把系統 URL + LINE QR 給
  Irene/Johnson，依測試計畫腳本真人點測，收回饋回填測試。

<div class="note" style="margin-top:24px;color:#94a3b8;font-size:12px">

本報告為 `_audit` 稽核軌跡，以 file:line / migration /
測試實查為據，反映 2026-06-27 當下 codebase。同步輸出 `.md` 版本（由
gen_docs_html.py 產生）。各項細節索引見來源清單（頁首）。

</div>

</div>
