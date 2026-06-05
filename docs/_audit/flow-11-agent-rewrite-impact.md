---
title: Flow 11 客戶不在場 — agent 重寫衝擊 deep audit
date: 2026-06-05
status: active
tier: 4
---

# Flow 11 客戶不在場（LINE Flex RSVP）— agent 重寫衝擊 deep audit

## 1. 目的

校正 WBS Flow 11 100% claim — 取證後實際為 80%。agent 核心重寫（commit `0f037f45` LockCore 落地）刪除舊 ReAct LangGraph agent 與 LINE Flex template render module；backend reschedule_proposal / customer-confirm / customer-reject 鏈路完整，但**客戶端 LINE 主動 push Flex carousel 鏈路 0%**。

## 2. 取證

### 2.1 ✅ Backend (API) — 完整

| 元件 | 路徑 | 狀態 |
|---|---|---|
| service `propose_reschedule_v2` | `api/services/work_order_service.py:1010` | ✅ INSERT `saas.reschedule_proposal` 獨立表（HD-04=a，CR-0007）|
| service `confirm_reschedule_by_customer` | `api/services/work_order_service.py:1116` | ✅ 寫 wo.scheduled_at + WS publish |
| service `reject_reschedule_by_customer` | `api/services/work_order_service.py:1207` | ✅ WS publish 給技師端 |
| endpoint `POST /tenants/{tid}/work-orders/{id}/reschedule:propose` | `work_orders_ops_v2.py:347` | ✅ admin 提案 |
| endpoint `POST .../reschedule:customer-confirm` | `work_orders_ops_v2.py:391` | ✅ |
| endpoint `POST .../reschedule:customer-reject` | `work_orders_ops_v2.py:418` | ✅ |

### 2.2 ✅ Web 客戶端 — 完整

- `web/track/[token]/page.tsx` 客戶 web 路徑可顯示提案、選時段、回送 confirm/reject。
- Web Token 路徑可用，但**需客戶主動進入 web**（沒有 LINE push 通知客戶有提案）。

### 2.3 ❌ LINE Flex 主動 push 鏈路 — 0%

取證命令：
```
grep -rn "reschedule_proposal\|propose_reschedule_v2\|push_reschedule" agent/  # → 全空
grep -n "reschedule\|propose\|flex\|Flex" api/services/line_push_service.py
# → 只有 text push (push_to_work_order_customer)，無 Flex template
```

**斷鏈點**：admin 透過 `POST /reschedule:propose` 寫入 `saas.reschedule_proposal` 後，沒有任何 caller 觸發 `line_push_service` 推 Flex carousel 給客戶 LINE。agent 重寫前可能在 ReAct LangGraph 內某個 node 監聽 reschedule_proposal INSERT → render Flex template → push；lockcore 重寫後該整段已刪。

**影響**：客戶若不在 LINE 收到 push，就不會點 confirm/reject — endpoint 形同孤兒；改期工作流退化為「admin 必須打電話通知客戶」+ 「客戶主動進 web/track 查看」。

## 3. WBS 修正

| 欄位 | 修正前 | 修正後 |
|---|---|---|
| Flow 11 完成度 | **100%**（淺取證腦補） | **80%**（backend 完整 + web 完整，LINE Flex push 鏈路 0%）|
| 缺口註記 | 「T11 提案 + LINE Flex RSVP + customer-confirm/reject endpoints + WS 推回技師」 | 「backend / web/track 完整；**LINE Flex 主動 push 客戶**鏈路因 agent 重寫被刪，lockcore 無對等實作（待 CIA 決定 lockcore 補回 / 純 web only / 另起 LINE bot）」|

## 4. 不立即 BUILD 的理由

1. **agent 重寫是 architecture lock（ADR-0109）**：lockcore + Agent Skills 標準是業主已拍板。Flex template 重建需要先決定走 lockcore tool 還是另起 LINE bot service。
2. **CIA gate**：跨 Architecture boundary（agent / api 邊界 + external integration LINE Messaging API），須先開 CIA 列 HD 取決於：
   - HD-1：Flex push 在 lockcore 重建 vs 純 web only vs 另起獨立 LINE bot service
   - HD-2：reschedule_proposal INSERT 觸發機制（DB trigger / outbox / API hook）
   - HD-3：Flex template 是 lockcore skill artifact 還是獨立 module
   - HD-4：與 Flow 3（scope change）/ Flow 4 / Flow 5 等其他需 LINE push 流的整合策略

## 5. 不影響 Flow 11 e2e 可用性的條件

若僅走 Web Token 路徑（客戶從 web/track 進）：
- ✅ 完整可用 — admin 提 propose，客戶從 web 收 → confirm/reject
- ❌ 客戶必須被另外通知（電話 / SMS / email）才會知道有提案

若需 LINE push：
- ❌ 0% — 待 CIA 決議

## 6. 後續

- 本 deep audit doc 收進 `docs/_audit/`
- WBS Flow 11 80% 註記補上 audit 結論引用
- **建議下一輪開 CR-0017 — Flow 11 LINE Flex push 重建 CIA**（業主裁決路徑）
- 在此 CR 開立並裁決前，本 audit 為 Flow 11 唯一 source of truth
