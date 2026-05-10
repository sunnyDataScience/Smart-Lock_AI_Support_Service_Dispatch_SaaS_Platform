---
title: Consumer Tracking Entry — 消費者端工單追蹤入口
phase: DESIGN
gate: TR4
status: Active
owners:
  - PM
  - Tech Lead
  - Product Designer
related:
  - "[[_flows-bdd-test/v-model-left/E5x--workflow-work-order]]"
  - "[[02-design/specs/openapi]]"
  - "[[decision-log/E7x--pm-alignment-Q1-Q10]]"
last_reviewed: 2026-05-07
status: superseded
superseded_by: docs_v2/ (見 docs_v2/4-exploration/audits/vibecoding-mapping-table-2026-05-10.md)
superseded_at: 2026-05-10
supersede_cr: CR-0007
---

# 消費者端工單追蹤入口（Consumer Tracking Entry）

## 0. Purpose

本文件為 V1.0 消費者端追蹤入口之 **唯一規格真相來源**，提供：
1. F-022 流程之入口設計
2. LINE Bot intent + Web 路徑雙軌共存規則
3. 與 Q9=B Scope Change 共用 token 機制之契約

**對應 PM 拍板**：
- [[decision-log/E7x--pm-alignment-Q1-Q10|Q3=C]]：兩者並存（**LINE 主 / Web VIP 備援**）

## 1. 兩者並存策略（Q3=C）

| 入口 | 對象 | 觸發 | 後端端點 | 認證方式 |
|---|---|---|---|---|
| **LINE Bot**（主） | 所有客戶 | LINE intent `查工單` 或推播短連結點擊 | `getWorkOrderPublicStatus` | LIFF user_id 對應 work_order.customer_id |
| **Web 追蹤頁**（VIP 備援） | VIP / 非 LINE 用戶 | 推播短連結 `https://app.example.com/track/{token}` | `getWorkOrderPublicStatus` | HMAC-signed token（無需登入） |

> **核心設計**：兩者共用同一後端端點 + 同一 token 機制，僅 UI 載體不同。

## 2. LINE Bot Intent 設計

### Intent: `查工單`
- **觸發詞**：「查工單」/「工單進度」/「我的維修進度」/「現在到哪了」
- **分支**：
  1. 若 LINE user 綁定 1 張 active 工單 → 直接顯示
  2. 若 LINE user 綁定 N 張 active 工單 → Quick Reply 列出選單
  3. 若 LINE user 無 active 工單 → 回覆「目前沒有進行中的工單」
- **Skill 定義位置**：`agent/skills/data/_common/work-order-status.md`

### Intent: 推播短連結點擊
- **格式**：`https://app.example.com/track/{HMAC-signed-token}`
- **動作**：開啟 LIFF（內嵌瀏覽器）→ 走 Web 追蹤頁同一路徑

## 3. Web 追蹤頁規格

### 路徑
- `web/src/app/track/[token]/page.tsx` — PR #40 placeholder 已建

### Token 機制
引用 [[02-design/specs/openapi|openapi.yaml]] §`/api/v1/public/work-orders/{token}/status`：
- **簽章演算法**：HMAC-SHA256(secret, work_order_id|expiry|nonce)
- **TTL**：30 天
- **歸檔**：完工 90 天後 → 410 Gone
- **撤銷**：Redis `revoked:{token_hash}` set
- **Rate limit**：60 req/min per token / per IP

### PII 遮罩
- 技師姓名 → 僅露姓氏（例：「王師傅」）
- 技師電話 → mask 末四碼（例：`****1234`）
- 客戶地址 → 顯示村里級別（不顯示完整地址；客戶本人除外）

### UI 行為
- ETA polling：`on_the_way` 狀態每 30 秒重抓
- 其他狀態不 polling
- 點 `technician_phone_masked` → 顯示「致電技師」按鈕（`href=tel:`）
- SSR vs CSR：建議 **CSR**（避免 token 進 server log）

## 4. 與 Q9=B Scope Change 共用 token 機制

| 共用面向 | 細節 |
|---|---|
| Token 簽章 | 同一 HMAC secret，但 nonce 不同（避免 token 互通） |
| Rate limit | 共用 Redis bucket（同一 token 只能用於同一場景） |
| 撤銷清單 | 同一 Redis set |
| Audit log | 共用 `public_token_access` event type |

**對應 spec**：`/api/v1/public/scope-changes/{token}` 端點 — 走同 token 模式（[[02-design/specs/openapi|openapi.yaml]] §2406+）

## 5. 影響範圍

- **後端**：`api/routers/public.py` 須實作 `getWorkOrderPublicStatus`（PR #40 spec 齊；full impl 待 BE 工時 1.5d）
- **前端**：`web/src/app/track/[token]/page.tsx` full impl（PR #40 placeholder；待 FE 工時 5d）
- **Agent**：`agent/skills/data/_common/work-order-status.md` skill 須建立
- **DB**：`work_orders.tracking_token` 欄位（含 expiry / nonce / revoked_at）

## 6. Verification

- [ ] `getWorkOrderPublicStatus` BDD scenario 涵蓋 4 個 status code（200 / 404 / 410 / 429）
- [ ] LINE Bot `查工單` intent 對 N=0/1/N+ 三分支有 unit test
- [ ] PII 遮罩 unit test（grep `mask_phone` / `mask_name`）
- [ ] Web 追蹤頁 lighthouse score ≥ 90（行動裝置優先）

## 7. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | Claude (assisted) | 初版：兩者並存（LINE 主 / Web VIP 備）+ 共用 token 機制 + PII 遮罩規則（Q3=C 拍板） |
