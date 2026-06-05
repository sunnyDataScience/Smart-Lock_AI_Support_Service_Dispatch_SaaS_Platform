# OpenAPI Codegen Runbook — Web Sprint Type Sync

> 給 web Sprint 1-5 BUILD 用：從 backend FastAPI 自動產 web TypeScript types，
> 取代 `web/src/components/phase-ii/types.ts` 手寫。

## 0. 為何需要

`web/src/components/phase-ii/types.ts` 是手寫 type contract（Sprint pre-build
asset）；長期會與 backend service 漂移。Sprint BUILD 開始後應 migrate 到
auto-gen，由 backend runtime schema 為單一 source of truth。

## 1. Backend 端：匯出 OpenAPI JSON

```bash
cd <project_root>
uv run python scripts/ops/export_openapi.py
# 輸出: docs/architecture/api/openapi-runtime.json
```

**成功訊息範例**：
```
[ok] exported 87 endpoints / 134 schemas to .../openapi-runtime.json (245,678 bytes)
```

## 2. Web 端：產 TypeScript types

```bash
cd web
npm install --save-dev openapi-typescript
npx openapi-typescript \
  ../docs/architecture/api/openapi-runtime.json \
  -o src/types/api.generated.ts
```

或寫 npm script（建議）：
```json
{
  "scripts": {
    "gen:types": "openapi-typescript ../docs/architecture/api/openapi-runtime.json -o src/types/api.generated.ts"
  }
}
```

## 3. 使用 auto-gen types

Sprint BUILD 時取代手寫 `phase-ii/types.ts`：

```tsx
// before (Sprint pre-build)
import type { TechStatement } from "@/components/phase-ii";

// after (auto-gen)
import type { components } from "@/types/api.generated";
type TechStatement = components["schemas"]["TechStatement"];
```

## 4. 何時跑

| 觸發條件 | 動作 |
|---|---|
| Backend 新增 FR / endpoint | 跑 §1 + §2 + 提交 `openapi-runtime.json` 變更 |
| Backend 改 response schema | 同上 |
| Web Sprint 開始前 | 跑 §1 + §2 同步最新 |
| CI 上線時 | 加入 pre-commit hook 自動 diff 提醒（roadmap） |

## 5. 已知限制

- **Decimal 欄位**：FastAPI 預設 `Decimal` 序列化為 `string`，auto-gen 會是
  `string` type — 與 `phase-ii/types.ts` 手寫 convention 一致 ✅
- **Datetime**：ISO string format，auto-gen 為 `string` — 一致 ✅
- **enum**：FastAPI Enum 會 gen literal union — 一致 ✅
- **空陣列預設**：auto-gen 可能用 `unknown[]`，需配合 `--default-non-nullable` flag
- **Custom 業務 helper**：`formatDecimal/formatDateTime/daysUntilDeadline`
  保留在 `phase-ii/labels.ts`，不會被 auto-gen 取代

## 6. Migration 順序

Sprint 1-5 BUILD 建議分階段 migrate：

1. **Sprint 1**: 只用 `phase-ii/types.ts`（pre-build）— 不動 OpenAPI codegen
2. **Sprint 1 完成後**: 跑 §1 + §2 產 `api.generated.ts`
3. **Sprint 2 開始**: 新 page 直接用 auto-gen；Sprint 1 page 暫不動
4. **Sprint 5 完成後**: 全面 migrate；刪 `phase-ii/types.ts`（保留 labels +
   api-client）

## 7. Troubleshooting

### `cannot import api.main:app` 錯誤

- 缺 deps → 跑 `uv sync`
- DB 連線 fail → script 已設 dummy `POSTGRES_URI`，但若 main.py 強驗則需
  改 `OPENAPI_EXPORT_MODE=1` skip startup hooks
- LiteLLM provider init fail → 同上，加 skip flag

### Auto-gen `unknown` 太多

```bash
npx openapi-typescript ... \
  --default-non-nullable \
  --export-type
```

### Sprint 端發現 type 對不上 backend

1. 確認 `openapi-runtime.json` 是最新（rerun §1）
2. 對比 backend service `_to_dict` shape
3. 開 issue / PR fix backend 或 web auto-gen 設定

## §A 對齊文件

- `web/src/components/phase-ii/types.ts` — 手寫 Sprint pre-build asset
- `web/src/components/phase-ii/README.md` §變更注意 — 三步同步流程
- `docs/_ops/wbs-100-closeout-plan.md` §1.2 — Sprint pre-build ready 條件
- `docs/architecture/api/openapi.yaml` — 既有 hand-curated OpenAPI（與 runtime 並存）
