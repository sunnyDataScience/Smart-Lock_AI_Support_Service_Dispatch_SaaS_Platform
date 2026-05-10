---
status: superseded
superseded_by: docs_v2/4-exploration/multi-tenant-platform/external-factors.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# Multi-Tenant External Factors Checklist

> **文件狀態：設計文件（V3.0 規劃）**
> 多租戶 SaaS 平台的外部因素分析，涵蓋平台依賴、商業模式、法規、安全、營運等非技術面。
> 建立日期：2026-04-21

---

## 1. LINE 平台限制（最致命的外部約束）

| 問題 | 影響 | 需要的行動 |
|------|------|-----------|
| 每個租戶需要獨立的 LINE Official Account | 租戶要自己去 LINE Business 申請 OA，不是平台方能代建的 | Onboarding SOP 必須包含「協助租戶申請 LINE OA」|
| LINE Messaging API 每月免費訊息有上限 | 免費方案 200 則/月，輕量方案 ~NT$800/5000 則 | 計費模型要涵蓋或轉嫁 LINE 訊息費用 |
| Push Message vs Reply Message | Reply 免費但 token 有效期 30s；超時只能用 Push（扣額度） | debounce 1.5s + agent 回覆如果 > 30s，全變 Push = 消耗租戶額度 |
| LINE channel 驗證 (verified/unverified) | Unverified 帳號有更嚴格的 API 限制 | 文件要告知租戶必須通過 LINE 認證 |
| Webhook URL 每個 channel 只能設一個 | 租戶的 LINE OA webhook 必須指向平台 | 如果租戶已有其他系統用了 webhook，會衝突 |

---

## 2. 商業模式與計費

| 缺少的 | 為什麼重要 |
|--------|-----------|
| LLM 成本如何歸屬到租戶 | Gemini API 按 token 計費，每個租戶用量不同。需 meter 每次 agent.ainvoke() 的 input/output tokens |
| 定價模型 | 按訊息量？按工單量？按技師數？按月固定？Freemium? |
| 超額處理 | 月訊息用完了，AI 停止回覆？降級為轉接真人？自動升級方案？ |
| 計費週期與金流 | 台灣 B2B 常見月結 + 發票。需串接第三方金流（藍新/綠界）或人工對帳？ |
| 免費試用期 | 新租戶 14 天免費？試用期結束未付款怎麼辦？停用還是降級？ |

### Metering 架構建議

```
每次 agent.ainvoke() 完成後：
  -> 記錄 {tenant_id, input_tokens, output_tokens, tool_calls, latency_ms}
  -> 累加到 tenant.monthly_message_used
  -> 如果 used >= quota * 0.9 -> 發警告給 tenant_admin
  -> 如果 used >= quota -> 執行超額策略
```

---

## 3. 租戶 Onboarding / Offboarding 生命週期

### Onboarding（新租戶上線）

1. 業務簽約 -> 建立 tenant record
2. LINE OA 設定
   - 租戶已有 OA -> 提供 webhook URL + channel secret
   - 租戶沒有 OA -> 指導申請流程（需 1-5 工作天）
   - 設定 channel_id 對照 -> 驗證 webhook 連通
3. 基本設定
   - 選擇服務品牌（從平台支援清單勾選）
   - 設定服務範圍（地區）
   - 設定營業時間
   - 客製 AI 人設（選填，有預設值）
4. 技師建檔（手動輸入 or CSV 匯入）
5. 試營運（內部測試帳號驗證整條流程）
6. 正式上線

### Offboarding（租戶離開）

1. 停用帳號 -> is_active = false
2. 資料保留期 -> 90 天？180 天？法規要求？
3. 資料匯出 -> 租戶有權下載自己的資料（GDPR/PDPA）
4. 資料刪除 -> 過期後 purge（但 audit_log 可能需保留更久）
5. LINE OA -> 租戶自行處理（webhook 移除或指向其他系統）

---

## 4. 法規與合規

| 法規 | 影響 | 需要的 |
|------|------|--------|
| 台灣個資法 (PDPA) | 每個租戶是獨立的「個資檔案保有者」，平台方是「受託處理者」 | 資料處理委託契約 (DPA) 範本 |
| 跨租戶資料洩露責任 | RLS bug 導致 A 租戶看到 B 租戶資料 | 定期 RLS 審計 + 滲透測試 |
| 消費者個資刪除請求 | 客戶可以要求刪除自己的資料 | GDPR-style 刪除 API，但保留 audit_log |
| 電子通訊紀錄保存 | 金管會/消保法可能要求保存客服對話 N 年 | audit_log retention policy 與法規對齊 |
| B2B 契約 | 平台方 vs 租戶的 SLA、liability、data ownership | 法務範本 |

---

## 5. Noisy Neighbor 問題

| 資源 | 場景 | 防護措施 |
|------|------|----------|
| LLM API | 某租戶瞬間大量客訴 | Per-tenant rate limiter + LLM 呼叫佇列 |
| PostgreSQL 連線 | 某租戶複雜查詢佔滿連線池 | PgBouncer + per-tenant connection limit |
| LINE Push API | 某租戶群發通知耗盡 rate limit | Per-tenant LINE API 獨立 rate bucket |
| GCS 儲存 | 某租戶大量上傳圖片 | Per-tenant storage quota |
| Memory | 某租戶長對話佔用大量 RAM | Memory compression threshold per-tenant |

