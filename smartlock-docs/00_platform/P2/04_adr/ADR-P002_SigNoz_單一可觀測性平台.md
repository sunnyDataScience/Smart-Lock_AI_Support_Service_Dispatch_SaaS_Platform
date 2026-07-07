# ADR-P002: 可觀測性分層 — SigNoz 系統監控 + OPIK Agent LLM Ops

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state / 理想態 v2）|
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）|
| 關聯缺口 | 系統監控空白、G-12；修正現況 OPIK 空掛（應正確接上，**非移除**）|

## 1. 背景與問題

平台的可觀測性有**兩個不同層次**，過去未區分：

1. **系統／服務層監控**：api 無集中 log/metric/trace，跨系統（agent/api/web/refinery）故障排查無單一視圖。此層目前**完全空白**。
2. **Agent LLM Ops 層**：agent 的 **OPIK/Comet** 是**開發階段的 LLM 可觀測性**（prompt 追蹤、LLM trace、eval），現況 secret 已注入但 code 未消費（**空掛**）。這一層**不能少**——它是 prompt 工程與 agent 品質迭代的必要工具，與系統監控是**不同層次、不可互相取代**。

## 2. 考量的選項

**系統監控層：**
- 選項 A：OpenObserve + SigNoz 分工（trace/APM vs log/長存）— 兩套維運複雜度加倍。
- 選項 B：擇一 SigNoz — OTel 一站涵蓋 trace/metric/log，單一維運面。
- 選項 C：擇一 OpenObserve — APM/分散式追蹤成熟度較弱。

**LLM Ops 層：**
- 選項 X：保留 OPIK（LLM 專用觀測 + eval）。
- 選項 Y：用 SigNoz trace 勉強涵蓋 LLM call — 缺 prompt/eval 專用能力，不適合 dev 迭代。

## 3. 決策

**兩層分開定案、互補並存：**

1. **系統監控 = SigNoz（單一平台，選項 B）**：先求單一維運、降複雜度；OTel 一站涵蓋 api/agent/web/knowledge-refinery 的 infra trace/metric/log。OpenObserve 暫不導入（保留為未來 log 量爆增時的長存選項）。
2. **Agent LLM Ops = OPIK/Comet（保留，選項 X）**：
   - **開發階段必備、不可少**——**修正現況空掛，讓 agent code 正確接上** OPIK，送 LLM trace / prompt / eval。
   - **上線後可經環境旗標關閉**（OPIK 會耗資源），prod 預設可關、按需開啟。

> 分工原則：**SigNoz = 系統/服務層（prod 常開，跨全系統）**；**OPIK = agent LLM 層（dev 必開、prod 可關）**。兩者層次不同、不重疊。

## 4. 後果

**正面**：系統監控單一 pane（SigNoz）+ LLM Ops 專用工具（OPIK）各司其職；OPIK 從「空掛」修正為「正確接上」，agent 品質迭代有據；prod 可關 OPIK 省資源。
**負面/風險**：兩套觀測系統（層次不同）；OPIK 的 dev/prod 開關需明確策略與預設；SigNoz log 長期保存/scale 未來再評估。
**影響範圍**：api/agent/web/knowledge-refinery 接 SigNoz OTel；**agent 需正確接上 OPIK**（消費現有 secret）並加環境旗標；`agent/P3/13` 與 `agent/P1/05` 的「OPIK 空掛」現況缺口 → 改為「已接上 + 可切換」。
**重新評估觸發**：log 量超 SigNoz 舒適區 → 重啟選項 A 分工；OPIK 若有更輕量替代 → 再議。

## 5. 執行計畫

1. 部署 SigNoz（跨品牌共用元件，見 [[ADR-P005]]）。
2. api（FastAPI）/ agent（LockCore）/ web（Next.js）/ knowledge-refinery 接 OTel（系統層 trace+metric+log）。
3. **agent 正確接上 OPIK**：消費現有 `OPIK_*` secret，LLM call 送 trace/prompt/eval（修正空掛）。
4. **OPIK 環境旗標**：dev 預設開、prod 預設關（可按需開），文件化開關策略與資源成本。
5. 系統層 SLI dashboard（SigNoz）：LINE push 成功率、WS 連線數/延遲、Vertex 延遲 P99、DB P95、派工事件 lag。

## 6. 選用影響區段

- **可觀測性**：分兩層——SigNoz（系統，單一）+ OPIK（agent LLM Ops，dev 必開/prod 可關）。
- **依賴**：各服務新增 OTel SDK；agent 接 OPIK SDK。
- **部署**：新增 SigNoz（集中式）；OPIK 依環境開關。
- **安全/成本**：trace/log 含 PII 需 scrubbing；OPIK prod 關閉以省資源。
