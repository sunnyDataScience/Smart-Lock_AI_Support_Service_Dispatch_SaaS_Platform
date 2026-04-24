# Page-Level Prompt: 管理員端 — 派工人工介入面板

> IA 編號 **A37**。當派工引擎自動派工失敗（連續 3 次技師拒單、熔斷、無候選）或管理員主動介入時啟用的手動派工介面。

---

## [PAGE META]

- **page_name**: 派工人工介入 Dispatch Manual Intervention
- **route_path**: `/admin/dispatch-manual` 或 `/admin/dispatch-manual?work_order_id=...`
- **page_type**: action-focused workspace
- **ia_pages**: A37
- **openapi_ops**: listDispatchCandidates, assignWorkOrder, escalateWorkOrder, getWorkOrder
- **asyncapi_ops**: subscribeDispatchQueue, subscribeWorkOrderUpdates
- **primary_goal**: 讓 dispatch_officer 在自動派工失敗情境下，快速人工指派最適技師
- **secondary_goal**: 保留完整決策紀錄（選擇理由、候選排序、審批鏈）供稽核
- **target_users**:
  - 主要：`dispatch_officer`、`operations_manager`
  - 次要：`tenant_admin`（升級情境接手）
- **entry_point**:
  - A28 派工佇列監控點「人工介入」按鈕
  - Flow 2 逾時重派告警 → Dashboard Banner 連結
  - Flow 14 排班衝突 → 直接帶 `work_order_id` 進入
- **expected_time_on_page**: 1–3 分鐘（平均單次介入）

---

## [STRUCTURE: SECTIONS]

1. **context_panel**
   - section_type: summary_panel
   - section_purpose: 顯示需介入工單的關鍵摘要（狀態、客戶、地點、過往派工嘗試）

2. **candidate_list**
   - section_type: ranked_table
   - section_purpose: 展示候選技師，可依「綜合分」「距離」「可用性」「歷史完成率」排序

3. **filter_sidebar**
   - section_type: filter_panel
   - section_purpose: 篩選候選（技能、服務區、技師分級、可用時段）

4. **candidate_detail_drawer**
   - section_type: side_drawer
   - section_purpose: 點技師列展開詳情（排班、近 30 日表現、熔斷狀態）

5. **assign_action_panel**
   - section_type: sticky_action
   - section_purpose: 底部固定操作列：指派 / 改期 / 升級主管 / 取消工單

6. **decision_reason_modal**
   - section_type: modal
   - section_purpose: 指派前強制填寫理由（稽核）

7. **audit_trail**
   - section_type: collapsible_section
   - section_purpose: 本工單派工嘗試歷史（含原自動派工記錄）

---

## [SECTION COMPONENT SPEC]

### Section: context_panel

- **layout**: 頂部卡片，寬度 100%、高度 120px，背景 surface.subtle
- **elements**:
  - wo_number: Heading H3 / required / 工單編號
  - status_badge: Badge / required / 當前工單狀態（`assigning` / `reassign_required`）
  - customer_info: Caption / required / 客戶姓名（去識別化）+ 電話（遮蔽末四碼）
  - address: Body / required / 地址 + Map pin 開啟 Google Map
  - urgency_badge: Badge / required / 緊急度（含 SLA 倒數計時）
  - attempt_count: Chip / required / 「已嘗試 N 次派工」
  - trigger_reason: Alert / required / 「為何進入手動模式」—（自動顯示觸發原因）
- **states**:
  - urgent: 緊急工單背景 #FEF2F2（淡紅），SLA 倒數倒計 < 15min 時紅色閃爍
  - normal: 預設白底

### Section: candidate_list

- **layout**: 表格式清單，每列高度 72px，支援虛擬滾動
- **columns**:
  - checkbox: 可複選（批量推播詢問意願）
  - avatar + name: 技師姓名 + 在線狀態 dot（綠=online, 灰=offline, 紅=busy）
  - level_badge: 技師分級（S/A/B/C）
  - distance: 距離 + 預估到場時間
  - rating: 評分（5 星 + 近 30 日完成率 %）
  - skills_match: 技能匹配度（0-100%）
  - availability: 可用性「立即」「30 分後」「X 小時」
  - circuit_status: 熔斷狀態（若有，顯示紅 Badge）
  - action: 「指派」按鈕（主要色；熔斷中 → disabled）
- **states**:
  - empty: 「無符合條件的技師」+ 調整篩選提示 + 「升級至主管」CTA
  - loading: Skeleton rows × 5
  - filtered: 顯示符合篩選的技師數（`共 12 位 / 總 45 位可用`）
