# CR-0145 — v1 API 凍結 gate 落實 + 收斂盤點(WBS 2.5.1)

- **日期**:2026-07-10
- **觸發面向**:CI quality gate(新守門)、ADR-003 凍結步驟 enforce
- **依據**:ADR-003(凍結→遷移→移除)、稽核 2026-07-10(凍結宣告後 CR-0114/0116/0118 仍增 v1、無 guard)

## §1 本輪交付(Gate-1 凍結)

- `scripts/ci/v1-freeze-check.py` + baseline(**195 個 v1 操作**快照 2026-07-10):runtime openapi 的 /api/v1 操作集**新增即 CI 紅**;減少=收斂方向,提示更新 baseline
- `.github/workflows/v1-freeze-check.yml`(api/** 觸發)

## §2 盤點現況(2026-07-10 稽核+本輪覆核)

- brand-portal 殘餘 v1 caller(非 auth):config×3/staff×3/kb manuals upload/accounting reconciliations——**全屬無 v2 對應清單**,遷移被 v2 端點缺位阻擋
- 無 v2 對應 legacy router ~32 支(auth、6 platform_*、public、kb_*、roles、system_config、reports_*、internal_ingest);platform-console 整站 v1
- CI/scripts 直打 v1(smoke-api.sh 等)——移除前須同步遷
- hit metrics in-memory 單機(無流量證明證據力不足)

## §8 Human Decisions Required(移除 gate 的三個業主待決)

1. **auth 端點定位**:舊盤點判 user-scoped auth「永久保留」與「caller 歸零後移除 v1」矛盾——要 auth 扁平化(v1 剝離)還是宣告 auth 為永久 v1 例外?(2.1.1-R2 Casdoor 授權碼流落地後 auth 面天然重構,建議併 R2 後決)
2. **platform_* 系列**:整組無 v2;要開 v2 平面還是宣告 platform 面為 v1 長期承諾?
3. **「5-gate」名實**:ADR-003 僅一句、實為 8 stage(正式計畫在已刪 docs/_audit,git 歷史)——建議業主確認以 ADR-003 三步(凍結/遷移/移除)為準,棄 8-stage 舊稱

## 驗收狀態

WBS 2.5.1 → 🔶:Gate-1 凍結 **enforced**(本輪);遷移/移除受 §8 業主裁決阻擋,依 ADR-003 節奏排 M3。M2 SIT(2.6.1)不依賴移除完成。

### 進度

- ✅ Gate-1 done(2026-07-10,branch `chore/v1-freeze-gate`):守門腳本+baseline 195 ops+CI workflow;自驗綠
