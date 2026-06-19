---
title: CR-0040 Evidence 治理 — 角色可見性（BR-M09-02）+ 保存期（BR-M09-03）
status: implemented
tier: 4-exploration
created: 2026-06-19
owner-decision: ✅ 2026-06-19 業主裁決全採建議預設（見 §8）
related: M09 Evidence / Q026(照片可見權限) / Q027(保存) / BR-M09-02 / BR-M09-03 / CR-0038 階段1
---

> ✅ **§8 已裁決（2026-06-19，全採建議預設）+ 已實作（見 §10）。** CR-0038 階段1「公單收尾」兩個 P0（Evidence 角色可見性 + 保存期）。

## 1. 動機（WHY）

- **BR-M09-02 角色可見性（P0）**：`media_service.list_media_for_work_order` 只用 `work_order_id + tenant_id` 過濾，**無角色過濾** → 品牌/會計使用者會看到**全部**照片，含客戶家中環境照。Q026 明示「品牌商不可看客戶家中環境照」「會計一張足矣」。這是隱私 P0。
- **BR-M09-03 保存期（P0）**：`media_files` 只有 `created_at`，**無 `retention_until`**、無清除機制。Q027：預設 1 年；保固/客訴案保留至結案 + buffer。

## 2. 觸發面向

| 面向 | 命中 | 說明 |
|---|:-:|---|
| DB schema | ✅ | media_files 加 retention_until（+ 視 HD-1 加 audience 欄）|
| API contract | ✅ | list media 依角色回不同子集（行為變更，非 schema）|
| Business rule | ✅ | 誰看得到哪些 purpose / 保存多久 |
| Test plan | ✅ | 角色可見性 + 保存期 component 測試 |

## 3. 現況（grounded，file:line）

- `SQL/Schema_media.sql:18` `media_files`：id/tenant_id/uploader_user_id/work_order_id/dispute_id/`purpose`(enum 7 值)/filename/.../`created_at`。**無 audience、無 retention_until**。
- `media_service.py:186 list_media_for_work_order`：`WHERE work_order_id AND tenant_id`，零角色過濾。
- `purpose` 已分類：door_check_before/after、completion_before/after、dispute_evidence_customer/technician、other。

## 4. API 契約變更

- `GET .../work-orders/{id}/media`（`media_v2`）回傳依**呼叫者角色**過濾後的子集（同端點、同 200，但 items 因角色而異）。
- 不新增 error code；下載端點 `GET /media/{id}` 亦套同一可見性檢查（非授權角色取不該看的 media → 403/404）。

## 5. 領域 / 資料（依 HD-1 決定）

- **保存期**：media_files 加 `retention_until TIMESTAMPTZ`（建立時依 purpose/case 類型算），+ 清除機制（cron）。
- **可見性**：HD-1 決定「規則式（purpose×role 查詢時硬過濾，不加欄位）」或「加 audience 欄（per-media 可覆寫）」。

## 6. 測試計畫

`test_cr_0040_evidence_governance.py`（component）：
- 品牌角色 list media → 看不到 customer 環境照（door_check/completion before）；看得到完工成品照。
- 客戶/師傅 → 看得到自己案件全部。
- 下載非可見 media → 403/404。
- retention_until 依 purpose 正確設定（一般 1yr / 保固 2yr）。
- 清除 cron：過期 media 被軟刪、未過期保留。

## 7. 風險

- 過度限制 → 該看的角色看不到（緩解：規則表清楚、測試覆蓋每角色）。
- 硬刪不可逆（緩解：HD-3 軟刪優先）。
- 既有 media 無 retention_until → backfill（建立時間 + 預設 1yr）。

---

## 8. 🛑 Human Decisions Required

| # | 決策 | 建議預設（依 spec Q026/Q027）| 業主裁決（2026-06-19）|
|:-:|---|---|---|
| **HD-1** | 可見性模型 | **規則式過濾**（purpose×role，不加欄位）| ✅ **規則式過濾** |
| **HD-2** | 可見性規則（Q026）| 品牌不看環境照、只看成品照；會計看完工/付款必要照 | ✅ **依 spec Q026** |
| **HD-3** | 保存期值（Q027）| 一般 1 年；保固/客訴 2 年 | ✅ **一般1年、保固/客訴2年** |
| **HD-4** | 清除方式 | 軟刪（deleted_at）| ✅ **軟刪** |

## 9. Suggested Implementation Order（裁決後）

1. migration 048：media_files 加 retention_until（+ deleted_at 若 HD-4 軟刪）+ backfill 既有（created_at + 1yr）。
2. `media_service`：list/get 加角色可見性過濾（依 HD-2 規則表）；upload 時算 retention_until。
3. `media_v2` router：list/get 傳入 user.role；download 套可見性檢查。
4. 清除 cron（仿 gdpr forget cron）：retention_until < now 的 media 軟刪。
5. `test_cr_0040_evidence_governance.py` component。
6. redeploy smoke + 更新 CHANGELOG / 完成度 / 本 CR §進度。

---

## 10. 進度

✅ **done（2026-06-19，branch `feat/cr-0040-evidence-governance`）**：
- **migration 048**：media_files 加 `retention_until` + `deleted_at` + backfill 既有（dispute 2yr / 其餘 1yr，套 dev backfill 7 筆）+ 清除 partial index。
- **`media_service`**：`_hidden_purposes(role)` 規則表（Q026：品牌隱藏環境照 door_check/completion_before、會計隱藏 door_check）；`list_media_for_work_order` + `get_media` 加 `role` 過濾（`purpose <> ALL` + 排除 `deleted_at`，不可見 → **404 不洩漏存在性**）；`upload_media` 算 `retention_until`（dispute 或 warranty WO → 2yr，其餘 1yr）；`soft_delete_expired_media()` 清除函式。
- **`media_v2` router**：list/get 傳 `user.role`。
- **cron**：`realtime/media_retention_cron.py`（每日軟刪過期）+ main.py lifespan 掛載/收尾。
- **測試** `test_cr_0040_evidence_governance.py` **6/6 pass**（品牌列表排除環境照/看得到成品照 + admin 看全部 / 品牌 get 環境照 404 / 軟刪過期 + list 排除軟刪 + 純函式規則表 ×3）；回歸 media 19 + 226 unit 全綠。

⏳ **follow-up**：(a) 客戶端（track token）evidence 可見性對齊；(b) 保固案 retention 已涵蓋（service_category warranty）；(c) 前端 evidence 面板依角色顯示（後端已過濾，前端只是少顯示）。
