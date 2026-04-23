# Page-Level Prompt: 技師端 — 帳戶中心

> 技師收入總覽、績效儀表板、個人檔案、排班管理與設定。

---

## [PAGE META]

- **page_name**: 帳戶中心 Account Center
- **route_path**: `/account`
- **page_type**: dashboard + profile (hybrid)
- **primary_goal**: 讓技師掌握收入狀況與績效表現
- **secondary_goal**: 管理個人排班、勤務狀態與通知偏好
- **target_users**:
  - 主要：已登入的外派技師（每日 1–2 次查看）
  - 次要：無
- **entry_point**: 底部導航第 3 個 Tab「帳戶」
- **expected_time_on_page**: 1–3 分鐘（查看收入/績效 → 調整設定 → 離開）

---

## [STRUCTURE: SECTIONS]

1. **profile_header**
   - section_type: hero
   - section_purpose: 技師頭像、姓名、勤務狀態快速切換

2. **income_overview**
   - section_type: stats_card
   - section_purpose: 當月收入總覽（大數字 KPI）+ 收入組成

3. **income_history**
   - section_type: list
   - section_purpose: 歷史結算紀錄列表

4. **performance_dashboard**
   - section_type: stats_cards
   - section_purpose: 績效 KPI（完成數、評分、準時率、拒單率）

5. **profile_section**
   - section_type: info_block
   - section_purpose: 個人資料、技能認證、服務區域

6. **schedule_section**
   - section_type: calendar_block
   - section_purpose: 本週排班 + 請假/加班申請

7. **settings_section**
   - section_type: settings_list
   - section_purpose: 通知偏好、勤務開關、App 資訊

8. **bottom_navigation**
   - section_type: navigation
   - section_purpose: 三 Tab 底部導航列（帳戶 active）

---

## [SECTION COMPONENT SPEC]

### Section: profile_header

- **layout**: 全寬卡片，背景漸層（#2563EB → #1E40AF），padding 24px 16px，圓角下方 16px
- **elements**:
  - avatar: AvatarCircle / required / 64×64px，圓形，白色邊框 3px，預設 fallback 為姓名首字
  - tech_name: H2 / required / 技師姓名，Noto Sans TC 20px SemiBold，白色
  - tech_id: Caption / required / 技師編號（例："T-00042"），白色 70% opacity，13px
  - availability_toggle: Switch / required / 「在線接單」文字 + Toggle 開關
    - ON：綠色圓點 + 「在線」白色文字
    - OFF：灰色圓點 + 「離線」白色 60% opacity
    - toggle touch area ≥ 44×44px
    - 切換 → PATCH `/api/v1/technicians/me/availability`
    - 切換為離線時：確認 Dialog「確定要離線？將不會收到新工單通知」
- **states**:
  - default: 顯示頭像 + 姓名 + 在線狀態
  - loading: skeleton（圓形 + 文字行）
  - toggling: toggle 短暫 disabled + Spinner

### Section: income_overview

- **layout**: 單欄 padding 16px，margin-top -16px（與 profile_header 重疊效果），背景白色，圓角 16px，shadow-md
- **elements**:
  - period_selector: SegmentedControl / required / 三選項：「本月」「上月」「自訂」，每個 segment min touch 44×44px
    - 「自訂」→ 展開日期範圍選擇器（兩個 DatePicker，min touch 44×44px）
  - total_earnings: KPINumber / required / 當月總收入，字體 Inter 36px Bold，色 #1E293B，例「$42,800」
  - earnings_label: Caption / required / 「本月收入」，色 #64748B，14px
  - earnings_formula: Body SM / required / 「= 工資佣金 + 獎金 - 扣款」，色 #94A3B8，12px
  - breakdown_bar: StackedHorizontalBar / required / 水平堆疊長條圖：
    - 綠色段：工資佣金（佔比最大）
    - 藍色段：獎金
    - 紅色段：扣款（如有）
    - 每段可點擊 → 顯示 Tooltip 金額 + 百分比
    - 長條高度 24px，圓角 12px
  - breakdown_legend: LegendRow / required / 三個圖例：
    - 工資佣金 $XX,XXX（綠點 + 文字）
    - 獎金 $X,XXX（藍點 + 文字）
    - 扣款 -$XXX（紅點 + 文字，無扣款時顯示 $0）
  - commission_info: CollapsibleCard / optional / 「佣金說明」展開：
    - 一般維修：70%
    - 安裝工程：60%
    - 客供安裝：80%
    - 字體 13px，色 #64748B