- **sort**:
  - 預設：綜合分數 desc（= 0.4 × 匹配度 + 0.3 × 距離權重 + 0.3 × 評分）
  - 可切：距離 asc / 評分 desc / 可用時間 asc
- **copy_constraints**: 技師姓名全顯，若重名附後 4 碼 id

### Section: filter_sidebar

- **layout**: 左側固定 240px，手機折疊為 drawer
- **elements**:
  - skill_checkbox: 鎖品牌複選（LOCKLY / Yale / August / 其他）
  - area_select: 服務區下拉（預設本工單區）
  - level_filter: 技師分級 S/A/B/C 複選
  - availability_filter: 即時 / 30 分內 / 1 小時內 / 自選時段
  - exclude_circuit: 開關「排除熔斷中技師」（預設 on）
  - rating_min: 最低評分 slider（0-5）
- **states**:
  - default / applied：applied 時頂部顯示「已套用 N 個篩選」+ 清除全部 btn

### Section: candidate_detail_drawer

- **layout**: 右側 drawer 寬度 400px，點 row 展開
- **elements**:
  - profile_header: 姓名 + 照片 + level
  - current_schedule: 時間軸（當天未來 24h 排班熱力圖）
  - performance_snapshot: 30 日完成率、平均評分、客訴數、熔斷歷史
  - skill_matrix: 已認證技能清單（對齊 A26 技師技能認證）
  - recent_feedback: 最近 5 則客戶評語（去識別化）
  - deep_link_to_a14: 按「查看完整技師檔案」→ A14 技師詳情

### Section: assign_action_panel

- **layout**: 底部 sticky，高度 72px，陰影 shadow-top
- **elements**:
  - primary_assign_btn: Button Primary / required / 「指派給 [技師名]」（選中技師後啟用）
  - alt_reschedule_btn: Button Secondary / 「改期 + 通知客戶」→ 開 T11 改期日曆
  - alt_escalate_btn: Button Warning / 「升級至 operations_manager」
  - alt_cancel_btn: Button Danger / 「取消工單（全退）」
- **states**:
  - no_selection: 主按鈕 disabled + 顯示「請先選擇技師」
  - escalated: 顯示「已升級，等候主管處理」+ 禁所有 action

### Section: decision_reason_modal

- **layout**: 中央 modal，寬 480px
- **elements**:
  - reason_select: 單選（下拉）— 預設理由：
    - auto_dispatch_exhausted（自動派工已窮盡）
    - customer_requested_specific_tech（客戶指名）
    - skill_shortage_override（技能不足但特殊情境覆蓋）
    - sla_rescue（SLA 即將違反強制指派）
    - other（手填）
  - reason_text: Textarea / required if `other` / 10-500 字
  - dual_sign_required: 自動偵測 → 若指派破格（熔斷技師、跨區）→ 強制 operations_manager 雙簽
  - confirm_btn: Primary / 「確認指派」
- **states**:
  - dual_sign_pending: 提交後等待第二簽核人（倒數 + WS notify）

### Section: audit_trail

- **layout**: 底部可折疊區，預設收合，展開後 Timeline
- **elements**:
  - timeline_item: 每筆派工嘗試（技師、時間、結果：accepted/declined/timeout）
  - manual_intervention_item: 本次介入記錄（操作人、理由、決策）
  - correlation_ids: 對應的 audit_events 連結（可 deep link 到 A20）

---

## [INTERACTION & STATE FLOW]

### 進入流程

| 來源 | 帶入參數 | 初始狀態 |
|:---|:---|:---|
| A28 派工佇列點「人工介入」 | `work_order_id` | context_panel 載入、候選自動計算 |
| Dashboard Banner（Flow 2 告警） | `work_order_id`, `from=alert` | 同上 + 顯示告警背景 |
| Flow 14 排班衝突 | `work_order_id`, `trigger=conflict` | 候選預濾「可用時段」 |
| 直接進入（無 id） | — | 顯示待介入工單佇列（列表模式） |

### 核心互動

1. 載入 context_panel + 候選候選列 + audit_trail
2. 使用者可調整 filter_sidebar → 候選即時重新排序
3. 點 row → 右側 drawer 展開詳情（不阻塞背景列表）
4. 選擇候選（checkbox 單選 / 複選批量）→ 底部 CTA 啟用
5. 點「指派給 X」→ decision_reason_modal 開啟
6. 填理由 → 偵測是否需雙簽 → 提交
7. 提交成功 → Toast「已指派」+ 返回 A28 並 highlight 此工單
8. 若雙簽 → 提交後顯示 pending 狀態，WS 等待第二簽核

### 例外互動

