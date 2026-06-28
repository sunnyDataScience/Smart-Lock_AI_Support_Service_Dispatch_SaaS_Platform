---
title: UI 設計規格全面 Re-Sync 計畫 + WBS
status: active
tier: 4-exploration
created: 2026-06-28
author: Claude (Opus 4.8) — 12-叢集平行盤點 workflow（對 dev_new_arch HEAD code 實查）
scope: docs/ui/web_design_spec_prompt_pipeline/ 全部 .md spec + design_all.pen 全部 frame
relates:
  - pages/MAPPING.md            # 既有索引（凍結於 2026-04-23，本計畫收尾時全面重寫）
method: 對 ~87 條現行前端路由逐一比對「既有 .md spec + .pen mockup frame」漂移
---

# UI 設計規格全面 Re-Sync 計畫 + WBS

> **緣由**：`pages/*.md`（22 份 spec）+ `pages/design_all.pen`（56 frame mockup）最後同步是 **2026-04-23**（凍結於 IA 52 頁）。
> 前端自此一路演進到 CR-0109，**新增 ~36 條路由**、~41 條既有頁面內容漂移。業主裁決（2026-06-28）：**全面 re-sync，.md + .pen 兩者都做，分多批跨多輪。**
>
> **本檔性質**：把「全面 re-sync」這個模糊大工程，轉成可逐批打勾的 backlog。後續每批執行依本檔。

---

## 0. 治理定位（重要）

- **這不是 contract / flow / architecture 變更，是「文件追上既有 code」** → tier-5 view 同步原則「**code wins**」，**不需 CIA**。code 已存在，spec/mockup 是落後的地圖。
- **同步原則**：
  1. **code 有、spec 無** → spec 補上現況（標 `➕ code 既有`）。
  2. **spec 有、code 無**（設計先行未實作，如 MFA / surcharge tab / 租戶設定 A34-36）→ **不刪**，標 `🚧 規格先行・未實作` 保留設計意圖。
  3. **兩者都有但不符** → spec 改成符合 code（標關鍵差異），保留未實作子項為 `🚧`。
- **分工**：`.md` spec 可平行（多 agent 各改一份）；`.pen` mockup 必須序列由主 agent 透過 Pencil MCP 改（桌面 app 單一連線，並行會衝突）→ **.pen 是節流瓶頸，決定批次節奏**。

---

## 1. 盤點總表（~87 路由 / 12 叢集）

狀態：🆕 NEW（code 有、無 spec 無 frame）｜🔶 DRIFTED（有對應已不符）｜✅ IN-SYNC｜👻 SPEC-ONLY（spec/frame 有、code 無）

### 1.1 auth-settings
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /login | 🔶 | med | 14 | NONE | 缺 tenant_selector / MFA / footer / 密碼顯隱；多了 /register 連結 |
| /tech-login | 🔶 | high | 14 | NONE | redirect 應 /pool 卻去 /home；缺 OTP；識別碼用 email 非手機；非 100dvh mobile |
| /vendor-login | 🆕 | high | — | — | 全新廠商登入，無 spec |
| /register | 🆕 | high | — | — | 技師/廠商雙角色註冊，無 spec |
| /forgot-password | 🆕 | med | — | — | CR-0025 列舉防護，無 spec |
| /reset-password | 🆕 | med | — | — | token 重設，無 spec |
| /settings | 🔶 | high | 14 | NIbRH | 多 system tab；缺 surcharge tab；profile/MFA/session 多為 disabled |
| /home | 🆕 | low | — | — | 技師首頁 dashboard，無 spec |

### 1.2 dashboard-conv-pc
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /dashboard | 🔶 | med | 02 | mPqkN | KPI 改為對話導向（CR-0003）；缺 realtime_status_bar / refresh |
| /conversations | 🔶 | low | 03 | cWcAu | tab 改 all/active/waiting_human/closed；缺 channel_filter / sort |
| /conversations/[id] | 🔶 | med | 03 | ordAo | 多 CreateProblemCardModal / DiagnosticReasoningPanel |
| /problem-cards | 🔶 | low | 04 | IvId3 | 多 source filter；status enum 不符；缺 entropy badge |
| /problem-cards/[id] | 🔶 | high | 04 | eXtZf | 多 auto-resolve / auto-match / convert / export / edit modal；FMEA 仍 placeholder |

