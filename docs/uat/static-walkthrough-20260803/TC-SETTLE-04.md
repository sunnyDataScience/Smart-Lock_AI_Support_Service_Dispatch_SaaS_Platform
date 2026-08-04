# TC-SETTLE-04 — 超越角色核准上限的退款升級

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **不一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；正式機金流環境不可用，本批不做執行期驗證。後續以本機 Docker 測試庫實跑既有測試，退款 5 檔 66 項全數通過，但無任何一項斷言「核准者角色不足即拒」或「額度上限」（見步驟 5） |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/refund_service.py:442-526`、`:551-673`、`:286-424`、`api/routers/refunds_v2.py:36-115`、`api/core/deps.py:293-301`、`api/services/config_service.py:133-155`、`web/brand-portal/src/app/admin/refunds/page.tsx:23-151`、`smartlock-docs/enterprise/13_Security_Architecture.md:90-106` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 5-tier 分層本身有實作（`resolve_tier` 依 `[1000,5000,30000,100000]` 推算；NTD 200,000 > 100,000 → L5），tier 對應核准角色的對照表也在 config 裡。但 TC 判定基準的兩條**都找不到對應程式碼**：①「拒絕並升級至上一層核准者」——`approver_role_for_tier` 的回傳值只被塞進 audit payload 的 `approver_role_required` 欄位，`create_refund_sod` 與 `submit_decision` 全程未拿它與任何角色比對，也沒有自動升級的程式碼；②「有效額度 = min(requested, role_limit)」——`role_limit` 這個概念在 `api`／`SQL`／`web` 全數零命中，金額只有 `> 0` 驗證與 tier 推算，不存在依核准者角色截斷金額的邏輯。`INSUFFICIENT_AUTHORITY` 這個 403 錯誤碼只存在於 `api/openapi.yaml`，`api/**/*.py` 零命中。 |

**TC 原文**｜前置：退款額度分層 L1–L5｜步驟：主管（L3）嘗試核 NTD 200,000（超 L3 上限）｜判定基準：拒絕並升級至上一層核准者；有效額度 = min(requested, role_limit)｜需求：FR-API-11｜旅程：SC-08

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 系統 | 推算金額分層 | `TierResolved(L5)` | 伺服器端推算 | `services/refund_service.py:473-491` | 200,000 > 100,000 → L5 |
| 主管（L3） | 核准 200,000 | `ApprovalRejected(403)` | 超上限即拒 | `services/refund_service.py:296-381` | **找不到**角色/上限比對；`submit_decision` 只比對「同一 user 不可重複簽」 |
| 系統 | 升級至上一層 | `ApprovalEscalated` | 自動升級 | — | **找不到**自動升級程式碼；`escalate` 是呼叫端顯式帶的 decision 值 |
| 系統 | 截斷有效額度 | `EffectiveAmountCapped` | min(requested, role_limit) | — | **找不到**；`role_limit` 全 repo 零命中 |
| 系統 | 記錄應有核准角色 | `AuditLogged` | 留痕 | `services/refund_service.py:628` | 寫進 audit payload，不作為判斷依據 |

---

## 走查紀錄

### 步驟 1 — 分層本身（TC 前置條件）

- **動作**：讀 tier 推算與 config
- **預期**：L1–L5 存在
- **實際**：存在；200,000 落 L5

`api/services/refund_service.py:479-491`

```python
    thresholds = refund_config.get("tiers", {}).get("thresholds")
    if not thresholds or len(thresholds) != 4:
        raise ApiError("INTERNAL_ERROR", "refund tier thresholds misconfigured", 500)
    amt = float(amount)
    if amt <= thresholds[0]:
        return "L1"
    if amt <= thresholds[1]:
        return "L2"
    if amt <= thresholds[2]:
        return "L3"
    if amt <= thresholds[3]:
        return "L4"
    return "L5"
