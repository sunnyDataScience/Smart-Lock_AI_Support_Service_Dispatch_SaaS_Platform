---
id: CR-0176
title: GDPR Crypto-Shredding — T0 銷毀 per-subject DEK（FR-API-16 / NFR-Priv-008 補洞）
status: in-progress
tier: 4-exploration
type: CIA
date: 2026-07-21
decided: 2026-07-21（業主「照建議」——HD-1~HD-7 全採建議欄）
author: Claude (codegraph 稽核驅動)
related:
  - FR-API-16
  - NFR-Priv-008
  - CR-0164 (GDPR forget 三缺口)
  - CR-0173 (技師 line_user_id Fernet 加密)
  - ADR-020 (三庫物理隔離)
  - docs/audit/smartlock-docs-capability-coverage-20260721.md
gate: 🛑 停在 §8 等業主裁決，未實作任何 code
---

# CR-0176 — GDPR Crypto-Shredding（T0 銷毀 per-subject DEK）

## §0 TL;DR

- **文件宣稱**（FR-API-16 / NFR-Priv-008）：GDPR forget 流程 **T0 銷毀 DEK（crypto-shredding）→ 資料即刻不可復原**；T+30d 硬刪 ciphertext row；append-only audit ledger 保留。
- **實作現況**（`api/services/gdpr_forget_service.py:204 soft_delete`）：T0 是**直接明文覆寫** `UPDATE users SET display_name='[REDACTED]', email='[REDACTED-'||id||']', phone=NULL`——**沒有任何 DEK、沒有 crypto-shredding**。全庫無 `crypto_shred`/`key_destroy`/`envelope` 命中（codegraph 稽核 2026-07-21）。
- **落差本質**：crypto-shredding 的前提是「PII 以**可單獨銷毀的每主體金鑰**加密」。目前 PII 明文落庫，`pii_crypto.py`（KYC）與 `line_uid_crypto.py`（CR-0173）雖有 Fernet 欄位加密，但都用**單一 master key**——銷毀它會讓**全部人**的資料不可讀，無法「只 shred 一個 data subject」。所以要補這洞，得先引入 **envelope encryption + per-subject DEK 註冊表**。
- **這是 data + domain + architecture 級變更**，依 `.claude/rules/change-governance.md` 硬 gate：**先產 CIA、停在 §8 等業主裁決，才動 code**。本文即該 CIA。

---

## §1 觸發判定（7 面向命中 → CIA 必須）

| 面向 | 命中 | 說明 |
|---|---|---|
| User/Business flow | ✅ | GDPR forget 的 T0 語意由「明文覆寫」改「銷毀金鑰」 |
| API contract | ⚠️ 輕 | 對外端點（`/gdpr/forget-requests`、`:soft-delete`、`:hard-delete`）**簽章不變**；語意與稽核欄位變 |
| Domain model | ✅ | 新增 entity：`DataEncryptionKey`（DEK 生命週期 active→destroyed） |
| DB schema | ✅ | 新表 DEK registry + PII 欄位密文欄 + migration + backfill |
| External integration | ⚠️ | KEK/master key 來源（Secret Manager / GCP KMS）— 見 HD-3 |
| Test plan | ✅ | 新測試類別：crypto-shred 後不可解、per-subject 隔離、legal-hold 交互 |
| Architecture boundary | ✅ | 引入金鑰管理層（key service）；三庫（品牌/技師/平台）各自的 PII 都要納管 |

→ 7 面向命中 5.5，**CIA 必須**，不可直接改 code。

---

## §2 現況（as-is）

- **T0 soft_delete**（`gdpr_forget_service.py:242-259`）：`UPDATE users SET display_name='[REDACTED]', email='[REDACTED-'||id||']', phone=NULL`。技師列改走權威庫 + `mirror_rows`（CR-0112）。PII 清除失敗屬硬失敗（CR-0164 D，不假性合規）。
- **T+30 hard_delete**（`:284`）：驗 `hard_delete_eligible_at <= NOW`（`HARD_DELETE_COOLDOWN_DAYS=30`）→ 物理刪 users row。cron `gdpr_hard_delete_cron.py` 每日掃。
- **legal-hold 前置**（`_has_active_legal_hold:51`）：subject 有 legal_hold media → 423 擋。
- **audit ledger**（`_forget_audit:33` → `audit_log_service.log_event`）：全流程 append-only（hash chain）。
- **既有欄位級加密（單 master key，非 per-subject）**：
  - `api/core/pii_crypto.py`：Fernet `encrypt_pii`/`decrypt_pii`（KYC PII），`@lru_cache _fernet()` 讀單把 master key。
  - `api/core/line_uid_crypto.py`（CR-0173）：Fernet + HMAC blind index，`LINE_UID_ENC_KEY`/`LINE_UID_BIDX_KEY`，單把。
