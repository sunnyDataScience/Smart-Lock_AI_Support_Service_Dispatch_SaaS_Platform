# Page-Level Prompt: 派工佇列監控 + 報表群（4 個子頁面）

> 對應 `guides/vibe_coding_build_strategy.md` → Step 5。
> 涵蓋 V2.0 營運管理核心：A28 派工佇列即時監控（拒單重派、人工介入）+ A29~A31 三大報表（KPI 儀表板、技師排行榜、營收報表），支撐平台數據化營運決策。
> 對齊 `E5x--frontend-information-arch.md` §6.23–6.24、`E5x--dispatch-operations-supplement.md` §4 & §7、`specs/sla-availability-spec.md`。

---

## [PAGE META]

- **page_name**: 派工佇列監控 + 報表群 (Dispatch Queue & Reports)
- **route_path**: `/admin/dispatch-queue` | `/admin/reports/kpi` | `/admin/reports/technician-ranking` | `/admin/reports/revenue`
- **page_type**: realtime_monitor + dashboard + analytics（即時監控 + 多維度報表分析）
- **primary_goal**: 提供即時派工決策介入介面與多維度營運分析報表，讓管理員能：(1) 即時介入困難派工；(2) 追蹤轉換漏斗、SLA、滿意度、爭議率、FTFR；(3) 管理技師績效；(4) 分析營收結構
- **secondary_goal**: 支援 CSV/Excel/PDF 匯出與排程週報、月報推送；拒單原因統計為月度優化決策提供數據依據
- **target_users**:
  - 主要：平台營運主管（A28 即時介入）、品牌管理者（A29~A31 策略決策）
  - 次要：財務主管（A31 營收分析）、人資主管（A30 技師績效管理）
- **entry_point**:
  - A28：側邊導航「派工佇列」Badge + A1 Dashboard「卡關工單」卡片點擊
  - A29~A31：側邊導航「報表」子選單 / A1 Dashboard「查看完整報表」連結
- **expected_time_on_page**:
  - A28 即時監控：長時停留 10-60 分鐘（營運高峰時段常駐）
  - A29 KPI：3-10 分鐘（每日/每週檢視）
  - A30 技師排行：5-15 分鐘（含下鑽查看個人績效）
  - A31 營收：5-20 分鐘（含資料匯出與切片分析）

---

## [STRUCTURE: SECTIONS]

### 共用結構

1. **page_shell**
   - section_type: layout_shell
   - section_purpose: 統一的頁面標題列 + 麵包屑 + 時間粒度切換（A29~A31）

### 子頁面 1 — 派工佇列監控 `/admin/dispatch-queue`

2. **dispatch_stat_header**
   - section_type: stats_cards
   - section_purpose: 4 張即時狀態卡片（卡關 / 第 2 次派工 / 第 3 次派工 / 逾時）

3. **dispatch_queue_table**
   - section_type: expandable_data_table
   - section_purpose: 可展開的派工嘗試列表，展開後顯示 1~3 次 DispatchAttemptTimeline

4. **manual_intervention_panel**
   - section_type: modal_dialog
   - section_purpose: 管理員人工介入操作（指派 / 放寬條件 / 加價 / 取消）

### 子頁面 2 — KPI 儀表板 `/admin/reports/kpi`

5. **kpi_toolbar**
   - section_type: filter_bar
   - section_purpose: 時間粒度切換（日/週/月/季）+ 技師/品牌切片 + 匯出

6. **kpi_funnel_section**
   - section_type: chart_block
   - section_purpose: 轉換漏斗（對話 → 問題卡 → 工單 → 派出 → 完工 → 滿意）

7. **kpi_sla_section**
   - section_type: chart_block
   - section_purpose: SLA 達成率（接單/到場/完工/回覆）依技師/品牌切片

8. **kpi_satisfaction_section**
   - section_type: chart_block
   - section_purpose: 滿意度（平均星等 / NPS / 差評率）

9. **kpi_dispute_section**
   - section_type: chart_block
   - section_purpose: 爭議率（退款率 / 保固索賠率 / 爭議升級率）

10. **kpi_efficiency_section**
    - section_type: chart_block
    - section_purpose: 技師效率（平均處理時長 / 一次修好率 FTFR）

### 子頁面 3 — 技師排行榜 `/admin/reports/technician-ranking`

11. **ranking_toolbar**
    - section_type: filter_bar
    - section_purpose: 週期選擇 + 多維排序（完工率 / 評分 / 週轉時間）

12. **ranking_table**
    - section_type: sortable_table
    - section_purpose: 技師績效排行，支援下鑽至個人績效頁

### 子頁面 4 — 營收報表 `/admin/reports/revenue`

13. **revenue_toolbar**
    - section_type: filter_bar
    - section_purpose: 時間粒度（日/週/月/季）+ 切片（技師 / 品牌 / 工項）+ 匯出

14. **revenue_line_chart**
    - section_type: chart_block
    - section_purpose: 營收趨勢折線圖（可疊加多條切片線）

15. **revenue_pivot_table**
    - section_type: pivot_table
    - section_purpose: 樞紐表（列 = 時間，欄 = 切片維度，值 = 營收 / 筆數）

16. **export_scheduler_modal**
    - section_type: modal_dialog
    - section_purpose: 匯出設定與排程定期發送（對齊 data-export-spec.md）

---

## [SECTION COMPONENT SPEC]

### Section: page_shell（所有四頁共用）

- **layout**: 頂部 page_header（固定 72px）+ 下方 main_content 區（`flex-1 p-6 bg-[#F8FAFC]`）
- **elements**:
  - breadcrumb: Breadcrumb / required / A28: 「首頁 > 派工佇列」/ A29: 「首頁 > 報表 > KPI 儀表板」/ A30: 「首頁 > 報表 > 技師排行」/ A31: 「首頁 > 報表 > 營收」
  - page_title: H1 / required / `text-2xl font-semibold text-[#1E293B]`
    - A28：「派工佇列監控」
    - A29：「KPI 儀表板」
    - A30：「技師排行榜」
    - A31：「營收報表」
  - realtime_indicator: Badge / required（僅 A28）/ `bg-green-100 text-green-700` 綠點 + 「即時連線中」/ WebSocket 斷線時變為 `bg-red-100 text-red-700` + 「連線中斷，重連中...」
  - last_updated: Text Caption / required / `text-sm text-gray-500` / A28 顯示「最後更新：{HH:mm:ss}」每秒更新；A29~A31 顯示「資料截至 {YYYY-MM-DD HH:mm}（延遲 < 5 分鐘）」
  - refresh_button: IconButton Ghost / optional / icon: RefreshCw / 手動重新整理
- **states**:
  - default: 正常顯示標題與副資訊
  - reconnecting: A28 的 realtime_indicator 顯示琥珀色 + pulse 動畫
  - stale_data: A29~A31 資料超過 10 分鐘未更新時，last_updated 變為 `text-amber-600` + 警告 icon
- **copy_constraints**: 頁面標題固定不可修改

---

### 子頁面 1: 派工佇列監控 `/admin/dispatch-queue`

### Section: dispatch_stat_header

