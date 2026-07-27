---
title: "ADR-035: 租戶資源歸屬授權契約與 BOLA／IDOR 守門"
version: 1.0
status: active
owner: Security Owner / API Owner
last-updated: 2026-07-27
refines:
  - ./ADR-005_四方RBAC模型與enforce.md
relates:
  - ./ADR-020_三庫物理隔離租戶模型.md
  - ./ADR-022_API_SURFACE單體多面塑形.md
---

# ADR-035: 租戶資源歸屬授權契約與 BOLA／IDOR 守門

| 欄位 | 內容 |
|---|---|
| 狀態 | 規劃中（安全契約定案；router matrix 與負向測試待 WBS 3.6.4 完成） |
| 層級 | 平台／系統級（security / api） |
| 關聯 ADR | refines [ADR-005](./ADR-005_四方RBAC模型與enforce.md) · [ADR-020](./ADR-020_三庫物理隔離租戶模型.md) · [ADR-022](./ADR-022_API_SURFACE單體多面塑形.md) |
| 來源規劃 | [Plane 借鏡架構優化規劃](../規格統控整理/Plane借鏡架構優化規劃_2026-07-27.md) D |

## Context（背景與問題）

平台已有 `get_current_user → require_tenant → role_required`、portal claim guard、
tenant-scoped route 與部分跨租戶回歸測試。這些是強項，但「使用者具有某角色」不代表
「URL 中任意 UUID 都屬於他可操作的租戶」。當品牌 DB、技師權威庫與 platform DB 的
資源交叉投影時，若 router 各自臨時拼接檢查，容易留下 BOLA／IDOR 缺口。

本平台採每品牌物理分庫，不能照搬 Plane 的 Instance → Workspace → Project 模型；
物理隔離仍需以 resource ownership contract 補強 defense-in-depth 與可測試性。

## Decision（決策）

所有接收 path、query 或 body 資源 ID 的 API，必須歸入以下授權契約之一：

| 資源面 | 必須同時成立的條件 |
|---|---|
| Brand tenant resource | path tenant、session/claim tenant scope、resource tenant、active membership 一致 |
| Technician resource | tech principal、brand entitlement、assignee／允許的最小投影一致；不可用品牌前端 tenant fallback 取代 |
| Platform resource | platform principal + 明確 capability；不得因 `X-Tenant-ID` 或 request body tenant 取得跨品牌權限 |
| Public capability resource | 短效／單次 capability、resource scope、expiry、使用狀態一致；不可只靠 UUID 不可猜 |
| Internal service resource | 由 [ADR-036](./ADR-036_機器身分與可撤銷服務憑證.md) 的 service principal、audience、scope 與 brand scope 驗證 |

執行規則：

1. 將 ownership check 收斂為可重用 policy/helper；router 不得只做 `resource exists`。
2. 先驗證 principal 與 portal，再解析 tenant／brand scope，最後在**同一查詢或交易**
   驗證資源歸屬，避免 check-then-use 漂移。
3. 所有 UUID／自然鍵都視為不可信輸入；讀、寫、批次、匯出、WebSocket subscribe 均適用。
4. 新端點在合併前必須選定一列 contract，並具 parameterized 負向案例：
   跨 tenant UUID、撤銷 membership、portal claim 不符、資源不屬 path tenant、
   service credential 過期／撤銷／錯 scope。
5. 拒絕採 fail-closed 並留下不含敏感資料的 audit reason；不得用前端隱藏按鈕或
   `404` 外觀取代後端 ownership 檢查。
6. 建立 API surface × contract × test ID 的機讀矩陣，納入 CI；未分類的新 mutation
   endpoint 直接 fail。

## Alternatives（考量的選項）

- **A：只靠 RBAC role** — 無法證明目標資源屬於目前 tenant，拒絕。
- **B：每個 router 自行檢查** — 短期快，但規則漂移且難形成回歸覆蓋，拒絕。
- **C：集中 ownership contract + parameterized negative tests（採用）** — 保留三庫
  模型，同時把 BOLA／IDOR 防線變成可稽核契約。
- **D：新增 Plane 式 workspace/project 階層** — 不解決現有三庫 ownership，且改變產品
  租戶模型，拒絕。

## Consequences（後果）

- ＋每個 URL／request ID 都有可對回的歸屬規則與負向測試。
- ＋角色、租戶、portal 與資源四個邊界不再被混成單一 middleware 判斷。
- ＋安全修復會永久落成 regression test，而非只關閉 issue。
- －需盤點全部 router；舊端點可能暴露原本隱藏的 tenant fallback 與查詢耦合。
- －platform／technician 投影資料需補明確 owner 與最小欄位，不能靠品牌 DB 猜測。

**完成門檻**：所有 mutation endpoint 與敏感 read／export endpoint 均已分類；BOLA／IDOR
matrix 無空白；跨 tenant、撤銷會員、錯 portal、錯 service scope 測試全部 fail-closed。

## 重評觸發

Casdoor claim 與跨品牌 membership 由 OD-004 定案後，需新增對應 principal projection；
不得以修改本 ADR 的 ownership 原則取代 OD-004 裁決。
