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

---

## §5 caller 歸零查核（2026-07-22，WBS 2.5.1 步驟2 結案）

**方法**：以「v1 handler 自身 summary 標 `[DEPRECATED]`」為權威訊號（API 自己宣告哪些有 v2 後繼），
而非關鍵字猜測——**關鍵字配對會誤判**，例如 `/api/v1/config`（`system_config.py`：單一設定物件
GET/PATCH）與 `/tenants/{tid}/m18/configs`（`config_m18.py`：namespace/key＋版本＋canary rollout）
**並非對等**，硬遷會壞。

**母體**：19 個自我宣告 DEPRECATED 的 v1 端點（audit-logs×2／customers×4／dispatch×2／
problem-cards×6／roles×2／technicians×2／…）。

**掃描**（排除四類非 caller：`v1-freeze-baseline.json` 凍結登記表、`api/tests/*` 雙掛驗證回歸測試、
`openapi-runtime.json`／`*_v2.py` docstring 等說明、`.next/` build 產物；並以**路徑邊界比對**
排除 `/technicians/login`、`/technicians/me/*` 這類被前綴誤配的 D5 例外／非 deprecated 端點）：

| 來源 | 結果 |
|---|---|
| 前端四站 | **0 處**（唯一命中 `brand-portal/app/admin/roles/page.tsx:119` 是**註解**，程式碼早已改打 `/tenants/{tid}/rbac/roles`） |
| agent／knowledge-pipeline | **0 處** |
| scripts | 1 處 → 本輪已遷：`scripts/dev/load_test.py` 的 `/api/v1/problem-cards` → `/tenants/{TENANT}/problem-cards`（該腳本其餘 v1 呼叫為 auth 例外或未標 deprecated 的自助端點，保留） |

> **✅ 結論：19 個 DEPRECATED v1 端點的真實 caller 全數歸零 → ADR-003 步驟2「遷移」完成。**
> ADR-003 §24「約 42 個 caller `[待確認]`」為 **stale**——遷移已隨各 CR 增量完成。
>
> **步驟3「移除」剩餘 gate**：① 有 v2 對等 ✅ ② 非 auth/platform（D5）✅ ③ caller 歸零 ✅（本次）
> ④ **deprecation metrics 30 天窗零命中 ⬜（需生產流量，metrics 為 in-memory，本機數據無意義）**
> ⑤ **移除屬 API contract 變更 → 需 CIA ⬜**。
> 即：**caller gate 已達成，但仍不可移除**——外部/行動端/腳本消費只有 metrics 能證明。