- **layout**: 4 欄等寬網格（Desktop 12-col grid 每張 3-col），間距 16px，margin-bottom 24px
- **elements**:
  - stuck_card: KPICard / required / 標題「卡關工單」/ 數值 `text-3xl font-bold` / 副標「需立即介入」/ 左側 4px border `border-red-500` / 背景 `bg-white` / icon: AlertOctagon（紅色）/ 點擊跳轉至下方表格並預篩 `attempt_num>=3`
  - retry_2_card: KPICard / required / 標題「第 2 次派工」/ 數值 / 副標「已重派一次」/ 左側 4px border `border-amber-500` / icon: RotateCw（琥珀色）/ 點擊預篩 `attempt_num=2`
  - retry_3_card: KPICard / required / 標題「第 3 次派工」/ 數值 / 副標「最後一次嘗試中」/ 左側 4px border `border-orange-500` / icon: AlertTriangle / 點擊預篩 `attempt_num=3`
  - timeout_card: KPICard / required / 標題「逾時未接」/ 數值 / 副標「15 分鐘未回應」/ 左側 4px border `border-red-600` / icon: Clock（紅色）/ 數值 > 0 時 pulse 動畫 / 點擊預篩 `latest_response=timeout`
- **states**:
  - default: 4 張卡片白色背景 + 對應色邊框
  - hover: `shadow-md translateY(-2px)` + `cursor-pointer`
  - loading: 每張卡片 Skeleton（標題 + 數值 + 副標）
  - realtime_bump: WebSocket 推送新事件導致數值變動時，數值短暫放大 1.1x + 背景閃爍 `bg-blue-50` 500ms
  - critical: 卡關工單數值 >= 5 時整張卡片背景變為 `bg-red-50` + 左邊框加粗至 6px
- **copy_constraints**: 標題固定 4-6 字

---

### Section: dispatch_queue_table

- **layout**: 全寬 DataTable，卡片容器（白色背景 `radius.lg` 8px `shadow-sm`），每列可展開
- **elements**:
  - table_toolbar: FilterBar / required / `flex gap-3 mb-4`
    - search_input: SearchInput / required / placeholder「搜尋工單編號、客戶、地址...」/ debounce 300ms
    - attempt_filter: Select / required / 全部 / 第 1 次 / 第 2 次 / 第 3 次
    - response_filter: Select / optional / 全部 / 待回應 / 已拒絕 / 已逾時
    - brand_filter: Select / optional / 品牌篩選
    - urgent_only_toggle: Switch / optional / 「僅顯示需介入」(`attempt_num>=3 || is_urgent`)
  - table_header: TableHeader / required / 欄位如下（固定表頭）：
    - col_expand: ExpandIcon / 寬 40px / 箭頭按鈕
    - col_wo_number: Text Code / 寬 160px / 工單編號 / `font-mono text-[#2563EB]` / 可點擊跳轉詳情
    - col_attempt_num: AttemptBadge / 寬 90px / 「第 {n} 次」
      - n=1：`bg-blue-100 text-blue-700`
      - n=2：`bg-amber-100 text-amber-700`
      - n=3：`bg-red-100 text-red-700` + 背景脈動 1.5s
    - col_candidate: AvatarText / 寬 160px / 當前推送的技師 Avatar + 姓名
    - col_match_score: MatchScoreBar / 寬 140px / 媒合分數進度條（0-100）
      - >=80：綠色填充 `bg-emerald-500` + 數字綠字
      - 60-79：藍色填充 `bg-blue-500`
      - 40-59：琥珀填充 `bg-amber-500`
      - <40：紅色填充 `bg-red-500` + Tooltip「信心不足，建議放寬條件」
    - col_rejection_reason: Text / 寬 auto / 拒單原因（最新一筆）/ 超長 truncate + Tooltip / 逾時顯示灰字「逾時未回應」
    - col_remaining_time: CountdownTimer / 寬 120px / 當前 attempt 剩餘時間
      - >5 分鐘：`text-gray-600`
      - 1-5 分鐘：`text-amber-600 font-medium`
      - <1 分鐘：`text-red-600 font-bold animate-pulse`
      - 已逾時：`text-red-600 font-bold` + 「已逾時 {n}min」
    - col_created_at: Text / 寬 140px / 工單建立時間 `YYYY-MM-DD HH:mm`
    - col_actions: ActionButtons / 寬 100px /
      - 「介入」Button Primary Small / 僅 `attempt_num>=3 || is_stuck` 時啟用 / 開啟 manual_intervention_panel
      - 三點選單：「手動指派」「放寬匹配」「加價」「取消工單」
  - expanded_row: DispatchAttemptTimeline / required / 點擊展開按鈕後顯示
    - **layout**: 水平時間軸，3 個節點並排（第 1、2、3 次嘗試），`flex items-start gap-4 p-6 bg-gray-50 rounded-lg mx-4 mb-4`
    - attempt_node: TimelineNode[] / required / 每個節點：
      - 圓形節點 indicator（48px）：
        - 已接受（accepted）：`bg-emerald-500 text-white` + 勾號 icon
        - 已拒絕（rejected）：`bg-red-500 text-white` + X icon
        - 已逾時（timeout）：`bg-gray-400 text-white` + 時鐘 icon
        - 進行中（pending）：`bg-blue-500 text-white animate-pulse` + Loader icon
        - 未啟動（not_started）：`bg-gray-200 text-gray-400` + 數字 icon
      - 節點下方資訊卡片：
        - attempt_label: Text / `font-semibold` / 「第 {n} 次派工」
        - technician_info: Avatar (32px) + 姓名 + 技師 ID
        - match_score_mini: Text / 「媒合分數 {score}/100」/ 依分數色碼
        - distance: Text Caption / 「距離 {km} km」
        - pushed_at: Text Caption / 「推送：{HH:mm:ss}」
        - responded_at: Text Caption / 「回應：{HH:mm:ss}」或 「尚未回應」
        - duration: Text Caption / 「耗時：{n} 分 {s} 秒」
        - rejection_reason: TextBlock / 僅 rejected 時顯示 / `bg-red-50 border-l-2 border-red-400 pl-2 py-1 text-sm text-red-700 italic` / 「拒絕原因：{reason}」
    - connector_line: Line / required / 節點間連接線 `border-t-2 border-dashed border-gray-300`
- **states**:
  - default: 依工單建立時間降序 + `attempt_num` 降序
  - hover: 整列 `bg-blue-50`（第 3 次列 hover `bg-red-50`）
  - selected: 列被展開時 `bg-blue-50 border-l-4 border-[#2563EB]`
  - loading: 8 列 Skeleton rows
  - empty: "目前無待介入派工" + icon: CheckCircle
  - error: ErrorState + 重試按鈕
  - realtime_new: WebSocket 推送新 attempt 時，該列從頂部滑入 + 背景閃爍 `bg-yellow-50` 2 秒
  - realtime_updated: 既有列 match_score 或 response 變更時，該欄位短暫 `bg-yellow-100` 500ms 閃爍
  - admin_notified: `attempt_num=3 && all_failed` 時整列 `bg-red-50 border-l-4 border-red-500` + 通知 Toast「工單 {wo_number} 3 次派工全部失敗，請立即介入」
- **copy_constraints**: 拒單原因在表格列截斷至 30 字，展開詳情無限制（最多 500 字）

---

### Section: manual_intervention_panel

