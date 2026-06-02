---
title: Legacy /api/v1 Sunset 決策備忘（解鎖型別重生 + spec 合併時機）
date: 2026-06-02
status: awaiting-owner-decision
author: Claude (Opus 4.8)
related:
  - docs/_audit/CR-0002-p2-tenant-scoped-rfc7807-rls.md (§8 D3/C-11 / §10 γ DEFERRED)
  - docs/_audit/spec-code-gap-audit-2026-06-01.md (§8 C-11)
unblocks:
  - 型別重生（D6，目前 DEFERRED）
  - 兩份 spec 合併時機
---

# Legacy `/api/v1` Sunset 決策備忘

> **為什麼需要這份**：型別重生（CR-0002 §10 已 DEFERRED）的安全前提是「legacy 路徑退場」或「v2 型別獨立 namespace」。要決定退場，得先有 **Sunset 策略 + 日期**。本備忘給你可拍板的選項，不替你決定。

---

## 1. 現況（dual-mount 實測 2026-06-02）

P2-α 已用「雙掛過渡」把 **13 個模組**做出 tenant-scoped v2，舊 `/api/v1` 全保留。但**前端遷移是部分完成**：

- **69 個 web 檔仍引用 `/api/v1`**；多個模組前端**同時**有 legacy 與 v2 呼叫（例：`/api/v1/customers` 與 `/tenants/{tid}/customers` 並存）→ 代表「主流程已遷 v2、次要呼叫仍 legacy」。
- **結論：沒有任何一個 legacy 路徑現在可以安全撤除**（仍有前端 caller）。Sunset 是「未來式」，要逐模組等前端歸零。

### 1.1 已有 v2 後繼（dual-mount）的模組

