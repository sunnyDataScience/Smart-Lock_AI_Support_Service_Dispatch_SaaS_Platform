# API 契約單一事實來源 (API Contract SSOT)

本目錄包含 `/api/v1/*` 所有 REST、WebSocket/SSE、Webhook、Domain Event 的**機器可讀契約**。

| 檔案 | 用途 | 狀態 |
|:---|:---|:---|
| `openapi.yaml` | REST API 契約（OpenAPI 3.1） | 骨架 v0.1 |
| `asyncapi.yaml` | WebSocket/SSE/Webhook/Domain Event 契約（AsyncAPI 2.6） | 骨架 v0.1 |
| `../error-codes.md` | 錯誤碼目錄（`error_code` 列舉） | 骨架 v0.1 |
| 13 份 `*-spec.md` | 領域技術規格（narrative，對齊本契約） | 既有 |

其餘敘事型規格位於：
- `../E5--api-design-specification.md` — 完整 API 設計規範敘事版
- `../E5x--frontend-architecture.md §8` — 前後端協作契約框架

---

## 為什麼需要機器可讀契約

前後端分離開發時，若僅以 Markdown 敘述協作，兩端各自推論 schema 會產生「API 斷鏈」：
欄位名不一致、枚舉值偏差、錯誤碼不互通、非同步消息格式錯亂。

機器可讀契約讓以下工作能自動化：
- 前端：`openapi-typescript` 自動生成 TypeScript 型別
- 後端：FastAPI `app.openapi()` 與本檔 diff 檢查防漂移
- Mock：`@stoplight/prism` 啟動 mock server，前端不必等後端
- 測試：`schemathesis` property-based 測試打爆邊界
- 文件：ReDoc / Swagger UI 自動呈現

---

## 本地驗證（無需安裝）

### Lint OpenAPI + AsyncAPI

```bash
# 使用 npx（需本機 Node 18+）
npx --yes @stoplight/spectral-cli lint \
  docs/02-design/specs/openapi.yaml \
  docs/02-design/specs/asyncapi.yaml \
  --ruleset .spectral.yaml
```

或用 Docker（無需 Node）：

```bash
docker run --rm -v "$PWD":/work -w /work \
  stoplight/spectral:latest lint \
  docs/02-design/specs/openapi.yaml \
  docs/02-design/specs/asyncapi.yaml \
  --ruleset .spectral.yaml
```

### 啟動 Mock Server（前端不必等後端）

```bash
npx --yes @stoplight/prism-cli mock docs/02-design/specs/openapi.yaml --port 4010
# 之後前端 API base URL 指向 http://localhost:4010
```

---

## CI 檢查

`.github/workflows/spec-lint.yml` 於 PR 變動本目錄時自動觸發 spectral lint。
後續階段將加入：
- 前端型別生成校驗（若 client 未重新生成 → 紅燈）
- 後端 `app.openapi()` 輸出 diff（若實作漂移 → 紅燈）
- Schemathesis 契約測試

---

## 新增端點流程

1. 於 `openapi.yaml` 的 `paths` 下新增端點，參考既有端點格式
2. 必要時於 `components/schemas` 新增 DTO
3. 若新增錯誤碼，同步更新 `../error-codes.md` 與 `openapi.yaml` `ApiErrorResponse.error_code.examples`
4. 對應的業務流程若在 `../E5x--work-order-interaction-flows.md` 有描述，於該 Flow 章節頂部加 metadata：
   ```markdown
   > **Endpoints:** `openapi#operationId=xxx`
   > **Events:** `asyncapi#operationId=yyy`
   > **Idempotency:** Required on step N
   ```
5. PR 必須通過 CI lint 才可 merge

---

## 版本策略

- 同一 `/api/v{N}/*` 下的變更遵循語義化版本（SemVer），記錄於 `info.version`
- 破壞性變更 → bump major + 新開 `/api/v{N+1}/*`
- 棄用（deprecated）欄位 / 操作 → 標 `deprecated: true` + `x-deprecation-notice`，至少一個 release 後移除

---

## 相關文件

- `openapi.yaml` / `asyncapi.yaml` — 機器可讀契約
- `../error-codes.md` — 錯誤碼目錄
- `../E5--api-design-specification.md` — 完整 API 設計規範敘事版
- `../E5x--frontend-architecture.md §8` — 前後端協作契約框架
- `../../../web_design_spec_prompt_pipeline/pages/MAPPING.md` — 頁面 ↔ API 對照索引
