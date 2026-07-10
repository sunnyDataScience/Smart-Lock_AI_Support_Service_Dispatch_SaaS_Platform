# CR-0153 — 三庫 URI 啟動守衛(ADR-020 Consequences 補課)

- **日期**:2026-07-10
- **狀態**:done(2026-07-10)
- **觸發面向**:Architecture boundary(三庫隔離 enforce)、部署 config
- **依據**:ADR-020 Consequences「連線 URI 配置須有啟動守衛,禁止漏設時靜默退回單庫」、13_Security §12 SA-04/DA-04 列;架構稽核 #6 查實零實作且文件自相矛盾(「須有」vs 附註「規劃中」);業主 2026-07-10「開工」

## §1 設計(裁決採 opt-in)

- `DB_URI_STRICT=1` 時依 `API_SURFACE` 斷言:全面要求 `POSTGRES_URI`;tech 面另要求 `TECH_POSTGRES_URI`;platform 面另要求 `PLATFORM_POSTGRES_URI`——漏設 RuntimeError 拒啟。
- **預設關閉**:pytest 單庫 fallback(既有測試地基)與本機零 env 情境行為完全不變——這正是文件「須有」與「規劃中」矛盾的解:enforce 落在部署面 opt-in,不動開發面語意。
- 接線:`scripts/deploy/api.sh` ENV_VARS 帶 `DB_URI_STRICT=1`(prod 一律 enforce);三站 compose api service 各帶(本機三庫拓撲齊備,守衛過=parity)。

## §8 裁決記錄(2026-07-10)

業主「開工」=採建議(opt-in env 開關+deploy 腳本啟用;可否決)。

### 進度

- ✅ done(branch `feat/db-uri-strict-guard`,2026-07-10):`core/db.assert_uri_strict()`+main.py 啟動呼叫(與 platform 密鑰守衛同層 fail-fast)+api.sh/三站 compose 接線。測試 4(預設 no-op/三面斷言)+unit 347+main import 綠;compose YAML/腳本語法過。
