---
id: CR-0033
title: "Change Impact Analysis — 免責合規（三段免責同意紀錄 + 客戶 PDF 免責段 + consumer 同意端點）"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-19
target-release: TBD（補洞優先）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0033: 免責合規

> **Tier**: 4-exploration → CIA（per-change）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 Domain model / DB schema / API contract / Business flow）
> **驅動來源**: 20260617 gap-audit roadmap S3（免責合規）+ 雙領域盤點 + 藍圖 PDF「派工單整合分析報告」模組 4（施工免責與合規）+ CR-0026 §8-Q3（免責段 defer）
> **🛑 法務佔位 first（同 CR-0032/0035 mock-first）：三段文本用藍圖語意當佔位、標 `待法務 sign-off`，結構先建，正式法務措辭待業主裁決，不卡建置。**

---

## 1. Change Statement

**As-is**（盤點實證）：
- `appearance_change_consents` 表只針對門外觀變更；**無通用 `work_order_consents`**。
- `digital_signatures` 表存在（GAP #19，三種簽署方式）但只用於完工簽名。
- **免責條款文字零存儲、零引用**；客戶版電子工單 PDF（CR-0027）**無免責段**（僅 footer「成本不對外揭露」）。
- 工單流程缺「派工前/服務前免責同意」收集點。

**To-be**：建通用 `work_order_consents` 紀錄三段免責同意（新機安裝 / 破壞鎖 / 個資）+ consumer 同意提交端點（複用 work_order_status token）+ 客戶 PDF 加免責段（藍圖模組 4 三段文本佔位）+ 客戶 `/consent/{token}` 頁簽署。**不做** hard dispatch gate（派工前強制同意 = 流程變更，另 CR）。

**Driver**：藍圖模組 4 法律合規（新機開孔/破壞鎖免責/個資授權）；決議 4 客戶電子工單；audit 留痕（IP + timestamp）。

## 2. Affected Flow

| ID | Action | Description |
|---|---|---|
| `BF` 免責同意 | New | 客戶開 `/consent/{token}` → 勾選三段免責 → 提交 → 紀錄（IP + 時間 + 文本版本）|
| `SF` 電子工單 | Modified | 客戶 PDF 加免責段（三段文本佔位 + 簽署狀態）|

## 3. Affected API

| API | Endpoint | Action |
|---|---|---|
| 取免責條款 + 狀態 | `GET /consumer/consents/{token}` | New（回三段文本 + 已同意狀態）|
| 提交免責同意 | `POST /consumer/consents/{token}` | New（body: consents map）|

> 複用 `work_order_status` purpose token（與 /track 同一 token，免另鑄）。

## 4. Affected Data

| Entity | Action |
|---|---|
| `work_order_consents`（新表，migration 043）| work_order_id FK / consent_type(new_installation/lock_destruction/personal_data) / accepted / accepted_at / text_version / ip_address / created_at；UNIQUE(work_order_id, consent_type) 冪等 upsert |
| 三段免責文本 | service 層常數（藍圖模組 4 佔位，`text_version='blueprint-draft-2026-06'`，待法務）|

> **不新建**：legal_text_versions 版本主檔（過度設計）—— 文本先當常數，版本化 Phase B。
> **不擴**：digital_signatures（免責同意用 work_order_consents 獨立紀錄，簽名圖另案）。

## 5. Affected Test

work_order_consents upsert 冪等（同 type 重複提交更新非重複插入）；consumer GET 回三段文本 + 狀態；POST 記錄 accepted + ip；token purpose 防護 404；PDF 含免責段（掃文字）且**仍不含成本**。

## 6. Affected Architecture

| Concern | Notes |
|---|---|
| 新 ADR？ | 否（最小變更，複用 consumer token + PDF 範式；無新架構決策）|
| 複用 | public_token（work_order_status）、consumer_v2 router 模式、work_order_document_service（reportlab 範式）|
| Multi-tenant | work_order_consents 無 tenant_id，沿 work_order JOIN（同 invoices/work_order pattern）|

## 7. Human Decisions Required（§8）

🛑 **法務佔位 first 不卡；以下為佔位→正式的待裁清單。**

| # | Question | 佔位預設 | Owner | Status |
|---|---|---|---|---|
| 1 | 三段免責**正式法務措辭** | 藍圖模組 4 語意佔位（標 `待法務`）| 業主/法務 | open |
| 2 | 免責同意是否為**派工前 hard gate**？ | **否**（先紀錄，不強制擋派工；hard gate 另 CR）| 業主 | open |
| 3 | 簽名圖留痕 vs 勾選即可？ | **勾選 + IP + timestamp**（簽名圖另案）| 業主/法務 | open |
| 4 | 個資條款分「簡版確認」vs「完整政策」？ | **單段個資授權**（佔位）| 業主/法務 | open |
| 5 | 文本改版時舊工單是否需重簽？ | **不需**（工單記當時 text_version 快照）| 業主/法務 | open |

