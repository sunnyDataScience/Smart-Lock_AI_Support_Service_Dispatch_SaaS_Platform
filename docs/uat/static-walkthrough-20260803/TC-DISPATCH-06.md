# TC-DISPATCH-06 — 品牌授權過濾與無授權資料時的 fail-closed

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 6） |
| 走查時間 | 2026-08-03 18:25（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/dispatch_service.py`、`api/services/work_order_service.py`、`api/services/config_m18_service.py`、`api/core/deps.py`、`api/core/auth.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 品牌授權過濾實作存在：自動媒合以授權集合過濾候選、手動派工在 `_assert_brand_authorized` 擋未授權技師（403 `TECHNICIAN_BRAND_NOT_AUTHORIZED`）。「無授權資料時 fail-closed」的分支同樣存在，但**由 M18 config `dispatch_policy.brand_auth_enforce` 控制且預設 off**；開關關閉時該情境回到不阻擋。另有主管（admin / operations_manager）帶 `override_reason` 的放行分支。 |

**TC 原文**｜前置：未授權該品牌的技師｜步驟：對其派工｜判定基準：品牌授權過濾擋下；無授權資料時不得 fail-open 放行（fail-closed 驗證）｜⚠ 未標註｜P0｜FR-TEC-02、FR-TEC-03｜SC-05、SC-12、SC-14

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 派工小編 | 對未授權技師派工 | `DispatchRejected` | 授權過濾擋下 | `services/work_order_service.py:2170-2176` | 403 `TECHNICIAN_BRAND_NOT_AUTHORIZED` |
| 系統 | 該品牌無授權資料 | `DispatchRejected` | fail-closed | `services/work_order_service.py:2149-2169` | 依 `brand_auth_enforced()` 二分：off → return（放行）；on → 403 `BRAND_AUTHORIZATION_LIST_EMPTY` |
| 系統 | 自動媒合過濾 | `CandidatesFiltered` | 只選已授權 | `services/dispatch_service.py:603-608` | `_auth_ids is not None` 才過濾 |
| 主管 | 帶 override_reason 派工 | `DispatchOverridden` | 安全閥 | `services/work_order_service.py:2131-2137` | `admin`/`operations_manager` + 非空 reason → 直接 return |

---

## 走查紀錄

### 步驟 1 — 授權集合查詢與三態收斂

- **動作**：讀 `_brand_authorized_ids`
- **預期**：回傳授權技師 id 集合
- **實際**：`brand` 為空 → `None`（不判斷）；查有列 → 集合；**查無列 → 由 M18 開關決定回 `set()`（fail-closed）或 `None`（不阻擋）**

`api/services/dispatch_service.py:361-388`

```python
    if not brand:
        return None
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT technician_id FROM technician_brand_authorization "
        "WHERE brand = %s AND authorized = TRUE "
        "  AND (cert_expires_at IS NULL OR cert_expires_at >= CURRENT_DATE)",
        (brand,),
    )
    rows = await cur.fetchall()
    if not rows:
        # 空集合＝誰都不符＝下游自然 fail-closed；None＝不判斷＝維持原本的放行。
        # 由 M18 開關決定走哪一邊（CR-0197 D1(c)）。
        if await brand_auth_enforced():
            logger.warning(
                "品牌「%s」無任何有效授權技師 → 派工 fail-closed（需先建立品牌授權名單，"
                "或由主管帶 override_reason 手動派工）", brand,
            )
            return set()
        # 閘門未啟用：維持 CR-0060 以來的行為。記 info 而非靜默 ——
        # 「閘門存在但沒在擋」必須看得見，否則會被誤以為派工資格已受控。
        logger.info(
            "品牌「%s」無有效授權技師，但 dispatch_policy.brand_auth_enforce 未啟用 "
            "→ 不阻擋（CR-0197 D1(c)：待營運補齊名單後再開）", brand,
        )
        return None
    return {str(r[0]) for r in rows}
```

### 步驟 2 — 開關的預設值

- **動作**：讀 `brand_auth_enforced`
- **預期**：確認 fail-closed 是否為預設行為
- **實際**：預設 off，且 config 讀取失敗亦視為未啟用

`api/services/dispatch_service.py:310-330`

```python
async def brand_auth_enforced() -> bool:
    """品牌授權閘門是否啟用（CR-0197 §8 D1(c)，業主 2026-08-01 裁決）。

    M18 config `dispatch_policy.brand_auth_enforce`，**預設 off**，比照
    `settlement_policy.reconcile_gate_enforce` 前例（monthly_settlement_service）。
    ...
    """
    from services import config_m18_service

    try:
        cfg = await config_m18_service.read_global_value(namespace="dispatch_policy")
    except Exception:  # noqa: BLE001 — 讀取失敗視同未配置（gate 預設 off）
        return False
    return bool(isinstance(cfg, dict) and cfg.get("brand_auth_enforce"))
```