- **layout**: Modal lg（max-width 720px），垂直分區
- **trigger**: 點擊列表「介入」按鈕 / 三點選單任一操作 / 卡關卡片點擊後從 Top 5 卡關工單選擇
- **elements**:
  - modal_header: H3 / 「人工介入 — {wo_number}」
  - work_order_summary: SummaryCard / required / `bg-[#F8FAFC] p-4 rounded-lg`
    - 客戶：{customer_name} + 電話
    - 地址：{address} + Google Maps 連結
    - 品牌/型號：{brand} {model}
    - 問題摘要：{symptom_summary}（截斷 3 行）
    - 當前狀態：StatusBadge
  - attempt_summary: AttemptTimelineMini / required / 簡化版 DispatchAttemptTimeline（顯示 1~3 次嘗試摘要）
  - intervention_tabs: Tabs / required / 4 個 Tab：
    - **Tab 1 — 手動指派**:
      - search_input: SearchInput / 「搜尋技師姓名 / ID / 技能」
      - technician_list: TechnicianCandidateRow[] / 顯示所有可用技師（不受媒合限制）
        - avatar + 姓名 + 技能 Tag + 距離 + 當前負荷 + 評分
        - 「指派」Button Primary Small
      - override_note: Textarea / optional / 「覆寫派工演算法原因（稽核用）」/ 最少 10 字
    - **Tab 2 — 放寬匹配條件**:
      - checkbox_ignore_distance: Checkbox / 「取消距離限制（原 30km）」
      - checkbox_ignore_skills: Checkbox / 「放寬技能匹配（允許品牌不符）」
      - checkbox_ignore_load: Checkbox / 「忽略負荷上限（允許超載技師）」
      - preview_count: Text / 「放寬後候選人：{n} 位」/ 即時計算
      - retry_btn: Button Primary / 「以新條件重派」
    - **Tab 3 — 加價**:
      - current_price: Text / 「目前報酬：NT$ {amount}」
      - bonus_amount: NumberInput / required / 「加價金額」/ 快捷：+100 / +200 / +500
      - new_price_preview: Text / 「加價後：NT$ {amount + bonus}」
      - reason_input: Textarea / required / 「加價原因（必填）」/ 最少 10 字
      - retry_btn: Button Primary / 「加價並重派」
    - **Tab 4 — 取消工單**:
      - warning_banner: AlertBanner / `bg-red-50 border-red-200 text-red-700` / icon: AlertTriangle / 「取消工單無法復原。若為客戶因素，請確認是否退款。」
      - cancellation_reason: Select / required / 「取消原因」：
        - dispatch_failed（派工失敗）
        - customer_canceled（客戶取消）
        - duplicate_order（重複工單）
        - out_of_service_area（超出服務範圍）
        - other（其他）
      - notes_input: Textarea / required / 「詳細說明」/ 最少 10 字
      - notify_customer: Checkbox / 預設勾選 / 「透過 LINE 通知客戶」
      - confirm_cancel_btn: Button Destructive / 「確認取消工單」
  - modal_footer:
    - cancel_btn: Button Ghost / 「關閉」
- **states**:
  - default: 預設進入 Tab 1 「手動指派」
  - submitting: 對應 Tab 的確認按鈕 Spinner + 「處理中...」
  - success: Modal 關閉 + Toast Success「已完成介入：{action_description}」+ 列表 refetch
  - failure: Toast Error + Modal 保持開啟 + 可重試
  - validation_error: Tab 內行內紅字錯誤訊息
- **copy_constraints**: 覆寫原因 / 取消說明最多 500 字

---

### 子頁面 2: KPI 儀表板 `/admin/reports/kpi`

### Section: kpi_toolbar

- **layout**: 全寬單列，水平排列，`flex flex-wrap gap-3 mb-6 items-center`
- **elements**:
  - granularity_toggle: SegmentedControl / required / 四個選項：日 / 週 / 月 / 季 / 預設「月」/ 選中項 `bg-[#2563EB] text-white`
  - date_range_picker: DateRangePicker / required / 依粒度動態切換：
    - 日：過去 30 天（可自訂）
    - 週：過去 12 週
    - 月：過去 12 個月
    - 季：過去 4 季
  - slice_selector: MultiSelect / optional / 切片維度：
    - 技師（動態載入）
    - 品牌（動態載入）
    - 服務類型（維修/保固/安裝）
  - compare_toggle: Switch / optional / 「與上期比較」/ 啟用後每區塊顯示 MoM / YoY 箭頭
  - export_btn: Button Secondary / icon: FileDown / 「匯出報告」/ 下拉選單：CSV / Excel / PDF
  - schedule_btn: Button Ghost / optional / icon: Calendar / 「排程週/月報」
- **states**:
  - default: 預設粒度「月」+ 過去 12 個月
  - url_synced: 所有參數同步 URL query params
  - loading: 下拉載入中 Spinner
  - exporting: 匯出按鈕 Spinner + 「生成中..」+ 完成後觸發下載

---

### Section: kpi_funnel_section

- **layout**: 全寬區塊，上方標題列 + KPIFunnelChart 元件，`bg-white rounded-xl border border-gray-200 p-6 mb-6`
- **elements**:
  - section_title: H2 / required / 「轉換漏斗」+ 資訊 icon Tooltip「從客戶對話到滿意完工的六階段轉換」
  - funnel_chart: KPIFunnelChart / required / recharts `<FunnelChart>` 六階段漏斗：
    - Stage 1: 對話建立（inquiring_count）/ 深藍 `#1E40AF`
    - Stage 2: ProblemCard 產出（qualified_count）/ 藍 `#2563EB`
    - Stage 3: 工單建立（dispatched_count）/ 淺藍 `#3B82F6`
    - Stage 4: 派出 / 接受（accepted_count）/ 青 `#06B6D4`
    - Stage 5: 完工（completed_count）/ 綠 `#10B981`
    - Stage 6: 滿意（rating>=4 count）/ 深綠 `#047857`
    - 每階段顯示：絕對值 + 轉換率（相對上一階段）
  - conversion_table: TableMini / required / 各階段轉換率橫向對照：
    - 對話 → 問題卡：{rate}% / 與上期 ±{n}pp
    - 問題卡 → 工單：{rate}%
    - 工單 → 派出：{rate}%
    - 派出 → 完工：{rate}%
    - 完工 → 滿意：{rate}%
  - drill_down_btn: Button Ghost / 「查看明細 →」/ 點擊開啟 Drawer 顯示每階段的工單清單
- **states**:
  - default: 漏斗圖 + 轉換率表
  - hover_stage: hover 某階段時該 stage 高亮 + Tooltip 顯示詳細分解
  - loading: 漏斗 Skeleton（六個灰色漸變矩形）
  - empty: 「選定期間無資料」+ 調整日期建議
  - error: ErrorState + 重試按鈕
  - comparison_mode: 啟用 compare_toggle 時，每階段下方顯示箭頭 icon + 變化百分比（上升綠色 / 下降紅色）

---

### Section: kpi_sla_section

