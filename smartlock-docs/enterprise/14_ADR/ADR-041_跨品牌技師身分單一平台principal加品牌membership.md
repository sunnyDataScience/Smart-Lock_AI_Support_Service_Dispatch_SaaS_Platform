---
title: "ADR-041: 跨品牌技師身分採單一平台 principal + 品牌 membership claim"
version: 1.0
status: active
owner: Identity Owner / Security Owner
last-updated: 2026-07-28
relates:
  - ./ADR-004_Casdoor統一IdP租戶License.md
  - ./ADR-035_租戶資源歸屬授權契約_BOLA_IDOR.md
  - ./ADR-036_機器身分與可撤銷服務憑證.md
  - ./OPEN_DECISIONS.md
---

# ADR-041: 跨品牌技師身分採單一平台 principal + 品牌 membership claim

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（2026-07-28 業主裁決）／Casdoor org 映射與 HA 證據仍為 rollout gate |
| 層級 | 平台級（identity / security） |
| 關聯 ADR | [ADR-004](./ADR-004_Casdoor統一IdP租戶License.md) · [ADR-005](./ADR-005_四方RBAC模型與enforce.md) · [ADR-035](./ADR-035_租戶資源歸屬授權契約_BOLA_IDOR.md) |
| 承接決策 | [OD-004](./OPEN_DECISIONS.md#od-004--casdoor-跨租戶-organization-與-claim-模型)（本 ADR 使其 `decided`） |
| WBS | 3.6.2 · 3.6.5 |

## Context（背景與問題）

同一位技師可能同時受多個品牌授權。ADR-P004 已把技師共享池升格為跨租戶的獨立系統，
`12_SAD §258` 明載「技師是**跨品牌身分**」。但 OD-004 一直沒定版「這件事怎麼表達在
identity 與 token 上」，導致 ADR-035 的 ownership matrix 只能先擋住跨租戶存取，不能
描述跨品牌 entitlement。

裁決過程中業主提出一項業務約束：**品牌之間可能互為競爭關係，A 品牌不應看到某位技師
也在接 B 品牌的案子**，同時平台方（思福）需要能從平台後台管理多品牌的技師合作關係。

這兩件事看似衝突，實際不衝突——它們落在不同的層。

## Decision（決策）

**定版「單一平台 principal + 品牌 membership claim」。**

1. **技師在平台只有一份身分**。不採「每品牌各複製一份技師帳號」。
2. **token 內容**：帶 principal、portal、可操作 brand scope 與版本／撤銷語義，
   **一次帶齊該技師目前已授權的全部品牌**。授權不以 UI 的 tenant fallback 決定。
3. **品牌間的競爭隔離不由收窄 token scope 達成**，而是由既有的兩道資料層機制保證：
   - **每品牌物理分庫**：A 品牌的 API 連的就是 A 品牌那顆庫，他牌工單不在其中——是
     物理上不存在，不是「查得到但擋住」。
   - **`tech_mirror` 最小化投影**：鏡射進品牌庫的技師欄位走白名單，不含
     `authorized_brands`、憑證與 PII（CR-0112 的原始目的）。
4. **平台跨品牌治理走 platform admin principal**：`platform_technicians` 的跨品牌師傅
   清單、師傅詳情（身分域 + `authorized_brands`）、跨品牌 lifecycle audit 與 brand
   authorization 授予／撤回。依 ADR-035，**不得以 `X-Tenant-ID` 取得跨品牌權限**。
5. **撤銷傳播**：停權／KYC 失效以平台身分為單一真相源；品牌面的可用性判定必須讀該
   真相源的投影，不得各自維護一份技師狀態。

## Rationale（為什麼這樣決）

**隔離需求不需要收窄 token。** 技師的 token 是發給技師端使用的，品牌員工從頭到尾不
經手它；而品牌後台能查到什麼，取決於它連的是哪顆資料庫，不取決於技師 token 裡寫了
幾個品牌。收窄 scope 只會多換一次登入與一組切換品牌的 UI，換不到額外的隔離。

裁決前逐一確認了三個可能的洩漏面，均為關閉狀態：品牌面技師 API 不吐
`authorized_brands`；`tech_mirror` 為白名單投影且不含憑證與 PII；稽核紀錄只存
`actor_id` / `actor_role`，不落 token claims 原文。

**反過來，「每品牌各複製帳號」會破壞這個業務需求本身。** 同一位技師在各品牌各有一個
帳號時，平台方失去「這是同一個人」的單一真相源：停權要逐品牌關（漏一個就是還在派工
給已停權者）、KYC 一致性無法保證、跨品牌接單總數算不準。而這些正是技師共享池對品牌
方的核心價值。競爭隔離要的是「品牌看不到彼此的案子」，不是「平台也認不出同一個人」。

## Alternatives（考量的選項）

- **A：每品牌 org 複製技師帳號** — 模型直觀，但違反跨品牌唯一身分，撤銷傳播與 KYC
  一致性風險高，且與 ADR-P004 的共享池架構直接衝突。拒絕。
- **B：external identity + 平台 entitlement graph** — 彈性最高，但需自建 membership
  與授權服務並自負稽核；現階段規模不成比例。
- **C：單一平台 principal + brand membership，token 收窄為單一品牌** — 隔離效果與
  採用方案相同（因為隔離本來就在資料層），卻多出切換品牌的登入與 UI 成本。不採。
- **D：單一平台 principal + brand membership，token 帶齊全部品牌（採用）**。

## Consequences（後果）

- ＋ADR-035 的 ownership matrix 可以新增跨品牌 principal projection，不再只能擋。
- ＋平台後台的跨品牌治理能力有了正當性依據，不再是「先做了但沒定版」。
- ＋WBS 3.6.2 的 OD-004 約束解除；3.6.5 的 `allowed_brand_scope` 可依本 ADR 定義。
- －token 會隨授權品牌數成長；需監控 claim 大小上限，必要時改帶 membership 版本號
  加一次查詢。
- －「隔離靠資料層」是本決策成立的前提：**任何未來新增的品牌面端點若開始回傳跨品牌
  欄位，就直接破壞本 ADR 的隔離假設**，必須納入 ADR-035 的負向契約測試。

**完成門檻**：Casdoor org／claim 映射定版並有 claim 範例與大小量測；登入／撤銷／換品牌
序列有負向測試；品牌面端點無任何跨品牌欄位外洩（BOLA 契約測試涵蓋）；IdP outage 行為
已定義。

## 重評觸發

- 品牌方要求「連平台也不得知道我用了哪些技師」——那會推翻共享池前提，屬產品層變更。
- token claim 大小逼近 IdP 或 header 上限。
- 出現跨品牌的委派管理需求（品牌管理員代管他牌技師授權）。