同一 docstring `:316-321` 記載預設 off 的理由：「prod 的 `technician_brand_authorization` 只有 CR-0060 留下的 `is_mock` seed（Generic/Kaadas/Philips/Samsung/Yale 各 13 筆），營運從未填過真實資料；實際在用的 Chatlock/Dormakaba/美樂/Xiaomi/Gateman 一筆都沒有。」

TC 判定基準寫「無授權資料時不得 fail-open 放行」；程式碼在開關預設值下走的是不阻擋分支。此處僅並陳，不裁定。

### 步驟 3 — 手動派工的授權檢查分支

- **動作**：讀 `_assert_brand_authorized`
- **預期**：未授權 → 擋
- **實際**：四條出口——override 放行、無 brand 放行、無授權資料（依開關）放行或 403、技師不在名單 403

`api/services/work_order_service.py:2131-2149`

```python
    if (
        actor_role in _QUOTE_GATE_OVERRIDE_ROLES
        and override_reason
        and override_reason.strip()
    ):
        logger.info("assign brand-auth overridden by %s for wo=%s", actor_role, wo_id[:8])
        return
    brow = await (await db_module._conn.execute(
        "SELECT brand FROM work_orders WHERE id = %s::uuid", (wo_id,))).fetchone()
    brand = brow[0] if brow else None
    if not brand:
        return  # 無品牌資訊無從判斷（_assert_dispatch_ready 另有品牌必填 gate）
```

`api/services/work_order_service.py:2149-2176`

```python
    if not auth:
        # fail-closed：無授權資料 ≠ 可以派給任何人（TC-DISPATCH-06）。
        # 但由 M18 開關控制是否真的擋（CR-0197 D1(c)，預設 off）——
        # 與 dispatch_service._brand_authorized_ids 共用同一個開關，語意必須一致。
        from services.dispatch_service import brand_auth_enforced

        if not await brand_auth_enforced():
            logger.info(
                "品牌「%s」無有效授權技師，但 dispatch_policy.brand_auth_enforce 未啟用 "
                "→ 手動派工不阻擋 wo=%s", brand, wo_id[:8],
            )
            return
        logger.warning(
            "品牌「%s」無任何有效授權技師，手動派工被擋 wo=%s", brand, wo_id[:8]
        )
        raise ApiError(
            "BRAND_AUTHORIZATION_LIST_EMPTY",
            f"品牌「{brand}」尚未建立任何技師授權名單，依授權閘門不可派工。"
            f"請先於平台後台建立該品牌的技師授權，或由主管帶 override_reason 強制派工",
            403,
        )
    authorized_ids = {str(r[0]) for r in auth}
    if technician_id not in authorized_ids:
        raise ApiError(
            "TECHNICIAN_BRAND_NOT_AUTHORIZED",
            f"技師未取得品牌「{brand}」授權，不可派工；主管可帶 override_reason 強制派工",
            403,
        )
```

呼叫點：`assign_order` 於 `:2251`、`reassign_order` 於 `:2427`（後者以必填 `reason` 當 override 傳入）。

### 步驟 4 — 自動媒合 vs 人工候選清單的兩種語意

- **動作**：比對兩條路徑對授權集合的用法
- **預期**：一致
- **實際**：auto-match 過濾、candidates 只標示

`api/services/dispatch_service.py:603-608`

```python
    # CR-0114 R4（裁決 7）：**自動派工維持只選已授權**——人工派工可挑未授權
    # (list_dispatch_candidates 標示可見),但自動指派不該自行派給沒修過該鎖品牌
    # 的師傅。無授權資料(None)時保守不過濾(沿用原語意)。
    _auth_ids = await _brand_authorized_ids(pc_brand)
    if _auth_ids is not None:
        scored = [c for c in scored if c["technician"].get("id") in _auth_ids]
```

`api/services/dispatch_service.py:537-551`

```python
    # CR-0114 R4（裁決 3）：鎖品牌授權由「過濾」改「標示」——全部啟用中師傅
    # 皆可見,每人標 brand_authorized（true/false/null）,已授權排前供人工挑選。
    # null = 該品牌無任何授權資料(無從判定;沿用原保守語意,不標未授權)。
    auth_ids = await _brand_authorized_ids(wo_brand)
    for c in candidates:
        if auth_ids is None:
            c["brand_authorized"] = None
        else:
            c["brand_authorized"] = c["technician"].get("id") in auth_ids
```

### 步驟 5 — FR-TEC-02 的准入閘門（生命週期）

- **動作**：確認另一道「不得進入候選集」的檢查
- **預期**：未過准入者不進候選
- **實際**：以生命週期狀態硬排除，與 `exclude_circuit` 無關

`api/services/dispatch_service.py:185-192`