- **layout**: 全寬區塊，左 1/2（總覽環形圖）+ 右 1/2（依技師/品牌切片橫條圖），`grid grid-cols-2 gap-6`
- **elements**:
  - section_title: H2 / 「SLA 達成率」+ Tooltip「對齊 specs/sla-availability-spec.md」
  - overview_donut: DonutChartGroup / required / 四個同心環形圖（recharts `<PieChart innerRadius>`）：
    - 接單 SLA（15 分鐘內接單）：達成率 {n}% / 目標 95%
    - 到場 SLA（承諾時段內到場）：達成率 {n}% / 目標 90%
    - 完工 SLA（預估時間內完工）：達成率 {n}% / 目標 85%
    - 回覆 SLA（客戶訊息 30 分內回覆）：達成率 {n}% / 目標 98%
    - 每環顏色依達成率：
      - 達標（>=target）：`fill-emerald-500` + 綠字百分比
      - 接近達標（target-5pp ~ target）：`fill-amber-500`
      - 未達標（<target-5pp）：`fill-red-500` + 紅字百分比 + 警告 icon
  - slice_bar_chart: BarChart / required / recharts `<BarChart layout="vertical">` 依切片維度（技師/品牌）顯示 SLA 達成率：
    - Y 軸：切片項（Top 10）
    - X 軸：達成率 0-100%
    - 目標線：垂直虛線標示 95% / 90% / 85%
    - 顏色：依是否達標 emerald / amber / red
  - alert_banner: AlertBanner / optional / 任一 SLA 未達標時顯示 `bg-red-50 border-red-200` / 「{sla_type} 未達標：{actual}% vs 目標 {target}%」+ 連結至爭議或逾時工單列表
- **states**:
  - default: 四個環形 + 切片長條
  - hover_ring: hover 某環形時該環放大 + Tooltip 顯示分子/分母
  - loading: 環形 Skeleton（四個灰色圓圈）+ 長條 Skeleton
  - below_target: 未達標時整個區塊加紅色邊框 `border-red-300`

---

### Section: kpi_satisfaction_section

- **layout**: 3 欄等寬網格，`grid grid-cols-3 gap-6`
- **elements**:
  - section_title: H2 / 「客戶滿意度」
  - avg_rating_card: LargeKPICard / required /
    - 標題「平均星等」
    - 大數字 `text-5xl font-bold` + 「/ 5.0」
    - 5 星視覺化（填充對應比例，琥珀色 `#F59E0B`）
    - 副標「共 {n} 則評分」
    - trend_arrow：vs 上期 ±{n}
  - nps_card: LargeKPICard / required /
    - 標題「NPS 淨推薦值」
    - 大數字（範圍 -100 ~ +100）
    - 色碼：
      - >=50 綠 `text-emerald-600`（世界級）
      - 0-49 藍 `text-blue-600`（優良）
      - -50-0 琥珀（需改善）
      - <-50 紅（警示）
    - 副標「Promoters {p}% / Passives {ps}% / Detractors {d}%」堆疊條形圖
  - bad_rating_card: LargeKPICard / required /
    - 標題「差評率」
    - 大數字 + 「%」（rating <= 2 的比率）
    - 色碼：<=5% 綠 / 5-10% 琥珀 / >10% 紅
    - 副標「共 {n} 則差評」+ 連結「查看差評明細 →」
  - rating_trend_chart: LineChart / required / 下方全寬趨勢圖 / recharts `<LineChart>` / X 軸時間 / Y 軸評分 / 三條線：平均評分 / NPS / 差評率
- **states**:
  - default: 三張卡片 + 趨勢圖
  - loading: 三張卡片 Skeleton + 圖表 Skeleton
  - drill_bad_ratings: 點擊「查看差評明細」→ Drawer 顯示 rating<=2 的工單清單 + 客戶原文
- **copy_constraints**: 卡片標題固定

---

### Section: kpi_dispute_section

- **layout**: 2 欄等寬網格 + 下方完整趨勢表，`grid grid-cols-2 gap-6`
- **elements**:
  - section_title: H2 / 「爭議與異常率」
  - dispute_rate_card: LargeKPICard / required /
    - 退款率：{rate}% / 目標 <5%
    - 保固索賠率：{rate}%
    - 爭議升級率：{rate}%
    - 每項色碼與進度條
  - rework_rate_card: LargeKPICard / required /
    - 返工率：{rate}% / 目標 <3%
    - 一次修好率 FTFR：{rate}% / 目標 >90%
  - dispute_breakdown_table: DataTable / required / 下方全寬 / 爭議類型分布：
    - 類型（價格 / 品質 / 保固 / 取消費 / 結算）
    - 數量
    - 佔比
    - 平均調解金額
    - 平均處理天數
    - 點擊某類型 → 跳轉 `/admin/disputes?type={type}`
- **states**:
  - default: 兩張卡片 + 分布表
  - critical: 任一率 > 目標時該數值紅字 + 警告 icon

---

### Section: kpi_efficiency_section

- **layout**: 全寬，上方 2 張卡片 + 下方技師效率矩陣
- **elements**:
  - section_title: H2 / 「技師效率」
  - avg_resolution_card: LargeKPICard / required / 「平均處理時長」/ 大數字 + 「小時」/ 分佈直方圖（recharts `<BarChart>`）
  - ftfr_card: LargeKPICard / required / 「一次修好率 (FTFR)」/ 大數字 + 「%」/ 目標 >90%
  - efficiency_matrix: ScatterChart / required / recharts `<ScatterChart>` /
    - X 軸：平均處理時長（小時）
    - Y 軸：FTFR (%)
    - 點 = 技師（點擊跳轉技師詳情）
    - 四象限分類：
      - 右上（高 FTFR + 高時長）：「品質優先型」
      - 左上（高 FTFR + 低時長）：「明星技師」⭐️
      - 右下（低 FTFR + 高時長）：「需培訓」⚠️
      - 左下（低 FTFR + 低時長）：「速度型」
    - 點大小：依工單量
    - 點顏色：依平均評分（5 星綠 → 1 星紅）
- **states**:
  - default: 兩張卡片 + 散佈圖
  - hover_point: 顯示技師姓名 + 核心指標 Tooltip
  - click_point: 跳轉至 `/admin/technicians/{id}/performance`

---

### 子頁面 3: 技師排行榜 `/admin/reports/technician-ranking`

### Section: ranking_toolbar

- **layout**: 全寬單列，水平排列
- **elements**:
  - period_selector: SegmentedControl / required / 本週 / 本月 / 本季 / 本年 / 自訂 / 預設「本月」
  - date_range_picker: DateRangePicker / optional / 選「自訂」時啟用
  - sort_by_selector: Select / required / 排序依據：
    - 綜合評分（預設，加權計算）
    - 完工率
    - 平均星等
    - 平均週轉時間（升序）
    - 完工工單數
    - 拒單率（升序）
    - 營收貢獻
  - region_filter: MultiSelect / optional / 服務區域篩選
  - skill_filter: MultiSelect / optional / 技能篩選（品牌 + 型號分類）
  - export_btn: Button Secondary / icon: FileDown / 「匯出 CSV」

---

### Section: ranking_table