```

config 預設：`api/services/refund_service.py:446-464`

```python
    "tiers": {
        # 升冪門檻：amount <= thresholds[0] → L1；> thresholds[3] → L5（ADR-0040 §97-104）
        "thresholds": [1000, 5000, 30000, 100000],
        # 每 tier 的核准角色（最低有權核准者；高 tier 需更高層級）
        "approver_roles": {
            "L1": "supervisor",
            "L2": "manager",
            "L3": "finance_manager",
            "L4": "director",
            "L5": "cfo",
        },
        # 每 tier 要求的核准簽核人數（單調不遞減）
        "required_approvals": {
            "L1": 1,
            "L2": 1,
            "L3": 2,
            "L4": 2,
            "L5": 3,
        },
    },
```

- TC 步驟：「主管（L3）嘗試核 NTD 200,000（超 L3 上限）」
- 程式碼：tier 是**由金額推算**的屬性（`resolve_tier`），不是核准者身上的屬性；200,000 推得 L5，程式碼中沒有「某角色的上限」這個資料

此處僅並陳，不裁定。

### 步驟 2 — `approver_role_for_tier` 的唯一消費點

- **動作**：追該函式的所有呼叫點
- **預期**：核准時比對角色
- **實際**：只出現在 audit payload

`api/services/refund_service.py:524-526`

```python
def approver_role_for_tier(tier: str, refund_config: dict) -> str | None:
    """查 tier 對應的最低核准角色（純函式）。"""
    return refund_config.get("tiers", {}).get("approver_roles", {}).get(tier)
```

唯一非測試呼叫點：`api/services/refund_service.py:617-628`

```python
    audit_payload = {
        "operator_id": sod_initiator,
        ...
        "config_version_applied": config_version,
        "approver_role_required": approver_role_for_tier(tier, refund_config),
    }
```

```
git grep -n "approver_role_for_tier\|required_approvals" -- api
api/services/refund_service.py:458   （config 宣告）
api/services/refund_service.py:524   （函式定義）
api/services/refund_service.py:628   （audit payload）
api/tests/test_refund_sod_5tier.py:137-149  （只驗 config 本身的完整性與單調性）
```

`required_approvals` 除 config 宣告與測試外，在 `api/` 中**零消費**。

### 步驟 3 — 核准路徑實際做的檢查

- **動作**：讀 `submit_decision` 的全部拒絕分支
- **預期**：含「核准者權限不足」
- **實際**：四種拒絕，皆與角色上限無關

`api/services/refund_service.py:317-365`

```python
    if decision not in {"approve", "reject", "escalate"}:
        raise ApiError(
            "VALIDATION_ERROR",
            "decision must be one of approve, reject, escalate",
            422,
        )
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason is required", 422)
...
    if current not in _DECISION_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot decide refund in status '{current}'; expected one of {sorted(_DECISION_FROM)}",
            409,
        )
...
    # 同一 user 不可重複簽
    prior_signers = {entry.get("user_id") for entry in chain if isinstance(entry, dict)}
    if decided_by_user_id in prior_signers:
        raise ApiError(
            "DUAL_SIGN_SAME_USER",
            "Same user cannot sign twice on the same refund",
            409,
        )

    # escalate 只允許 pending 階段（已雙簽中要 escalate 應走另一路徑）
    if decision == "escalate" and current != "pending":
```

該函式的簽章不接收金額、tier 或核准者角色（`:296-303`）：

```python
async def submit_decision(
    *,
    tenant_id: str,
    refund_id: str,
    decision: str,
    reason: str,
    decided_by_user_id: str,
) -> dict:
```

router 側的角色守衛為 `role_required(*REVIEW_ROLES, fail_closed=True)`（`routers/refunds_v2.py:91`），該集合為 `("admin", "operations_manager", "reviewer")`（`core/deps.py:293-301`），與 tier 無關。

新狀態的計算只看 `requires_dual_sign` 與現況（`refund_service.py:368-381`）：

```python
    if decision == "reject":
        new_status = _REJECTED_STATUS
    elif decision == "escalate":
        new_status = _ESCALATED_STATUS
    else:  # approve
        if current == "csm_approved":
            # 第二簽完成 → final approved
            new_status = _FINAL_APPROVED_STATUS
        elif requires_dual_sign:
