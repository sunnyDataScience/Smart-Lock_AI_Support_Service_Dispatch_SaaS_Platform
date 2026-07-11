#!/usr/bin/env bash
# cr0164-purge-tech-projection-pii.sh — 一次性清空「品牌投影庫」技師 users 列的
# 憑證/PII（CR-0164 B 回填）。**僅限拆庫（split-DB）prod 環境的品牌投影庫**。
#
# ⚠️ 防呆：單庫 fallback（技師權威即本庫）執行會清光真實技師憑證、登入全壞。
# 故本腳本強制要求 TECH_POSTGRES_URI 已設定且與 POSTGRES_URI 不同（＝確認拆庫），
# 否則拒絕執行。因此**不放進 SQL/migrations/**（避免 db-init 對所有環境自動套用）。
#
# 用法：POSTGRES_URI=<品牌投影庫> TECH_POSTGRES_URI=<技師權威庫> \
#         ./scripts/db/cr0164-purge-tech-projection-pii.sh
set -euo pipefail

: "${POSTGRES_URI:?需設 POSTGRES_URI（品牌投影庫）}"
: "${TECH_POSTGRES_URI:?未設 TECH_POSTGRES_URI → 疑為單庫 fallback，拒絕執行（清空會毀技師憑證）}"

if [ "$POSTGRES_URI" = "$TECH_POSTGRES_URI" ]; then
  echo "❌ POSTGRES_URI == TECH_POSTGRES_URI（單庫）→ 拒絕執行，避免清空真實技師憑證" >&2
  exit 1
fi

echo "==> 對品牌投影庫清空技師 users 列的 password_hash/email/phone/address"
psql "$POSTGRES_URI" -v ON_ERROR_STOP=1 <<'SQL'
UPDATE users SET
  password_hash = NULL, email = NULL, phone = NULL, address = NULL, updated_at = NOW()
WHERE role = 'technician'
  AND (password_hash IS NOT NULL OR email IS NOT NULL
       OR phone IS NOT NULL OR address IS NOT NULL);
SQL
echo "✅ 完成（tech_mirror 白名單已確保未來鏡射不再帶入這些欄）"