- **layout**: 全寬，卡片容器，頂部 Top 3 展示區 + 下方完整排行表
- **elements**:
  - top_3_podium: PodiumCards / required / `grid grid-cols-3 gap-4 mb-6`
    - rank_1_card: 金色邊框 `border-yellow-400 border-2` + 皇冠 icon / 技師大頭像（80px）+ 姓名 + 綜合分數 + 核心指標
    - rank_2_card: 銀色邊框 `border-gray-400` / 同格式
    - rank_3_card: 銅色邊框 `border-orange-400` / 同格式
    - 每張卡片可點擊 → 跳轉技師詳情
  - ranking_table: TechnicianRankingTable / required / 對齊 `E5x--frontend-architecture.md` §3.3 元件：
    - col_rank: Text / 寬 60px / 排名數字（前 3 名顯示獎牌 icon）
    - col_avatar: Avatar / 寬 60px / 技師頭像 40px + 線上狀態小綠點
    - col_name: Text / 寬 140px / 姓名 + 技師 ID
    - col_total_orders: Text Number / 寬 100px / 總工單數
    - col_completed_orders: Text Number / 寬 100px / 完工數（對齊 SQL §7.2）
    - col_completion_rate: ProgressBar / 寬 140px / 完工率（completed / total）
      - >=95% 綠色進度條
      - 85-94% 藍色
      - 70-84% 琥珀
      - <70% 紅色
    - col_avg_rating: StarRating / 寬 120px / 平均星等 + 數字（保留 2 位小數）
    - col_avg_resolution: Text / 寬 120px / 平均週轉時間「{hours} hr」/ 升序箭頭表示排名
    - col_rejection_rate: Text / 寬 100px / 拒單率 {%} / 色碼：
      - <=10% 綠 / 10-30% 琥珀 / >30% 紅 / >50% 紅 + 「停權中」Badge
    - col_revenue: Text Number / 寬 140px / 營收貢獻 `NT$ {amount}` / 千分位格式
    - col_actions: ActionButtons / 寬 120px /
      - 「查看詳情」Link / 跳轉 `/admin/technicians/{id}/performance`
      - 「發送通知」IconButton / 開啟 Toast 給技師的訊息 Modal
  - pagination: Pagination / required / 每頁 25 / 50 / 100，預設 25
  - drill_down_drawer: Drawer / required / 點擊「查看詳情」開啟右側 Drawer
    - 技師基本資料卡片
    - 當期詳細 KPI（細項 SLA / 客戶評分分布 / 完工時間直方圖）
    - 最近 10 筆工單列表
    - 歷史趨勢折線圖（近 6 期綜合分數）
    - 「前往完整檔案 →」連結
- **states**:
  - default: Top 3 金銀銅 + 完整排行表
  - hover: 整列 `bg-blue-50` + 游標 pointer
  - loading: Top 3 三張 Skeleton + 表格 10 列 Skeleton
  - empty: 「選定期間無技師資料」
  - error: ErrorState + 重試按鈕
  - suspended_row: 拒單率停權技師整列 `bg-red-50 opacity-60`
- **copy_constraints**: 技師姓名最多 10 字

---

### 子頁面 4: 營收報表 `/admin/reports/revenue`

### Section: revenue_toolbar

- **layout**: 全寬單列，水平排列，`flex flex-wrap gap-3 mb-6`
- **elements**:
  - granularity_toggle: SegmentedControl / required / 日 / 週 / 月 / 季 / 年 / 預設「月」
  - date_range_picker: DateRangePicker / required
  - slice_dimension: Select / required / 切片維度：
    - 整體（無切片）
    - 按技師
    - 按品牌
    - 按服務類型（維修/保固/安裝/改裝）
    - 按地區
  - include_filters: MultiSelect / optional / 對應切片的多選篩選（最多顯示 Top 10，其餘合併為「其他」）
  - compare_period: Switch / optional / 「與上期比較」/ 啟用後折線圖顯示雙線（本期實線 + 上期虛線）
  - export_btn: Button Primary / icon: FileDown / 「匯出」/ 下拉：
    - CSV（樞紐表原始資料）
    - Excel（含圖表）
    - PDF（報告格式）
  - schedule_btn: Button Secondary / icon: Calendar / 「排程發送」/ 開啟 export_scheduler_modal
- **states**:
  - default: 粒度「月」+ 過去 12 個月 + 整體切片
  - url_synced: 所有參數同步 URL query

---

### Section: revenue_line_chart

- **layout**: 全寬區塊，`bg-white rounded-xl border border-gray-200 p-6 mb-6`
- **elements**:
  - section_title: H2 / 「營收趨勢」
  - summary_stats: StatRow / required / 水平排列 4 個統計：
    - total_revenue: 「總營收 NT$ {sum}」+ 與上期比較箭頭
    - total_orders: 「完工工單 {count}」
    - avg_order_value: 「平均客單 NT$ {avg}」
    - growth_rate: 「成長率 ±{n}%」/ 色碼
  - line_chart: LineChart / required / recharts `<LineChart>` /
    - X 軸：時間（依粒度格式化：日 `MM/dd` / 週 `YYYY-Www` / 月 `YYYY-MM` / 季 `YYYY-Qn`）
    - Y 軸：營收 NT$（自適應，含千分位 K/M 簡化）
    - 主線：本期（實線，色 `#2563EB`，線寬 2px）
    - 輔線：上期（虛線，色 `#94A3B8`，`strokeDasharray 5 5`）— 僅 compare_period 啟用時
    - 切片線：每個切片項一條線（最多 5 條 + 「其他」聚合線，色票循環：`#2563EB`, `#F59E0B`, `#10B981`, `#EF4444`, `#8B5CF6`, `#94A3B8`）
    - 資料點：圓形 marker（hover 放大 1.5x + Tooltip）
    - 工具：
      - legend: Legend / 可點擊切換切片線顯示
      - tooltip: CustomTooltip / 顯示該時間點所有切片的營收 + 佔比
      - brush: Brush / 底部時間刷子 / 可拖拉選取縮放區間
  - annotations: AnnotationDots / optional / 標記重大事件（活動、促銷、系統異常）/ 點擊顯示註解
- **states**:
  - default: 本期實線 + 資料點
  - loading: 圖表 Skeleton（灰色漸變矩形）
  - hover_point: 該資料點放大 + Tooltip 顯示完整切片明細
  - zoomed: brush 選取後，X 軸範圍縮小，資料點密度增加
  - empty: 「選定期間無營收資料」
  - error: ErrorState + 重試按鈕

---

### Section: revenue_pivot_table

- **layout**: 全寬，`bg-white rounded-xl border border-gray-200 p-6 mb-6`
- **elements**:
  - section_title: H2 / 「營收樞紐表」
  - pivot_controls: ToolbarRow / required /
    - rows_selector: Select / 列維度 / 預設「時間」
    - cols_selector: Select / 欄維度 / 預設對應上方 slice_dimension
    - values_selector: MultiSelect / 數值維度 / 選項：營收 / 工單數 / 平均單價 / 成長率 / 預設「營收」
    - total_rows_toggle: Switch / 「顯示總計列」/ 預設 on
    - total_cols_toggle: Switch / 「顯示總計欄」/ 預設 on
  - pivot_table: DataTable / required / 固定表頭 + 固定首欄
    - 表頭：欄維度值 + 「總計」
    - 首欄：列維度值 + 「總計」
    - 儲存格：對應數值 / 千分位格式 / 負值紅字括號 `(NT$ 1,000)`
    - 熱度染色 (Conditional Formatting)：
      - 依該欄最大值色階漸變（`bg-blue-50` → `bg-blue-500`）
      - 可 toggle 關閉（頂部 checkbox 「數據熱圖」）
    - 儲存格 hover：顯示原始值 + 佔總計百分比 + 與上期變化
    - 儲存格點擊：Drawer 顯示該儲存格對應的工單明細列表
  - table_footer:
    - row_count: 「共 {n} 列 × {m} 欄」
    - last_updated: 「資料截至 {timestamp}」
