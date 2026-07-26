# CR-0184 — audit hash-chain re-baseline checkpoint + verify 增強（修 UAT-0723-F3）

- **日期**：2026-07-26
- **來源**：UAT-0723-F3（稽核 hash chain 斷裂，`audit/verify` 回 valid:false）；業主 0726 裁決「選 1：checkpoint 再基準＋verify 增強」
- **分支**：`feat/cr-0184-audit-chain-checkpoint`（L2；audit 合規 NFR-Aud-001 + DB schema + API contract）
- **狀態**：實作完成，待部署＋建 prod checkpoint

## §1 根因（0726 調查 prod audit_events 143 列）

`verify` 回 valid:false 的根因＝**CR-0166 R1-5 advisory lock 部署前（~2026-07-12）的並發競態造成 5 個歷史鏈分叉**：兩三筆 audit 同時讀到同一 prev_hash 各自 append（斷點 e425b8e9 與前列 prev_hash＝753770e6、entry_hash＝a4b35c99 皆相同）。分叉集中在 07-06（1）與 07-12 03:43（4，含一三叉），**之後到今天零分叉**（lock 已修好寫入路徑）。**非 seed 污染、非現行 code 缺陷、非竄改**（每列 entry_hash 各自重算皆符，僅線性鏈接分叉）；驗證器本身正常。

歷史分叉無法「解叉」（改 entry_hash 即破壞既有防竄改證據），故採非破壞式 re-baseline。

## §2 設計（業主選 1）

1. **migration 116**：`audit_chain_checkpoint` 表（baseline_entry_hash/row_id/created_at＋note/created_by）。落品牌庫（audit_events 所在）。
2. **service**（`audit_log_service.py`）：
   - `create_chain_checkpoint`：在鏈 advisory lock 內快照鏈末（最新 entry_hash）為新基準。
   - `get_latest_checkpoint`。
   - `verify_audit_chain(use_checkpoint=True)` 增強：有 checkpoint 時只驗基準列「之後」（`(created_at,id) > baseline`，expected_prev 從 baseline_entry_hash 起）；遇斷後 **resync**（以該列 entry_hash 續驗）以回報**所有**斷點 `breaks[]`；`broken_at` 保留第一個（向下相容）。回 `{checked, valid, broken_at, breaks, checkpoint}`。
3. **router**（`audit_v2.py`）：verify 加 `use_checkpoint` query；新增 `POST /tenants/{tid}/audit/checkpoint`（admin-only）建 re-baseline。
4. **re-baseline 操作**：prod 呼叫 POST checkpoint（基準＝目前鏈末）＝在歷史下畫乾淨線，往後保證可驗證。歷史保留不刪。

## §3 驗證

- **拋棄式 PG16 整合測試**（真 service 函式）：全鏈 verify 偵測分叉✓／checkpoint 後 valid✓／基準後乾淨列 valid✓／基準後分叉列偵測✓。
- **pytest**：`test_cr_0184_audit_checkpoint.py` 3 案（隔離自清，2099 時戳不擾真實鏈）；既有 `test_cr_0068`/`test_cr_0164` shape 斷言更新為新超集；audit 測試 9 pass。
- migration 116 冪等（二套驗證）＋drift-check ✓；app import OK（518 路由）。

## §8 Human Decisions Required

（無阻斷項；業主已定選 1。checkpoint 基準取「目前鏈末」＝在全部歷史下畫線；若日後想證明 07-12 後的乾淨尾段，可另建以較早雜湊為基準的 checkpoint——機制已支援。）

## §9 Implementation Order

1. ✅ migration 116＋service（checkpoint CRUD＋verify 增強）＋router（use_checkpoint＋POST checkpoint）。
2. ✅ 測試（整合＋pytest＋既有 shape 更新）。
3. ⏳ 部署 smart-lock-api → 建 prod checkpoint（POST）→ verify(use_checkpoint) 應 valid:true。
4. ⏳ Plane F3 收 Done。