- **states**:
  - default: 顯示本月收入
  - loading: KPI 數字 skeleton + bar skeleton
  - empty: 「本月尚無收入紀錄」
  - period_switching: 數字淡出 → 載入 → 淡入（300ms）
  - custom_range_open: 日期選擇器展開

### Section: income_history

- **layout**: 單欄 padding 16px，margin-top 16px
- **elements**:
  - section_title: H3 / required / 「結算紀錄」，Noto Sans TC 16px SemiBold
  - settlement_list: List / required / 垂直列表，每項間距 8px
  - settlement_item: Card / repeated / 全寬，padding 14px，圓角 8px，背景白色，shadow-sm
    - period_text: Body MD SemiBold / required / 結算期間（例：「2026/03/01 – 2026/03/31」），15px
    - amount_text: Body LG Bold / required / 金額（例：「$38,500」），18px Bold，色 #059669
    - status_badge: Badge / required /
      - `draft`：灰色 Badge「草稿」
      - `confirmed`：藍色 Badge「已確認」
      - `paid`：綠色 Badge「已發放」
    - chevron_icon: Icon / required / ChevronRight 16px，色 #94A3B8
    - 點擊 → 展開結算詳情（inline expand 或 modal）
  - settlement_detail: CollapsibleContent / conditional / 展開後顯示：
    - 工單列表：每筆工單的 WO 編號 + 完工日期 + 佣金金額
    - 獎金明細（如有）
    - 扣款明細（如有）
    - 合計列
  - load_more_btn: Button Ghost / conditional / 「載入更多」，min touch 44×44px（分頁載入）
- **states**:
  - default: 最近 5 筆結算紀錄
  - loading: 3 張 skeleton 卡片
  - empty: 「尚無結算紀錄」
  - expanded: 某筆結算展開詳情
  - load_more_loading: 底部 Spinner

### Section: performance_dashboard

- **layout**: 2×2 Grid，gap 12px，padding 16px
- **elements**:
  - section_title: H3 / required / 「績效總覽」，全寬，16px SemiBold
  - kpi_completions: MiniKPICard / required / 圓角 12px，padding 14px，背景白色，shadow-sm
    - kpi_icon: Icon / required / CheckCircle 20px，色 #2563EB
    - kpi_value: Body LG Bold / required / 月完成數（例「23」），Inter 24px Bold
    - kpi_label: Caption / required / 「本月完成」，12px，色 #64748B
  - kpi_rating: MiniKPICard / required /
    - kpi_icon: Icon / required / Star 20px，色 #F59E0B
    - kpi_value: Body LG Bold / required / 平均評分（例「4.8」），24px Bold
    - kpi_label: Caption / required / 「平均評分」，12px
    - star_display: StarRow / required / 5 顆星填充顯示（支援半星），每顆 16px
  - kpi_ontime: MiniKPICard / required /
    - kpi_icon: Icon / required / Clock 20px，色 #10B981
    - kpi_value: Body LG Bold / required / 準時率百分比（例「96%」），24px Bold
    - kpi_label: Caption / required / 「準時率」，12px
    - progress_ring: MiniRing / optional / 小環形進度（外徑 32px），色 #10B981
  - kpi_rejection: MiniKPICard / required /
    - kpi_icon: Icon / required / XCircle 20px，色 #EF4444
    - kpi_value: Body LG Bold / required / 拒單率（例「3%」），24px Bold
    - kpi_label: Caption / required / 「拒單率」，12px
    - 拒單率 > 10% 時值變紅色警示
  - rating_sparkline: SparklineChart / optional / 全寬，高度 60px，顯示近 30 天評分趨勢折線圖
    - 線條色 #F59E0B，區域填充 #F59E0B 10% opacity
    - X 軸隱藏，Y 軸範圍 1–5
    - 最右端顯示當前值圓點