- **states**:
  - default: 預設樞紐（時間 × 切片 × 營收）
  - loading: 10x6 Skeleton 儲存格
  - empty: 「無資料可供樞紐」
  - error: ErrorState + 重試按鈕
  - heatmap_on: 儲存格依熱度色階染色
  - cell_hover: 儲存格 `bg-blue-100` + Tooltip
  - sticky_header: 垂直/水平捲動時表頭首欄固定
- **copy_constraints**: 欄標題最多 15 字（超長 truncate）

---

### Section: export_scheduler_modal

- **layout**: Modal md（max-width 560px）
- **trigger**: 點擊「排程發送」按鈕
- **elements**:
  - modal_header: H3 / 「排程定期發送報表」+ Tooltip「對齊 specs/data-export-spec.md」
  - report_name_input: Input / required / 「報表名稱」/ placeholder「2026 月度營收報告」/ 最多 50 字
  - format_radio: RadioGroup / required / 格式：CSV / Excel / PDF / 預設 Excel
  - frequency_select: Select / required / 頻率：每日 / 每週（指定週幾）/ 每月（指定日期）/ 每季
  - time_picker: TimePicker / required / 發送時間 / 預設 09:00
  - recipients_multiselect: MultiSelect / required / 收件人（管理員名單，可多選）/ 支援手動輸入 email
  - filter_snapshot: InfoBlock / required / 快照：當前頁面篩選條件 `bg-[#F8FAFC] p-3 rounded-lg text-sm`
    - 「時間粒度：{granularity}」
    - 「切片維度：{slice}」
    - 「篩選條件：{filters}」
    - 「快照時間：{now}」
  - include_raw_data_toggle: Switch / optional / 「附加原始資料 CSV」
  - next_send_preview: Text / `text-sm text-gray-500` / 「下次發送：{next_datetime}」
  - confirm_btn: Button Primary / 「儲存排程」
  - cancel_btn: Button Ghost / 「取消」
- **states**:
  - default: 預設頻率「每月」+ 當月 1 日 09:00
  - validation_error: 欄位下方行內紅字錯誤
  - saving: Spinner + 「建立排程中...」
  - success: Modal 關閉 + Toast「排程已建立，下次發送 {datetime}」
  - failure: Toast Error + Modal 保持開啟
- **copy_constraints**: 報表名稱最多 50 字

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

#### A28 派工佇列監控
1. 進入頁面 → 建立 WebSocket 連線 `/realtime/dispatch-queue` → 載入初始佇列
2. 即時事件處理：
   - `dispatch.attempt.created` → 新增列（頂部滑入 + 閃爍）
   - `dispatch.attempt.responded` → 更新對應列 match_score / response 欄位（短暫閃爍）
   - `dispatch.attempt.timeout` → 該列狀態變更 + 計數卡片更新
   - `dispatch.all_failed` → 列變紅 + 彈出 Toast 通知管理員
3. 點擊「介入」→ 開啟 manual_intervention_panel
   - Tab 1 手動指派 → `POST /api/v1/work-orders/{id}/manual-dispatch` → 成功 Toast + 列表 refetch
   - Tab 2 放寬條件 → `POST /api/v1/work-orders/{id}/redispatch?relax=true` → 新 attempt 建立
   - Tab 3 加價重派 → `POST /api/v1/work-orders/{id}/redispatch?bonus={amount}` → 新 attempt 建立
   - Tab 4 取消工單 → `PATCH /api/v1/work-orders/{id}/cancel` → 工單狀態變更 + LINE 通知客戶
4. 拒單原因統計 → 點擊卡片下方「本月拒單原因 Top 10」連結 → 跳轉 A29 kpi_efficiency_section 下鑽

#### A29 KPI 儀表板
1. 進入頁面 → 讀取 URL params 恢復篩選 → 並行請求五大區塊 API
2. 切換時間粒度 → URL 同步 → 全頁 refetch（showLoadingOverlay）
3. 切換切片維度 → 各區塊 API 重新請求（帶 slice param）
4. 啟用「與上期比較」→ 各區塊顯示 trend arrow + 上期虛線
5. 任一區塊「查看明細」→ Drawer 開啟 → 顯示對應明細表 + 跳轉連結
6. 匯出 → 下拉選擇格式 → `POST /api/v1/reports/export` body: `{ report_type: "kpi", format, filters }` → 生成中 Toast → 完成後自動下載

#### A30 技師排行榜
1. 進入頁面 → 載入當月排行 → Top 3 + 完整表
2. 切換週期 → refetch
3. 切換排序依據 → 前端 reorder（無需 API）
4. 點擊「查看詳情」→ Drawer 開啟 → 載入技師完整績效 `GET /api/v1/technicians/{id}/performance?period=...`
5. Drawer 內「前往完整檔案」→ 跳轉 `/admin/technicians/{id}`

#### A31 營收報表
1. 進入頁面 → 載入預設（月度整體）→ 折線圖 + 樞紐表同步載入
2. 切換切片維度 → 折線圖多線切換 + 樞紐表列/欄重組
3. brush 時間刷子拖拉 → 折線圖縮放 + 樞紐表資料範圍更新（前端計算）
4. 樞紐表儲存格點擊 → Drawer 顯示對應期間/切片的工單明細
5. 匯出 → 同 A29 匯出流程
6. 排程發送 → 開啟 export_scheduler_modal → `POST /api/v1/reports/schedule` → 排程建立

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop LG (≥1440px) | 完整多欄佈局 | 所有圖表/表格完整顯示 |
| Desktop (1024-1439px) | 保留多欄但收縮 | A28 展開 timeline 保持 3 節點並排 / A29 環形 4 個改為 2x2 Grid / A30 Top 3 podium 保持 3 欄 |
| Tablet (768-1023px) | 2 欄改為 1 欄 | A28 表格欄位精簡（隱藏 match_score 細節）/ A29 圖表區塊改為單欄堆疊 / A30 表格隱藏 revenue 欄 / A31 折線圖保留 + 樞紐表改為水平捲動 |
| Mobile (<768px) | 單欄堆疊，圖表簡化 | A28 表格改為卡片式 + 展開 timeline 改為垂直時間軸（3 節點由上至下）/ A29 漏斗改為垂直條形 / A30 Top 3 podium 垂直堆疊 + 表格轉為卡片 / A31 折線圖保留（滑動查看）+ 樞紐表改為下拉切換顯示模式 |

### 資料更新策略

- **A28 派工佇列**：
  - WebSocket `/realtime/dispatch-queue` 長連線，即時推送
  - 備援 polling：WebSocket 斷線時降級為 `refetchInterval: 15_000`
  - 統計卡片與表格資料共用 TanStack Query cache
- **A29 KPI**：
  - TanStack Query，`staleTime: 300_000`（5 分鐘，對齊 Materialized View 刷新週期）
  - 手動 refetch 按鈕觸發 invalidate
- **A30 技師排行**：
  - `staleTime: 300_000`
  - 切換週期 → 獨立 query key
- **A31 營收**：
  - `staleTime: 300_000`
  - 樞紐表點擊明細 → 獨立 query（by cell coordinates）
- **SLA 告警**：
  - WebSocket `/realtime/sla-alerts`（所有頁面共用全域通道）→ 觸發頂部 Toast + Bell 紅點
