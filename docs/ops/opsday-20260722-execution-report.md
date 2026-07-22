# OPS 批次日執行報告 — 2026-07-22

> runbook＝`docs/ops/ops-batch-day-20260722.md`。本檔記錄**實際執行結果**（對照 0719 `cloud-deploy-report`）。
> 執行者：Claude（業主 sunny@funngo.ai gcloud 認證下逐步執行＋判讀）。基準：0719 部署（水位 110、七服務舊 revision）。

## 執行摘要：Step 1/2/4/5/6 完成 ✅；Step 3 WIF 待 gh 安裝

| Step | 內容 | 結果 |
|---|---|---|
| 1 | 5 把金鑰建立＋授權 | ✅ GDPR_DEK_KEK／USER_PII_BIDX_KEY／MEDIA_ENC_KEY／LINE_UID_ENC_KEY／LINE_UID_BIDX_KEY 建立＋runtime SA accessor；既有 9 把齊備 |
| 2 | DB migration | ✅ 品牌庫 111-114 套用+登錄（水位 110→114）；技師庫 Schema_line_notify（enc/bidx 欄+索引）；套前備份已建 |
| 3 | CD WIF | ⬜ **未做**——需先 `brew install gh && gh auth login`（本機無 gh）。腳本 `opsday-20260722-3-wif.sh` 備妥，獨立於重佈 |
| 4 | 重佈 7 服務 | ✅ 全新 revision，image tag `ad7b8435`（本輪 HEAD）；順序 tech→brand→platform api→agent→web×3 |
| 5 | backfill | ✅ 技師 1 列 line_user_id 加密（明文清空）；品牌 69 列 users PII 加密+盲索引（明文保留供 dual-read） |
| 6 | 收尾驗證 | ✅ 自動化項全綠（見下）；真實 LINE 端到端項移交外部測試 |

## Step 2 — DB（品牌庫 lock-ai-db / 技師庫 lock_tech）

- 套前備份：`gcloud sql backups create --instance=lock-ai`（opsday-20260722 pre-migration）✅
- 前置 gate：A2 strict outbox 重複 = **0**（可套 111）；套前基線 users enc/bidx 欄不存在 ✅
- migration 111/112/113/114 逐檔 `ON_ERROR_STOP=1` 套用+登錄 `schema_migrations`（水位含 110,111,112,113,114）
- 落庫驗證：`saas.data_encryption_key`+`saas.purge_audit`（含 append-only trigger）；users 5 欄（display_name_enc/email_enc/phone_enc/email_bidx/phone_bidx）；3 索引（idx_users_email_bidx/phone_bidx/uq_outbox_ref_kind_strict）；技師庫 line_user_id_enc/bidx + idx_technicians_line_bidx

## Step 4 — 重佈 revision 對照

| 服務 | 舊 → 新 | health |
|---|---|---|
| lock-tech-api | 00004 → **00005-gsl** | 200 db:ok |
| smart-lock-api | 00023 → **00024-8hh** | 200 db:ok |
| lock-platform-api | 00003 → **00004-8lv** | 200 db:ok |
| smart-lock-agent | 00013 → **00014-r6b** | Ready=True（/health 404 為已知誤報；callback 回 400=容器活） |
| smart-lock-web | 00021 → **00022-kpl** | 200 |
| lock-tech-web | 00004 → **00005-mdw** | 200 |
| lock-platform-web | 00004 → **00005-c88** | 200 |

- **api.sh 本輪烤入的 8 把 secrets 全數 pre-flight 通過**（GDPR_DEK_KEK/USER_PII_BIDX_KEY/MEDIA_ENC_KEY/LINE_CHANNEL_SECRET＋tech 面 LINE_UID_ENC/BIDX_KEY）——不再靠手動 set-env。

## Step 6 — 收尾驗證（自動化）

| 驗證 | 結果 |
|---|---|
| 三 api /health | 200 + `{"status":"ok","checks":{"db":"ok"}}` |
| 三站 web / | 200 |
| 客戶 webhook 無簽名 | **401**（fail-closed，LINE_CHANNEL_SECRET 掛載生效） |
| 技師 webhook 錯簽名 | **403** |
| tech-api log | 無 LINE_UID dev fallback（金鑰正確掛載；OTEL 未設=SigNoz 未部署，預期無害） |

## 移交外部測試人員（真實 LINE / 互動流程）

- 品牌後台登入→改客戶資料→再讀（dual-write/read 無感驗證）
- LINE 客服問答一輪（agent 重佈無回歸）
- 派單→技師 LINE 實收＋深連結非 localhost（TECH_PORTAL_URL 生效）
- LiveSkill 親驗版：改 FAQ→發佈→60s LINE 新答

## 效果 / 遺留

**達成**：CR-0172~0177 全系列 hardening＋GDPR crypto-shred＋blind index＋技師加密**在 prod 生效**；「手動 set-env 被重佈洗掉」根治（8 secrets 烤入 api.sh）；v1 deprecation 30 天窗自今日起算。

**遺留**：
- **Step 3 WIF**（CD 按鈕化）——待 `brew install gh` 後跑 `opsday-20260722-3-wif.sh`
- **S5 DROP 明文欄**——刻意延後（過渡窗 dual-read 中；明文與密文同值，S5 前不動）
- 明確排除四項不變：Casdoor 上雲／RAG cutover／SigNoz 叢集／KYC 金鑰再加密
