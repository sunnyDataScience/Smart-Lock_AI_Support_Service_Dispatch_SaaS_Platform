#!/usr/bin/env bash
# split-tech-db.sh — 技師身分庫拆分:建 tech DB schema 子集 + 從品牌庫搬技師資料
# (CR-0112 方案 B,業主 2026-07-03 裁決)
#
# 設計:tech DB = 權威庫;品牌庫保留技師列當投影(35 張品牌表 FK 指向
# users/technicians,投影讓 FK 與派工/佣金 JOIN 不用改)。本腳本做**初始**
# 拆分(schema + 全量拷貝);之後的一致性由 api 的雙寫鏡射(tech_mirror)維持,
# 可用 --verify 隨時比對兩庫。
#
# 用法(兩個 stack 都起來後):
#   ./scripts/db/split-tech-db.sh            # 建 schema + 搬資料(冪等:已有資料則跳過,--force 重搬)
#   ./scripts/db/split-tech-db.sh --verify   # 只比對兩庫技師域資料量與最新異動
#
# 在 tech-db 容器內執行 pg_dump/psql(pg17 工具,且同時可達品牌庫 db:5432 與本機 tech 庫),
# 免除 host 端 pg 工具版本不符問題。
set -euo pipefail

TECH_CONTAINER="${TECH_CONTAINER:-lock-tech-tech-db-1}"
BRAND_URI="${BRAND_URI:-postgresql://lock:0000@db:5432/lock_AI_data}"
TECH_URI="${TECH_URI:-postgresql://lock:0000@localhost:5432/lock_tech}"

# 技師身分域表(FK 相依順序:users → technicians → 其餘)
TABLES_ORDERED=(users technicians technician_skill technician_brand_authorization technician_certification technician_schedule_requests)
SAAS_TABLES=(saas.technician_lifecycle_event)

c_blue=$'\033[36m'; c_grn=$'\033[32m'; c_red=$'\033[31m'; c_yel=$'\033[33m'; c_rst=$'\033[0m'
log() { printf '%s[split-tech-db]%s %s\n' "$c_blue" "$c_rst" "$*"; }
ok()  { printf '%s[split-tech-db]%s %s\n' "$c_grn" "$c_rst" "$*"; }
err() { printf '%s[split-tech-db]%s %s\n' "$c_red" "$c_rst" "$*" >&2; }

dex() { docker exec -i "$TECH_CONTAINER" "$@"; }
bq()  { dex psql "$BRAND_URI" -tAc "$1"; }   # 品牌庫查詢
tq()  { dex psql "$TECH_URI"  -tAc "$1"; }   # 技師庫查詢

docker inspect "$TECH_CONTAINER" >/dev/null 2>&1 || { err "找不到容器 $TECH_CONTAINER —— 先起 web/tech-portal/docker-compose.yml"; exit 1; }

# ── verify 模式 ──────────────────────────────────────────────────────────
verify() {
  log "比對兩庫技師域資料(品牌庫=投影,技師庫=權威)…"
  local drift=0
  for t in technicians technician_skill technician_brand_authorization technician_certification; do
    local b t2
    b=$(bq "SELECT count(*) FROM $t")
    t2=$(tq "SELECT count(*) FROM $t")
    if [ "$b" = "$t2" ]; then ok "  $t: $t2 ✓"; else err "  $t: 品牌 $b vs 技師 $t2 ✗ 漂移"; drift=1; fi
  done
  local bu tu
  bu=$(bq "SELECT count(*) FROM users WHERE role='technician'")
  tu=$(tq "SELECT count(*) FROM users")
  if [ "$bu" = "$tu" ]; then ok "  users(技師列): $tu ✓"; else err "  users(技師列): 品牌 $bu vs 技師 $tu ✗ 漂移"; drift=1; fi
  # 單一居所表只在技師庫(品牌庫殘留為拆分前舊資料,僅供 fallback,不比對)
  ok "  technician_schedule_requests(單一居所): 技師庫 $(tq "SELECT count(*) FROM technician_schedule_requests") 筆"
  ok "  saas.technician_lifecycle_event(單一居所): 技師庫 $(tq "SELECT count(*) FROM saas.technician_lifecycle_event") 筆"
  [ $drift -eq 0 ] && ok "無漂移" || { err "偵測到漂移 —— 可 --force 重搬(以品牌庫為準)或查 api 雙寫 log"; exit 1; }
}

