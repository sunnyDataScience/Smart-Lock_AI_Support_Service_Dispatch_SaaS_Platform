#!/usr/bin/env bash
# ============================================================
# OPS 批次日 20260722 — Step 1：Secret Manager 金鑰批次建立＋授權
#
# 建 5 把新金鑰（openssl rand，冪等：已存在跳過不覆蓋）並授權 runtime SA：
#   GDPR_DEK_KEK        — CR-0176 envelope KEK（migration 112 前必建）
#   USER_PII_BIDX_KEY   — CR-0176 S5 blind index HMAC（migration 114 配套）
#   MEDIA_ENC_KEY       — FR-API-08 media 位元組加密
#   LINE_UID_ENC_KEY    — CR-0173 技師 line_user_id Fernet
#   LINE_UID_BIDX_KEY   — CR-0173 blind index（必須與 ENC_KEY 不同值）
# 並驗證既有 secrets 齊備（LINE_CHANNEL_SECRET 等，agent 已用=應已存在）。
#
# ⚠️ 鐵律：金鑰一旦有密文落庫就**永不輪換**（輪換=既有密文全滅）。
#          本腳本絕不覆蓋既有 secret（已存在一律跳過）。
# 用法：./scripts/ops/opsday-20260722-1-secrets.sh
# ============================================================
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-cedar-scope-489604-g3}"
RUNTIME_SA="lock-ai@${PROJECT_ID}.iam.gserviceaccount.com"
NEW_KEYS=(GDPR_DEK_KEK USER_PII_BIDX_KEY MEDIA_ENC_KEY LINE_UID_ENC_KEY LINE_UID_BIDX_KEY)
EXISTING_EXPECTED=(POSTGRES_URI API_JWT_SECRET_KEY INTERNAL_API_TOKEN
                   LINE_CHANNEL_ACCESS_TOKEN LINE_CHANNEL_SECRET
                   TECH_POSTGRES_URI PLATFORM_POSTGRES_URI
                   PLATFORM_LINE_CHANNEL_SECRET PLATFORM_LINE_CHANNEL_ACCESS_TOKEN)

echo "== 專案：${PROJECT_ID}（runtime SA=${RUNTIME_SA}）=="
gcloud config set project "${PROJECT_ID}" --quiet

echo ""
echo "== 1) 建 5 把新金鑰（已存在＝跳過，絕不覆蓋）=="
for key in "${NEW_KEYS[@]}"; do
    if gcloud secrets describe "${key}" &>/dev/null; then
        echo "  SKIP: ${key} 已存在（不覆蓋——輪換會滅既有密文）"
    else
        # printf %s：不帶尾換行（0720 checklist 鐵律）
        printf %s "$(openssl rand -hex 32)" | \
            gcloud secrets create "${key}" --data-file=- --replication-policy=automatic
        echo "  CREATED: ${key}"
    fi
    gcloud secrets add-iam-policy-binding "${key}" \
        --member="serviceAccount:${RUNTIME_SA}" \
        --role="roles/secretmanager.secretAccessor" --quiet >/dev/null
    echo "         授權 ${RUNTIME_SA} accessor ✓"
done

echo ""
echo "== 2) 驗證既有 secrets 齊備（缺=後續 api.sh pre-flight 會擋）=="
missing=0
for key in "${EXISTING_EXPECTED[@]}"; do
    if gcloud secrets describe "${key}" &>/dev/null; then
        echo "  OK: ${key}"
    else
        echo "  MISSING: ${key} ← 需人工補建（值來自對應憑證，非隨機）"
        missing=1
    fi
done

echo ""
if [[ "${missing}" == "1" ]]; then
    echo "⚠️ 有缺漏 secrets（上列 MISSING）——補齊後再進 Step 4 重佈。"
else
    echo "✅ Step 1 完成：5 把金鑰就緒＋既有 secrets 齊備。下一步：Step 2 DB。"
fi