- **問題**：這兩者能「加密欄位」但**不能 crypto-shred 單一主體**——因為所有人共用一把 key。

---

## §3 目標（to-be）

Envelope encryption：
```
KEK（master，Secret Manager / KMS，全系統一把）
  └─ 加密 ─▶ DEK（per data-subject，存 dek_registry）
                └─ 加密 ─▶ 該 subject 的 PII 欄位密文
```
- **寫 PII**：取（或建）該 subject 的 DEK → 用 DEK 加密欄位 → 存密文。
- **讀 PII**：用 KEK 解 DEK → 用 DEK 解密欄位。
- **forget（T0 crypto-shred）**：**銷毀該 subject 的 DEK**（清空/覆寫金鑰材料，留 tombstone）→ 其所有 PII 密文**瞬間不可復原**，不需逐欄覆寫、不需等 T+30。
- **T+30 hard_delete**：仍物理刪殘留 ciphertext row（defense in depth）；audit ledger 保留 ≥ 法定年限。

---

## §4 契約 / 介面影響（API contract）

- **對外 endpoint 簽章不變**：`POST /tenants/{tid}/gdpr/forget-requests`、`:soft-delete`、`:hard-delete`（`gdpr_forget_v2.py`）request/response schema 不動 → **無 breaking**。
- **內部語意變**：`soft_delete` 的 action 由「redact overwrite」改「destroy DEK」；audit `extra` 增 `dek_id` / `crypto_shredded_at`。
- **PII 讀寫路徑**：所有讀 `users.display_name/email/phone`（及 §HD-2 選定的其他表）的 service 需改走解密 helper（影響面廣，見 §6 盤點）。

---

## §5 Domain model 影響

新增 entity **DataEncryptionKey（DEK）**：
- `dek_id`、`tenant_id`、`subject_user_id`（或 §HD-1 選定的粒度鍵）、`wrapped_dek`（KEK 加密後的 DEK 材料）、`key_version`、`status`（active / destroyed）、`created_at`、`destroyed_at`、`destroyed_by`。
- 生命週期：`active` → （forget）→ `destroyed`（wrapped_dek 清空、destroyed_at 蓋章；row 保留為 tombstone 供稽核）。
- 不變式：一個 subject 至多一把 active DEK；destroyed 後不可復活（新資料需新 subject 或拒絕）。

---

## §6 DB schema 影響

- **新表** `saas.data_encryption_key`（DEK registry，見 §5 欄位）+ index（subject_user_id, status）。
- **PII 欄位密文化**：對 §HD-2 選定的欄位加 `<col>_enc`（bytea/text 密文）欄；過渡期明文欄與密文欄並存（dual-read），cutover 後 DROP 明文欄。
- **三庫都要**（ADR-020）：品牌庫 `users`、技師權威庫 `users`（+ KYC，已 Fernet）、平台庫 `users` 各自納管；DEK registry 放哪庫需定（見 HD-1）。
- **backfill**：既有明文 PII 需逐列建 DEK + 加密（**app 層，Fernet 不能在 SQL 跑**，比照 CR-0173 `scripts/backfill_*`）。
- **migration**：至少 3 支（DEK registry / PII enc 欄 / cutover DROP），跨三庫。

---

## §7 測試計畫影響

新增測試類別：
- crypto round-trip（KEK→DEK→欄位）與非確定性密文。
- **crypto-shred 後不可解**：destroy DEK → decrypt 該 subject PII → raise / 回 tombstone，**永不回明文**。
- **per-subject 隔離**：shred A 不影響 B 的可讀性（這正是單 master key 做不到、本 CR 的核心價值）。
- legal-hold 交互：hold 中 subject 不得 shred（沿用 423）。
- dual-read 過渡：明文回退 / 密文優先 / backfill 冪等。
- 回歸：forget 全流程（received→crypto-shred→T+30 hard delete→audit chain 完整）。

---

## §8 🛑 Human Decisions Required（✅ 業主 2026-07-21 裁決：「照建議」全採建議欄）

> 以下每項填完，我才依 §9 順序實作。

