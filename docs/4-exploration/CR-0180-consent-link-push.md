# CR-0180 — CIA：免責簽署連結 LINE 主動推播（UAT-0720-06 前半段）

- **日期**：2026-07-22
- **來源**：0720 Irene issue list「Where to sign 免責聲明？」；Plane UAT-0720-06（seq 46）
- **狀態**：🛑 **CIA 產出，停在 §8 等業主裁決**（觸發 API contract＋External integration＋草稿法律文本對外）

## §1 現況（codegraph 稽核 2026-07-22）

簽署鏈**後半段已完整、前半段完全缺席**：
- ✅ public 簽署頁 `/consent/[token]`（CR-0033）→ `/consumer/consents/{token}` GET/POST → `work_order_consents` upsert＋IP 留痕
- ✅ token 簽發器既在：`public_token.generate_token(wo_id, purpose='work_order_status')`（HMAC stateless，30 天 TTL，consent 端點刻意複用此 purpose）
- ✅ LINE 推播基建既在：`line_push_service.push_to_work_order_customer`（notify_delay 同 pattern）
- ✅ 後台模組 4 ConsentPanel 唯讀顯示三段簽署狀態
- ❌ **全 repo 無任何地方鑄造並發送 /consent/ 連結**——docstring 說的「LINE 推播短連結」入口不存在，客戶實際到不了簽署頁

## §4 最小方案（偵察已定，半天工作量）

1. `consent_service.send_sign_link()`：租戶守門 → generate_token → 組 `{WEB_BASE_URL}/consent/{token}` → LINE 推文字 → `work_order_events` 留痕（token_hash）→ 回 `{notification_sent, channel, public_path}`
2. 新端點 `POST /tenants/{tenantId}/work-orders/{id}/consents:send-link`（guard 對齊既有 GET consents＋idempotency）＋ openapi.yaml
3. ConsentPanel 加「發送簽署連結」按鈕：LINE 推成功顯示已送；客戶未綁 LINE（channel='none'）給 admin 完整連結可複製
4. 測試：推播文字含連結且 token 可驗、非 LINE 客戶備援、越租戶 404

## §8 Human Decisions Required 🛑

1. **草稿法律文本對外**（關鍵）：三段免責文本目前是「待法務定稿」佔位（`TEXT_VERSION=blueprint-draft-2026-06`，法務窗口=Irene）。做了按鈕＝把草稿文本正式推給真實客戶簽。**要等法務定稿才開放此按鈕，還是先上（測試環境/內部驗證用）？**
2. **token 授權外溢知情**：consent 複用 `work_order_status` token（CR-0033 既定設計）——發簽署連結等於同時發了工單進度查詢授權（同 token 可查工單進度）。維持複用或另立 purpose？（維持＝零改動；另立＝多一段 token 邏輯）
3. **WEB_BASE_URL 部署 parity**（上線前必做）：`api.sh`/compose 皆未烤入 `WEB_BASE_URL`，prod 未設會組出 `https://lock-ai-web.example.com/consent/…` 死連結——既有 Flex 連結（/track/scope、/quotes）同病。本 CR 是否順手把 WEB_BASE_URL 烤入 api.sh？（建議：是；0719 部署參數 parity 雷同源）

## §9 建議實作順序（裁決後）

1. WEB_BASE_URL 烤入 api.sh＋確認 Cloud Run 現值（決策 3）
2. service＋endpoint＋openapi（依決策 2 的 token 語意）
3. ConsentPanel 按鈕＋i18n（依決策 1 決定按鈕開放條件）
4. 測試＋（若走 outbox Flex 重試路線可日後平移，不構成回頭路）

## 附註

- UAT-0720-06 其餘兩問另行：「工單 two version」＝v1/v2 雙棧遷移設計非 bug（已在卡上說明）；「服務條款修改入口」＝等法務文本定稿後做文本主檔＋編輯 UI（與決策 1 同一前置）。
