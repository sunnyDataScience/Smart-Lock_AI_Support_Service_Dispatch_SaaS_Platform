# 壓測 + 資安掃描報告(上線前)

- **日期**:2026-07-17(20260715 清單 #26 壓測 / #27 資安掃描)
- **範圍**:本機 docker 環境基線;**雲端 Cloud Run 數字另測**(壓測腳本 env 可覆寫)
- **結論**:壓測讀路徑全綠;資安掃出 13 依賴漏洞、修 12、餘 1 記豁免;
  bandit 高嚴重度零發現、npm 四站零漏洞

---

## 一、壓測(#26)

工具:`scripts/dev/load_test.py`(aiohttp 併發;**單次登入拿 token 重用,
不壓登入端點**——A1 防爆破會鎖帳號;只壓讀端點、可重複跑)。

### 20 併發 × 300 req/端點

| 端點 | 成功 | RPS | p50 | p95 | p99 |
|---|---|---|---|---|---|
| /health(基線) | 300/300 | 1328 | 11 | 48 | 49 |
| work-orders | 300/300 | 1605 | 12 | 14 | 17 |
| quotes | 300/300 | 1599 | 12 | 14 | 20 |
| problem-cards | 300/300 | 1686 | 12 | 12 | 16 |
| notifications | 300/300 | 1320 | 12 | 48 | 49 |
| tech work-orders | 300/300 | 1319 | 11 | 45 | 47 |
| tech line-binding | 300/300 | 1748 | 11 | 12 | 17 |

### 50 併發 × 500 req/端點

| 端點 | 成功 | RPS | p50 | p95 | p99 |
|---|---|---|---|---|---|
| work-orders | 500/500 | 1436 | 29 | 71 | 72 |
| quotes | 500/500 | 1506 | 28 | 68 | 69 |
| problem-cards | 500/500 | 1653 | 28 | 30 | 36 |
| tech work-orders | 500/500 | 1426 | 29 | 58 | 58 |

**結論**:兩檔壓力**零錯誤、零 5xx**;p99 皆 < 75ms。本機單容器即
1300–1700 RPS,對智慧鎖售後這種**低 QPS、人操作型**業務綽綽有餘。
- 未觀察到連線池耗盡 / DB 瓶頸(psycopg request-scoped pool 撐住 50 併發)
- **雲端待補**:Cloud Run 冷啟動、min-instances、Cloud SQL 連線上限的實測數字
  (env `BASE_BRAND=https://…` 覆寫後重跑同腳本即可)

## 二、資安掃描(#27)

### ① Python 依賴(pip-audit,190 套件)

初掃 **13 漏洞 / 5 套件** → 升級後剩 1:

| 套件 | 動作 | 說明 |
|---|---|---|
| pillow 12.2→12.3 | ✅ 修 | 7 個 CVE(影像解析) |
| click 8.1→8.4 | ✅ 修 | PYSEC-2026-2132 |
| httplib2 0.31→0.32 | ✅ 修 | PYSEC-2026-3444 |
| soupsieve 2.8.3→2.8.4 | ✅ 修 | 2 個 |
| **ecdsa 0.19.2** | ⚠ **豁免** | PYSEC-2026-1325 Minerva 時序側信道;**無上游修復版**;經 python-jose 傳遞,**本專案 JWT 用 HS256(對稱),不走 ECDSA 簽章路徑 → 不受影響**。待 python-jose 移除 ecdsa 依賴或改用 PyJWT 時一併清 |

### ② 前端依賴(npm audit --omit=dev)

四站(brand/tech/platform/landing)**全部 0 vulnerabilities**。

### ③ 靜態掃描(bandit -lll 高嚴重度)

`api/services`、`api/routers`、`api/core`、`agent/scripts`——**零高嚴重度發現**。
(硬編碼密鑰、SQL 注入、weak crypto 等高危類型均無命中)

### ④ Security headers 快檢

- api 回應帶 `x-request-id`(可追蹤);CORS 由 `CORS_ORIGINS` env 控管(白名單)
- **雲端待補**:HSTS / X-Frame-Options / X-Content-Type-Options 由 Cloud Run
  前緣或反代層統一補(應用層不重複設,避免與 LB 衝突)

## 三、上線前 checklist(本項相關)

- [x] 依賴漏洞掃描(pip-audit + npm audit)+ 高危修復
- [x] 靜態掃描(bandit 高嚴重度)
- [x] 讀路徑壓測(本機基線)
- [ ] 雲端壓測(Cloud Run + Cloud SQL 實測數字)— 需上雲窗口
- [ ] ecdsa 隨 python-jose→PyJWT 遷移清除(非阻塞,追蹤)
- [ ] 前緣 security headers(HSTS 等)於 Cloud Run/LB 層設定 — OPS