if [ "${1:-}" = "--verify" ]; then verify; exit 0; fi

# ── 冪等防護 ─────────────────────────────────────────────────────────────
if [ "${1:-}" != "--force" ]; then
  existing=$(tq "SELECT count(*) FROM technicians" 2>/dev/null || echo "")
  if [ -n "$existing" ] && [ "$existing" -gt 0 ]; then
    log "技師庫已有 $existing 筆 technicians → 跳過(--force 以品牌庫為準重搬)"
    verify
    exit 0
  fi
fi

# ── 1. schema 子集(從品牌庫 dump 這幾張表的 DDL)────────────────────────
log "建立 schema 子集(pg_dump --schema-only)…"
dex psql "$TECH_URI" -q -c "CREATE SCHEMA IF NOT EXISTS saas" >/dev/null
# 表 DEFAULT 依賴的 extension(uuid_generate_v4 等;pgvector 映像皆內建可裝)
dex psql "$TECH_URI" -q -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' >/dev/null
dex psql "$TECH_URI" -q -c 'CREATE EXTENSION IF NOT EXISTS pgcrypto' >/dev/null
# FK 指向集合外的 constraint(saas.technician_lifecycle_event→saas.tenant)會失敗跳過,可容忍
dex bash -c "pg_dump '$BRAND_URI' --schema-only --no-owner --no-privileges \
  -t users -t technicians -t technician_skill -t technician_brand_authorization \
  -t technician_certification -t technician_schedule_requests -t saas.technician_lifecycle_event \
  | psql '$TECH_URI' -q -v ON_ERROR_STOP=0" 2>&1 | grep -v "already exists" | head -5 || true

# 排班審核者(resolver_user_id)是後台帳號,不在技師庫 users → 該 FK 在技師庫必炸,拆掉
dex psql "$TECH_URI" -q <<'SQL'
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT conname FROM pg_constraint
    WHERE conrelid = 'technician_schedule_requests'::regclass
      AND contype = 'f'
      AND pg_get_constraintdef(oid) LIKE '%resolver_user_id%'
  LOOP
    EXECUTE format('ALTER TABLE technician_schedule_requests DROP CONSTRAINT %I', r.conname);
  END LOOP;
END $$;
SQL

# ── 2. 資料搬遷(--force 時先清空,FK 反序)────────────────────────────────
if [ "${1:-}" = "--force" ]; then
  log "--force:清空技師庫既有資料…"
  dex psql "$TECH_URI" -q -c "TRUNCATE saas.technician_lifecycle_event, technician_schedule_requests, technician_certification, technician_brand_authorization, technician_skill, technicians, users CASCADE" || true
fi

log "搬 users(僅 role='technician' 列)…"
dex bash -c "psql '$BRAND_URI' -c \"\\copy (SELECT * FROM users WHERE role='technician') TO stdout\" \
  | psql '$TECH_URI' -c '\\copy users FROM stdin'"

for t in technicians technician_skill technician_brand_authorization technician_certification technician_schedule_requests; do
  log "搬 ${t} ..."
  dex bash -c "psql '$BRAND_URI' -c '\\copy (SELECT * FROM ${t}) TO stdout' \
    | psql '$TECH_URI' -c '\\copy ${t} FROM stdin'"
done
log "搬 saas.technician_lifecycle_event…"
dex bash -c "psql '$BRAND_URI' -c '\\copy (SELECT * FROM saas.technician_lifecycle_event) TO stdout' \
  | psql '$TECH_URI' -c '\\copy saas.technician_lifecycle_event FROM stdin'"

verify
ok "拆分完成。接著讓兩個 api 都帶 TECH_POSTGRES_URI 重起(見 web/tech-portal/docker-compose.yml 檔頭)。"
