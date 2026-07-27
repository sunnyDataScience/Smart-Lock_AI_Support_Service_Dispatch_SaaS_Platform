---
title: "ADR-040: OHS 服務間憑證定版為受控 opaque credential"
version: 1.0
status: active
owner: Security Owner / Platform Owner
last-updated: 2026-07-28
relates:
  - ./ADR-036_機器身分與可撤銷服務憑證.md
  - ./ADR-004_Casdoor統一IdP租戶License.md
  - ./OPEN_DECISIONS.md
---

# ADR-040: OHS 服務間憑證定版為受控 opaque credential

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（2026-07-28 業主裁決）／production bootstrap 與 fallback 歸零仍為 release gate |
| 層級 | 平台級（identity / security） |
| 關聯 ADR | [ADR-036](./ADR-036_機器身分與可撤銷服務憑證.md) · [ADR-004](./ADR-004_Casdoor統一IdP租戶License.md) · [ADR-035](./ADR-035_租戶資源歸屬授權契約_BOLA_IDOR.md) |
| 承接決策 | [OD-001](./OPEN_DECISIONS.md#od-001--ohs-服務間憑證模式)（本 ADR 使其 `decided`） |
| WBS | 3.6.5 |

## Context（背景與問題）

ADR-036 刻意不替 OD-001 選 transport，只固定「不論選哪一條都必須遵守」的機器身分
生命週期。CR-0190 落地後，該生命週期已經是可執行的 runtime：migration 121 的
`service_principal` / `service_credential` / `service_credential_audit`、
`core/deps.py` 的 `X-Service-Credential` 驗證鏈，以及 agent／refinery／technician OHS
三條 caller 的切換路徑。

OD-001 因此從「兩個空選項二選一」變成一個更窄的問題：**已經有一套達標的受控 opaque
credential，還要不要再往上換成 OIDC client-credentials。**

## Decision（決策）

**定版受控 opaque service credential（`X-Service-Credential`）為 OHS 服務間憑證的長期
模式**，生命週期一律依 ADR-036，不因「已定版」而放寬任何一項。

1. **OIDC client-credentials 不否決，改為重審項**。重審觸發條件是「第一個非自建的
   外部接入方出現」——他方 ERP、外部派工商，或任何不由本團隊部署的 caller。屆時以新
   ADR 定案，不修改本 ADR。
2. **`X-Internal-Token` 的定位不變**：仍是有時限 fallback，不因本 ADR 取得長期地位。
   移除條件維持 ADR-036 的門檻——production 使用量連續一個 release window 為零。
3. **新增 caller 的預設是 service principal**，不得以「先接上再說」為由沿用共用 token；
   新增 caller 屬 architecture change，走 CIA。

## Rationale（為什麼這樣決）

ADR-036 已經把安全下限拉齊：hash-only 儲存、audience／scope／brand scope、expiry、
最長 24 小時 rotation overlap、立即撤銷、last-used 與逐次 audit。**換成 OIDC 不會再
提高這個下限**——它提高的是「發放與撤銷的規模化能力」。

而規模化的受益者目前不存在：三條 caller（agent、refinery、technician OHS）全是自建
服務，部署與密鑰配置同屬一個團隊。OIDC 的核心優勢「不必為每個接入方分發與輪替密鑰」
在只有自己人的情況下換不到實際價值，卻要多養一套 Casdoor client 的建立、輪替與撤銷
流程，以及 IdP 故障時的服務間呼叫降級路徑。

`13_Security_Architecture.md` 先前已記載這個判斷的雛形：「OD-001 仍決定最終 transport
是否改 OIDC client-credentials，**不影響 lifecycle 下限**」。本 ADR 把該觀察扶正為決議。

## Alternatives（考量的選項）

- **A：現在就換 OIDC client-credentials** — 目標架構上更乾淨，但為尚不存在的外部接入
  方付出 IdP 耦合與故障域擴大的代價；OD-001 原本的「技術建議」即為此，本裁決不採。
- **B：維持 `X-Internal-Token` 共用密鑰** — 無法最小撤銷與追蹤，ADR-036 已拒絕。
- **C：受控 opaque credential 定版，OIDC 列重審（採用）** — 安全下限已達標，把 transport
  升級綁在真正會受益的觸發條件上。

## Consequences（後果）

- ＋WBS 3.6.5 的 gate 從「OD-001 未定案」縮小為單一條件：fallback 使用量歸零觀察期。
- ＋`16_API_Spec.yaml` 中「服務憑證尚未定版」的警語可以移除，API 文件不再對讀者傳達
  未定狀態。
- ＋不引入 IdP 對服務間呼叫的可用性依賴；Casdoor 故障不會連坐 OHS 呼叫。
- －密鑰的建立與輪替仍是人工操作，接入方一多就會成為瓶頸——這正是重審觸發條件要盯的。
- －未來若真的要換 OIDC，已發出的 credential 需要一次遷移；規模小時代價低，這也是
  現在不急著換的前提。

**完成門檻**：production 每條 internal caller 可辨識 principal；過期、撤銷、錯 audience、
錯 scope、跨 brand 均 fail-closed；`X-Internal-Token` 使用量連續一個 release window 為零
後移除 fallback。

## 重評觸發

- 第一個非自建的外部系統要接技師共享池。
- 接入方數量成長到人工發放與輪替密鑰成為瓶頸。
- Casdoor 已成為所有 portal 唯一登入，且服務間也需要統一的 audience/scope 治理。