| # | 決策 | 選項 | 我的建議 |
|---|---|---|---|
| **HD-1** | **DEK 粒度** | (a) per-subject（每 user 一把）(b) per-tenant（每租戶一把）(c) per-(tenant,purpose) | **(a)**——唯一能「只 shred 一個 data subject」而不波及他人；成本=DEK 數量多（可接受，registry 輕量） |
| **HD-2** | **納入 crypto-shred 的 PII 範圍** | (a) 僅 `users`(display_name/email/phone) (b) +`work_orders` 客戶欄(customer_name/phone/address) (c) +`conversations`/LINE 訊息 (d) 全部含 KYC | **(b)**——forget 針對「身分+聯絡」PII，users+工單客戶欄是核心；KYC 已 Fernet（另評估遷 per-subject）；對話/訊息量大另立 CR |
| **HD-3** | **KEK（master）來源** | (a) app 層 Fernet master（Secret Manager env，沿用 pii_crypto 慣例）(b) GCP KMS envelope（KMS 加解 DEK） | **(a) 先行、(b) follow-up**——先沿用專案既有 Fernet 慣例快速落地；KMS 更合規但增運維，對齊上雲窗口再升 |
| **HD-4** | **「銷毀 DEK」語意** | (a) 硬刪 DEK row (b) 保留 tombstone（清空金鑰材料 + destroyed_at 蓋章） | **(b)**——可稽核「何時、被誰銷毀」而金鑰不可復原（GDPR 問責 + 不可逆兼顧） |
| **HD-5** | **既有明文 PII 過渡** | (a) 一次性 backfill 後即 cutover (b) dual-read 過渡窗 + 背景 backfill + 後 DROP 明文欄 | **(b)**——比照 CR-0173，零停機、可回退；DROP 明文欄為獨立收尾步 |
| **HD-6** | **T0 crypto-shred 與 T+30 hard delete 併存？** | (a) crypto-shred 取代 hard delete (b) 兩者併存 | **(b)**——crypto-shred=即時不可讀（滿足「T0 銷毀」）；hard delete=移除殘留 ciphertext（defense in depth）；audit ledger 均保留 |
| **HD-7** | **讀 PII 效能 / 快取** | (a) 每次解密不快取 (b) DEK 解密結果 per-request 快取，forget 後即時逐出 | **(b)**——避免同 request 重複解 KEK→DEK；被 shred 的 subject 不快取/立即失效 |

---

## §9 Suggested Implementation Order（待 §8 定案後）

- **S0** 全域 PII 欄位盤點（哪些 service 讀 users.display_name/email/phone + §HD-2 選定欄）+ 現有 Fernet 用量地圖；產出改造清單。
- **S1** DEK registry 表 + KEK 加密 + `key_service`（get_or_create_active / decrypt_dek / destroy_dek），單元測試（含 destroy 後不可解）。
- **S2** PII 欄位密文欄 + 讀寫 helper（dual-read：enc 優先、明文回退）；先 `users`（品牌庫）。
- **S3** backfill 腳本（app 層 Fernet，比照 `scripts/backfill_tech_line_uid_encryption.py`），三庫分批。
- **S4** `gdpr_forget_service.soft_delete` 改為 **destroy DEK**（取代明文 UPDATE overwrite）；audit 增 `dek_id`/`crypto_shredded_at`；legal-hold 前置不動。
- **S5** 讀路徑全面 cutover + DROP 明文欄（獨立步、可回退前保留窗）。
- **S6** 測試補齊（§7）+ 更新 `21_Traceability_Matrix` 對應 FR-API-16/NFR-Priv-008 row + CHANGELOG + 完成度文件。

---

## §10 風險 / 回滾

- **風險 R1**：讀路徑改造面廣，漏改一處 → 該處讀到密文亂碼。緩解：dual-read + S0 盤點 + grep 收斂 + 型別 SoT 檢查。
- **風險 R2**：KEK 遺失 = 全部 DEK 不可解 = 全 PII 不可讀（比明文更脆）。緩解：KEK 走 Secret Manager + 備援 + 輪替程序（HD-3(b) KMS 可再降此風險）。
- **風險 R3**：backfill 期間新舊寫入交錯。緩解：dual-write（明文欄過渡期同步）或 backfill 前先切寫路徑。
- **回滾**：S1-S3（純新增，dual-read）可安全回滾（密文欄留著、讀仍回退明文）；S4（forget 改銷毀 DEK）與 S5（DROP 明文欄）是不可逆點——S5 前務必確認 S1-S4 穩定。

---

## §11 進度

