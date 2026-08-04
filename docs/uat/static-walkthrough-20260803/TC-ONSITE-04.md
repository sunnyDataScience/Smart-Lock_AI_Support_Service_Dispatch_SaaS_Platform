# TC-ONSITE-04 — 加價 > NTD 2000 的主管覆核與三件套齊備

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，分層核可與分級相關 9 項全數通過（見步驟 5） |
| 走查時間 | 2026-08-03 21:15（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/work_order_service.py:2890-2921`、`:2988-3009`、`:1519-1591`、`api/services/quote_engine_service.py:450-455`、`:527-545`、`api/routers/quote_v2.py:196-200`、`:230-250`、`api/services/media_service.py:31-41`、`api/services/signature_service.py:112-174`、`api/services/approval_inbox_service.py:1-72` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 「>2000 須主管」的強制點存在，但落在**報價送出**（`quote_engine_service.transition(action="send")`，`:538-545`，403 `REQUOTE_SUPERVISOR_REQUIRED`，主管角色白名單 `("operations_manager", "admin")`），且判定基準是 v+1 與前版報價的 `total_amount` 差額，不是 scope change 的加價金額。scope change 側的 `_classify_scope_tier` 雖產出 `requires_supervisor=True`，該旗標無任何執行期讀取者。TC 所述「三件套（影音＋文字＋before/after 照）必齊」在程式碼中找不到對應閘門：`media_files.purpose` 白名單九值皆為靜態圖片用途，無影音類別，也無「before/after 成對」的檢核。 |

**TC 原文**｜前置：加價 > NTD 2000｜步驟：發起 scope change｜判定基準：強制主管覆核；三件套（影音+文字+before/after 照）必齊｜需求：FR-API-08｜旅程：SC-07

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | 發起 scope change（>2000） | `ScopeChangeRequested(major)` | delta>2000 或 pct≥50% | `work_order_service.py:2910-2911` | tier=`major`、`requires_supervisor=True` |
| 系統 | 進主管覆核佇列 | `SupervisorReviewRequired` | major 強制 | — | **找不到**；`requires_supervisor` 無讀取者 |
| 小編 | `:send` v+1 報價 | `SendRejected(403)` | delta>2000 限主管 | `quote_engine_service.py:538-545` | 403 `REQUOTE_SUPERVISOR_REQUIRED` |
| 主管 | `:send` v+1 報價 | `QuoteSent` | ops_manager/admin | `quote_engine_service.py:453` | `_REQUOTE_SUPERVISOR_ROLES = ("operations_manager", "admin")` |
| 系統 | 三件套齊備檢核 | `EvidenceCompleteChecked` | 影音+文字+前後照 | — | **找不到**；完工硬閘查的是張數／簽名／序號 |
| 主管 | 於 approval inbox 決議 | `ApprovalResolved` | 集中收件匣 | `approval_inbox_service.py:37` | scope_change 以 `severity="medium"` 列入 inbox，非阻斷式 |

---

## 走查紀錄

### 步驟 1 — >2000 的分級與旗標

- **動作**：讀 `_classify_scope_tier`
- **預期**：>2000 → major 且需主管
- **實際**：一致（旗標層面）

`api/services/work_order_service.py:2908-2921`

```python
    delta = max(0.0, (new_price or 0.0) - (original_price or 0.0))
    pct = (delta / original_price) if original_price and original_price > 0 else (1.0 if delta else 0.0)
    if delta > float(policy["standard_max"]) or pct >= float(policy["major_pct"]):
        tier = "major"
    ...
    return {
        "tier": tier,
        "delta": round(delta, 2),
        "pct": round(pct, 4),
        "requires_supervisor": tier == "major",
    }