```

`escalated` 只在呼叫端顯式傳 `decision="escalate"` 時產生，且該狀態不在 `_DECISION_FROM = {"pending", "csm_approved"}`（`:289`）中，即升級後無後續核准路徑。

### 步驟 4 — TC 指名概念的零命中

- **動作**：grep TC 判定基準的識別碼
- **預期**：命中
- **實際**：零命中

```
git grep -in "role_limit\|approval_limit\|approve_limit" -- api SQL web
（無輸出）
```

```
git grep -n "INSUFFICIENT_AUTHORITY" -- api
api/openapi.yaml:60, :432, :1575, :1605, :1864, :2700, :4031, :4060, :5394, :5483
```

即 `INSUFFICIENT_AUTHORITY` 只出現在契約檔，`api/**/*.py` 與 `web/` 零命中。

前端側：`web/brand-portal/src/app/admin/refunds/page.tsx:23`、`:124` 記載

```
 * 取代舊 reason_code。tier 由伺服器從 amount 推算（門檻 1k/5k/30k/100k → L1..L5）。
...
      // tier 不傳——伺服器從 amount 推算；reason_code / requested_by_role 已不需要。
```

該頁面對 tier 的處理止於顯示（`:150-151` 建立成功後顯示 `tier`），無上限判斷。

### 步驟 5 — 執行既有測試

- **動作**：跑退款測試
- **預期**：取得執行證據
- **實際**：66 項通過，但無一項覆蓋本 TC 判定基準

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_refund_sod_5tier.py \
  tests/test_refund_sod_endpoint.py tests/test_refund_dual_sign.py \
  tests/test_create_refund_request.py tests/test_refund_decision_v2_endpoint.py \
  -q -p winloop_plugin --tb=line

66 passed in 3.84s
```

與 tier 角色相關的兩項只驗 config 結構：`api/tests/test_refund_sod_5tier.py:137-149`

```python
def test_approver_roles_cover_all_tiers():
    roles = CFG["tiers"]["approver_roles"]
...
        assert tier in roles, f"missing approver role mapping for {tier}"
        assert roles[tier], f"empty approver role for {tier}"


def test_required_approvals_escalates_with_tier():
...
    assert seq == sorted(seq), "required_approvals must be monotonic non-decreasing"
```

**無對應測試**：搜尋 `api/tests/` 中「核准者角色不足 → 拒絕」或「額度上限截斷」的斷言，零命中。

---

## 觀測到的其他事實

- `DEFAULT_REFUND_CONFIG["tiers"]["approver_roles"]` 的五個值（`supervisor` / `manager` / `finance_manager` / `director` / `cfo`）不在系統 7 角色正典中；正典為 `platform_admin` / `admin` / `operations_manager` / `customer_service` / `reviewer` / `technician` / `dispatcher`（`smartlock-docs/enterprise/13_Security_Architecture.md:96-102`）。
- 另一條金額門檻獨立存在：`_DUAL_SIGN_THRESHOLD = 100000.0`（`services/refund_service.py:120`），在 `create_refund_request`（legacy 路徑）用來自動決定 `requires_dual_sign`（`:258-262`）；`create_refund_sod`（本 TC 路徑）不設定該欄位。
- `smartlock-docs/enterprise/04_SRS.md:586` 記載裁決 D1：「5×3」＝5 層金額分層 × SoD 三維，並稱實作完整落地（`resolve_tier` + 三維 SoD + `refund_class` 5 類）。該裁決文字未提及角色上限或自動升級。
- tier 值落庫後有 CHECK 約束 `tier IN ('L1'..'L5')`（`SQL/migrations/002-refund-sod-5tier.sql:47-48`）。
- 退款 seed 資料中有一筆 `approval_chain` 記載 `"decision":"escalate","reason":"金額超過授權額度"`（`SQL/seeds/refund_requests.sql:38`），該值為靜態種子資料，非程式碼產生。