- **states**:
  - default: 顯示 4 張 KPI + sparkline
  - loading: 4 張 skeleton card + skeleton line
  - error: 「績效資料載入失敗」+ 重試按鈕

### Section: profile_section

- **layout**: 單欄 padding 16px，margin-top 16px，背景白色，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「個人資料」，16px SemiBold
  - info_rows: InfoRowList / required /
    - phone_row: InfoRow / required / 圖示 Phone + 「電話」+ 號碼值，只讀
    - email_row: InfoRow / required / 圖示 Mail + 「Email」+ Email 值，只讀
    - edit_notice: Caption / required / 「如需修改個人資料，請聯繫管理員」，色 #94A3B8，12px
  - skill_badges_section: SubSection / required /
    - subtitle: Body SM Bold / required / 「技能認證」，14px SemiBold
    - badge_list: BadgeRow / required / 水平可捲動（horizontal scroll），每個 Badge：
      - 品牌名稱（例：「Yale 認證」「Gateman 認證」「Samsung 認證」）
      - 背景 #DBEAFE，字體 13px #2563EB，padding 6px 12px，圓角 full
      - 到期指示：距到期 < 30 天 → 橘色邊框 + 「即將到期」小字
      - 已過期 → 紅色邊框 + 刪除線 + 「已過期」
      - 每個 Badge min touch area 44×32px（高度因 Badge 較小可放寬至 32px，但間距確保不誤觸）
  - service_regions_section: SubSection / required /
    - subtitle: Body SM Bold / required / 「服務區域」，14px SemiBold
    - region_tags: TagRow / required / wrap 排列：
      - 每個 Tag（例：「台北市中山區」「台北市大安區」），背景 #F1F5F9，字體 13px，padding 6px 12px，圓角 full
- **states**:
  - default: 顯示個人資料 + 認證 + 區域
  - loading: skeleton rows
  - no_badges: 「尚未取得任何認證」
  - no_regions: 「尚未指派服務區域」

### Section: schedule_section

- **layout**: 單欄 padding 16px，margin-top 16px，背景白色，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「本週排班」，16px SemiBold
  - week_view: HorizontalDayBlocks / required / 水平排列 7 天（週一至週日）：
    - 每天一個 Block，寬度 = (螢幕寬 - 32px padding) / 7
    - day_label: Caption / required / 星期（「一」「二」...），10px，色 #64748B
    - date_label: Body SM / required / 日期數字，13px
    - shift_indicator: ColorBlock / required / 高度 32px，圓角 4px：
      - 有排班：#2563EB（藍色）+ 時段文字（例「9-18」，白色 10px）
      - 已請假：#F59E0B（琥珀）斜線紋理
      - 加班：#10B981（綠色）
      - 休息日：#F1F5F9（淺灰）
    - today_ring: 今日日期加粗 + 底部 4px 圓點 #2563EB
  - action_buttons: Flex Row / required / 間距 12px
    - leave_request_btn: Button Outline / required / 「請假」，min touch 44×44px，寬度 50%，高度 44px
    - overtime_request_btn: Button Outline / required / 「加班」，min touch 44×44px，寬度 50%，高度 44px
    - 點擊 → 底部 Sheet 表單：
      - 日期選擇（DatePicker，touch area 44×44px）
      - 時段選擇（時間選擇器，touch area 44×44px）
      - 原因輸入（TextArea，placeholder「請填寫原因」，min 高度 60px）
      - 提交按鈕（full-width，高度 48px）
      - 提交後 Toast「已送出申請，等待管理員審核」
- **states**:
  - default: 顯示本週排班
  - loading: skeleton blocks
  - request_pending: 已申請的日期 Block 上顯示 pending 圖示（小時鐘）
  - request_approved: Toast「請假/加班申請已通過」
  - request_rejected: Toast「申請未通過，原因：{reason}」

### Section: settings_section

