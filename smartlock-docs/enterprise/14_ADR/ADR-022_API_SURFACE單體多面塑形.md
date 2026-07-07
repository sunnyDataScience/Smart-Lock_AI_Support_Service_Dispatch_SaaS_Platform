---
title: "ADR-022: API_SURFACE 單體多面塑形（一 codebase → 三暴露面 + 背景任務策略）"
version: 1.0
status: active
owner: api 系統 tech lead
last-updated: 2026-07-07
upstream:
  - smartlock-docs/api/P2/04_adr/ADR-001_API_SURFACE_單體多面部署.md
---

# ADR-022: API_SURFACE 單體多面塑形（一 codebase → 三暴露面 + 背景任務策略）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 系統級（api）|
| 關聯 ADR | [ADR-005](./ADR-005_四方RBAC模型與enforce.md) · [ADR-004](./ADR-004_Casdoor統一IdP租戶License.md) · [ADR-006](./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md) · [ADR-002](./ADR-002_per-brand授權部署.md) |

## Context（背景與問題）

api 需同時服務三個前端與三種信任邊界：

- **品牌營運後台（dispatch）**：完整控制平面——工單、派工、帳務、結算、知識庫；背景任務（LINE 推播、SLA、GDPR 硬刪、自動結案）須執行。
- **師傅端（tech，跨品牌共用）**：技師身分、接單、到場簽名、對帳單、媒體上傳等精簡面；背景任務**不得**在此執行（與品牌實例接同顆 DB 會雙跑 → 重複推播 / 告警）。
- **平台 console（platform）**：跨品牌治理——品牌申請、審核、platform admin；token 為跨品牌最高權限，須獨立信任邊界。

工單 / 帳務 / 技師邏輯高度共用，複製 codebase 必然漂移。

## Decision（決策）

**單一 codebase + `API_SURFACE` 環境變數塑形**（一份 `api/Dockerfile`，三 compose 僅環境變數不同）：

| surface | port | 路由塑形 | 背景 worker |
|---|---|---|---|
| `all`（預設 / pytest / 雲端單體）| — | 全掛零過濾 | 全開 |
| `dispatch` | :8001 | **剔除**清單：`/api/v1/platform` + `/api/v1/technicians/register` | 全開 |
| `tech` | :8002 | **保留**清單 `_TECH_SURFACE_PREFIXES`（auth / technicians / work-orders / media / tenants 子集）| 全停 |
| `platform` | :8003 | 只留 `/api/v1/platform` 前綴 | 全停 |

- `_RUN_BACKGROUND_WORKERS = API_SURFACE not in (tech, platform)`——多實例接同顆 DB 不重複推播 / 告警。
- **platform 面獨立信任邊界**：獨立簽章密鑰 + 啟動守衛（密鑰 ≥ 16 字元、含弱值即 `RuntimeError` 拒啟；compose 以 `:?` 強制必填）。認證統一朝 Casdoor OIDC token 驗證收斂（[ADR-004](./ADR-004_Casdoor統一IdP租戶License.md)）。
- **明確約束**：`API_SURFACE` 是**部署塑形（deployment shaping），非安全邊界**——前綴過濾只縮小暴露面；授權由每端點 RBAC（`role_required` / `require_tenant` / `require_platform_admin`，deny-by-default，[ADR-005](./ADR-005_四方RBAC模型與enforce.md)）把關。

## Alternatives（考量的選項）

- **A：單一 codebase + `API_SURFACE` 塑形（採用）** — 一份 code、一個 Dockerfile；共用邏輯改一次三端生效。
- **B：三套獨立 codebase** — 暴露面天然乾淨，但共用邏輯三處維護必然漂移，bug fix 打三次。
- **C：API Gateway 前置 + 單體全掛** — 授權可上移為真邊界，但引入 Gateway 基礎設施，且背景任務雙跑仍需另解。

## Consequences（後果）

**正面**：單一真相源（工單 / 帳務 / 技師邏輯改一次三端同步）；背景任務不雙跑；platform 密鑰分級降低跨品牌偽造風險。
**風險**：前綴過濾非安全邊界——端點漏掛 RBAC 守衛時 surface 過濾擋不住（靠 [ADR-005](./ADR-005_四方RBAC模型與enforce.md) enforce 為真隔離）；dispatch 用剔除清單，新增平台 / 註冊類路由易漏收；同 codebase 耦合面——router 變更須考慮三面行為。
**影響範圍**：`api/main.py`（surface 塑形 + worker 開關 + 啟動守衛）、三 compose、部署拓撲（[ADR-002](./ADR-002_per-brand授權部署.md)）。
**重評觸發**：引入 API Gateway / 集中 identity 可將授權上移；三面共用邏輯 < 50% 時重估獨立 codebase；水平擴展多實例前先完成 [ADR-006](./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md) Phase 1。

## Status 附註

- 雲端起步以 `API_SURFACE=all` 單體承載，隨品牌數展開為 per-brand bundle（dispatch 面）+ 集中 tech / platform 面（[ADR-002](./ADR-002_per-brand授權部署.md)）。