```python
# CR-0051 / BR-M06 / G004-G005：生命週期「不可派工」狀態（未核准/停權/終止/退回）—
# 與「操作性不可用」（inactive/on_leave/circuit）區分；前者一律硬排除候選，不受 exclude_circuit 影響。
_DISPATCH_INELIGIBLE_STATUSES = {"pending_approval", "suspended", "terminated", "rejected"}


def _is_dispatch_eligible(status: str | None) -> bool:
    """BR-M06：技師是否具派工資格（生命週期狀態非未核准/停權/終止/退回）。"""
    return status not in _DISPATCH_INELIGIBLE_STATUSES
```

`_score_rows` 於 `:430-431` 呼叫（`if not _is_dispatch_eligible(status): continue`）。

### 步驟 6 — 執行既有測試

- **動作**：跑派工測試（由統籌者於本批次執行，數字沿用不重跑）
- **預期**：取得執行證據
- **實際**：第一輪無資料庫多數失敗；建立本機測試庫後重跑，八檔 52 項全數通過（含 `test_cr_0051_dispatch_eligibility.py` 8 項）

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0051_dispatch_eligibility.py tests/test_cr_0030_dispatch_mode.py \
  tests/test_manual_dispatch.py tests/test_dispatch_v2_endpoint.py tests/test_dispatch_plan_v2_endpoint.py \
  tests/test_cr_0164_tech_mirror_projection.py tests/test_cr_0172_tech_dispatch_outbox.py \
  tests/test_dispatch_fairness_load.py -q --tb=no
13 failed, 39 passed in 3.87s
```

單獨執行 `tests/test_manual_dispatch.py::test_admin_assign_does_not_write_bypass_audit` 時（同為無 DB 環境）：

```
cd api && python -m pytest tests/test_manual_dispatch.py::test_admin_assign_does_not_write_bypass_audit -q --tb=line
1 failed in 3.02s

ERROR    api.db:db.py:48 環境變數 POSTGRES_URI 未設定
api/tests/test_manual_dispatch.py:350: AssertionError: {"type":"urn:smartlock:error:security_state_unavailable","status":503,
"error_code":"SECURITY_STATE_UNAVAILABLE","message":"安全狀態不可驗（撤銷/停權查核離線）——關鍵金流/派工寫入拒絕執行（SA-05 fail-closed）"}
```

該回應未進入本 TC 的品牌授權判斷，而是在更前面的授權守衛被擋下。產生點 `api/core/deps.py:326-334`：

```python
        if fail_closed:
            from core.auth import security_state_verifiable

            if not await security_state_verifiable(user.role):
                raise ApiError(
                    error_code="SECURITY_STATE_UNAVAILABLE",
                    message="安全狀態不可驗（撤銷/停權查核離線）——關鍵金流/派工寫入拒絕執行（SA-05 fail-closed）",
                    status_code=503,
                )
```

判準函式 `api/core/auth.py:202-215` 在 DB 不可用時回 `False`（`return (await _security_conn(role)) is not None`）。派工寫入端點（`assignWorkOrderV2`、`planDispatchV2`、`assignDispatch`、`planDispatchAutoMatchV2`）皆以 `fail_closed=True` 掛載。

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」），逐檔執行 `cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/<檔名> -q -p winloop_plugin --tb=no`：

```
test_cr_0051_dispatch_eligibility.py       8 passed in 0.38s
test_cr_0030_dispatch_mode.py              3 passed in 2.97s
test_manual_dispatch.py                   10 passed in 2.99s
test_dispatch_v2_endpoint.py               6 passed in 2.97s
test_dispatch_plan_v2_endpoint.py          8 passed in 2.96s
test_cr_0164_tech_mirror_projection.py     5 passed in 0.46s
test_cr_0172_tech_dispatch_outbox.py       5 passed in 0.40s
test_dispatch_fairness_load.py             7 passed in 0.40s
```

八檔 52 項全數通過；安全狀態可驗後 `test_admin_assign_does_not_write_bypass_audit` 不再落入 `SECURITY_STATE_UNAVAILABLE` 分支。`test_cr_0051_dispatch_eligibility.py` 的 8 項覆蓋的是步驟 5 的生命週期准入閘門（`_is_dispatch_eligible` 七種狀態參數化 + `_score_rows` 排除不合格者）；步驟 1-3 的品牌授權集合查詢與三態收斂不在該檔覆蓋範圍內，實跑亦無對應案例被執行。

---

## 觀測到的其他事實

- `api/services/dispatch_service.py:336-341` 記載追溯鏈補正：`BR-M07-01` 在 `smartlock-docs/` 全庫零命中，現行對應為 `04_SRS.md` FR-TEC-02 / FR-TEC-03。
- `smartlock-docs/enterprise/04_SRS.md:352` 記 FR-TEC-02 後置條件「未過准入閘門不得進入派工候選集」，`:362` 另註「不變且未被放寬」。
- 授權查詢走技師權威庫連線 `db_module.require_tech_conn()`（`dispatch_service.py:364`、`work_order_service.py:2143`），單庫 fallback 為同一連線。
- CIA 文件 `docs/4-exploration/CR-0197-brand-authorization-gate-activation.md` 為此開關的來源文件。