- ✅ **S1 done**（branch `feat/cr-0176-gdpr-crypto-shred`）：DEK 基礎建設落地——
  `core/dek_crypto.py`（envelope 純密碼學：KEK wrap/unwrap DEK + 加解密）＋
  `services/dek_service.py`（registry 生命週期：get_or_create／encrypt_pii／decrypt_pii／
  destroy_dek tombstone ＋ 請求域 cache）＋ migration 112（`saas.data_encryption_key`
  ＋ partial unique index ＋ tombstone CHECK 不變式 ＋ users 密文欄備妥）。
- ✅ **S4 done**：`gdpr_forget_service.soft_delete` 接 `destroy_dek`（crypto-shred，
  audit 增 `dek_crypto_shredded`；HD-6 明文清除併存過渡）。
- ✅ **S6（unit）done**：unit **11 passed**——crypto round-trip／**per-DEK 隔離**／
  非確定性／銷毀不可解（6）＋ 服務層 encrypt→decrypt→destroy→不可讀 ＋ **shred A 不影響 B**
  ＋ 無 DEK no-op ＋ 重用 active（5）；皆純函式/in-memory registry，不碰 DB。
  migration 112 **拋棄式 Postgres 16 實測**（DDL／ON CONFLICT 匹配 partial index 去重／
  tombstone／CHECK 反例全綠）。
- ✅ **S2 done（2026-07-22，branch `feat/cr-0176-s2-pii-cutover`）**：品牌庫 users 三欄
  dual-write/read cutover——
  - helper（`dek_service.py`）：`USER_PII_FIELDS`／`encrypt_user_pii`（同句寫入用）／
    `dual_write_user_pii`（RETURNING 後補寫，enc「只缺不舊」不 stale）／
    `decrypt_user_pii_row`（**enc 優先、明文回退；DEK 已銷毀＝None fail-closed 不回退明文**）。
  - **9 個品牌庫寫入點全接**（偵察窮盡對帳：CIA 原記 11 點中 #1 register_technician、
    #6 create_technician 落技師權威庫＝延伸範圍，本輪 9 點）：create_staff_user／
    register_vendor（enc 同句 INSERT）、update_profile（同句 UPDATE，技師列跳過）、
    create_conversation upsert（同交易補寫）、staff_application approve（交易內同句）、
    create_customer（RETURNING＋同交易補寫）、update_customer（整體取代＝三欄全量、同交易）、
    escalation phone 回填（RETURNING＋best-effort）、gdpr soft_delete（**改為同句清空
    *_enc**——早於 hard delete 的 defense in depth，dual-read 回退 [REDACTED]）。
  - 讀路徑參考接線 2 處：`get_profile`（/auth/me）＋ `_fetch_customer_row`（單筆客戶）。
    **列表讀路徑（list_customers/list_staff_users/conversations）過渡窗維持明文**（明文
    仍權威且與密文同值），S5 一併切換。
- ✅ **S3 script done（同輪）**：`scripts/backfill_user_pii_encryption.py`（sync psycopg、
  冪等 WHERE 明文非空∧enc 空、**destroyed DEK 絕不重建**、[REDACTED] 列跳過、KEK 不符
  exit 3 fail-loud、--dry-run 不建 DEK；**不清明文**）。**prod 實跑待業主環境**。
- ⬜ **S5 pending**：列表讀路徑切換＋ DROP 明文欄（不可逆點）。**新盤出的 S5 前置**：
  - ⚠️ email/phone 有 **WHERE 等值查詢**（login `auth_service.py:54/:250`、EMAIL_TAKEN
    去重、phone 去重 `customer_service.py:383`、password_reset）——DROP 前須先建
    **blind index**（比照 CR-0173 bidx）或明確裁決保留該兩欄明文。
  - ⚠️ `users.address` 有寫讀點但不在 HD-2 users 欄位清單（歸 work_orders phase 2 脈絡）
    ——S5 前需業主澄清 address 歸屬。
- ⬜ **範圍延伸**：work_orders 客戶欄（HD-2 phase 2）、技師/平台庫 users（ADR-020 三庫；
  技師列品牌庫投影由 `mirror_rows` 整列覆蓋，enc 恆 NULL＝回退明文，待技師庫同款覆蓋）。

> **S2/S3 驗證**：unit **17 passed**（S2 新增 6：enc-first／明文回退／shred fail-closed／
> dual-write SQL／空 no-op ＋ 既有 11 回歸），皆 in-memory 不碰 DB；DB 整合測試（真
> migration 112 庫上 9 寫入點 round-trip）留業主環境。
> **deploy**：prod 設 `GDPR_DEK_KEK`（Secret Manager）→ **先套 migration 112 再佈本輪
> code**（寫入點已引用 *_enc 欄，順序顛倒會 500）→ 跑 S3 backfill（同一組 KEK）。
