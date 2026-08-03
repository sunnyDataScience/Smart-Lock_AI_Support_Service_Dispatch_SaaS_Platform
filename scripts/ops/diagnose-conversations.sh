#!/usr/bin/env bash
# ============================================================
# 唯讀診斷：LINE 對話為何不出現在品牌後台 /conversations
#
# 原理：後台列表的 SQL 是
#     conversations c JOIN users u ON c.user_id = u.id WHERE u.tenant_id = <租戶>
# 所以一則對話要在後台看得見，**其關聯 user 的 tenant_id 必須等於後台租戶**。
# 對話本身存在不代表看得到——本腳本直接驗這條 join 是否成立。
#
# 全部是 SELECT，不寫入任何資料。
#
# 用法：
#   ./scripts/ops/diagnose-conversations.sh                     # 預設租戶
#   TENANT=<uuid> ./scripts/ops/diagnose-conversations.sh       # 指定租戶
#   PORT=5600 ./scripts/ops/diagnose-conversations.sh           # 換 proxy 埠
#
# 前置：cloud-sql-proxy 已安裝、gcloud 已登入（權杖隔夜會過期）。
#   ⚠️ 連 prod 一定要 --gcloud-auth——用 ADC 常撞 invalid_rapt。
#
# 2026-08-03 從家目錄的業主執行包收進 repo（其餘 12 支一次性腳本已刪）。
# ============================================================
set -uo pipefail

PROJECT_ID="${PROJECT_ID:-cedar-scope-489604-g3}"
REGION="${REGION:-asia-east1}"
INSTANCE="${PROJECT_ID}:${REGION}:lock-ai"
PORT="${PORT:-5599}"
TENANT="${TENANT:-00000000-0000-0000-0000-000000000001}"

command -v cloud-sql-proxy >/dev/null || { echo "FAIL: 缺 cloud-sql-proxy"; exit 1; }

echo "== 啟動 cloud-sql-proxy（--gcloud-auth）=="
cloud-sql-proxy --gcloud-auth --port "$PORT" "$INSTANCE" >/tmp/csp-diag.log 2>&1 &
PROXY_PID=$!
trap 'kill $PROXY_PID 2>/dev/null' EXIT
for i in $(seq 1 15); do nc -z 127.0.0.1 "$PORT" 2>/dev/null && break; sleep 1; done
nc -z 127.0.0.1 "$PORT" 2>/dev/null || { echo "FAIL: proxy 未就緒"; tail -5 /tmp/csp-diag.log; exit 1; }
echo "  proxy OK (port $PORT)"

LOCAL_URI="$(gcloud secrets versions access latest --secret=POSTGRES_URI 2>/dev/null | python3 -c '
import sys, urllib.parse as u
p = u.urlparse(sys.stdin.read().strip())
pw = u.quote(u.unquote(p.password or ""), safe="")
print(f"postgresql://{p.username}:{pw}@127.0.0.1:'"$PORT"'{p.path}")
')"
[[ -z "$LOCAL_URI" ]] && { echo "FAIL: 取不到 POSTGRES_URI"; exit 1; }
Q() { psql "$LOCAL_URI" -X -P pager=off -c "$1"; }

echo ""
echo "========================================"
echo " ① conversations / users 真實欄位"
echo "========================================"
Q "SELECT table_schema||'.'||table_name AS 表, string_agg(column_name, ', ' ORDER BY ordinal_position) AS 欄位
     FROM information_schema.columns
    WHERE table_name IN ('conversations','users')
    GROUP BY 1 ORDER BY 1;"

echo "========================================"
echo " ② 【核心】最近 10 筆對話 → 其 user 的 tenant_id"
echo "    （tenant 欄若非 00000000 或 NULL ＝ 後台查詢 join 不到，故看不到）"
echo "========================================"
Q "SELECT left(c.id::text,8) AS conv, c.status,
          left(coalesce(c.session_id,'(null)'),22) AS session,
          left(coalesce(u.id::text,'NULL'),8) AS 用戶,
          coalesce(left(u.tenant_id::text,8),'❌NULL') AS 租戶,
          to_char(c.created_at AT TIME ZONE 'Asia/Taipei','MM-DD HH24:MI') AS 建立
     FROM conversations c LEFT JOIN users u ON c.user_id = u.id
    ORDER BY c.created_at DESC LIMIT 10;"

echo "========================================"
echo " ③ 模擬後台實際查詢（能撈到幾筆＝頁面會顯示幾筆）"
echo "========================================"
Q "SELECT count(*) AS 後台看得到的對話數
     FROM conversations c JOIN users u ON c.user_id = u.id
    WHERE u.tenant_id = '$TENANT'::uuid;"

echo "========================================"
echo " ④ 系統中所有租戶（確認後台登入的是哪個）"
echo "========================================"
Q "SELECT left(id::text,8) AS 租戶id, name,
          (SELECT count(*) FROM users u WHERE u.tenant_id = t.id) AS 用戶數
     FROM tenants t ORDER BY created_at LIMIT 10;" 2>/dev/null \
  || Q "SELECT left(id::text,8) AS 租戶id, name FROM saas.tenant ORDER BY 1 LIMIT 10;"

echo "========================================"
echo " ⑤ 目前處於人工接管（escalated）的對話"
echo "========================================"
Q "SELECT left(c.id::text,8) AS conv, left(coalesce(c.session_id,''),22) AS session,
          coalesce(left(u.tenant_id::text,8),'NULL') AS 租戶,
          to_char(c.updated_at AT TIME ZONE 'Asia/Taipei','MM-DD HH24:MI') AS 更新
     FROM conversations c LEFT JOIN users u ON c.user_id = u.id
    WHERE c.status='escalated' ORDER BY c.updated_at DESC LIMIT 10;"

echo ""
echo "判讀："
echo "  ②租戶欄=❌NULL 或非 00000000 → 找到主因：user 沒掛對租戶 → 後台 join 不到"
echo "  ③=0 但②有資料              → 同上，確認主因"
echo "  ③>0                        → 資料看得到，問題在前端／登入身分"
echo "  ⑤列出的就是被接管的對話（修好前留下的）"
