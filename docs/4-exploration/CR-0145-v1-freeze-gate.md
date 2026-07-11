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

> ✅ **業主裁決（2026-07-12，CR-0166 R7 D5「照建議」）——三待決全數定案：**
> 1. **auth ＝ v1 永久例外**：user-scoped auth 端點宣告為 v1 長期承諾，**不剝離、不列入移除清單**（Casdoor 授權碼流 2.1.1-R2 已落地，auth 面已天然重構，v1 端點作為相容承諾保留）。
> 2. **platform_* ＝ v1 長期承諾**：**不開 v2 平面**；platform console 面以 v1 為長期正典。
> 3. **5-gate 名實 ＝ 以 ADR-003 三步（凍結／遷移／移除）為準**，棄 8-stage 舊稱。
>
> **R7 收斂範圍（依裁決）**：freeze gate 已 enforced（Gate-1，本 CR）；auth/platform 保留 →
> 移除清單 = 「有 v2 對等且 caller 歸零」的非 auth/非 platform v1 端點。**移除須先過 30 天
> deprecation-metrics 零命中窗**（CR-0159 鐵律：server 端產生的 URL 消費 grep 不到，不可只憑
> 靜態掃描移除）——**該 metrics collector 尚未部署，故本輪只定案 + 排程，不實際移除端點**。
> 詳見 `CR-0166-R7-v1-convergence-plan.md`。

1. ~~auth 端點定位~~ → **定案：v1 永久例外**（見上）。
2. ~~platform_* 系列~~ → **定案：v1 長期承諾不開 v2**（見上）。
3. ~~「5-gate」名實~~ → **定案：ADR-003 三步為準**（見上）。

## 驗收狀態

WBS 2.5.1 → 🔶:Gate-1 凍結 **enforced**(本輪);遷移/移除受 §8 業主裁決阻擋,依 ADR-003 節奏排 M3。M2 SIT(2.6.1)不依賴移除完成。

### 進度

- ✅ Gate-1 done(2026-07-10,branch `chore/v1-freeze-gate`):守門腳本+baseline 195 ops+CI workflow;自驗綠
