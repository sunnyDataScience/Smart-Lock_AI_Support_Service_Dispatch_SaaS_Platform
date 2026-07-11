# CR-0166 R7 — v1 API 收斂計畫（D5 定案後）

- **日期**：2026-07-12
- **依據**：ADR-003（v1 收斂三步：凍結／遷移／移除）、CR-0145（Gate-1 凍結 enforced）、CR-0159（v1 cutover 鐵律）。
- **業主裁決**：D5「照建議」（2026-07-12）——見 CR-0145 §8 定案。

## §1 D5 定案摘要

| 面 | 定案 | 含義 |
|---|---|---|
| **auth** | v1 永久例外 | user-scoped auth v1 端點不移除；作為相容承諾長期保留 |
| **platform_*** | v1 長期承諾 | 不開 v2 平面；platform console 以 v1 為長期正典 |
| **5-gate 名實** | ADR-003 三步 | 棄 8-stage 舊稱，統一凍結／遷移／移除 |

## §2 收斂狀態（ADR-003 三步）

1. **凍結（Gate-1）**：✅ **enforced**（CR-0145）——`scripts/ci/v1-freeze-check.py`＋baseline 195 ops，新增 v1 即 CI 紅。
2. **遷移**：v1 有 v2 對等者，前端 caller 逐步改用 v2（進行中，隨各 CR）。
3. **移除**：**受 deprecation-metrics 30 天零命中窗阻擋（CR-0159 鐵律）**——server 端產生的
   URL 消費（如 media_url）grep 不到，不可只憑靜態掃描移除。

## §3 移除清單條件（本輪不執行移除）

可移除 = 全部滿足：
- ① 有 v2 對等端點；
- ② **非 auth、非 platform_***（D5 保留）；
- ③ 前端四站靜態 grep caller 歸零；
- ④ **server 端 deprecation-metrics 30 天窗零命中**（防 data-driven URL 消費，CR-0159）。

**阻擋點**：④ 的 metrics collector 尚未部署。故本輪：
- ✅ 定案 D5（auth/platform 保留、ADR-003 三步）。
- ✅ 凍結 gate 持續 enforced。
- ⏭ **移除延後**至 metrics collector 部署（併 R6 上雲＋SigNoz／CR-0156 OTel 埋點的
  deprecation 命中計數）後，逐端點過窗才移除。

## §4 後續 op（非本輪）

- 部署 deprecation-metrics collector（api middleware 記 v1 端點命中，落 SigNoz／DB）。
- 30 天窗後，對「有 v2＋caller 歸零＋metrics 零」的非 auth/platform v1 端點逐一移除。
- 每移除一批更新 `v1-freeze-baseline.json`（`--update-baseline`）。

> **結論**：R7 的**治理定案**（D5）與**凍結維持**已完成；**實際端點移除**是 metrics-gated 的
> 未來 op（誠實邊界——不在無 metrics 窗下盲移，避免破壞 server-generated URL 消費）。
