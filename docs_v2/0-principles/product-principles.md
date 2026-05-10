---
title: Product Principles — Mission, Non-Goals, Quality Bars
tier: 0
status: active
last_updated: 2026-05-10
sources_merged:
  - "_pending-merge_sla-policy.md → §SLA-policy"
  - "_pending-merge_workday-sla-policy.md → §workday-policy"
  - "../4-exploration/prd-2026-q1-v1-launch.md → §mission, §scope"
  - "../4-exploration/_pending-merge-user-journey-map.md → §user-roles"
related:
  - "glossary.md"
  - "frontend-quality-attributes.md"
  - "../1-decisions/architecture-overview.md"
---

# Product Principles

> 本檔為產品最高憲法：**Mission / 非任務 / 品質基準 / SLA / 工作日規則**。
> tier 1-5 任何文件不得與本檔衝突；要改本檔必開 ADR。

---

## §1 Mission

**Smart Lock AI Support & Service Dispatch SaaS Platform** — 用 AI 客服 + 智能派工，為智能鎖品牌商與鎖匠服務商提供 LINE 報修 → 自動分診 → 派工 → 完工 → 帳務的端到端 SaaS 平台。

### 三層解決機制

```
L1 知識庫直答（< 1s 回應，覆蓋 60%+ FAQ）
  ↓ 無解
L2 LLM 推理 + SOP 載入（< 5s 回應，覆蓋 25% 進階問題）
  ↓ 無解
L3 升級人工：客服接管 / 派工技師現場處理（剩餘 15%）
```

---

## §2 非任務（Non-Goals）

明確排除：

| 不做 | 理由 |
| :-- | :-- |
| 智能鎖製造 | 平台不碰硬體 |
| 自有鎖匠團隊 | 平台只媒合與管理，不雇用 |
| 醫療 / 保險 / 金融顧問 | 領域外 |
| C2C 平台 | 只服務 B2B (品牌商) + 鎖匠服務商 |
| 跨國市場（V1）| 先做台灣；V3 才考慮多語系 |
| 自研 LLM | 用 Vertex AI / OpenAI 等托管模型 |

---

## §3 品質基準（Quality Bars）

| 維度 | 目標（V1）|
| :-- | :-- |
| LINE 報修首次回應 | < 5s（包含 AI 初判） |
| L1 知識庫命中率 | ≥ 60% |
| L2 LLM 推理成功率 | ≥ 25%（剩餘 15% 升級 L3）|
| 自動派工 → assigned 狀態 | ≤ 30s |
| SLA 2hr 到場（Soft Target）| Dashboard 變紅，無賠償 |
| 退款處理 SLA | 7 工作日 |
| 月結爭議 SLA | 7 工作日（含跨春節 / 國定假日不計算）|
| 系統可用性 | 99.5%（V1）|
| 測試覆蓋率 | 80%+ |

詳細前端 quality attributes（Core Web Vitals / A11y）見 [`frontend-quality-attributes.md`](./frontend-quality-attributes.md)。

---

## §4 SLA Policy（V1 全 Soft Target）

> **Q5=B 拍板**：V1.0 所有 SLA **均為 Soft Target**（不寫入消費者合約，避免法律風險）。
> Hard SLA 待 V2.0 配合金流整合與保險方案後評估。

### Hard vs Soft 定義

| 類型 | 破線後果 | 自動補償 | 觸發升級 | 法律約束 |
| :-- | :-- | :-- | :-- | :-- |
| **Hard SLA** | 自動沖銷、退款、補償 | ✅ 有 | ✅ 自動 | ✅ 寫入合約 |
| **Soft Target** | Dashboard 警報 + 升級主管 | ❌ 無 | ✅ 自動 | ❌ 內部營運指標 |

### V1 SLA 清單（全為 Soft Target）

| ID | 描述 | 閾值 | 破線行為 |
| :-- | :-- | :-- | :-- |
| SLA-001 | LINE 首次回應 | 5s | 警報 + 升 SRE |
| SLA-002 | 派工到 assigned | 30s | 警報 + 升 dispatcher |
| SLA-003 | 技師到場（紅色警報）| 2hr | Dashboard 變紅 + 升 Ops Manager |
| SLA-004 | 退款處理 | 7 工作日 | 警報 + 升 Ops Director |
| SLA-005 | 月結爭議 | 7 工作日 | 警報 + 升 Ops Director |
| SLA-006 | 系統可用性 | 99.5% | 月報追蹤 |

對應實作見 [`2-contracts/modules/sla-monitor.md`](../2-contracts/modules/sla-monitor.md)。

---

## §5 工作日 Policy（Q4=C 拍板）

> **唯一資料來源**：[`holidays`](https://pypi.org/project/holidays/) Python 套件 `country_holidays('TW')`

### 工作日定義

| 條件 | 工作日 |
| :-- | :--: |
| 週一 ~ 週五 且 不在台灣國定假日清單 | ✅ |
| 週六 / 週日 | ❌ |
| 國定假日（元旦 / 春節 / 清明 / 端午 / 中秋 / 國慶 / 勞動節 等） | ❌ |
| 補班日（如「補春節後第一週週六上班」） | ❌（V1 不處理；以套件為準） |

### Helper 契約

實作於 `agent/core/workday.py`：

```python
def is_workday(d: date, country: str = "TW") -> bool: ...
def add_workdays(start: date, n: int, country: str = "TW") -> date: ...
def workday_diff(start: date, end: date, country: str = "TW") -> int: ...
```

寫入 `disputes.sla_deadline`、`refunds.sla_deadline` 等欄位前必須呼叫 `add_workdays(created_at, 7)`。

---

## §6 技術硬限制

| 限制 | 說明 |
| :-- | :-- |
| Python 版本 | 3.11+（uv workspace） |
| Node 版本 | 18+（web） |
| LLM provider | LiteLLM 統一介面（不直連 vendor SDK） |
| Postgres 版本 | 16+ 含 pgvector 0.7+ |
| 部署平台 | GCP Cloud Run（agent + api 兩個 service） |
| 資料隔離（V3）| Shared DB + RLS（per ADR-0010 拍板）|

詳見 [`../1-decisions/architecture-overview.md`](../1-decisions/architecture-overview.md) 與相關 ADR。

---

## §7 用戶角色（4 + 治理層）

| 角色 | 說明 | 主要旅程 |
| :-- | :-- | :-- |
| 消費者 | LINE Bot 報修 | UF-0001 LINE 報修 → ProblemCard |
| 技師 | Web App (PWA) 接單 | UF-0002 接單 → 出發 → 到場 → 完工 |
| 客服 | Admin Panel 後台 | UF-0010 SOP 草稿審核、UF-0011 對話接管 |
| 客服主管 | Admin Panel | UF-0007 雙簽爭議、UF-0013 報表 |
| Ops Manager / Director | Admin Panel | UF-0008 退款覆核、UF-0012 RBAC |

詳細旅程見 [`../4-exploration/_pending-merge-user-journey-map.md`](../4-exploration/_pending-merge-user-journey-map.md)。

---

## §8 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 | MERGE 初版：mission + non-goals + SLA + workday + 技術硬限制 |
