---
id: CR-0115
title: "師傅註冊擴充為 KYC 等級（登入/註冊分離 + 敏感 PII + 文件上傳）"
status: accepted
tier: 4-exploration
owner: HYBRID
created: 2026-07-05
target-release: dev_new_arch
product-version: null
supersedes: null
superseded-by: null
---

# CR-0115: 師傅註冊擴充為 KYC 等級（登入/註冊分離 + 敏感 PII + 文件上傳）

> **Tier**: 4-exploration → Change Impact Analysis（per-change ephemeral；實作後 archive）
> **Mandated by**: `.claude/rules/change-governance.md`（觸發面向：API contract / Domain model / DB schema / External integration / Test plan）

---

## 1. Change Statement

**As-is**：師傅自助註冊（`POST /api/v1/technicians/register`，tech-login 頁「註冊」tab）只收 **6 個欄位** —— 姓名 / 手機 / Email / 密碼 / 服務地區 / 專長品牌（capabilities）。註冊與登入同框 tab 擠在單一 440px 卡片。核准前 `is_active=FALSE`、`status=pending_approval`。

**To-be**：
1. **登入與註冊分離** —— `/tech-login` 只留登入；新增獨立 `/tech-register` **多步驟表單**（步驟 1 基本 → 步驟 2 專業 → 步驟 3 敏感/撥款 → 步驟 4 文件 → 確認）。
2. **註冊欄位擴充為 KYC 等級**（業主 2026-07-05 裁決：最大範圍）——
   - **Tier 1（非敏感）**：年資、自我介紹、交通工具、可服務時段、緊急聯絡人+電話、專業證照（自填）。
   - **Tier 2（敏感 PII）**：身分證字號、生日、通訊地址、撥款銀行帳戶（代碼+帳號）、統一編號（選填）。
   - **Tier 3（文件上傳）**：身分證正反面、證照掃描、保險證明/良民證。
   - **同意條款**：服務條款 + 隱私權同意、背景查核授權（勾選）。

**Driver**：業主回報現有註冊「資訊太少」、要求參考業界類似系統擴充。研究（PRO360 / ALOA / 各州鎖匠執照 / 水電師傅平台）顯示技師媒合/派工平台普遍收 **身分核實（身分證）+ 專業資格（證照/年資）+ 撥款帳戶 + 文件佐證**。本平台為 **B2B 派工 + 月結拆帳**，撥款帳戶與證照/年資（派工信任度）尤其關鍵。

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| 師傅自助註冊流（tech self-register，ID 待對 `PRIN-0001` 指派） | **Modified** | 單步 6 欄 → 多步驟 KYC 表單；新增文件上傳與同意條款環節 |
| 師傅上線審核流（technician onboard-approve，`technician_lifecycle_service`） | **Modified** | 核准前**審核頁需能檢視新欄位與上傳文件**（reviewer/admin 決策依據） |
| 登入流（`/tech-login`） | **Modified** | 移除註冊 tab，改「還沒有帳號？申請成為師傅」外連 `/tech-register` |
| 媒體上傳流（media upload） | **Modified/New** | 現行上傳需登入；註冊為**公開前帳號態** → 需公開前上傳策略（見 §8-2） |

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| 師傅註冊 FR（ID 待確認，對 `FR-0044`/`FR-0045` 技師 profile 佔位規格） | **Modified** | 註冊必填/選填欄位集擴充；驗證規則（身分證格式、銀行帳號、生日）新增 |
| 隱私權 / PII 處理 NFR | **New** | 身分證字號、銀行帳戶、證件掃描的**加密/遮罩/存取控管/保留政策**（KYC 資料最小揭露） |
| 上傳檔案 NFR | **New** | 檔案型別白名單（jpg/png/pdf）、大小上限、公開上傳 rate limit / 防濫用 |

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `registerTechnician` | `POST /api/v1/technicians/register` | Schema change | **No（加性）** | request body 新增大量選填/必填欄位；既有 6 欄不變，舊 caller 不送新欄仍合法（但業務上核准條件可能要求新欄） |
| 公開文件上傳 | `POST /api/v1/technicians/registration-documents`（暫名） | **New** | No | 公開前帳號態上傳；需 rate limit + 短期 token / 一次性關聯（見 §8-2） |
| `getTechnician` / 審核清單 | 平台/品牌審核端點 | Response change | No（加性） | 回應加新 profile 欄 + 文件清單供審核頁；敏感欄位**遮罩回傳**（見 §8-3） |
| `uploadMediaV2` | `POST /tenants/{tid}/media` | Enum change | No | `purpose` enum 加 `technician_id_doc` / `technician_cert` / `technician_insurance` |