- **URL State**：所有篩選條件、時間粒度、切片維度同步至 URL query params，支援刷新保留與分享

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:

  - **派工佇列 (A28)**:
    - GET `/api/v1/work-orders/dispatch-queue` — 取得當前佇列
      - Query params: `attempt_num[]`, `response[]`, `brand`, `urgent_only`, `search`, `page`, `limit`
      - Response: `{ data: DispatchQueueItem[], total: number, summary: { stuck, retry_2, retry_3, timeout } }`
      - DispatchQueueItem: `{ work_order_id, wo_number, customer_name, address, brand, model, current_attempt: { attempt_num, technician, match_score, pushed_at, responded_at, response, rejection_reason, remaining_seconds }, attempts_history: DispatchAttempt[], is_stuck: boolean, is_urgent: boolean }`
    - POST `/api/v1/work-orders/{id}/manual-dispatch` — 手動指派（覆寫演算法）
      - Body: `{ technician_id: string, override_reason: string }`
      - Response: `{ success, work_order, new_attempt }`
    - POST `/api/v1/work-orders/{id}/redispatch` — 重新派工（放寬條件 / 加價）
      - Body: `{ relax_distance?: boolean, relax_skills?: boolean, relax_load?: boolean, bonus_amount?: number, reason: string }`
      - Response: `{ success, new_attempt }`
    - PATCH `/api/v1/work-orders/{id}/cancel` — 取消工單
      - Body: `{ cancellation_reason: string, notes: string, notify_customer: boolean }`
    - GET `/api/v1/reports/dispatch-rejection-reasons?period=...` — 拒單原因統計（供 A29 下鑽）

  - **KPI 儀表板 (A29)**:
    - GET `/api/v1/reports/kpi` — 完整 KPI（五大區塊合併回傳）
      - Query params: `granularity` (day|week|month|quarter), `date_from`, `date_to`, `slice_by` (none|technician|brand|service_type), `slice_values[]`, `compare_previous` (boolean)
      - Response: `{ funnel: FunnelData, sla: SLAData, satisfaction: SatisfactionData, dispute: DisputeData, efficiency: EfficiencyData, generated_at, data_freshness_minutes }`
    - GET `/api/v1/reports/kpi/funnel` — 轉換漏斗單獨（支援下鑽）
    - GET `/api/v1/reports/kpi/sla-breakdown?slice_by=...` — SLA 依切片
    - GET `/api/v1/reports/kpi/bad-ratings?period=...` — 差評明細

  - **技師排行 (A30)**:
    - GET `/api/v1/reports/technician-ranking` — 排行榜
      - Query params: `period` (this_week|this_month|this_quarter|this_year|custom), `date_from`, `date_to`, `sort_by`, `region[]`, `skills[]`, `page`, `limit`
      - Response: `{ data: TechnicianRanking[], total, period_summary }`
      - TechnicianRanking: `{ rank, technician_id, name, avatar_url, total_orders, completed_orders, completion_rate, avg_rating, avg_resolution_hours, rejection_rate_pct, revenue_contribution, composite_score, is_suspended, trend: { score_delta, rank_delta } }`
    - GET `/api/v1/technicians/{id}/performance` — 技師個人績效（Drawer 下鑽）
      - Response: `{ technician, current_period: KPIs, recent_orders: WorkOrder[10], history_trend: TrendPoint[] }`

  - **營收報表 (A31)**:
    - GET `/api/v1/reports/revenue` — 營收趨勢 + 樞紐
      - Query params: `granularity`, `date_from`, `date_to`, `slice_by` (none|technician|brand|service_type|region), `slice_values[]`, `compare_previous`
      - Response: `{ time_series: TimePoint[], pivot: PivotData, summary: { total_revenue, total_orders, avg_order_value, growth_rate }, generated_at }`
      - TimePoint: `{ time_label, total, by_slice: { [key]: number } }`
      - PivotData: `{ rows: string[], columns: string[], cells: number[][], row_totals: number[], col_totals: number[], grand_total }`
    - GET `/api/v1/reports/revenue/drill-down?time={time}&slice_value={value}` — 儲存格明細（工單清單）

  - **報表匯出與排程**:
    - POST `/api/v1/reports/export` — 匯出
      - Body: `{ report_type: "kpi"|"technician-ranking"|"revenue"|"dispatch-queue", format: "csv"|"xlsx"|"pdf", filters: object }`
      - Response: `{ file_url, expires_at }` — 非同步生成，大檔案回傳 job_id 供輪詢
    - POST `/api/v1/reports/schedule` — 建立排程
      - Body: `{ report_name, report_type, format, frequency, cron_expression, recipients: string[], filters: object, include_raw_data }`
      - Response: `{ schedule_id, next_send_at }`
    - GET `/api/v1/reports/schedules` — 列出現有排程
    - DELETE `/api/v1/reports/schedules/{id}` — 取消排程

- **WebSocket Events**:
  - Channel: `/realtime/dispatch-queue` (A28)
    - `dispatch.attempt.created`: `{ work_order_id, attempt }` — 新派工嘗試
    - `dispatch.attempt.responded`: `{ work_order_id, attempt_num, response, responded_at, rejection_reason? }`
    - `dispatch.attempt.timeout`: `{ work_order_id, attempt_num }`
    - `dispatch.all_failed`: `{ work_order_id, total_attempts, requires_admin: true }`
    - `dispatch.admin_intervened`: `{ work_order_id, action, actor }` — 其他管理員介入時同步
  - Channel: `/realtime/sla-alerts` (全域)
    - `sla.warning`: `{ work_order_id, sla_type, remaining_minutes }`
    - `sla.breached`: `{ work_order_id, sla_type, breach_duration_minutes }`

- **Zustand Store**:
  - `useDispatchQueueStore`: 當前篩選、WebSocket 連線狀態、選中的工單
  - `useReportsFilterStore`: 各報表頁面的篩選狀態（granularity、date_range、slice）
  - `useExportQueueStore`: 非同步匯出任務佇列（job_id + 進度）

- **error_cases**:
  - 網路錯誤：Toast「網路連線異常」+ TanStack Query 自動重試（指數退避）
  - WebSocket 斷線（A28）：頂部 realtime_indicator 變紅 + 自動重連（1s, 2s, 4s, 8s, max 30s）+ 降級為 polling
  - API 403 權限不足：報表頁面整體顯示「您無權限查看此報表」+ 申請連結
  - API 404 工單不存在：Toast「工單已被刪除或不存在」+ 列表 refetch
  - API 409 衝突（其他管理員同時介入）：Toast「此工單已被 {admin_name} 處理」+ Modal 關閉 + 列表 refetch
  - API 422 驗證錯誤：Modal 內行內錯誤訊息
  - API 500 伺服器錯誤：Toast + 重試按鈕
  - 資料延遲過長（>10 分鐘）：頂部 Banner「資料更新延遲，實際可能有差異」+ 手動重新整理按鈕
  - 匯出檔案過大（>100MB）：Toast「檔案過大，已改為背景任務，完成後通知」+ Bell 通知中心
  - 排程衝突：Toast「此名稱排程已存在」+ 修改建議

---

## [EXCEPTION TO GLOBAL RULES]

