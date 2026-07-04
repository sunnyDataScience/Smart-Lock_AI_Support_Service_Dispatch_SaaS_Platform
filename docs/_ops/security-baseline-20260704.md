# 上線前資安基線報告 — 2026-07-04

> 20260702 會議 §四「三件套」(弱掃/資安掃描/壓測)的 AI 半(AI-6);
> 工具選型待公司資安人員回覆(AI-5,人工項)後對齊替換。
> 掃描腳本:`scripts/security/baseline-scan.sh`(工具存在才跑、報告落 `reports/`)。

## 三件套現況

| 件 | 工具 | 狀態 |
|---|---|---|
| 壓測 | Locust(`loadtest/`,CR-0019) | ✅ 既有:100 VU 30min 技師場景 + SLA gate(p95 GET 500ms/POST 1s/error≤1%) |
| 弱點掃描 | pip-audit + npm audit(本次跑)/ trivy(裝了即掃) | ✅ 已跑,發現如下 |
| 資安掃描 | gitleaks + OWASP ZAP baseline(裝了/給 URL 即掃) | ⏳ 本機未裝 gitleaks;ZAP 待部署後對 staging URL 跑 |

## 弱掃發現(2026-07-04)

### Python(pip-audit):32 個已知漏洞 / 10 套件,全部有修復版

| 套件 | 現版 | 修復版 | 漏洞數 | 備註 |
|---|---|---|---|---|
| aiohttp | 3.13.4 | 3.14.1 | 11 | agent 側(LINE/LLM HTTP) |
| starlette | 1.0.0 | 1.3.1 | 5 | ⚠️ FastAPI 直接相依,升級需驗相容 |
| yt-dlp | 2026.3.17 | 2026.6.9 | 4 | data pipeline(bronze 抓取),非服務路徑 |
| python-multipart | 0.0.27 | 0.0.31 | 3 | api 檔案上傳解析 |
| urllib3 | 2.6.3 | 2.7.0 | 2 | 傳遞相依 |
| cryptography / idna / langsmith / litellm / pydantic-settings | — | 各有 fix | 各 1-2 | |

### Node(npm audit,prod deps):1 high + 1 moderate

| 套件 | 嚴重度 | 漏洞 | 修復 |
|---|---|---|---|
| next | high | DoS with Server Components | `npm audit fix`(patch 版) |
| postcss | moderate | XSS via unescaped `</style>` | 同上 |

## 修補建議(待業主裁決時點)

- **建議 UAT 後統一修**:距 7/9 Johnson UAT 剩 3 個工作日,依賴升級(尤其
  starlette 1.0→1.3、aiohttp 3.13→3.14)需要全套回歸 + Playwright 重驗,
  現在動風險大於收益;UAT 為內部驗收、非公網開放,曝險窗可控。
- **例外**:若資安人員(AI-5)要求上線前修,優先順序:next(high,
  patch 升級低風險)→ python-multipart(上傳路徑)→ starlette/aiohttp(需完整回歸)。
- 修補輪執行方式:各別 bump + `uv lock` / `npm audit fix` → 全套 pytest 1544
  + tsc + Playwright 冒煙 → 依 `.claude/rules/security.md` 檢查單收尾。

## 部署後待跑(staging/prod URL 出來後)

```bash
ZAP_TARGET=https://<web-url> ./scripts/security/baseline-scan.sh   # ZAP 被動基線
brew install gitleaks trivy && ./scripts/security/baseline-scan.sh # 補 secrets/映像掃
```