### 1.3 knowledge-base
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /knowledge-base | ✅ | low | 05 | — | redirect |
| /knowledge-base/cases | 🔶 | med | 05 | 6NfKH | PAGE_SIZE 20≠12；多 verified filter；缺 search_mode_toggle / success_rate / usage_count |
| /knowledge-base/cases/[id] | 🔶 | med | 05 | 6NfKH | 缺 usage 指標；solution 純文字非 Markdown |
| /knowledge-base/cases/[id]/edit | 🔶 | med | 05 | 6NfKH | 缺 applicable_models / RichText / dirty_close |
| /knowledge-base/cases/new | 🔶 | med | 05 | 6NfKH | 同上 |
| /knowledge-base/manuals | 🔶 | high | 05 | iooQ7 | 缺 PDF viewer；表格欄位不符；缺 progress bar |
| /knowledge-base/sop-drafts | 🔶 | med | 05 | SE1Ga | PAGE_SIZE 20≠15；缺 sort + 完整 status filter |
| /knowledge-base/sop-drafts/[id] | 🔶 | high | 05 | X2ubf | 缺 request_changes / save_draft 按鈕；缺 review_history；非 RWD |
| /knowledge-base/family-reviews | 🆕 | high | — | — | 全新「家族雙審」流程，無 spec |

### 1.4 work-orders
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /work-orders | ✅ | low | 06 | D6xEP | 列表大致符 |
| /work-orders/kanban | 🔶 | high | 06 | JedbW | 路由命名漂移：spec 預期 /work-orders/dispatch?view=kanban |
| /work-orders/map | 🔶 | high | 06 | xMjEI | 同上：spec 預期 ?view=map |
| /work-orders/[id] | 🔶 | high | 07 | GbKMe | legal_hold🔒 / SLA 真實化 / 完工報告 / 異常 / 客戶資訊；issue_bundles 結構不符；完工照片分類標籤缺 |

### 1.5 technicians
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /technicians | 🔶 | med | 08 | 4386B | 篩選用單選非 multi-select；多 inline approve |
| /technicians/[id] | 🔶 | high | 16 | KxaZT | 單頁 vs spec 三 tab 子頁；佣金/獎懲/技能矩陣已轉真（CR-0104/06/07）；排班仍 mock |
| /admin/technicians-lifecycle | 🆕 | low | — | — | FR-0044 生命週期稽核，無 spec |

### 1.6 accounting
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /accounting | 🔶 | high | 09 | CXCxi | spec 單頁 3-tab vs code 4 獨立路由；多 Reconciliations 區 |
| /accounting/invoices | 🔶 | med | 09 | fC8Bq | 獨立路由非 tab；缺 date_range / overdue toggle |
| /accounting/revenue | 🔶 | med | 09 | WiPWg | 獨立路由非 tab；granularity 控制不符 |
| /accounting/vouchers | 🆕 | high | — | — | 全新傳票/分錄頁，無 spec |

### 1.7 admin-advanced
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /admin/refunds | 🔶 | med | 10 | wUDUW | 多 CreateRefundModal / escalate / realtime |
| /admin/roles | 🔶 | med | 10 | KesCS | 多重設密碼；缺自訂角色完整流程 / 臨時授權 |
| /admin/inventory | 🔶 | med | 10 | cBWxl | 缺行內編輯 / 調撥 / 報廢；篩選選項不符 |
| /admin/audit-events | 🔶 | med | 10 | j9E5r | event type enum 不符；缺日期範圍 / actor filter / resource 欄 |
| /admin/warranty-claims | 🔶 | med | 10 | JbQPX | status enum 完全不同；缺證據燈箱；多 CreateWarrantyModal |
| /admin/warranty-claims/[id] | 🆕 | high | — | — | 全新詳情頁，無 spec |
| /admin/disputes | 🔶 | med | 10 | ftCX0 | status enum 不符；多兩階段 co-sign；缺存草稿 |