| 模組 | legacy `/api/v1` | v2 tenant-scoped | 前端遷移狀態 |
|---|---|---|---|
| M11 Cancellation | /work-orders/{id}/cancel | /tenants/{tid}/work-orders/{id}/cancel | ✅ 主流程已遷（P1-A）|
| M11 Refund | /refunds(+/{id}) | /tenants/{tid}/refunds | ⚠️ create 已遷；list/decision 仍 legacy |
| M13 Warranty | /warranty-claims | /tenants/{tid}/devices/{did}/warranty | ⚠️ device view P3；claim 仍 legacy |
| M04 Customers | /customers(+/{id}) | /tenants/{tid}/customers | ⚠️ 主頁已遷；殘留 legacy caller |
| M03 ProblemCards | /problem-cards | /tenants/{tid}/problem-cards | ⚠️ 部分 |
| M05 Technicians | /technicians | /tenants/{tid}/technicians | ⚠️ admin 已遷；me/* 保留 legacy |
| M06 Dispatch | /dispatch/* | /tenants/{tid}/dispatch:* | ⚠️ 部分（work-order 詳情頁仍有 legacy）|
| M06 WorkOrders | /work-orders(+actions) | /tenants/{tid}/work-orders(+:actions) | ⚠️ 核心已遷；operational 雜項 legacy |
| M11 Pricing | /pricing/calculate | /tenants/{tid}/pricing/calculate | ✅ PricingForm 已遷 |
| M16 Consumer | /public/work-orders/{token}/status | /consumer/work-orders/{token} | ✅ track 頁已遷 |
| M17 Audit | /audit-logs(+/export) | /tenants/{tid}/audit/events(+/exports) | ⚠️ 主頁已遷；export 殘留 legacy |
| M17 RBAC | /roles | /tenants/{tid}/rbac/roles | ✅ /admin/roles 已遷 |
| M17 Vouchers | /accounting/vouchers | /tenants/{tid}/vouchers | ✅ 已遷 |

### 1.2 Legacy-only（無 v2 後繼，C-11 KEEP）

無 tenant-scoped 後繼、α 刻意不遷的 ~40 條：`auth/*`、`conversations`、`dashboard/stats`、`notifications/*`、`inventory/items`、`disputes`、`reconciliations`、`settlements`、`invoices`、`dispatch-logs`、`admin/schedule-requests`、`knowledge-base/*`(cases/manuals/export)、`media/*`、`config`、`family-reviews`、`sentiment-alerts`、`data-corrections`、`resolution`、`reports/*`、`pricing-rules` CRUD、`work-orders` operational（reschedule/delay/door-check…）、`technicians/me/*`、`vouchers/{id}/void`(P3)。

---

## 2. 🛑 待你拍板的決策

| # | 決策 | 選項 | 建議 |
|---|---|---|---|
| **DS-1** | **Sunset 觸發條件** | (A) 固定日期全體退場；(B) **per-module 條件式**：某模組「前端 `/api/v1` caller 歸零 + 1 sprint 觀察」才撤該 legacy 路徑 | **(B)** — 安全、可逆、對齊逐頁 ship；避免固定日期到了前端還沒遷完就斷線 |
| **DS-2** | **Sunset header 日期** | (a) 暫不填 Sunset（只留 Deprecation）；(b) 給一個保守遠期日（如 2026-Q4） | **(a)** 現在；待某模組前端歸零再對該模組填 `Sunset:` |
| **DS-3** | **Deprecation 範圍**（現為 blanket）| 現 DeprecationMiddleware 對**所有** `/api/v1` 蓋 Deprecation，含 `auth/login`、`conversations` 等**無 v2 後繼**者 → 誤導（它們不會退場）。(A) 維持 blanket；(B) **只對「有 v2 後繼」的 legacy 路徑蓋** | **(B)** — 改 middleware 用一份「有後繼的 legacy path 前綴清單」判斷；auth 等核心不標 Deprecated |
| **DS-4** | **Legacy-only(§1.2) 是否永久保留** | (A) 永久 KEEP（無 Sunset）；(B) P3 為部分（如 conversations/knowledge-base）規劃 v2 | **(A)** 現階段；P3 再個別評 |
| **DS-5** | **型別重生時機**（被本備忘解鎖）| (A) 等所有 migrated-legacy 退場後再「覆蓋重生」；(B) **現在就做「v2 型別獨立 namespace」**（新 spec → `web/types/api.v2.generated.ts` + 後端 v2 models，**不覆蓋** legacy generated）| **(B)** 可現在安全做（additive），讓 v2 前端/後端逐步改用正式 typed client；(A) 的覆蓋重生留到 §1.1 全部前端歸零後 |

---

## 3. 建議時間線（若採各項建議）

```
現在 ──► DS-3：refine DeprecationMiddleware（只標有後繼者）  [小, 低風險, 可立即做]
      └► 前置：合併兩份 spec 成單一完整 spec（D6 namespace）  [中, spec-only]
           └► DS-5(B)：v2 型別獨立 namespace 重生（不覆蓋 legacy）  [中, additive 安全]
                └► 前端 v2 呼叫逐頁改用 generated v2 types
                     └► 某模組前端 /api/v1 caller 歸零 → 對該 legacy 路徑填 Sunset:（DS-2）
                          └► 過 Sunset → 撤該 legacy router（DS-1 B）
                               └► 全部 migrated-legacy 撤完 → 可選擇覆蓋重生統一 generated
並行：P3 補缺合約（與本線無依賴）
```

---

## 4. 對「型別重生」的直接結論

- **不需要**等全部 Sunset 才動型別——採 **DS-5(B)**（v2 獨立 namespace、不覆蓋 legacy）即可現在安全推進，前提是先 **合併兩份 spec**（否則 v2 types 缺 companion 的 57 paths）。
- **覆蓋式**重生（取代現有 `generated.py` / `api.generated.ts`）才需等 §1.1 全部前端歸零 + legacy 撤除（避免炸 121 個 importer，詳見 CR-0002 §10 數據）。

---

**🛑 請於 §2 DS-1～DS-5 給出裁示（或「全照建議」），我據此排下一步。**