- **layout**: 單欄 padding 16px，margin-top 16px，背景白色，圓角 12px，shadow-sm，margin-bottom 預留 bottom_navigation 高度 + 24px
- **elements**:
  - section_title: H3 / required / 「設定」，16px SemiBold
  - notification_toggles: ToggleList / required /
    - new_order_toggle: SettingRow / required / 「新工單通知」+ Toggle，預設 ON，touch area 44×44px
    - status_update_toggle: SettingRow / required / 「狀態更新通知」+ Toggle，預設 ON
    - schedule_toggle: SettingRow / required / 「排班提醒」+ Toggle，預設 ON
    - 每列高度 ≥ 52px（padding + toggle 確保 touch target）
  - availability_row: SettingRow / required / 「接單開關」+ 大型 Toggle（同 profile_header，此處為快捷操作），touch area 44×44px
  - divider: Separator / required
  - app_info: InfoBlock / required /
    - version_row: SettingRow / required / 「App 版本」+ 版本號（例「v1.2.3」），只讀
    - build_row: SettingRow / optional / 「Build」+ build number，只讀，色 #94A3B8
  - logout_btn: Button Destructive Ghost / required / 「登出」，全寬，高度 48px，紅色文字 #EF4444，min touch 44×44px
    - 點擊 → 確認 Dialog「確定要登出？」→ 確認 → 清除 token + 導向 `/login`
- **states**:
  - default: 顯示所有設定項
  - toggle_saving: toggle 切換後短暫 disabled + 小 Spinner（PATCH API 中）
  - logout_confirming: 確認 Dialog 顯示

### Section: bottom_navigation

- **layout**: 同 11_tech_pool.md 定義
- **elements**: 同 11_tech_pool.md，tab_account 為 active（#2563EB），其餘 inactive（#94A3B8）

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. **頁面載入**：
   - 並行呼叫：GET `/api/v1/technicians/me` + GET `/api/v1/technicians/me/earnings` + GET `/api/v1/technicians/me/schedule`
   - 渲染 profile_header → income_overview → income_history → performance → profile → schedule → settings

2. **查看收入**：
   - 預設顯示本月
   - 切換「上月」→ 重新 GET earnings（帶 period 參數）→ 數字動畫更新
   - 切換「自訂」→ 展開日期選擇器 → 選完後查詢

3. **查看結算詳情**：
   - 點擊結算項目 → inline expand 顯示工單列表 + 佣金明細
   - 點擊「載入更多」→ 分頁載入歷史結算

4. **切換在線狀態**：
   - 切換 availability toggle → PATCH `/api/v1/technicians/me/availability` body: `{ available: true/false }`
   - 離線時停止接收新工單 Push Notification
   - profile_header 與 settings_section 的 toggle 雙向同步

5. **請假/加班申請**：
   - 點按鈕 → Bottom Sheet 表單 → 填寫日期 + 時段 + 原因 → 提交 POST
   - 成功 → Toast + 排班 Block 更新（pending 狀態）

6. **通知偏好調整**：
   - 切換 toggle → PATCH 更新偏好
   - 關閉「新工單通知」時：確認 Dialog「關閉後將不會收到新工單推送，確定？」

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Mobile (<480px) | 單欄全寬（主要設計） | 標準體驗 |
| Tablet (481–768px) | 單欄 max-width 480px 居中 | 左右留白 |
| Desktop (769px+) | 不支援（技師端為純 Mobile PWA） | 顯示「請使用手機操作」提示頁 |

### 資料更新策略

