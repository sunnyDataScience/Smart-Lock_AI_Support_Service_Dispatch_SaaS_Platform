#!/usr/bin/env bash
# ============================================================
# OPS 20260802 — 帳務封鎖止血停機的「還原」腳本
#
# ── 背景 ────────────────────────────────────────────────────
# 2026-08-02 05:53 UTC 起，Vertex AI 對本專案回 403：
#     "Lightning dunning decision is deny for project: projects/1083648618124"
# dunning = Google 的催繳／風控流程。實測 8 個 GCP API，**只有 Vertex AI
# 被拒**，Cloud SQL / Cloud Run / Secret Manager / Artifact Registry /
# Cloud Storage / Cloud Logging 全部正常 —— 是分級封鎖，非全面停權。
#
# 根因無法從本專案排除：專案綁在帳單帳戶 017423-B4EDC9-A75ABB，而
# sunny@funngo.ai 對該帳戶**無讀取權限**（`gcloud billing accounts list`
# 只看得到 017946-89EC36-B9324D，兩者不同）。付款狀態須由有權限者查。
#
# ── 當日採取的止血動作（本腳本負責還原）──────────────────────
#   22:48  業主自 Console 停 Cloud SQL（activationPolicy=NEVER）
#   23:0x  Claude 將 4 個 min-instances=1 的 Cloud Run 服務改為 0，
#          並替 smart-lock-agent 恢復 CPU throttling
#
# 停機前設定（還原基準）：
#   SERVICE            MIN  MAX  CPU  MEM    cpu-throttling
#   lock-platform-api   1    1    1   1Gi    (預設 true)
#   lock-tech-api       1    1    1   1Gi    (預設 true)
#   smart-lock-api      1    1    1   1Gi    (預設 true)
#   smart-lock-agent    1    3    2   2Gi    false  ← 見下方警告
#   lock-platform-web   0    3    1   512Mi  (預設 true)
#   lock-tech-web       0    3    1   512Mi  (預設 true)
#   smart-lock-web      0    3    1   512Mi  (預設 true)
#
# ⚠️ 本腳本**刻意不還原** smart-lock-agent 的 `--no-cpu-throttling`。
#    那是 2026-07 Cloud Run 費用 +522%（NT$1,861 毛額）的主因之一：
#    CPU 永遠配置＝閒置也全速計費。LINE gateway 是請求驅動的，
#    spool flush 也在請求週期內完成，不需要 CPU 常駐。
#    若確定要完全還原原狀，見檔尾註解掉的那行。
#
# 用法：
#   gcloud auth login                                    # 權杖隔夜會過期
#   ./scripts/ops/opsday-20260802-restore-from-cost-shutdown.sh
#
# 前置條件：帳單問題已解決（否則 Vertex AI 仍 403，agent 起來也沒有 LLM）。
#   驗證方式見檔尾 §4。
# ============================================================
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-cedar-scope-489604-g3}"
REGION="${REGION:-asia-east1}"
SQL_INSTANCE="${SQL_INSTANCE:-lock-ai}"

# min-instances 需還原為 1 的服務（web 三站原本就是 0，不在此列）
MIN1_SERVICES=(lock-platform-api lock-tech-api smart-lock-api smart-lock-agent)

echo "=========================================="
echo " 0. 前置檢查"
echo "=========================================="
if ! gcloud auth print-access-token >/dev/null 2>&1; then
  echo "  ERROR: gcloud 未登入或權杖已過期 → 先跑 gcloud auth login" >&2
  exit 1
fi
echo "  身分：$(gcloud config get-value account 2>/dev/null)"
echo "  專案：${PROJECT_ID}"

echo
echo "=========================================="
echo " 1. 啟動 Cloud SQL：${SQL_INSTANCE}"
echo "=========================================="
CURRENT_STATE="$(gcloud sql instances describe "${SQL_INSTANCE}" \
                   --project="${PROJECT_ID}" --format='value(state)')"
if [ "${CURRENT_STATE}" = "RUNNABLE" ]; then
  echo "  已是 RUNNABLE，跳過"
