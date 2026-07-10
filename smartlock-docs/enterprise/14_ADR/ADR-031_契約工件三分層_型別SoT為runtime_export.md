---
title: "ADR-031: 契約工件三分層——前端型別 SoT＝FastAPI runtime export；設計稿 spec 專職設計期契約"
version: 1.0
status: active
owner: 業主
last-updated: 2026-07-10
refines:
  - ./ADR-022_API_SURFACE單體多面塑形.md   # 補「契約工件如何生成與守門」的工具鏈層
  - ./ADR-028_web檔案層拆分_四站獨立專案.md # api.generated.ts 四份同步的上游來源改定
---

# ADR-031: 契約工件三分層——型別 SoT＝runtime export

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（業主裁決 2026-07-09：「做 1」——型別 SoT 改認 runtime export） |
| 層級 | 系統(api/web)・工具鏈 |
| 關聯 ADR | refines [ADR-022](./ADR-022_API_SURFACE單體多面塑形.md) · [ADR-028](./ADR-028_web檔案層拆分_四站獨立專案.md) |
| CIA | CR-0126 |

## Context（背景）

push 前 CI 預檢（2026-07-09）發現契約鏈三份工件互相矛盾，且型別同步 CI
（api-types-sync）因觸發路徑失準**從未真正執行過**（假沉默）：

| 工件 | 內容 | 實況 |
|---|---|---|
| `api/openapi.yaml`（設計稿） | 145 條無前綴路徑、手工策展 | 缺前端在用的 `Settlement`/`RevenueSummary` 等 schema；與 runtime 路徑前綴不符 |
| FastAPI runtime（`api.main:app`） | `/api/v1/*` 464 端點、341 schemas | 前後端實際運行的契約 |
| 四站 `api.generated.ts`（入庫） | CR-0111 時代 runtime 快照 | 四站 tsc 靠它全綠，但已落後 runtime 數月 |

歷史工作流（`scripts/ops/export_openapi.py` docstring 可證）本來就是「runtime
export → openapi-typescript」；web 拆分 rewire 時誤把生成來源接到設計稿 spec，
從設計稿重生成會令四站 tsc 爆數百錯。

## Decision（裁決）

1. **前端型別的 SoT＝runtime export**：`generate-api-types.sh` 先跑
   `scripts/ops/export_openapi.py`（離線 import `api.main:app`，不需起服務）再以
   釘版 `openapi-typescript@7.13.0` 生成，一次寫入四站（ADR-028 四份同步不變）。
   api-types-sync CI 改盯 `api/**/*.py`（型別隨程式碼變，不隨設計稿變）。
2. **設計稿 `api/openapi.yaml` 專職設計期契約**：spec-lint／mock-smoke／
   contract-check 的對象不變；承載尚未實作端點的設計（如 ADR-027
   `/internal/requote-requests`）。它**不是**型別來源。兩層人讀正典不變：
   `16_API_Spec.yaml`（導讀視圖）→ `api/openapi.yaml`（機讀設計稿）。
3. **operationId 全域唯一為硬約束**：v2 router 與 legacy 同名 operationId（12 組，
   FastAPI 匯出時即告警）令生成型別重複宣告而編譯失敗。v2 端點一律 `*V2` 後綴、
   技師自身資料改 `*TechnicianProfile`（operationId 屬 codegen 元資料，前端僅
   消費 `components`，改名零波及）。
4. **runtime 未宣告 response_model 的端點，前端以 `api.local.ts` 補丁承接**：
   依實際回傳形狀本地宣告（如 Notification 系列），檔頭註明「後端補宣告
   response_model 後應遷回 api.generated 並刪除對應項」——缺口顯性化，不做
   隱性 any。

## Alternatives（被否決的替代方案）

- **把設計稿補齊到與 runtime 一致（145→464 端點）再生成**：工程量大且會持續
  漂移（雙手工維護），被否決。
- **保留 CR-0111 時代快照、api-types-sync 轉 warn-only**：假綠變種——check 存在
  但永遠不會綠，被否決。

## Consequences（後果）

- ✅ 型別鏈第一次真正閉環：`--check` 冪等可擋漂移；api 程式碼改動即觸發同步檢查。
- ✅ 四站 tsc 0 錯誤 + next build 全綠；api unit 331 passed（op-id 改名零功能波及）。
- ⚠️ api-types-sync CI 需 uv + Node 雙環境（原純 Node），時長增加約 1 分鐘。
- ⚠️ `api.local.ts` 是顯性技債清單：後端逐步補 response_model 時應同步縮減。
- 重評觸發：若未來設計稿與 runtime 收斂為單一 spec（如改用 spec-first 工作流），
  開新 ADR 重審本分層。

## Status 附註

- 勘誤：§2 例證 `/internal/requote-requests` 當時實際僅載於 16_API_Spec 導讀層，`api/openapi.yaml` 於 2026-07-10 本輪回補（連同 role-assignments）。