- **A28 派工佇列 WebSocket 長連線**：此頁面為即時監控核心，維持持久 WebSocket 連線（進入頁面建立，離開斷開），與一般頁面 REST-only 模式不同
- **A28 計數卡片實時動畫**：數值變動時的放大 + 閃爍動畫（500ms）超出 Global 「禁止自訂 CSS 動畫超過 500ms」規則，但因屬關鍵即時反饋（非裝飾），屬合理例外
- **A28 `attempt_num=3` 列脈動背景**：紅色背景 pulse 動畫（1.5s infinite）為持續性警示狀態指示，非短暫操作回饋
- **A29 環形圖群組**：四個同心環形並列的視覺化超出 Global 標準圖表元件庫，需使用 recharts `<PieChart>` 多重 innerRadius 自訂實作
- **A31 折線圖 Brush 元件**：底部時間刷子為 recharts 標準元件，但超出一般折線圖互動範圍；允許在樞紐表上方使用以增強時間縮放體驗
- **A31 樞紐表熱圖染色**：條件格式化顏色漸變（`bg-blue-50` → `bg-blue-500`）非 Global Design Token 直接定義，但色階基於品牌 Primary 色，視為合理擴展
- **A30 Top 3 Podium 金銀銅邊框**：使用 `border-yellow-400`（金）、`border-gray-400`（銀）、`border-orange-400`（銅），超出標準語義色 Token，但僅限排行榜視覺表達，不影響其他頁面
- **報表匯出非同步任務**：生成 PDF/大型 Excel 可能 >30 秒，採用背景任務 + Bell 通知中心提示完成，與一般 API 同步回應模式不同

---

## [ACCEPTANCE CRITERIA]

### 共用（四頁）
- [ ] URL 同步：所有篩選條件、時間粒度、切片維度寫入 URL query params，刷新保留，可分享連結
- [ ] 三態完整：loading / error / empty 在每個區塊均正確實作
- [ ] RWD 三個斷點佈局正確（Desktop / Tablet / Mobile）
- [ ] 符合 Design System 視覺規範（Primary #2563EB、Accent #F59E0B、Secondary #1E293B、BG #F8FAFC、Font Inter + Noto Sans TC）
- [ ] 所有圖表使用 recharts，元件對齊 `E5x--frontend-architecture.md` §3.3 元件目錄

### A28 派工佇列監控
- [ ] 4 張計數卡片即時更新（WebSocket `/realtime/dispatch-queue`）
- [ ] 第 2 次派工自動標黃（列 `bg-amber-50`），第 3 次標紅（列 `bg-red-50`）
- [ ] `attempt_num=3 && all_failed` 觸發 Toast 通知 + 列整個 pulse 動畫
- [ ] `DispatchAttemptTimeline` 元件正確展開，3 節點狀態（accepted/rejected/timeout/pending/not_started）視覺化正確
- [ ] match_score 進度條色碼正確（>=80 綠 / 60-79 藍 / 40-59 琥珀 / <40 紅）
- [ ] 剩餘時間倒數計時器正確（>5min 灰 / 1-5min 琥珀 / <1min 紅 pulse / 逾時顯示 "已逾時 {n}min"）
- [ ] 管理員介入四種操作均可執行：手動指派 / 放寬條件 / 加價 / 取消工單
- [ ] 覆寫原因必填（至少 10 字）並寫入 audit-events
- [ ] WebSocket 斷線自動重連（指數退避）+ 降級 polling
- [ ] 拒單原因統計點擊可跳轉 A29

### A29 KPI 儀表板
- [ ] 五大區塊完整（轉換漏斗 / SLA / 滿意度 / 爭議 / 效率）
- [ ] 時間粒度切換（日/週/月/季）正確
- [ ] 切片維度（技師 / 品牌 / 服務類型）正確
- [ ] 「與上期比較」正確顯示 MoM / YoY 趨勢箭頭
- [ ] 資料延遲 < 5 分鐘（Materialized View）+ 顯示最後更新時間
- [ ] 任一 SLA 未達標觸發 alert_banner 警示
- [ ] NPS 計算正確（Promoters % - Detractors %）
- [ ] FTFR 散佈圖四象限分類正確（明星技師 / 品質優先 / 速度型 / 需培訓）
- [ ] 每區塊「查看明細」Drawer 下鑽正確
- [ ] 匯出 CSV / Excel / PDF 功能正常

### A30 技師排行榜
- [ ] 週期選擇（本週/本月/本季/本年/自訂）正確
- [ ] 多維排序（7 種依據）正確
- [ ] Top 3 podium 金銀銅視覺正確
- [ ] 完工率進度條色碼正確（>=95% 綠 / 85-94% 藍 / 70-84% 琥珀 / <70% 紅）
- [ ] 拒單率 > 50% 技師自動顯示「停權中」Badge + 列整體 opacity-60
- [ ] 下鑽 Drawer 顯示完整績效 + 歷史趨勢 + 最近 10 筆工單
- [ ] 「前往完整檔案」連結至 `/admin/technicians/{id}/performance`

### A31 營收報表
- [ ] 時間粒度切換（日/週/月/季/年）正確
- [ ] 切片維度（整體 / 技師 / 品牌 / 服務類型 / 地區）正確
- [ ] 折線圖多線切換 + legend 可點擊切換顯示
- [ ] brush 時間刷子縮放功能正常
- [ ] 「與上期比較」雙線（本期實線 + 上期虛線）正確
- [ ] 樞紐表列/欄維度重組正確 + 總計列/欄切換
- [ ] 熱度染色（conditional formatting）正確
- [ ] 儲存格點擊 Drawer 顯示工單明細
- [ ] 匯出 CSV（原始資料）/ Excel（含圖表）/ PDF（報告格式）正常
- [ ] 排程發送 Modal 功能完整（對齊 `data-export-spec.md`）
- [ ] 下次發送時間預覽正確

### 效能
- [ ] 各頁首次載入 LCP < 2.5s
- [ ] A28 WebSocket 推送到 UI 更新延遲 < 500ms
- [ ] A29 五大區塊並行載入 < 3s 全部完成
- [ ] A31 樞紐表 100x20 儲存格渲染 < 300ms
- [ ] A31 折線圖 365 個資料點流暢互動（hover FPS > 30）
- [ ] 匯出大檔案（>10MB）採非同步任務 + Bell 通知

### 無障礙
- [ ] Tab 順序：toolbar → main content → pagination
- [ ] 所有可互動元素可透過鍵盤操作
- [ ] 色彩對比度達 WCAG 2.1 AA 標準
- [ ] 圖表提供 aria-label 描述 + 資料表替代檢視
- [ ] Modal 開啟時 focus trap；Escape 關閉
- [ ] 即時更新元素使用 `aria-live="polite"`，錯誤警示使用 `aria-live="assertive"`

---

## [T1.5 §6.24 補漏] A29 排程與多格式匯出

**匯出格式：** PDF / XLSX / CSV 三選一，對齊 `specs/data-export-spec.md`。

**排程自動發送 API：**
```
POST /api/v1/reports/schedule
Body: {
  report_type: "kpi_dashboard | technician_ranking | revenue",
  frequency: "daily | weekly | monthly",
  cron_expression: "0 9 * * 1",
  format: "pdf | xlsx | csv",
  recipients: ["admin@example.com"],
  filters: { period_from: ISO8601, tenant_id: uuid }
}
```

**UI：** A29 新增「排程清單」子區（啟用/停用/改收件人/查發送歷史）；失敗指數退避 3 次全失敗通知建立者。

**多租戶匿名比較（V3.0）：** 指向 `18_admin_multi_tenant.md` A36 超管；A29 本身僅單租戶範圍。

---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