**破壞性評估**：request 為加性（不移除既有欄、不改型別）→ 非破壞。但若把部分新欄設**必填**，等同對「透過 API 直接註冊」的既有整合造成軟破壞 → 屬 §8-4 決策。

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `technicians` | 新增非敏感欄：`years_experience INT`、`bio TEXT`、`vehicle_type VARCHAR`、`availability_note VARCHAR`、`emergency_contact_name VARCHAR`、`emergency_contact_phone VARCHAR` | 一次 online migration；全 nullable，backfill 不需 |
| `technicians`（或新表 `technician_kyc`） | 敏感 PII：`national_id`、`birth_date`、`address`、`bank_code`、`bank_account`、`tax_id` | **儲存位置與加密方式待 §8-1**（獨立表 + 欄位加密 vs 主表明文 vs app 層遮罩） |
| `technician_certification` | 沿用既有表存自填證照（cert_name/brand/obtained_at/expires_at） | 無 DDL；註冊時 INSERT |
| `media` + `technician_registration_document`（暫名關聯表） | 文件上傳落 media（本機 `MEDIA_ROOT`，可換 GCS，schema 不變）+ 關聯表綁 technician_id / doc_type / media_id / 審核狀態 | 新表 online migration |
| `users`/`technicians` state | `status=pending_approval` 語意不變；文件審核可能新增子狀態（見 §8-5） | app-level |

**狀態機影響**：師傅生命週期 `pending_approval → active` 不變；是否插入「文件補件中 / 待核實」中間態屬 §8-5。

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `test_technician_login_status_gate.py` | Update | 註冊 body 擴充後仍 pending / 核准後可登入 |
| 註冊欄位驗證（新） | New | 身分證格式、銀行帳號、生日、必填/選填邊界、同意未勾拒絕 |
| 公開文件上傳（新） | New | 型別白名單、大小上限、rate limit、未關聯 technician 拒絕、跨 technician 存取拒絕 |
| PII 遮罩（新） | New | 審核端點回傳 national_id / bank_account **遮罩**（僅末 N 碼）；非授權角色不得取全值 |
| 審核頁文件檢視（新） | New | reviewer/admin 可列文件、非授權角色 403 |

覆蓋率：預估 +8~12 TC。

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Unchanged | 仍在 tech 身分域（權威庫 tech-db + 投影）；註冊寫 tech conn |
| PII 儲存 | **需 ADR** | `ADR-NNNN`：敏感 PII 儲存策略（獨立 `technician_kyc` 表 + 欄位加密 / KMS vs pgcrypto vs app 層）＋遮罩讀取＋保留與刪除（GDPR/個資法） |
| 公開上傳 | **需 ADR/決策** | 公開前帳號態的文件上傳如何防濫用（rate limit、短期 token、先建 pending 帳號再上傳） |
| External integration | 檔案儲存 | 本機 `MEDIA_ROOT`（MVP）；雲端須確認 GCS bucket 與存取權（敏感證件不可公開 URL） |
| 投影鏡射 | Check | 新增欄位是否需鏡射到品牌庫投影（`tech_mirror` 白名單）—— 敏感 PII **不應**鏡射到品牌庫（最小揭露） |

## 8. Human Decisions Required

✅ **§8 全數裁決 2026-07-05（業主）。** code 解凍，依 §9 實作。

| # | Question | Owner | Status | Decision（2026-07-05 業主） |
|---|---|---|---|---|
| 1 | 敏感 PII（身分證/銀行帳戶）怎麼存？ | Architect/業主 | **decided** | **(a) 獨立 `technician_kyc` 表 + 欄位加密 + 讀取遮罩、不鏡射品牌庫** |
| 2 | 文件上傳時機與授權（註冊是公開前帳號態）？ | Architect/業主 | **decided** | **(a) 兩階段：先送基本資料建 pending 帳號 → 回一次性 token → 憑 token 上傳** |
| 3 | 審核頁誰能看敏感 PII 全值 / 文件？ | 業主 | **decided** | **(a) 平台管理員看全值＋文件、品牌端唯讀遮罩** |
| 4 | 哪些新欄「必填」？ | 業主/UX | **decided** | **(a) 必填=年資/服務地區/緊急聯絡人/同意條款；PII+文件核准前補即可** |
| 5 | 是否需要「文件待核實」中間狀態？ | 業主 | **decided** | **(a) 不加，沿用 pending_approval（零狀態機變更）** |
| 6 | PII/證件保留與刪除政策？ | 業主/法遵 | **decided** | **(c) 本 CR 先不定、記 backlog（帳號終止後刪除天數 N 另定）** |
| 7 | 雲端證件儲存落點？ | Architect | **decided** | **分階段：本機 `MEDIA_ROOT` 先動、GCS private bucket + signed URL 另 CR** |