### 1.8 customers-diagnostics
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /admin/customers | 🔶 | med | 15 | E3vKS | 缺 5 個欄位（device/satisfaction/risk/preferred_tech/warranty）；統計卡多為 disabled |
| /admin/customers/[id] | 🔶 | high | 15 | E3vKS | 整個 5-tab 結構未建（profile/devices/history/financial/notes_risk）；缺 merge modal |
| /admin/customers/[id]/edit | 🆕 | high | 15 | — | spec 預期 inline tab 編輯，code 為獨立頁 |
| /admin/customers/new | 🆕 | high | 15 | — | spec 預期 Modal，code 為獨立頁 |
| /admin/ai-governance | 🆕 | high | — | — | FR-0050 AI 治理軌跡，無 spec |
| /admin/sentiment-alerts | 🆕 | high | — | — | FR-0018 情緒告警，無 spec |
| /admin/sop-feedback | 🆕 | high | — | — | FR-0051 SOP 回饋，無 spec |
| /admin/knowledge-base/sop-performance | 🔶 | med | 15 | — | code 顯示管理狀態非績效指標；缺績效表 / drilldown |

### 1.9 dispatch-reports
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /admin/dispatch-queue | 🔶 | med | 17 | w2E0T | 4 卡語義不符；pool 用簡化卡片非完整派工日誌表 |
| /admin/dispatch-manual | ✅ | low | 20 | — | 大致符（排序公式為單切換非加權）|
| /admin/reports/kpi | 🔶 | med | 17 | M59wz | 漏斗 5 階非 6；FTFR/SLA/滿意度 placeholder |
| /admin/reports/revenue | 🔶 | med | 17 | MRdMj | 缺 slice 多維 / pivot table / brush |
| /admin/reports/technician-ranking | ✅ | low | 17 | XwG89 | 大致符（sort 選項少、缺營收欄）|
| /admin/schedule-requests | 🆕 | high | — | — | 排班例外管理，無 spec |
| /admin/material-requests | 🆕 | high | — | — | 補料彙整視圖，無 spec |

### 1.10 multitenant-b2b-governance（spec 18 僅涵蓋 /admin/settings/tenant* + /admin/super/*，皆 code 無 → 👻）
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /admin/brand-b2b | 🆕 | high | — | — | FR-0047 品牌 B2B 結算，無 spec |
| /admin/config-governance | 🆕 | high | — | — | M18 設定治理 SoD 雙簽，無 spec |
| /admin/payout-rules | 🆕 | high | — | — | 技師薪酬規則表，無 spec |
| /admin/rma-quality | 🆕 | high | — | — | FR-0048 RMA 品質，無 spec |
| /admin/gdpr-forget-queue | 🆕 | high | — | — | FR-0053 GDPR 遺忘佇列，無 spec |
| /admin/api-status | 🆕 | low | — | — | 連線 smoke test 工具頁，無 spec |
| /admin/approval-inbox | 🆕 | high | — | — | FR-0049 統一審批匣（5 類），無 spec |
| A34/A35/A36 租戶設定/品牌/超管 | 👻 | — | 18 | — | spec 先行・code 未建 → 標 🚧 保留 |