else
  echo "  目前 state=${CURRENT_STATE} → 設 activationPolicy=ALWAYS"
  gcloud sql instances patch "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" --activation-policy=ALWAYS --quiet
  echo "  等待進入 RUNNABLE（最多 10 分鐘）..."
  for _ in $(seq 1 30); do
    CURRENT_STATE="$(gcloud sql instances describe "${SQL_INSTANCE}" \
                       --project="${PROJECT_ID}" --format='value(state)' 2>/dev/null || echo '?')"
    echo "    state=${CURRENT_STATE}"
    [ "${CURRENT_STATE}" = "RUNNABLE" ] && break
    sleep 20
  done
  if [ "${CURRENT_STATE}" != "RUNNABLE" ]; then
    echo "  ERROR: 逾時仍未 RUNNABLE（state=${CURRENT_STATE}），中止" >&2
    exit 1
  fi
fi

echo
echo "=========================================="
echo " 2. 還原 Cloud Run min-instances 1"
echo "=========================================="
for SVC in "${MIN1_SERVICES[@]}"; do
  printf '  %-20s ... ' "${SVC}"
  gcloud run services update "${SVC}" \
    --region="${REGION}" --project="${PROJECT_ID}" \
    --min-instances=1 --quiet >/dev/null 2>&1 \
    && echo "OK" || { echo "FAILED"; exit 1; }
done

echo
echo "=========================================="
echo " 3. 設定驗證"
echo "=========================================="
gcloud run services list --region="${REGION}" --project="${PROJECT_ID}" \
  --format="table(
    metadata.name:label=SERVICE,
    spec.template.metadata.annotations.'autoscaling.knative.dev/minScale':label=MIN,
    spec.template.metadata.annotations.'run.googleapis.com/cpu-throttling':label=CPU_THROTTLING,
    status.conditions[0].status:label=READY)"
echo
echo "  CPU_THROTTLING 欄位：true 或空白 = throttling 開啟（省錢，預期值）"
echo "                        false      = CPU 永遠配置（昂貴，非預期）"

echo
echo "=========================================="
echo " 4. 行為驗證（不只看 health 200）"
echo "=========================================="
for U in "https://smart-lock-api-sjmxp23sqq-de.a.run.app/health" \
         "https://lock-tech-api-sjmxp23sqq-de.a.run.app/health" \
         "https://lock-platform-api-sjmxp23sqq-de.a.run.app/health" \
         "https://smart-lock-agent-sjmxp23sqq-de.a.run.app/health"; do
  printf '  %-58s ' "${U##*//}"
  curl -s --max-time 60 -w ' [HTTP %{http_code}]\n' "${U}" || echo "(無回應)"
done
echo
echo "  三個 API 應為 HTTP 200 且 checks.db=ok"
echo "  （若仍 db:disconnected → 資料庫尚未接受連線，等 1-2 分鐘重試）"

echo
echo "  Vertex AI 封鎖是否已解除："
TOKEN="$(gcloud auth print-access-token)"
VERTEX_CODE="$(curl -s -o /tmp/vertex_probe.json -w '%{http_code}' --max-time 30 \
  -X POST -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
  "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/publishers/google/models/gemini-2.0-flash:generateContent" \
  -d '{"contents":[{"role":"user","parts":[{"text":"ping"}]}]}')"
if [ "${VERTEX_CODE}" = "200" ]; then
  echo "    HTTP 200 → 已解除，agent 的 AI 回覆應可正常運作"
else
  echo "    HTTP ${VERTEX_CODE} → 仍被封鎖，agent 會回 fallback 訊息"
  grep -o '"message"[^,]*' /tmp/vertex_probe.json 2>/dev/null | head -1 | sed 's/^/      /'
fi

echo
echo "=========================================="
echo " 還原完成"
echo "=========================================="
echo "  ⚠️ 尚未涵蓋、需人工確認："
echo "     - LINE Bot 對話（agent 的 AI 回覆需 Vertex 解封）"
echo "     - 師傅站 / 品牌後台 / 平台 console 的 UI 登入流程"

# ── 完全還原成停機前原狀（較貴，預設不執行）─────────────────
# smart-lock-agent 停機前帶 --no-cpu-throttling。若確定需要 CPU 常駐：
#
#   gcloud run services update smart-lock-agent \
#     --region="${REGION}" --project="${PROJECT_ID}" \
#     --min-instances=1 --no-cpu-throttling --quiet