## 9. Suggested Implementation Order

§8 全數裁決後，依相依順序實作（各步一 branch，`--no-ff` 併回 dev_new_arch）：

1. **Decisions** → 寫 `ADR-NNNN`（PII 儲存策略 + 公開上傳策略，記 §8-1/§8-2 結論）
2. **Schema** → migration：`technicians` 非敏感欄 + `technician_kyc`（或加密欄）+ `technician_registration_document` 關聯表 + `media.purpose` enum
3. **Domain/Service** → `register_technician` 擴充（寫非敏感欄 + KYC 表 + 證照 INSERT）；PII 加密/遮罩 helper；文件上傳 service（依 §8-2 時機）
4. **API** → `registerTechnician` body 擴充（openapi）；公開文件上傳端點（依 §8-2）；審核端點回傳新欄 + 遮罩（依 §8-3）
5. **Tests** → §6 全部（先 TDD RED）
6. **UI（前端）** → `/tech-login` 拆註冊 tab → 登入 only + 連結；新 `/tech-register` 多步驟表單（步驟 1 基本 / 2 專業 / 3 敏感撥款 / 4 文件 / 確認）；i18n
7. **審核頁** → 平台 console 師傅審核頁顯示新欄 + 文件檢視（依 §8-3）
8. **Traceability** → 更新 traceability matrix（新 BF/UF/SF/API/TC）
9. **Docs sync** → docs_html regen；completion-status + CHANGELOG

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 敏感 PII 外洩（身分證/銀行/證件） | Medium | **High** | 獨立表 + 加密 + 讀取遮罩 + 存取角色最小化 + 私有 bucket；不鏡射到品牌庫 |
| 公開上傳端點被濫用（塞垃圾檔） | Medium | Medium | 兩階段 token（§8-2a）或 rate limit + 型別/大小白名單 |
| 欄位過多 → 註冊放棄率升高 | High | Medium | 多步驟表單 + PII/文件核准前補件（§8-4a）+ 進度指示 |
| 必填新欄軟破壞 API 直連 | Low | Low | 新欄預設選填、必填集最小化（§8-4） |
| 雲端證件公開 URL 誤設 | Low | High | private bucket + signed URL；CI 檢查（§8-7） |

**Rollback**：schema 加性（新欄 nullable、新表獨立）→ 反向相容；前端 `/tech-register` 為新頁，回退僅需還原 `/tech-login` 註冊 tab。可 feature-flag 新表單、异常時切回舊 6 欄 tab。

## 11. Out of Scope

- 自動背景查核 / 第三方 KYC 供應商串接（本 CR 只蒐集 + 人工審核；自動核實另 CR）
- 證照到期自動提醒 / 重新認證流程（另 CR）
- 撥款系統與銀行帳戶的實際請款串接（金流未接，見 completion-status）
- 品牌授權（technician_brand_authorization）自助申請（CR-0114 已定「標示」語意，不在此）

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主） | sunny | 2026-07-05 | ✅ §8 全數裁決 |
| Architect | | | |
| Engineering Lead | | | |
| QA Lead | | | |

---

## 進度

_依 §9 順序實作，每步一 branch、`--no-ff` 併回 dev_new_arch。_

- ⏳ S1 Decisions/ADR — 待
- ⏳ S2 Schema（technicians 非敏感欄 + technician_kyc 加密表 + registration_document 表 + media purpose）— 待
- ⏳ S3 Domain/Service（register 擴充 + PII 加密/遮罩 + 兩階段 token 上傳）— 待
- ⏳ S4 API（register body + 公開上傳端點 + 審核回傳遮罩）— 待
- ⏳ S5 Tests — 待
- ⏳ S6 UI（/tech-login 拆分 + /tech-register 多步驟）— 待
- ⏳ S7 審核頁（平台 console 顯示新欄+文件）— 待
