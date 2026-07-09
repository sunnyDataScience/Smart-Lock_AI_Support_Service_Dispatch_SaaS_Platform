# CR-0126: 前端型別 SoT 改認 FastAPI runtime export（契約工件三分層）

- **日期**: 2026-07-09
- **狀態**: done（業主裁決「做 1」後實作完成）
- **觸發面向**: API contract（契約工件生成鏈）、CI 工具鏈
- **產出 ADR**: ADR-031（refines ADR-022 · ADR-028）

## §1 背景與問題

push 前 CI 預檢發現 `api/openapi.yaml:6011` 重複 `description` key（已於
`fix/openapi-dup-description-key` 修除）。追查時發現**型別同步鏈整條斷裂**：

1. 入庫四站 `api.generated.ts` 源自 **runtime export**（`/api/v1/*` 前綴、
   CR-0111 時代快照）——`scripts/ops/export_openapi.py` docstring 可證此為
   原始工作流。
2. 設計稿 `api/openapi.yaml`（145 條無前綴路徑）缺前端在用的多個 schema
   （`Settlement`、`RevenueSummary`、`AuditLogEntry`…）；web 拆分 rewire 時
   誤把 `generate-api-types.sh` 來源接到它——從它重生成，四站 tsc 爆數百錯。
3. `api-types-sync.yml` 觸發路徑歷來失準（先盯 `web/lib/`、後盯已解散的
   `web/packages/shared/`）——`--check` **從未真正執行**（假沉默）。
4. 以現行 runtime 重生成仍有 65 個 tsc error：v1/v2 router 撞 operationId
   12 組（生成型別重複宣告）＋部分端點未宣告 response_model（schema 自
   runtime 消失，如 Notification 系列）。

## §4 契約影響

- operationId 改名 12 組（v2 → `*V2`；technicians 自身資料 → `*TechnicianProfile`）。
  operationId 屬 codegen 元資料；前端僅消費 `components`、`operations[]` 全 repo
  零引用；api 測試僅註解提及。**路徑、schema、行為零變更**。
- 端點集合、request/response schema：零變更（本 CR 只動生成鏈與元資料）。

## §8 Human Decisions Required

| # | 決策 | 裁決 |
|---|---|---|
| 1 | 型別 SoT 歸屬：runtime export（方案1）vs 設計稿補齊（方案2） | ✅ 業主 2026-07-09「做1」 |
| 2 | 設計稿 `api/openapi.yaml` 角色 | 維持設計期契約（spec-lint/mock-smoke/contract-check 對象）；不再是型別來源（實作時採定，記於 ADR-031 §2） |
| 3 | runtime 未宣告 response_model 的端點型別 | 前端 `api.local.ts` 顯性補丁，後端補宣告後遷回（實作時採定，記於 ADR-031 §4） |

### 進度

- ✅ S1 done：`generate-api-types.sh` 改 runtime export 來源＋釘版
  openapi-typescript@7.13.0；`api-types-sync.yml` 改盯 `api/**/*.py`＋uv 環境
- ✅ S2 done：api 12 組 operationId 去重（api unit 331 passed）
- ✅ S3 done：四站型別重生成（30,279 行，`--check` 冪等通過）
- ✅ S4 done：四站消費端修復——`api.local.ts` 補丁（Notification 系列/兩個
  Envelope）＋SystemConfigForm 13 處 nullable 收斂＋function_tests 縮窄。
  四站 tsc 0 ＋ next build 全綠
- ✅ S5 done：ADR-031＋INDEX＋CHANGELOG＋completion-status＋.claude/docs 同步

## §9 實作順序（已完成）

1. 生成鏈與 CI 改接 → 2. api op-id 去重 → 3. 重生成 → 4. 前端修復 → 5. 治理文件。

## 遺留（顯性技債）

- `api.local.ts`（四站同款）：後端為 notifications／manuals upload／pricing rules
  等端點補 response_model 後，應遷回 api.generated 並縮減本檔。
- `api/models/generated.py` `function_tests: list[dict]` 宜補為
  `_FunctionTestResult` 結構型別（前端已以斷言縮窄）。
- FastAPI 匯出仍有一則 `Duplicate Operation ID` 警告已消除（12 組全清）。