## 8. Suggested Implementation Order

1. migration 043：work_order_consents（idempotent，UNIQUE(work_order_id, consent_type)）
2. consent_service：三段文本常數 + record_consents（upsert）+ get_consents
3. API：GET/POST /consumer/consents/{token}（複用 work_order_status token）
4. PDF：work_order_document_service 加免責段（三段佔位文本 + 簽署狀態）
5. 前端 `/consent/{token}` 客戶頁（三段卡 + 勾選 + 提交）+ AuthGuard PUBLIC_PREFIXES
6. Tests（TDD）
7. 三同步

## 9. Risks & Rollback

| Risk | Mitigation |
|---|---|
| 法務措辭未定稿即出客戶 PDF | 文本標 `待法務 sign-off`；text_version 記錄；定稿後改常數 + 升版 |
| 成本外洩（PDF 加段時誤帶成本）| 免責段純法律文字，無金額欄；_fetch_customer_view 仍不取 unit_price |
| 同意紀錄不可否認性弱（僅勾選）| IP + timestamp + text_version 留痕；簽名圖強留痕另 CR |

**Rollback**：新表 + 新端點 + PDF 加段，全可逆（刪表/移除 PDF 段還原）。

## 10. Out of Scope

派工前 hard gate（流程變更）、legal_text_versions 版本主檔、簽名圖留痕、個資完整政策頁 → follow-up / Phase B（§8 待裁後）。

## 11. 實作進度

- ✅ **實作（`feat/cr-0033-disclaimer-consent`）**：
  - migration `043`：`work_order_consents`（consent_type/accepted/accepted_at/text_version/ip_address；UNIQUE(work_order_id, consent_type) 冪等 upsert；idempotent）。
  - `consent_service`：三段藍圖佔位文本常數（`CONSENT_TEXTS` + `TEXT_VERSION='blueprint-draft-2026-06'`，**待法務**）+ `record_consents`（ON CONFLICT upsert）+ `get_consents`（永遠回三段 + 狀態）。
  - 消費端點（`consumer_v2.py`，複用 `work_order_status` token）：`GET /consumer/consents/{token}`（三段文本 + 同意狀態）+ `POST`（勾選提交，upsert + IP 留痕）；purpose 防護 404、bad body 422。
  - PDF（`work_order_document_service`）：應付總額後、關防前插**免責段**（三段佔位文本 + ☑/☐ 簽署狀態）；best-effort 取同意狀態，缺失不阻斷 PDF；**仍不含成本**。
  - 前端 `/consent/[token]`（mobile-first CSR、bare fetch、三段卡 + 勾選 + 提交、全勾才可送）+ i18n `pages.consentPublic`（zh-TW/en）+ AuthGuard `PUBLIC_PREFIXES` 加 `/consent/`。
- ✅ **測試（router-level）**：`test_cr_0033_consent.py::TestConsumerConsentRouter` 4 pass（GET 三段 / POST 記錄 / purpose 404 / bad body 422）；`tsc --noEmit` 0 error。
- ✅ **migration 043 已套 dev DB + service/PDF 測試全綠**：record/get upsert 冪等 / unknown type 422 / PDF 含免責段；CR-0033 共 10 測試 + CR-0027/consumer 回歸 40 pass。
- ✅ **對抗式審查（安全/正確/治理 3 lens）後修正**（治理 lens clean）：
  - text_version **從 DB 讀回**每段簽署當時版本（達成 §8-Q5 快照意圖，原本誤回當前常數）。
  - consent value **嚴格 bool 驗證**（router + service 雙層）：防 `bool("false")==True` 強制轉換漏洞 → 422。
  - PDF 免責段**法律文本永遠顯示**（以 CONSENT_TEXTS 為底疊狀態）：fetch 失敗也出三段（全 ☐），不整段消失。
  - consent_service **tenant defense-in-depth**：沿 work_orders→...→users.tenant_id JOIN 驗工單屬租戶（token HMAC 之外的 DB 層守門）；錯租戶 404。
  - PDF merge **白名單欄位**（防未來 consent_service 回傳意外欄混入客戶 PDF）。
- ⏳ **已知限制（follow-up，與既有 public 端點一致）**：`request.client.host` 在 proxy（Cloud Run）後為 LB IP，真實客戶 IP 需 trusted-proxy header 中介（平台級）；public token 端點 rate limit（平台級 TODO，所有 /consumer/* 皆缺）。
- ⏳ §8 正式值：三段法務措辭 / 派工前 hard gate / 簽名圖留痕（待業主+法務）—— 佔位 first 不卡。
- 分支：`feat/cr-0033-disclaimer-consent`