### 1.11 tech-pwa
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /pool | 🔶 | high | 11 | Vv7Dq 等 | spec 全螢幕地圖+bottomsheet vs code grid 卡片清單 |
| /my-orders | ✅ | low | 12 | 1GIKj/jLA69 | 符 |
| /my-orders/[id] | 🔶 | med | 12 | CNR7a 等 | 完工表單內嵌雙簽；function test 6 項 |
| /my-orders/[id]/delay | ✅ | low | 19 | — | 符 |
| /my-orders/[id]/door-check | 🔶 | med | 19 | — | 照片 ≥3（前/中/後）vs spec 前/後 |
| /my-orders/[id]/material-request | ✅ | low | 19 | — | 符 |
| /my-orders/[id]/reschedule | 🔶 | med | 22 | — | code 7 日條 vs spec 月曆；多 cross-tab sync |
| /my-orders/[id]/scope-change | ✅ | low | 19 | — | 符 |
| /my-orders/[id]/signature | ✅ | low | 19 | — | 符 |
| /account | 🔶 | med | 13 | qFXmE 等 | 收入為 skeleton；缺 period_selector |
| /account/schedule | 🔶 | med | 19 | — | 月曆 + 每日工單數 badge；多 close-today |
| /account/statements | 🆕 | high | — | — | FR-0045 師傅薪資單，無 spec |
| /account/commission-statements | 🆕 | high | — | — | FR-0046 派工佣金單，無 spec |

### 1.12 global-orphans
| 路由 | 狀態 | 嚴重 | spec | frame | 關鍵漂移 |
|---|---|---|---|---|---|
| /notifications | ✅ | low | 21 | — | 符（preference 連結少 /admin 前綴）|
| /admin/cases | 🆕 | high | — | — | **CR-0108 進線建案**，無 spec ← Batch 1 |
| /admin/staff | 🆕 | high | — | — | 員工帳號管理，無 spec |
| /admin/exceptions | 🆕 | high | — | — | 異常管理控制臺，無 spec |
| /admin/vendor-approvals | 🆕 | high | — | — | 廠商審核，無 spec |
| /admin/quote-catalog | 🆕 | med | — | — | 報價目錄，無 spec |
| /admin/quotes | 🆕 | high | — | — | 報價工作臺，無 spec |
| /quotes/[token] | 🆕 | med | — | — | 消費者匿名報價同意，無 spec |
| /consent/[token] | 🆕 | med | — | — | 消費者匿名免責同意，無 spec |
| /scope-change/[token] | 🆕 | med | — | — | 消費者匿名加價同意，無 spec |
| /track/[token] | 🆕 | med | — | — | 消費者匿名工單追蹤，無 spec |
| /vendor | 🆕 | high | — | — | 廠商門戶，無 spec |

---

## 2. 批次計畫（WBS）

> `.pen` 序列瓶頸 → 每批先平行做完 `.md`，再由主 agent 序列補 `.pen` frame。
> 一批一分支（依專案規範），完成更新本表 §3 進度 + CHANGELOG + system-completion-status。

| 批次 | 範圍 | .md 動作 | .pen 動作 | 狀態 |
|---|---|---|---|---|
| **B1** | 進線建案（end-to-end）+ 工單詳情 spec | 新建 `24_admin_intake_cases` ✅；改 `07` 🔄 | 新建 Intake Cases frame `kjAsn` ✅；GbKMe 改 → 併入 B2 | 🔄 本輪 |
| **B2** | 工單列表/看板/地圖/**詳情** + 技師 | 改 `06`/`08`/`16`（路由命名、技師轉真） | D6xEP/JedbW/xMjEI/**GbKMe**/4386B/KxaZT | ☐ |
| **B3** | 全新 admin 孤兒頁（~17） | 新建 `25`~`41` 系列 spec | 新建對應 frame（量最大）| ☐ |
| **B4** | 帳務/進階/客戶/派工報表 | 改 `09`/`10`/`15`/`17`/`20` | CXCxi/wUDUW/E3vKS/w2E0T 等 | ☐ |
| **B5** | 技師 PWA + 認證 + 全域 + token 頁 | 改 `11`/`12`/`13`/`19`/`22`/`14`；新建 token/vendor spec | pool/order/account frame + 新 token frame | ☐ |
| **收尾** | 索引 + 鏡像 | MAPPING.md 全面重寫；標 👻 A34-36/offline | — + gen_docs_html regen | ☐ |