- 熔斷中技師點擊 → Toast 說明熔斷原因 + 解除時間
- 跨區指派 → 強制顯示警告：「距離 X km，車馬費差額 Y」
- 批量詢問意願（複選 3+ 技師）→ 推播 LINE Flex「想接這單嗎」→ 最快接受者勝出
- 升級主管後此頁變成唯讀（operations_manager 看到接手連結）

### Dirty State

| 情境 | 處置 |
|:---|:---|
| 填到一半切換 work_order_id | 不保留，重新載入 |
| decision_reason_modal 填到一半關閉 | sessionStorage 保留 5 分鐘（同工單再開還原） |
| 篩選條件 | URL query string（可書籤） |

### 錯誤狀態

| 情境 | 行為 |
|:---|:---|
| 工單已被其他人指派（WS 事件）| Toast + 自動返回 A28 |
| 候選查詢失敗 | 空狀態 + 重試 CTA |
| 雙簽逾時（> 30 分）| 自動取消、釋放工單回自動派工 |

---

## [DATA & API]

### 查詢候選

```
GET /api/v1/dispatch/candidates?work_order_id={id}&filters=...
  → {
      candidates: [
        { tech_id, name, score, distance_km, rating, skill_match,
          availability, circuit_status, level, online },
        ...
      ],
      total: 45,
      auto_dispatch_attempts: [...]  // 歷史嘗試
    }
```

### 指派

```
POST /api/v1/work-orders/{id}/assign
Headers:
  Idempotency-Key: <uuid>
  X-Cross-Tenant-Reason: (若跨租戶)
Body: {
  technician_id: uuid,
  reason_code: enum,
  reason_text: string,
  override_flags: { allow_circuit, allow_cross_area }
}
Response 200: WorkOrderEnvelope (status updated to assigned)
Response 409: WORK_ORDER_CONFLICT (已被他人接)
Response 423: TECHNICIAN_CIRCUIT_BREAKER_OPEN (需 override + 雙簽)
Response 409: REFUND_DUAL_SIGN_REQUIRED (需第二簽核)
```

### 升級

```
POST /api/v1/work-orders/{id}/escalate
Body: { level: operations_manager | tenant_admin, reason }
```

### WebSocket 訂閱

- `/realtime/dispatch-queue` — 他人操作此工單時即時同步
- `/realtime/work-orders/{id}` — 工單狀態變化

---

## [EXCEPTION TO GLOBAL RULES]

- 指派操作強制 `Idempotency-Key`（防雙擊）
- 若覆寫熔斷（override_flags.allow_circuit=true）→ 強制 `operations_manager` 雙簽
- 本頁所有動作**無論成功失敗**皆產出 `audit_event`（category=dispatch.manual）
- 跨租戶指派需帶 `X-Cross-Tenant-Reason` header（僅 super_admin 可用，一般隔離）

---

## [ACCEPTANCE CRITERIA]

- [ ] 進入後 < 2 秒載入 context + top 20 候選
- [ ] 篩選後候選列表即時更新 < 500ms
- [ ] 指派成功後 A28 佇列監控同步移除此工單
- [ ] 熔斷技師無法被指派（除 override + 雙簽）
- [ ] 雙簽超時自動釋放工單
- [ ] 所有指派皆產出可追溯 audit_event
- [ ] 深連結 `?work_order_id=xxx` 可直達並正確載入
- [ ] 跨 tab 操作同一工單時 WS 同步、衝突 Toast 提示
- [ ] 行動裝置（iPad Pro 12.9）可用 — filter_sidebar 折疊為 drawer

---

## 導航與狀態 (Navigation & State)

對齊 `docs/02-design/E5x--frontend-navigation-matrix.md §1.3`：

- **Upstream**: A28 派工佇列、Dashboard Flow 2 Alert、Flow 14 衝突解決
- **Downstream**: A12 工單詳情（指派完成返回）、T11 改期日曆、A14 技師詳情（drawer 連結）
- **State Persistence**: filter via URL query、reason_modal via sessionStorage（5 分鐘窗）
- **Error Navigation**: 409 自動返回 A28、403 只讀降級、deeplink 404 回 A28
- **Deep Link**: supported
- **Multi-tab Sync**: WS + BroadcastChannel

---

## 校對檢核表

- [ ] 綜合分數公式 0.4/0.3/0.3 權重是否合理？
- [ ] 批量詢問意願「最快接受者勝出」是否會造成技師間不公？
- [ ] 升級主管後「30 分鐘雙簽逾時自動釋放」是否合理？
- [ ] 跨區車馬費差額顯示是否需預覽具體金額？
- [ ] 熔斷覆寫（override_flags）是否應限 tenant_admin？
