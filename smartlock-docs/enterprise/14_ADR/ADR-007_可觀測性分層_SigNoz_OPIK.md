---
title: "ADR-007: 可觀測性分層（SigNoz 系統監控 + OPIK Agent LLM Ops）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-10
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P002_SigNoz_單一可觀測性平台.md
---

# ADR-007: 可觀測性分層（SigNoz 系統監控 + OPIK Agent LLM Ops）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 平台級 |
| 關聯 ADR | [ADR-002](./ADR-002_per-brand授權部署.md) · [ADR-009](./ADR-009_Model_Orchestration_Layer.md) · [ADR-012](./ADR-012_Agent_Configuration_Studio.md) |

## Context（背景與問題）

平台的可觀測性有兩個不同層次，須分開治理、不可互相取代：

1. **系統／服務層監控**：跨系統（agent / api / web / knowledge-refinery）的集中 log / metric / trace，故障排查需要單一視圖。
2. **Agent LLM Ops 層**：prompt 追蹤、LLM trace、eval——是 prompt 工程與 agent 品質迭代的必要工具，屬開發階段能力，與系統監控是不同層次。

## Decision（決策）

**兩層分開定案、互補並存：**

1. **系統監控 = SigNoz（單一平台）**：OTel 一站涵蓋 api / agent / web / knowledge-refinery 的 trace / metric / log，單一維運面。系統層 SLI dashboard 至少涵蓋：LINE push 成功率、WS 連線數/延遲、Vertex 延遲 P99、DB P95、派工事件 lag。
2. **Agent LLM Ops = OPIK/Comet**：agent LLM call 送 trace / prompt / eval；並作為 prompt / skill 改動的 eval gate（[ADR-012](./ADR-012_Agent_Configuration_Studio.md)）。

> 分工原則：**SigNoz = 系統/服務層（prod 常開，跨全系統）**；**OPIK = agent LLM 層（dev 必開、prod 預設關、可按環境旗標開啟以省資源）**。

## Alternatives（考量的選項）

**系統監控層：**
- **A：OpenObserve + SigNoz 分工**（trace/APM vs log 長存）— 兩套維運複雜度加倍。
- **B：擇一 SigNoz（採用）** — OTel 一站涵蓋，單一維運面。OpenObserve 保留為未來 log 量爆增時的長存選項。
- **C：擇一 OpenObserve** — APM / 分散式追蹤成熟度較弱。

**LLM Ops 層：**
- **X：OPIK（採用）** — LLM 專用觀測 + eval。
- **Y：用 SigNoz trace 涵蓋 LLM call** — 缺 prompt / eval 專用能力，不適合 dev 迭代。

## Consequences（後果）

**正面**：系統監控單一 pane + LLM Ops 專用工具各司其職；agent 品質迭代有據；prod 可關 OPIK 省資源。
**風險**：兩套觀測系統（層次不同）；OPIK dev/prod 開關需明確策略與預設；trace / log 含 PII 需 scrubbing；SigNoz log 長期保存 / scale 未來再評估。
**影響範圍**：api（FastAPI）/ agent（LockCore）/ web（Next.js）/ knowledge-refinery 接 OTel SDK；agent 接 OPIK SDK（消費 `OPIK_*` secret）+ 環境旗標。監控細節見 [25_Monitoring_Spec](../25_Monitoring_Spec.md)。
**重評觸發**：log 量超出 SigNoz 舒適區 → 重啟選項 A 分工；OPIK 出現更輕量替代 → 再議。

## Status 附註

- 🔜 規劃中：SigNoz 部署（跨品牌集中共用元件）與四系統 OTel 接入；agent OPIK 接線 + dev 開 / prod 關旗標。
- **2026-07-10 落地（CR-0156）**：四系統 OTel 接入 code 面完成——api（CR-0136＋PII scrub）、agent（lockcore/observability.py＋line.webhook／agent.turn span）、refinery（FastAPI 自動埋點）、web（brand-portal instrumentation.ts＋@vercel/otel 參考實作，三站複製後續輪）；**agent OPIK 已接**（OPIK_API_KEY opt-in，litellm callback 法）。全部 opt-in／no-op 預設／PII 遮蔽。殘＝SigNoz 叢集部署與 secrets 配置（OPS）。