### 新頁 spec 編號預留（B3 / B5）
`24` intake-cases（B1）｜`25` staff｜`26` exceptions｜`27` vendor-approvals + vendor-portal｜`28` quotes-workbench + quote-catalog｜`29` approval-inbox｜`30` config-governance｜`31` payout-rules｜`32` rma-quality｜`33` gdpr-forget-queue｜`34` brand-b2b｜`35` ai-governance｜`36` sentiment-alerts｜`37` sop-feedback｜`38` schedule-requests + material-requests｜`39` technicians-lifecycle｜`40` tech-statements（薪資/佣金）｜`41` public-token-pages（consent/quote/scope-change/track）｜`42` auth-extras（vendor-login/register/forgot/reset/home）

---

## 2.1 跨切面任務（cross-cutting，獨立追蹤）

- **sidebar nav 全域漂移 → ✅ 已統一（2026-06-28 業主指出後優先處理）**：
  - 現行 `Sidebar.tsx` 為 **4 分組（開單流程／審核與例外／知識與報表／設定與主檔）+ 18 項 + 子選單**；.pen 原為 4 月「12 項平鋪」舊版，**每張 frame 各自內嵌一份**。
  - 建立**唯一正典元件 `P9Dej`「Comp — Admin Sidebar」**（對齊現行結構，置於畫布 x=1600,y=23918，screenshot 驗證完美）。
  - ⚠️ **Pencil ref/instance 渲染 bug**：把 `P9Dej` 以 `type:ref` 放進 frame 的 flex row，instance 整個塌掉不渲染（master 正常）。多種 width/height 設定皆失敗 → **改用「以 `P9Dej` 為母版、各 frame 內嵌 `C()` copy + `descendants` 覆寫該頁 active」**。代價：非 ref 的「改一處全更新」，但 `P9Dej` 仍是單一正典，未來改 nav = 改 `P9Dej` + 重新 copy propagate。
  - 已套用 **29 張 admin frame**（cases + 28 既有），各自正確標當前頁 active。**技師 PWA frame**（手機，底部 nav）與 **派工看板 `JedbW`**（全寬無 sidebar）不適用，略過。
  - ⚠️ 注意：~900px 高的 frame 完整 nav 幾乎填滿（真機側欄本就 scroll），少數最底項可能略裁，屬可接受。
  - **lucide icon 名稱對照**：active 樣式 = item frame `fill #1E3A5F` + 左 3px `#2563EB` border + padding `[10,12,10,9]`、icon `fill #2563EB`、text `#FFFFFF/600`。
  - **踩雷紀錄**：Pencil 對「fill_container 父 → fit_content 巢狀分組 frame」算高會 bug（項目重疊）→ nav 必須**平鋪**進 navSection，不可用中間分組 frame 包。

## 3. 進度

- 2026-06-28 S0 done（branch `docs/ui-spec-resync`）：12-叢集盤點 workflow 完成，產出本計畫 + WBS。
- 2026-06-28 B1 進行中（branch `docs/ui-spec-resync`）：
  - ✅ 新建 `pages/24_admin_intake_cases.md`（289 行，對 CR-0108 code 逐行查證，標 ✅ 已實作 / 🚧 規格先行）。
  - ✅ 新建 .pen frame「Admin — Intake Cases (進線建案)」`kjAsn`（clone E3vKS 改造：sidebar active=進線案件、代客建案表單卡、案件列表 4 態示例 + SLA 逾時徽章）。screenshot 驗證通過。
  - ✅ `pages/07_admin_work_order_detail.md` 對 code 同步完成（17 區塊，➕15／🚧30+；含「`MediaGallery.tsx` legal_hold 為孤兒元件、工單詳情頁實用 `LineMediaGallery`」之誠實記錄）。
  - ✅ **sidebar 全域統一**（見 §2.1）：建正典元件 `P9Dej` + propagate 至 29 張 admin frame，各標當前頁 active。業主 2026-06-28 指出 sidebar 漂移後優先完成。
  - GbKMe（工單詳情 frame）主內容 surgery（SLA/完工/legal_hold 視覺）→ 併入 B2（本輪已換正確 sidebar）。
