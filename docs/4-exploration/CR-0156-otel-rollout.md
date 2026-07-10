# CR-0156 — agent/refinery/web OTel＋agent OPIK 埋點(ADR-007 補課)

- **日期**:2026-07-10
- **狀態**:done(2026-07-10)
- **觸發面向**:可觀測性(跨 agent/refinery/web 三系統;opt-in 零行為變化)
- **依據**:ADR-007 影響範圍「api/agent/web/knowledge-refinery 接 OTel SDK;agent 接 OPIK SDK」、25_Monitoring §2/§3;架構稽核 #4 查實三系統零埋點且被 WBS 1.4.1 誤標「部署面 OPS」;業主 2026-07-10「開工」

## §1 範圍(全部照 api/core/observability.py 範式:opt-in/no-op 預設/PII 遮蔽硬性)

| 線 | 內容 |
|---|---|
| agent | lockcore/observability.py(OTel+scrub)+line_gateway 請求 span+loop turn span+**OPIK**(OPIK_API_KEY 設定時掛 litellm 整合,LLM call 追蹤) |
| refinery | observability.py+service.py 接線(FastAPI 自動埋點) |
| web | brand-portal **參考實作**(instrumentation.ts+@vercel/otel,比照 CR-0146 先例;三站複製=後續輪) |

## §8 裁決記錄(2026-07-10)

業主「開工」=採建議案(可否決);web 只做 brand-portal 參考實作(其餘隨三站複製輪)。

### 進度

- ✅ done(branch `feat/otel-rollout`,2026-07-10,三線並行實作+主流程復驗):
  - agent:lockcore/observability.py(scrub 同源)+line.webhook/agent.turn span(薄包裝零改動原邏輯)+OPIK opt-in(litellm callback 字串法)+pyproject [otel] extra;測試 11 新+全套 **186 綠**
  - refinery:observability.py+service 接線+[otel] extra;測試 11 新,全套 14 passed 9 skipped
  - web:brand-portal src/instrumentation.ts(@vercel/otel,Next 15 hook)+vitest 6 測;tsc 0+build 綠+standalone 包含 instrumentation;PII 實查(token 走 header 不入 URL)
  - 遺留:三站複製(tech/landing/platform)、@vercel/otel 深度出站遮蔽(無 filter hook,隨複製輪)、SigNoz 叢集+secrets=OPS、OPIK prod 開啟前 PII 評估