- **收入資料**：進入頁面時取得，period 切換時重新查詢
- **績效 KPI**：進入頁面時取得，快取 5 分鐘
- **排班資料**：進入頁面時取得，申請提交後即時更新
- **個人資料**：進入頁面時取得，長期快取（read-only）

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/technicians/me` — 取得技師個人資料（姓名、電話、Email、頭像、技能認證、服務區域）
  - GET `/api/v1/technicians/me/earnings` — 取得收入資料。查詢參數：`period`（this_month / last_month / custom）, `start_date`, `end_date`。回傳：total, commission, bonus, penalty, settlements[]
  - GET `/api/v1/technicians/me/earnings/settlements/{id}` — 取得單筆結算詳情（工單列表 + 各筆佣金）
  - GET `/api/v1/technicians/me/performance` — 取得績效 KPI（completions, avg_rating, ontime_rate, rejection_rate, rating_trend[]）
  - GET `/api/v1/technicians/me/schedule` — 取得排班資料。查詢參數：`week_of`（日期）。回傳 7 天排班陣列
  - PATCH `/api/v1/technicians/me/availability` — 切換在線狀態。Body: `{ available: boolean }`
  - POST `/api/v1/technicians/me/schedule/requests` — 提交請假/加班申請。Body: `{ type: "leave" | "overtime", date, start_time, end_time, reason }`
  - PATCH `/api/v1/technicians/me/notification-preferences` — 更新通知偏好。Body: `{ new_order: boolean, status_update: boolean, schedule_reminder: boolean }`
- **error_cases**:
  - 網路錯誤：顯示快取的個人資料 + 收入（可能非最新），Toast「離線模式，資料可能未更新」
  - API 錯誤（5xx）：各 Section 獨立錯誤處理，顯示「載入失敗」+ 重試按鈕
  - 權限不足（401/403）：導向登入頁
  - availability 切換失敗：Toast「狀態切換失敗」+ toggle 回彈至原狀態

---

## [EXCEPTION TO GLOBAL RULES]

- **profile_header 漸層背景**：此 Section 使用品牌色漸層（#2563EB → #1E40AF）取代標準白色背景，打破全局背景規則
- **income_overview 負 margin 疊加**：使用 margin-top: -16px 讓收入卡片與 profile_header 視覺疊加，營造層次感
- **sparkline 圖表**：使用輕量 SVG 繪製，不引入完整圖表庫（保持 PWA bundle 輕量）
- **week_view 緊湊佈局**：7 天 Block 寬度較小，day_label 字體 10px 低於全局最小 12px 規範，但僅用於星期標籤不影響可讀性

---

## [ACCEPTANCE CRITERIA]

### Profile Header
- [ ] 頭像正確顯示（有圖片/fallback 首字）
- [ ] 姓名、技師編號正確
- [ ] 在線開關切換正常，PATCH API 成功
- [ ] 離線確認 Dialog 正確顯示

### 收入總覽
- [ ] 本月收入 KPI 數字正確（=佣金+獎金-扣款）
- [ ] 水平堆疊長條圖正確顯示三段比例
- [ ] 期間切換（本月/上月/自訂）正常運作
- [ ] 自訂日期範圍選擇器可用
- [ ] 佣金說明展開顯示三種比例（70%/60%/80%）

### 結算紀錄
- [ ] 結算列表正確顯示期間、金額、狀態 Badge
- [ ] 點擊展開顯示工單明細
- [ ] 「載入更多」分頁正常

### 績效儀表板
- [ ] 4 張 KPI 卡片正確顯示：完成數、評分、準時率、拒單率
- [ ] 評分顯示星星（支援半星）
- [ ] 拒單率 > 10% 紅色警示
- [ ] 評分趨勢 sparkline 正確繪製

### 個人資料
- [ ] 電話、Email 正確顯示（只讀）
- [ ] 技能認證 Badge 水平可捲動
- [ ] 到期提醒（橘色）/ 已過期（紅色）正確顯示
- [ ] 服務區域 Tag 正確 wrap 排列

### 排班管理
- [ ] 本週 7 天 Block 正確顯示排班狀態（有班/請假/加班/休息）
- [ ] 今日標記明顯（圓點）
- [ ] 請假/加班按鈕開啟 Bottom Sheet 表單
- [ ] 表單提交成功 Toast + Block 更新

### 設定
- [ ] 通知偏好 Toggle 切換 + API 同步
- [ ] 關閉新工單通知有確認 Dialog
- [ ] App 版本號正確顯示
- [ ] 登出流程：確認 Dialog → 清除 token → 跳轉登入頁

### 通用
- [ ] 所有可點擊元素 touch target ≥ 44×44px
- [ ] Toggle 元件 touch area ≥ 44×44px
- [ ] Loading / Error / Empty 三態完備
- [ ] BottomNav 正確顯示，帳戶 Tab active
- [ ] 頁面可垂直捲動，底部預留 BottomNav 空間


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
