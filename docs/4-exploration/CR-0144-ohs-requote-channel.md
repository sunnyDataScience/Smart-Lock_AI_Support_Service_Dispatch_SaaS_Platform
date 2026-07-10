# CR-0144 — OHS requote command 通道(WBS 2.4.3)

- **日期**:2026-07-10
- **狀態**:實作中
- **觸發面向**:API contract(新端點 /internal/requote-requests)、Domain(quote v+1 串鏈)
- **依據**:ADR-027(技師只提交 diff 不定價/品牌報價引擎唯一權威)、16_API_Spec.yaml:391-417(規格已定 🔜)、FR-TEC-07、TC-DISPATCH-07(P0)、CR-0128(報價先行可複用鏈)

## §1 稽核缺口(2026-07-10 查實)→ 本輪範圍

| 缺口 | 本輪 |
|---|---|
| POST /internal/requote-requests 未實作 | ✅ 實作(require_internal_token;spec 對齊 16_API:391) |
| request_id 冪等回放/409 進行中 | ✅ `requote_requests` 表(migration 097):UNIQUE(tenant_id, request_id) 回放;同 WO 有 open 修正 → 409 |
| quote v+1 串鏈(supersedes_quote_id 欄存在但零讀寫) | ✅ 建 v+1 quote(draft)寫 supersedes_quote_id + version+1 |
| 技師零定價權 | ✅ item_diffs 不含金額;金額由小編於品牌後台報價編輯流補(既有 CR-0128 鏈) |
| 降級 initiated_via=cs_fallback | ✅ body 選填 `initiated_via`(technician_command/cs_fallback),audit payload 記錄 |
| 驗證:technician_id=assignee + 工單狀態 | ✅ assignee_ref 比對 403;狀態 ∈ {in_progress, on_site(若存在)} 403 否則 |
| 分層核可(501-2000 小編/>2000 主管) | ⚠ 金額由後續定價才知——v+1 quote 進既有 quote 審核流(threshold 既有 config);分層細化記遺留(金額未定時無從分層) |
| tenant 路由表(技師平台→各品牌 api) | 部署面:同 stack 內 tech 側經 LOCK_API_BASE_URL 直呼;多品牌路由表隨 AI-2/AI-3(ADR-016 完整形態,業主裁決) |
| tech-portal requote UI | 最小版:my-orders 詳情加「回報加項(不含價)」;既有 scope-change 自填單價頁與 ADR-027 相悖 → 記遺留待業主裁決退場 |

## §9 實作順序

1. migration 097 `requote_requests`(tenant_id/request_id/work_order_id/technician_id/reason/item_diffs/initiated_via/status/created_quote_id;UNIQUE(tenant_id,request_id)) → 2. `services/requote_service.py`(驗證+冪等+v+1 quote 建立+audit) → 3. router internal 端點 → 4. 測試(TC-DISPATCH-07:冪等回放/409/403 非 assignee/狀態不符/v+1 串鏈) → 5. tech-portal 最小 UI → 6. 治理 → merge

### 進度

- ✅ 通道 done(2026-07-10,branch `feat/ohs-requote-channel`):migration 097+REGISTRY;requote_service(assignee/狀態 403、request_id 冪等回放 200、同單 open 409、v+1 supersedes 串鏈——欄位首次真正寫入、cs_fallback 降級標記、audit);/internal/requote-requests(require_internal_token,對齊 16_API:391);測試 4/4(TC-DISPATCH-07 核心)。types 重生
- ✅ UI 入口 done(同輪續):browser 端點 `/tenants/{tid}/work-orders/{woId}/requote-requests`(TECH_ACTION 白名單;technician=本人發起、後台角色=cs_fallback 降級代發起);**scope-change 舊頁原地改造**為 requote 表單(移除自填單價——ADR-027 tier-1 正典直接落地,退場議題就地解決);測試 5/5;types 重生;tech/brand tsc 0
- 遺留:多品牌 tenant 路由表隨 AI-2/AI-3(ADR-016 完整形態,業主 0703 裁決)