---

## 6. 品牌 OEM 衝突

| 場景 | 問題 | 解法 |
|------|------|------|
| 多家租戶都賣 Dormakaba | 共用平台 Dormakaba SOP？兩家維修方式不同？ | 平台 SOP = 原廠標準；租戶可 override |
| 品牌原廠上傳新 SOP | 會覆蓋所有租戶的技能嗎？ | 不會。OEM 上傳進平台層，租戶有 override 的不受影響 |
| 租戶自己加了平台沒有的品牌（如 Yale） | 其他租戶看不到 | 正確。租戶自訂 skills 不共享，除非同意上架為平台共用 |

---

## 7. 技師歸屬模型

| 模型 | 說明 | 現有架構支援 |
|------|------|-------------|
| 專屬技師 | 師傅只服務一家鎖匠店 | 支援（現有設計） |
| 共享技師 | 師傅同時跑多家店（像 Uber 司機） | 不支援 — 需要 technician_tenants 多對多表 |
| 平台媒合技師 | 師傅不屬於任何店，平台直接派工 | 不支援 — 需要 platform-level technician pool |

---

## 8. 客戶歸屬衝突

同一個人（同一個 LINE user_id）可能先找「鎖市」修鎖，後來找「台北鎖王」裝新鎖。

- 兩個租戶都有這個客戶的 user_facts（RLS 隔離，正確行為）
- 客戶可能抱怨「我之前說過地址了怎麼還要重講」
- 這是**設計決策，不是 bug**：跨租戶資料共享有個資法風險

---

## 9. 災難復原 & 資料備份

| 缺少的 | 多租戶後更重要的原因 |
|--------|---------------------|
| 跨租戶影響半徑 | 單租戶 DB 掛了影響你一家；多租戶影響所有客戶 |
| 備份策略 | Cloud SQL point-in-time recovery，但恢復時是恢復所有租戶 |
| 租戶級別恢復 | 某租戶要求「恢復到昨天」— 目前無法只恢復一個租戶 |
| 高可用 | Cloud SQL HA (failover replica) 變成必須 |

---

## 10. Per-Tenant 監控

```
必須新增的 metrics（per-tenant 維度）：

tenant.messages.count          — 每個租戶的訊息量
tenant.agent.latency_p99       — 每個租戶的 agent 回應時間
tenant.agent.error_rate        — 每個租戶的錯誤率
tenant.llm.tokens_used         — 每個租戶的 token 消耗（計費依據）
tenant.work_orders.created     — 每個租戶的工單量
tenant.work_orders.completed   — 完工率
tenant.line.push_count         — LINE push 使用量（成本追蹤）
tenant.storage.media_bytes     — 媒體儲存量
```

---

## 11. 微服務拆分觸發條件

| 觸發條件 | 門檻 | 拆什麼 |
|----------|------|--------|
| AI Agent 延遲拖垮 Dispatch API | Agent P99 > 8s 且 Dispatch 需要 < 500ms | Agent 獨立 Cloud Run |
| 某租戶流量佔 80% | 單一租戶 QPS > 全平台 50% | 該大戶獨立部署 |
| 團隊拆成 2+ 小組 | > 5 人且每週部署衝突 > 3 次 | 按 Domain 拆 repo + service |
| 合規要求物理隔離 | Enterprise 客戶/政府標案 | 該租戶獨立 DB + instance |

在這些門檻到達之前，拆微服務只會增加複雜度、降低開發速度。

---

## 12. 優先級總覽

| # | 因素 | 類別 | 嚴重度 |
|---|------|------|--------|
| 1 | LINE OA 每租戶獨立申請 + 費用 | 平台依賴 | **Critical** |
| 2 | LINE 訊息費用轉嫁/涵蓋 | 商業模式 | **Critical** |
| 3 | LLM token 成本 per-tenant metering | 計費 | **High** |
| 4 | 定價模型 & 金流串接 | 商業模式 | **High** |
| 5 | 租戶 onboarding/offboarding SOP | 營運 | **High** |
| 6 | 台灣個資法 DPA 範本 | 法規 | **High** |
| 7 | 跨租戶資料洩露 RLS 審計 | 安全 | **High** |
| 8 | Noisy Neighbor per-tenant rate limit | 穩定性 | **Medium** |
| 9 | 品牌 OEM SOP 衝突解決 | 知識庫 | **Medium** |
| 10 | 技師共享模型（跨租戶） | 商業模式 | **Medium** |
| 11 | 客戶跨租戶歸屬 | UX/法規 | **Medium** |
| 12 | Per-tenant 監控 metrics | 可觀測 | **Medium** |
| 13 | 災難復原（租戶級別恢復） | 基建 | **Medium** |
| 14 | 免費試用 & 超額處理策略 | 商業模式 | **Low** |
| 15 | White-label（租戶品牌化） | UX | **Low** |

**最關鍵的三件事**（先解決再談技術）：
1. **LINE OA 生態的限制** — 決定 onboarding 流程和成本結構
2. **定價模型** — 按什麼收費？怎麼 meter？怎麼收錢？
3. **DPA 法律範本** — 多租戶 = 受託處理者，法律責任完全不同