```

`test_cr_0038_bucket4.py:38-50` 覆蓋「金額觸發 major」與「比例觸發 major」兩條。

### 步驟 2 — `requires_supervisor` 是否被強制

- **動作**：全 repo 搜尋消費者
- **預期**：major 提案被擋下等主管
- **實際**：僅寫入資料，無執行期消費者

```
$ grep -rn "requires_supervisor" --include=*.py --include=*.tsx --include=*.ts api web
api/services/work_order_service.py:2900   （docstring）
api/services/work_order_service.py:2920   （產生點）
api/services/work_order_service.py:2988   （註解）
api/tests/test_cr_0038_bucket4.py:26,34,42,50   （測試斷言）
```

`record_scope_change` 對 major 的處理與 minor 完全相同——一律 `status='pending'`、一律 mint token、一律推 LINE：

`api/services/work_order_service.py:2992-2997`

```python
    cur = await db_module._conn.execute(
        "INSERT INTO scope_changes "
        "  (work_order_id, technician_id, reason, "
        "   original_scope, new_scope, original_price, new_price, status) "
        "VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, %s::jsonb, %s, %s, 'pending') "
        "RETURNING id",
```

且 `admin_override`（`scope_change_service.py:273-331`）的 RBAC 為 `_DISPATCH_ALLOWED_ROLES`（`work_orders_v2.py:71-76`＝`admin`/`operations_manager`/`dispatcher`/`customer_service`），比 `_REQUOTE_SUPERVISOR_ROLES` 寬。

- TC 判定基準：>2000 **強制**主管覆核
- 程式碼：scope change 路徑無強制點；報價路徑（下一步）有

此處僅並陳，不裁定。

### 步驟 3 — 報價側的 >2000 主管強制

- **動作**：讀 `transition(action="send")` 的分層核可段
- **預期**：>2000 非主管 403
- **實際**：一致，且 legacy 未帶 `actor_role` 亦 fail-closed

`api/services/quote_engine_service.py:450-453`

```python
# CR-0150（ADR-027 Decision 3／16_API:397）：requote v+1 送出分層核可。
# delta=|v+1 總額 − v 總額|：≤500 逕送；501–2000 小編核可（OPS 角色執行送出
# 即核可，身分由 router RBAC 保證）；>2000 主管覆核（僅下列角色可執行送出）。
_REQUOTE_TIER_EDITOR_MAX = 2000.0
_REQUOTE_SUPERVISOR_ROLES = ("operations_manager", "admin")
```

`api/services/quote_engine_service.py:527-545`

```python
    if action == "send":
        rq = await (await conn.execute(
            "SELECT supersedes_quote_id, COALESCE(total_amount, 0) "
            "FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if rq and rq[0]:
            prev = await (await conn.execute(
                "SELECT COALESCE(total_amount, 0) FROM quote WHERE id = %s::uuid",
                (rq[0],))).fetchone()
            delta = abs(float(rq[1]) - float(prev[0] if prev else 0))
            if delta > _REQUOTE_TIER_EDITOR_MAX and (actor_role or "") not in _REQUOTE_SUPERVISOR_ROLES:
                raise ApiError(
                    "REQUOTE_SUPERVISOR_REQUIRED",
                    f"修正報價價差 {delta:.0f} 超過 {_REQUOTE_TIER_EDITOR_MAX:.0f}，"
                    "須由主管（operations_manager／admin）執行送出（CR-0150 分層核可）",
                    403,
                )
```

三個條件差異需注意：

| 面向 | TC 判定基準 | 程式碼 |
|---|---|---|
| 觸發對象 | scope change 加價 | `quote.supersedes_quote_id` 非空（即 requote v+1） |
| 金額來源 | 現場加價金額 | `abs(v+1.total_amount − prev.total_amount)` |
| 觸發時點 | 發起 scope change 時 | 報價 `:send` 時 |
| 非主管的結果 | 覆核流程 | 403 拒絕送出 |

此處僅並陳，不裁定。

`actor_role` 的來源：`api/routers/quote_v2.py:196-200`

```python
    # actor_role 供 CR-0150 requote 分層核可（send 時 delta>2000 限主管角色）
```

### 步驟 4 — 三件套的檢核落點

- **動作**：找「影音＋文字＋before/after 照」的齊備檢核
- **預期**：>2000 時三者必齊才放行
- **實際**：找不到；現有硬閘為張數／簽名／序號

`api/services/work_order_service.py:1551-1576`（完工硬閘）

```python
    # 技師正規完工 — 三道硬閘
    min_photos = int(policy.get("min_photos", 3))
    n_photos = len(photo_evidence_ids or [])
    if n_photos < min_photos:
        raise ApiError(
            "INSUFFICIENT_PHOTOS",
            f"完工照片至少 {min_photos} 張（目前 {n_photos} 張）",
            422,
        )
    if policy.get("require_signature", True):
        if not signature_evidence_id or not await _signature_exists(wo_id):
            raise ApiError("SIGNATURE_REQUIRED", "完工需客戶簽名（簽名紀錄不存在）", 422)
    serial_cats = policy.get("serial_required_categories") or []
```

該閘門是「完工」的閘，不是 scope change 的閘；且只數張數，不分 before/after 是否成對。

媒體用途白名單（`api/services/media_service.py:31-41`）：

```python
_ALLOWED_PURPOSES = {
    "door_check_before",
    "door_check_after",
    "completion_before",
    "completion_during",   # CR-0054：施工中拓孔結構照（PDF §四 施工前/中/後三類）
    "completion_after",
    "completion_signature",  # 技師完工客戶簽名（前端 my-orders/[id] 簽名上傳用）
    "dispute_evidence_customer",
    "dispute_evidence_technician",
    "other",
}
```

九個用途皆為影像／簽名類。可接受的 content type 亦限於影像：`api/services/media_service.py:43-46` 記載 CR-0194 移除 HEIC 並加 magic bytes 驗證，**找不到**影音（video/audio）類別或用途。

TC 指名之「三件套（影音+文字+before/after 照）」在程式碼中的字面與語意對應搜尋結果：

```
$ grep -rn "三件套" --include=*.py --include=*.ts --include=*.tsx api web agent
（0 筆）
```

僅在文件層有記載（`smartlock-docs/enterprise/04_SRS.md:180`、`:464`、`02_BRD.md:286`、`15_SDS.md:244`）。

此處僅並陳，不裁定。

### 步驟 5 — 執行既有測試

- **動作**：跑分層核可與分級測試
- **預期**：取得執行證據
- **實際**：9 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0150_tiered_approval.py tests/test_cr_0038_bucket4.py \
  -q -p winloop_plugin --tb=line
9 passed
```

`test_cr_0150_tiered_approval.py::test_delta_over_2000_editor_403_supervisor_ok`（`:68-98`）以 v1=3000／v2=5500（delta=2500）驗 403 與主管放行：

```python
        with pytest.raises(ApiError) as ei:
            await qe.transition(tenant_id=TID, quote_id=q2, action="send",
                                actor_role="customer_service")
        assert ei.value.error_code == "REQUOTE_SUPERVISOR_REQUIRED"
        assert ei.value.status_code == 403

        # legacy 呼叫端未帶 actor_role → fail-closed 同 403
```

該檔無任何三件套相關斷言。

---

## 觀測到的其他事實

- `_classify_scope_tier` 的 `major_pct=0.5` 使「原價 1000、加價 600」在金額上屬 standard，但比例上被判 major（`work_order_service.py:2910`）。
- `scope_changes` 提案進入 `approval_inbox_service` 的統一收件匣（`:4`、`:37`），SLA 為 1 天（`:67`），severity 固定 `medium`，不因 tier 提升。
- 完工硬閘的 `min_photos` 預設 3，門檻讀 M18 config `completion_policy`（`work_order_service.py:1536-1539`），非 TC 所述的 before/after 成對規則。
- `quote_engine_service.py:547-556` 另有一道「總額超過 `discount_policy.approval_threshold` 不可從 draft 直送」的 409 `APPROVAL_REQUIRED`，判定對象是報價總額而非價差。
