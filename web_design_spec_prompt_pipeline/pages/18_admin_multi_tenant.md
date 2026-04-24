# Page-Level Prompt: 多租戶管理（V3.0，3 個子頁面）

> 對應 `guides/vibe_coding_build_strategy.md` → Step 5。
> 多租戶管理涵蓋「租戶設定（A34）、品牌客製（A35）、超管平台（A36）」三個頁面群，對齊 `docs/02-design/platform-multi-tenant/*` 與 `E5x--frontend-architecture.md §1.4 / §3.3`。
> **版本標記：V3.0** — 本頁面群全部由 feature flag `multi_tenant.v3_enabled` 控制，非 V3.0 租戶訪問時回傳 404。

---

## [PAGE META]

- **page_name**: 多租戶管理 Multi-Tenant Admin (V3.0)
- **route_path**: `/admin/settings/tenant` | `/admin/settings/tenant/brand` | `/admin/super/*`
- **page_type**: tabbed_multi_page（A34 分頁式 Tabs / A35 編輯器 + 即時預覽 / A36 超管控制台）
- **ia_pages**: A34, A35, A36
- **openapi_ops**: none
- **asyncapi_ops**: none
- **primary_goal**: 提供 V3.0 多租戶 SaaS 的租戶自助設定、品牌白牌化客製，以及超級管理員跨租戶運營控制台
- **secondary_goal**: 落實前端租戶隔離三層模型（傳輸層 / 快取層 / 狀態層），確保切租戶時零快取污染；敏感操作全部寫入 `audit-events`
- **target_users**:
  - 主要：`tenant_admin`（A34/A35）、`super_admin`（A36）
  - 次要：平台營運（A36 計費/訂閱檢視）、財務（訂閱續費）
- **entry_point**:
  - A34: 左側導覽「設定 → 租戶設定 (V3.0)」，僅 `tenant_admin` 以上可見
  - A35: 從 A34 的「品牌」Tab 點擊「開啟完整編輯器」，或直接 deep-link
  - A36: 僅 `super_admin` 登入後，右上角 `TenantSwitcher` 旁出現「超管控制台」入口
- **expected_time_on_page**: A34 5-15 分鐘 / A35 10-30 分鐘（含預覽調整）/ A36 2-20 分鐘（依租戶數量）

---

## [STRUCTURE: SECTIONS]

### 共用結構（A34 / A35 / A36 三頁皆適用）

1. **page_shell**
   - section_type: layout_shell
   - section_purpose: 頂部 AppBar（含 `TenantSwitcher` 超管專屬元件）+ 左側導覽 + 右側內容區

2. **v3_feature_gate**
   - section_type: route_guard
   - section_purpose: 進頁前檢查 `multi_tenant.v3_enabled` feature flag 與使用者角色；不符合直接 redirect 或 404

3. **tenant_safety_banner**
   - section_type: alert_banner（僅 A36 超管切入他租戶時顯示）
   - section_purpose: 提示「您目前以超管身份檢視租戶 {tenant_name}」並提供「回到本我租戶」按鈕

### 子頁面 A34 — 租戶設定 `/admin/settings/tenant`

4. **tenant_settings_tabs**
   - section_type: horizontal_tabs
   - section_purpose: 5 個 Tab 切換：品牌 / 整合 / 定價 / 服務區域 / API 金鑰

5. **tab_brand_summary**
   - section_type: form_panel
   - section_purpose: 品牌設定快覽（Logo 縮圖、色票、AI 客服人設片段），提供「開啟完整編輯器」按鈕跳轉 A35

6. **tab_integrations**
   - section_type: form_panel
   - section_purpose: LINE OA 綁定、金流、Email SMTP、Webhook URL 管理

7. **tab_pricing**
   - section_type: form_panel
   - section_purpose: 價目表、分潤率、SLA 門檻、雙簽金額門檻設定

8. **tab_service_regions**
   - section_type: form_panel
   - section_purpose: 營業區域（台北/新北/...）與服務時段（營業日/時間）

9. **tab_api_keys**
   - section_type: data_table + modal
   - section_purpose: B2B API 金鑰建立、撤銷、查看最後使用時間；**建立時僅顯示一次全文**，之後僅顯示 masked prefix

### 子頁面 A35 — 品牌客製化 `/admin/settings/tenant/brand`

10. **brand_editor_layout**
    - section_type: split_layout
    - section_purpose: 左側編輯器（60%）+ 右側即時預覽沙盒（40%），Desktop 並排、Tablet/Mobile 上下堆疊

11. **brand_logo_upload**
    - section_type: drag_drop_upload
    - section_purpose: Logo 拖放上傳、尺寸/格式驗證、前端壓縮、預覽

12. **brand_color_palette**
    - section_type: color_pickers
    - section_purpose: 主色 / 輔助色 / 強調色選擇（HSL + Hex 雙模式），即時反映至預覽區

13. **brand_ai_persona**
    - section_type: form_group
    - section_purpose: AI 客服暱稱、開場白、術語詞彙表、敏感詞黑名單

14. **brand_line_flex_template**
    - section_type: code_editor + preview
    - section_purpose: LINE Flex Message 範本編輯（JSON Schema 驗證 + 預覽）

15. **brand_preview_sandbox**
    - section_type: iframe_split
    - section_purpose: 分屏顯示 Admin Panel 預覽（上）+ LINE Flex Message 預覽（下），對應元件 `BrandPreviewSandbox`

### 子頁面 A36 — 超管平台 `/admin/super/*`

16. **super_sidebar_nav**
    - section_type: sidebar_nav
    - section_purpose: 超管專屬側邊欄（租戶列表 / 訂閱計費 / 使用量 / 跨租戶 KPI / 新建租戶精靈）

17. **super_tenants_list**
    - section_type: data_table
    - section_purpose: 所有租戶列表，含訂閱等級、使用量、狀態；支援搜尋、狀態篩選、排序

18. **super_create_tenant_wizard**
    - section_type: multi_step_wizard
    - section_purpose: 4 步驟精靈：基本資料 → LINE OA 綁定 → 訂閱方案 → 確認建立

19. **super_tenant_detail_drawer**
    - section_type: side_drawer
    - section_purpose: 點擊租戶後開啟右側抽屜，顯示該租戶的訂閱、使用量、計費紀錄、操作（停用 / 切入檢視 / 升降級）

20. **super_cross_tenant_dashboard**
    - section_type: stats_grid + charts
    - section_purpose: 跨租戶匿名化 KPI 彙總（總 MRR、活躍租戶數、訊息總量、平均回應時間）

---

## [SECTION COMPONENT SPEC]

### Section: page_shell

- **layout**: 頂部 AppBar（`h-16 sticky top-0 z-40 bg-white border-b`）+ 左側導覽（`w-60` Desktop）+ 右側 `flex-1 p-6 bg-[#F8FAFC]`
- **elements**:
  - tenant_switcher: `TenantSwitcher` / required / 僅 `super_admin` 可見，AppBar 右側，`flex items-center gap-2`
    - 下拉顯示所有租戶（帶 search 輸入框、debounce 200ms）
    - 項目格式：`{tenant.display_name} — {plan}`，當前租戶 `bg-blue-50 text-[#2563EB] font-medium`
    - 切換時：`POST /api/v1/super/switch-context { tenant_id }` → 取回短期 token → `queryClient.clear()` → `useTenantStore.reset()` → `router.push('/admin/super/dashboard')`
  - version_badge: Badge / required / `V3.0` 文字 + `bg-purple-100 text-purple-700 text-xs font-mono rounded-full px-2`
  - current_tenant_indicator: Text / required / AppBar 顯示 `目前租戶：{tenant.display_name}`，僅當 `super_admin` 已切入他租戶時顯示
- **states**:
  - default: 一般租戶管理員（`tenant_admin`）看不到 `TenantSwitcher`
  - super_mode: `super_admin` 切入他租戶時，AppBar 底部出現琥珀色細條 `h-1 bg-amber-400` 提示模式
  - loading: `TenantSwitcher` 載入中 Spinner + "切換租戶中..."
  - error: 切換失敗 Toast + 保留原租戶
- **copy_constraints**: 租戶名稱最多 30 字，超過 truncate

### Section: v3_feature_gate

- **layout**: 無 UI 呈現，為 Middleware 層檢查
- **elements**:
  - flag_check: ServerComponent / required /
    - 從 `GET /api/v1/features` 或 JWT payload 讀 `multi_tenant.v3_enabled`
    - false → `notFound()` 回傳 404
  - role_check: ServerComponent / required /
    - A34/A35: 要求 `role === 'tenant_admin' || 'super_admin'`
    - A36: 要求 `role === 'super_admin'`
    - 不符合 → `redirect('/admin/dashboard')` + Toast "您沒有權限訪問此頁面"
- **states**: N/A（純邏輯層）

### Section: tenant_safety_banner

- **layout**: 全寬 Banner，`bg-amber-50 border-amber-200 text-amber-800 rounded-lg p-3 mb-4 flex items-center gap-3`
- **elements**:
  - icon: AlertTriangle / required / `text-amber-600`
  - message: Text / required / "您目前以超管身份檢視租戶：{tenant_name}（{tenant_slug}）— 所有操作將寫入 audit-events"
  - exit_btn: Button Ghost Small / required / "回到本我租戶" / 觸發 `POST /api/v1/super/switch-context { tenant_id: originalTenantId }`
- **states**:
  - default: 僅在 `super_admin` 已切入他租戶時顯示
  - hidden: 未切換時不渲染
- **copy_constraints**: 固定文案，租戶名稱超過 20 字 truncate

---

### 子頁面 A34: 租戶設定 `/admin/settings/tenant`

### Section: tenant_settings_tabs

- **layout**: 水平 Tabs，`border-b border-gray-200 mb-6 flex gap-6`
- **elements**:
  - section_title: H2 / required / "租戶設定" + V3.0 Badge
  - tab_brand: TabItem / required / icon: Palette / "品牌客製" / deep-link `?tab=brand`
  - tab_integrations: TabItem / required / icon: Link / "整合設定" / `?tab=integrations`
  - tab_pricing: TabItem / required / icon: DollarSign / "定價策略" / `?tab=pricing`
  - tab_regions: TabItem / required / icon: MapPin / "服務區域" / `?tab=regions`
  - tab_api_keys: TabItem / required / icon: Key / "API 金鑰" / `?tab=api-keys`
  - dirty_indicator: Badge / optional / 任一 Tab 有未儲存變更時，Tab 名稱旁加 amber `•` 圓點
- **states**:
  - active: `border-b-2 border-[#2563EB] text-[#2563EB] font-medium`
  - inactive: `text-gray-600 hover:text-gray-900`
  - dirty: Tab 名稱旁 `w-1.5 h-1.5 rounded-full bg-amber-500` 點
  - loading: 對應 Tab 內容 Skeleton
- **copy_constraints**: Tab 名稱最多 6 字

### Section: tab_brand_summary

- **layout**: 卡片式佈局，`bg-white rounded-xl p-6 border border-gray-200`
- **elements**:
  - section_title: H3 / required / "品牌客製快覽"
  - logo_preview: Image / required / 當前 Logo 縮圖 `w-20 h-20 object-contain rounded-lg border`
  - color_swatches: ColorSwatches / required / 三個色塊並排顯示主色/輔助色/強調色
  - ai_persona_snippet: Text / required / AI 客服暱稱 + 開場白前 60 字 + "..."
  - open_editor_btn: Button Primary / required / icon: ExternalLink / "開啟完整編輯器" / 跳轉 A35 `/admin/settings/tenant/brand`
  - last_updated: Text Caption / required / "最後更新：{yyyy/MM/dd HH:mm} by {actor}"
- **states**:
  - default: 顯示摘要
  - loading: 欄位 Skeleton
  - empty: 尚未設定任何品牌資料 → 顯示 CTA "開始客製您的品牌"
- **copy_constraints**: AI 人設片段最多 60 字 + 截斷

### Section: tab_integrations

- **layout**: 垂直表單，分區塊（LINE OA / 金流 / Email SMTP / Webhook）
- **elements**:
  - line_oa_section: FormGroup / required / 區塊標題 "LINE 官方帳號"
    - line_channel_id_input: Input / required / "Channel ID" / readonly（由後端 resolve 後不可改）
    - line_channel_secret_input: PasswordInput / required / "Channel Secret" / 顯示 masked，點眼睛 icon 需輸入當前密碼才 reveal
    - line_access_token_input: PasswordInput / required / "Access Token" / 同上
    - test_connection_btn: Button Secondary / "測試連線" / 呼叫 `POST /api/v1/tenants/me/integrations/line/test`
    - webhook_url_display: CodeBlock / required / 顯示平台統一 webhook URL（複製按鈕）
  - payment_section: FormGroup / required / 區塊標題 "金流"
    - provider_select: Select / required / 綠界 / 藍新 / Stripe
    - merchant_id_input: Input / required / "Merchant ID"
    - api_key_input: PasswordInput / required / 同 LINE secret 處理
  - email_section: FormGroup / required / 區塊標題 "Email SMTP"
    - host / port / username / password / from_address 等欄位
  - webhook_section: FormGroup / optional / 區塊標題 "Webhook URL"
    - event_subscriptions: CheckboxGroup / required / 可訂閱事件清單（work_order.created / completed / ...）
    - webhook_url_input: Input / required / `https://...` 格式驗證
    - secret_display: PasswordField / required / HMAC 簽章用 secret，可重新產生
  - save_btn: Button Primary / required / "儲存整合設定" / 需輸入當前密碼確認（sensitive modal）
- **states**:
  - default: 顯示當前設定（secret 皆 masked）
  - dirty: 有變更時 Save 按鈕亮起 + Tab 旁 amber 圓點
  - reveal_secret: 點眼睛 icon → 彈出密碼確認 Modal → 驗證成功後 5 秒內顯示明文 → 自動 re-mask
  - test_connection_success: Toast 綠色 "LINE 連線測試成功"
  - test_connection_fail: Toast 紅色 + 錯誤詳情
  - saving: Save Spinner + "儲存中..."
- **copy_constraints**: 各輸入框 placeholder 最多 40 字

### Section: tab_pricing

- **layout**: 垂直表單，對齊 `tenants.pricing_rules` JSON schema
- **elements**:
  - section_title: H3 / required / "定價策略"
  - base_price_table: DataTable / required / 可編輯的價目表
    - col_service_type: Text / 服務類型（開鎖 / 換鎖 / 保養 / ...）
    - col_base_price: NumberInput / 基礎價格 / min: 0
    - col_urgent_multiplier: NumberInput / 急件倍率 / 0.1-5.0
    - col_actions: IconButton / 刪除列
  - add_service_type_btn: Button Secondary / "新增服務類型"
  - commission_rate_input: NumberInput / required / "技師分潤率 (%)" / 0-100 / step: 0.5
  - sla_thresholds: FormGroup / required / "SLA 門檻"
    - response_time_input: NumberInput / "首次回應 (分鐘)" / default: 30
    - dispatch_time_input: NumberInput / "派工時限 (分鐘)" / default: 120
  - dual_sign_threshold_input: NumberInput / required / "退款雙簽金額門檻 (NT$)" / default: 100000
  - save_btn: Button Primary / required / "儲存定價"
- **states**:
  - default: 顯示當前設定
  - validating: 分潤率超過 100% → 紅色錯誤訊息
  - dirty: Save 按鈕亮起
  - saving: Spinner + "儲存中..."
  - conflict: 另一位 tenant_admin 同時編輯 → 409 → Toast "定價已被其他管理員修改，請重新載入"
- **copy_constraints**: 服務類型名稱最多 20 字

### Section: tab_service_regions

- **layout**: 兩欄：左 Checkbox 行政區選擇 + 右營業時段表
- **elements**:
  - section_title: H3 / required / "服務區域與營業時段"
  - region_checkboxes: CheckboxGroup / required / 台灣行政區（台北市 / 新北市 / ...）以縣市分群
  - selected_regions_badges: BadgeList / required / 已選區域可視化
  - business_hours_grid: WeeklyHoursGrid / required / 七天 × 每天起訖時間 + "公休" 勾選
  - save_btn: Button Primary / required / "儲存服務區域"
- **states**:
  - default: 顯示當前設定
  - empty: 至少需選一個區域 → Save 按鈕 disabled
  - dirty: Save 按鈕亮起
- **copy_constraints**: 區域名稱不可編輯（後端固定列表）

### Section: tab_api_keys

- **layout**: 表格 + 頂部「建立新金鑰」按鈕，對齊 `b2b-api-spec.md`
- **elements**:
  - section_title: H3 / required / "B2B API 金鑰"
  - warning_banner: AlertBanner / required / `bg-amber-50 border-amber-200 text-amber-800 rounded-lg p-3 mb-4`
    - 文案："金鑰僅在建立時顯示一次，請妥善保存。之後僅能看到前綴 `prefix_xxxxxx`。"
  - create_key_btn: Button Primary / required / icon: Plus / "建立新 API 金鑰"
  - api_keys_table: DataTable / required /
    - col_name: Text / required / 金鑰名稱（如 "社區管委會整合"）
    - col_prefix: Text Code / required / `font-mono` / 例 `sk_live_a7b2...` + 複製按鈕
    - col_scopes: BadgeList / required / 權限範圍 Badge（`work-order.read` 等）
    - col_created_at: Text / required / 建立日期
    - col_last_used: Text / required / 最後使用時間 / 若從未使用 `text-gray-400 italic` "從未使用"
    - col_status: StatusBadge / required /
      - active：`bg-green-100 text-green-700` "啟用"
      - revoked：`bg-gray-100 text-gray-500` "已撤銷"
    - col_actions: ActionButtons / required /
      - "撤銷" Button Destructive Small / 需當前密碼確認 + 二次確認
  - create_key_modal: Dialog / required / shadcn/ui `<Dialog>`
    - title: "建立新 API 金鑰"
    - name_input: Input / required / "金鑰名稱" / 最多 40 字
    - scopes_multiselect: MultiSelect / required / 權限範圍勾選（至少選一項）
    - expiry_select: Select / optional / 有效期（30/90/365 天/永久）
    - current_password_input: PasswordInput / required / "當前密碼" / 敏感操作二次驗證
    - confirm_btn: Button Primary / "建立"
    - cancel_btn: Button Ghost / "取消"
  - key_reveal_modal: Dialog / required / 建立成功後強制顯示
    - title: "金鑰建立成功 — 僅顯示一次！"
    - alert: AlertBanner / `bg-red-50 border-red-300 text-red-800` / "請立即複製並妥善保存。關閉此視窗後將無法再查看完整金鑰。"
    - key_display: CodeBlock / required / 完整 API Key `sk_live_abcdef1234567890...` + 「複製」按鈕
    - confirm_copied_checkbox: Checkbox / required / "我已複製並保存此金鑰"（勾選後才能關閉）
    - close_btn: Button Primary / "我已保存，關閉"（disabled 直到 checkbox 勾選）
  - revoke_confirm_modal: Dialog / required /
    - title: "撤銷 API 金鑰"
    - warning: Text / "撤銷後無法復原，使用此金鑰的整合將立即失效"
    - current_password_input: PasswordInput / required / "當前密碼"
    - reason_input: Textarea / required / "撤銷原因（記入 audit-events）" / 最少 10 字
    - confirm_btn: Button Destructive / "確認撤銷"
- **states**:
  - default: 顯示金鑰列表，敏感欄位僅顯示 prefix
  - creating: 建立中 Spinner
  - key_revealed: Reveal Modal 開啟，複製按鈕高亮
  - revoking: 撤銷中 Spinner
  - empty: "尚未建立任何 API 金鑰" + CTA
  - password_error: 密碼錯誤 Toast + 保留 Modal 開啟
- **copy_constraints**: 金鑰名稱最多 40 字，撤銷原因最少 10 字、最多 200 字

---

### 子頁面 A35: 品牌客製化 `/admin/settings/tenant/brand`

### Section: brand_editor_layout

- **layout**: Desktop `grid grid-cols-[60%_40%] gap-6 h-[calc(100vh-4rem)]`，編輯器左、預覽沙盒右；Tablet/Mobile 上下堆疊
- **elements**:
  - editor_container: Main / required / `overflow-y-auto bg-white rounded-xl p-6 border`
  - preview_container: Aside / required / `sticky top-20 rounded-xl bg-gray-100 p-4 border` — `BrandPreviewSandbox` 容器
  - save_floating_bar: FloatingActionBar / required / 底部浮動列（dirty 時顯示）
    - dirty_status: Text / "您有未儲存變更"
    - reset_btn: Button Ghost / "捨棄變更"
    - save_btn: Button Primary / "儲存所有變更"
- **states**:
  - default: 左右並排，預覽區即時反映編輯
  - dirty: 底部浮動列亮起
  - saving: Save 按鈕 Spinner + "儲存中..."
  - saved: Toast "品牌設定已儲存" + 2 秒後 floating bar 隱藏

### Section: brand_logo_upload

- **layout**: 卡片區塊，`bg-white rounded-lg p-4 mb-6 border`
- **elements**:
  - section_title: H3 / required / "品牌 Logo"
  - dropzone: DropZone / required / `border-2 border-dashed border-gray-300 rounded-lg p-8 text-center`
    - 拖曳提示 icon: UploadCloud `w-12 h-12 text-gray-400`
    - 文案："拖放 Logo 圖片至此，或點擊選擇檔案"
    - 限制文案：`text-sm text-gray-500` "PNG / JPG / SVG，最大 2MB，建議正方形 512×512"
  - current_logo_preview: Image / required / 已上傳時顯示 `w-32 h-32 object-contain border rounded-lg`
  - replace_btn: Button Ghost Small / required / "更換 Logo"
  - remove_btn: Button Destructive Small / optional / "移除"
  - favicon_upload: DropZone / optional / "Favicon（選填，32×32 ICO/PNG）"
- **states**:
  - default: 若已有 Logo 顯示預覽；未有則顯示 DropZone
  - dragging_over: DropZone `bg-blue-50 border-blue-400`
  - uploading: 進度條 + "壓縮中..." / "上傳中 {percent}%"
  - validation_error: 紅色訊息 "檔案超過 2MB" / "不支援的格式"
  - compress_in_progress: "前端壓縮中..."（使用 browser-image-compression）
  - upload_success: Toast "Logo 上傳成功" + 預覽區立即更新
- **copy_constraints**: 檔名顯示最多 30 字 truncate

### Section: brand_color_palette

- **layout**: 三個色塊水平排列，`grid grid-cols-3 gap-4 mb-6`
- **elements**:
  - section_title: H3 / required / "色票配置"
  - primary_color_picker: ColorPicker / required / "主色 (Primary)" / 預設 `#2563EB`
    - hex_input: Input / required / `font-mono` / Hex 輸入（#RRGGBB）
    - hsl_sliders: HSLSliders / required / 色相/飽和度/亮度三條滑桿
    - preview_swatch: Swatch / required / `w-full h-16 rounded-lg shadow-inner`
    - contrast_checker: Badge / required / WCAG 對比度檢查
      - AA：`bg-green-100 text-green-700` "AA ✓"
      - AAA：`bg-green-200 text-green-800` "AAA ✓"
      - Fail：`bg-red-100 text-red-700` "對比不足"
  - secondary_color_picker: ColorPicker / required / "輔助色 (Secondary)" / 預設 `#1E293B`
  - accent_color_picker: ColorPicker / required / "強調色 (Accent)" / 預設 `#F59E0B`
  - on_primary_color_picker: ColorPicker / optional / "主色上的文字色" / 預設白
  - reset_defaults_btn: Button Ghost / optional / "重置為預設色票"
- **states**:
  - default: 顯示當前色票
  - picking: Picker 展開 + 滑桿互動
  - realtime_preview: 滑桿變動時 500ms debounce 後更新預覽沙盒
  - low_contrast_warning: AA 未通過 → 紅色 Warning Banner "主色與文字對比度不足，可能影響可讀性"
- **copy_constraints**: 色碼顯示大寫 Hex（#2563EB）

### Section: brand_ai_persona

- **layout**: 垂直表單，`bg-white rounded-lg p-4 mb-6 border`
- **elements**:
  - section_title: H3 / required / "AI 客服人設"
  - agent_name_input: Input / required / "AI 暱稱" / 最多 20 字 / 預設 "AI 客服"
  - agent_persona_textarea: Textarea / required / "AI 人設說明（覆寫預設 system prompt）" / 最少 50 字、最多 2000 字
    - 附字數統計 `{n}/2000`
    - 空白時顯示 placeholder "例：你是專業的電子鎖維修顧問，語氣溫和有耐心..."
  - greeting_template_textarea: Textarea / required / "開場白模板" / 最多 200 字 / 支援變數 `{customer_name}` / `{business_hours}`
  - vocabulary_table: EditableTable / optional / "術語詞彙表"
    - col_term: Input / 術語（例 "貓眼"）
    - col_definition: Input / 說明
    - col_action: IconButton / 刪除
    - add_row_btn: "新增術語"
  - sensitive_words_list: TagInput / optional / "敏感詞黑名單" / 每個詞為一個 Tag，Enter 新增
- **states**:
  - default: 顯示當前人設
  - validating: 人設少於 50 字 → 紅色提示
  - dirty: 浮動 Save bar 亮起
- **copy_constraints**: AI 暱稱最多 20 字，人設 50-2000 字

### Section: brand_line_flex_template

- **layout**: 垂直佈局，`bg-white rounded-lg p-4 mb-6 border`
- **elements**:
  - section_title: H3 / required / "LINE Flex Message 範本"
  - template_type_tabs: Tabs / required / 4 種範本：
    - "工單確認" (work_order_confirm)
    - "派工通知" (dispatch_notify)
    - "完工通知" (completion_notify)
    - "範圍變更確認" (scope_change_confirm)
  - code_editor: CodeEditor / required / Monaco editor, JSON syntax highlighting
    - JSON Schema 驗證（LINE Flex Message spec）
    - 即時錯誤標紅
    - 支援變數 placeholder（如 `{{customer_name}}`）
  - variables_panel: SidePanel / required / 可用變數列表（可點擊插入）
  - reset_template_btn: Button Ghost / optional / "重置為平台預設範本"
  - validate_btn: Button Secondary / "驗證 JSON" / 呼叫 `POST /api/v1/tenants/me/brand/flex/validate`
- **states**:
  - default: 顯示當前範本 JSON
  - invalid_json: 編輯器內紅色底線 + 下方 Error Panel 列出錯誤
  - validating: Spinner + "驗證中..."
  - validation_success: Toast 綠色 "範本格式正確"
  - validation_fail: 紅色 Alert + 詳細錯誤（`{path}: {message}`）
- **copy_constraints**: JSON 無字數限制（滾動）

### Section: brand_preview_sandbox

- **layout**: 垂直分屏，`flex flex-col gap-4 h-full`，對應元件 `BrandPreviewSandbox`
- **elements**:
  - preview_title: H4 / required / "即時預覽" + `Loader2 animate-spin` icon（重整時）
  - preview_tabs: Tabs / required /
    - "Admin Panel" — iframe 載入 `/admin/dashboard?preview_tenant={draft_brand_config_id}`
    - "LINE Flex Message" — 模擬 LINE 聊天 UI（使用 `@line/flex-message-preview` 或自刻）
  - admin_preview_iframe: iframe / required / `w-full h-[50%] rounded-lg border` / 套用 draft 品牌設定
  - line_preview_container: MockPhone / required / `w-full h-[50%]` / iPhone 外框 + LINE 聊天氣泡
    - 顯示 Flex Message 渲染結果
    - 模擬機器人頭像（使用 draft Logo）
    - 切換 Light / Dark mode 開關
  - refresh_btn: IconButton / required / icon: RefreshCw / "重新渲染預覽"
  - device_toggle: ToggleGroup / optional / Desktop / Tablet / Mobile 三種預覽尺寸
- **states**:
  - default: 左側編輯即時（300ms debounce）同步至右側預覽
  - loading: iframe Skeleton + "載入預覽中..."
  - preview_error: iframe 載入失敗 → "預覽暫時不可用，請重試" + 重試按鈕
  - out_of_sync: 編輯器 dirty 但預覽尚未更新 → 預覽區加半透明遮罩 + "重新渲染預覽" 按鈕
- **copy_constraints**: iframe 固定高度 50/50 分屏，不可調整

---

### 子頁面 A36: 超管平台 `/admin/super/*`

### Section: super_sidebar_nav

- **layout**: 左側 `w-60` 固定，`bg-white border-r py-6 px-3 sticky top-16`
- **elements**:
  - super_badge: Badge / required / `bg-purple-100 text-purple-700 font-semibold` "超級管理員" + icon: ShieldCheck
  - nav_tenants: NavItem / required / icon: Building2 / "租戶列表" / path: `/admin/super/tenants`
  - nav_create_tenant: NavItem / required / icon: Plus / "新建租戶" / path: `/admin/super/tenants/new`
  - nav_billing: NavItem / required / icon: Receipt / "訂閱計費" / path: `/admin/super/billing`
  - nav_usage: NavItem / required / icon: Activity / "使用量監控" / path: `/admin/super/usage`
  - nav_analytics: NavItem / required / icon: BarChart3 / "跨租戶 KPI" / path: `/admin/super/analytics`
  - nav_audit_global: NavItem / required / icon: FileSearch / "全局稽核" / path: `/admin/super/audit`
- **states**:
  - active: `bg-purple-50 text-purple-700 font-medium border-l-2 border-purple-500`
  - inactive: `text-gray-600 hover:bg-gray-50`
- **copy_constraints**: 導覽名稱最多 6 字

### Section: super_tenants_list

- **layout**: 全寬，頂部搜尋+篩選列 + DataTable + 右上「新建租戶」CTA
- **elements**:
  - section_title: H2 / required / "租戶列表"
  - stats_summary: StatCards / required / `flex gap-4 mb-4`
    - total_tenants: Card / "租戶總數" + 數量
    - active_tenants: Card / "活躍租戶" / `bg-green-50 text-green-700`
    - suspended_tenants: Card / "已停用" / `bg-gray-50 text-gray-600`
    - trial_tenants: Card / "試用中" / `bg-amber-50 text-amber-700`
  - search_bar: Input / required / icon: Search / placeholder: "搜尋租戶名稱、slug 或 Channel ID..." / debounce 300ms
  - plan_filter: Select / optional / 全部 / Starter / Professional / Business / Enterprise
  - status_filter: Select / optional / 全部 / 活躍 / 試用 / 已停用 / 逾期
  - tenants_table: DataTable / required /
    - col_slug: Text Code / required / `font-mono` / 租戶 slug（例 `taipei-lockking`）
    - col_display_name: Text / required / 顯示名稱
    - col_plan: PlanBadge / required /
      - Starter：`bg-gray-100 text-gray-700` "Starter"
      - Professional：`bg-blue-100 text-blue-700` "Pro"
      - Business：`bg-purple-100 text-purple-700` "Business"
      - Enterprise：`bg-gradient-to-r from-amber-100 to-yellow-100 text-amber-900` "Enterprise"
    - col_usage: UsageBar / required / `{used}/{quota}` 訊息數 + 進度條
      - <70%：綠色
      - 70-90%：琥珀色
      - >90%：紅色 + 脈動
    - col_technicians: Text Number / required / 技師數量
    - col_mrr: Text Number / required / "NT$ {amount}/月"
    - col_expires_at: Text / required / 方案到期日 / 逾期紅字
    - col_status: StatusBadge / required /
      - active：`bg-green-100 text-green-700` "活躍"
      - trial：`bg-amber-100 text-amber-700` "試用"
      - suspended：`bg-gray-100 text-gray-500` "已停用"
      - past_due：`bg-red-100 text-red-700` "逾期"
    - col_actions: ActionButtons / required /
      - "切入檢視" Button Primary Small / 觸發租戶切換流程
      - "詳情" Button Ghost Small / 開啟 Detail Drawer
      - "停用 / 啟用" Button Ghost Small / 需二次確認
  - create_tenant_btn: Button Primary / required / icon: Plus / "新建租戶" / 跳轉 Wizard
- **states**:
  - default: 顯示租戶列表
  - hover: 整列 `bg-purple-50`
  - loading: 10 列 Skeleton + 統計卡 Skeleton
  - empty: "尚無租戶" + 建立 CTA（實務上至少有平台自己一個租戶）
  - quota_warning: 使用量 > 90% 的列左側 `border-l-4 border-amber-500`
  - switching_context: 點擊切入 → 全屏遮罩 "切換至 {tenant_name}..."
- **copy_constraints**: 租戶顯示名稱最多 30 字 truncate

### Section: super_create_tenant_wizard

- **layout**: `max-w-3xl mx-auto`，4 步驟進度指示器 + 主內容區
- **elements**:
  - step_indicator: StepIndicator / required / 4 步驟：基本資料 → LINE OA → 訂閱方案 → 確認
  - step1_basic_info: FormStep / required /
    - slug_input: Input / required / "租戶 slug" / 英數小寫 + 連字號 / 唯一性驗證 `GET /api/v1/super/tenants/check-slug?slug=...`
    - display_name_input: Input / required / "顯示名稱" / 最多 200 字
    - contact_email_input: EmailInput / required / "管理員 Email"
    - contact_phone_input: Input / required / "聯絡電話"
    - owner_name_input: Input / required / "聯絡人姓名"
  - step2_line_oa: FormStep / required /
    - line_channel_id_input: Input / required / "LINE Channel ID"
    - line_channel_secret_input: PasswordInput / required / "Channel Secret" / AES-256 加密後儲存
    - line_access_token_input: PasswordInput / required / "Access Token"
    - test_connection_btn: Button Secondary / "測試 LINE 連線"
    - skip_checkbox: Checkbox / optional / "稍後綁定" / 勾選後本步驟欄位變 optional
  - step3_plan: FormStep / required /
    - plan_cards: PlanCards / required / 四張方案卡（Starter / Professional / Business / Enterprise），可選一
      - 顯示月費、訊息額度、技師數、功能對比
      - 選中時 `ring-2 ring-[#2563EB]`
    - trial_checkbox: Checkbox / optional / "開通 14 天免費試用"
    - custom_quota_input: NumberInput / optional / 僅 Enterprise 顯示 / "自訂訊息額度"
    - billing_cycle_select: Select / required / 月繳 / 年繳（年繳 9 折）
  - step4_confirm: ReviewStep / required /
    - summary_card: 顯示前三步所有選項
    - admin_password_input: PasswordInput / required / "您的管理員密碼" / 敏感操作驗證
    - tos_checkbox: Checkbox / required / "我確認已閱讀並同意服務條款"
    - create_btn: Button Primary / "建立租戶"
  - prev_btn / next_btn: Button / required / 步驟切換
- **states**:
  - default: 步驟 1
  - validating_slug: slug 輸入時 debounce 400ms → 顯示 "檢查中..." → "✓ 可用" / "✗ 已被使用"
  - step_invalid: 必填未填或格式錯 → Next 按鈕 disabled + 行內錯誤
  - submitting: Create 按鈕 Spinner + 步驟指示器全部灰化
  - success: 成功後跳轉至 `/admin/super/tenants/{new_id}` 並 Toast "租戶 {name} 已建立"
  - error: 建立失敗 Toast + 停留在 Step 4
- **copy_constraints**: slug 最多 50 字、顯示名稱最多 200 字

### Section: super_tenant_detail_drawer

- **layout**: 右側抽屜 `w-[720px]`，`fixed right-0 top-16 bottom-0 bg-white border-l shadow-2xl overflow-y-auto`
- **elements**:
  - drawer_header: Header / required / 租戶名稱 + plan Badge + 關閉按鈕
  - tenant_info_section: InfoGrid / required / slug / display_name / created_at / channel_id / owner
  - subscription_section: Card / required /
    - current_plan: Badge / required
    - mrr: Text / required / "NT$ {amount}/月"
    - next_billing_date: Text / required
    - upgrade_btn: Button Primary / "升降級方案" / 開啟方案切換 Modal
  - usage_section: Card / required /
    - message_usage: ProgressBar / required / `{used}/{quota}` 訊息數
    - technician_count: Text / required / 技師數 / 方案上限
    - storage_usage: ProgressBar / required / 媒體儲存空間
    - api_calls_today: Text / required / 今日 API 呼叫次數
    - usage_chart: LineChart / required / 過去 30 天使用量趨勢
  - billing_history_section: DataTable / required / 近 12 個月帳單
    - col_invoice_no / col_period / col_amount / col_status / col_download
  - danger_zone: Card Destructive / required / `bg-red-50 border-red-200`
    - suspend_tenant_btn: Button Destructive / "停用租戶" / 需二次確認 + 輸入 slug 驗證
    - delete_tenant_btn: Button Destructive / optional / "永久刪除" / 需超管密碼 + 輸入 slug 三次確認 / 僅無資料時可刪
  - close_btn: IconButton / required / icon: X / 關閉抽屜
- **states**:
  - default: 抽屜開啟動畫 `transition-transform duration-300 translate-x-0`
  - loading: 各區塊 Skeleton
  - suspending: 停用中 Spinner + "處理中..."
  - error: 載入租戶詳情失敗 → Error State + 重試
- **copy_constraints**: 抽屜 header 租戶名稱最多 40 字

### Section: super_cross_tenant_dashboard

- **layout**: 網格佈局 `grid grid-cols-1 lg:grid-cols-3 gap-6`
- **elements**:
  - section_title: H2 / required / "跨租戶 KPI（匿名化）"
  - disclaimer: Text Caption / required / `text-gray-500` "所有數據已匿名化處理，不包含任何租戶可識別資訊"
  - kpi_cards: StatCards / required /
    - total_mrr: Card / "總 MRR" / NT$ {amount}
    - active_tenants: Card / "活躍租戶數" / {count}
    - total_work_orders: Card / "總工單量（30d）"
    - avg_response_time: Card / "平均首次回應時間"
    - total_messages: Card / "AI 總訊息量（30d）"
    - churn_rate: Card / "月流失率" / 百分比
  - mrr_trend_chart: LineChart / required / 過去 12 個月 MRR 趨勢
  - plan_distribution_chart: DonutChart / required / 方案分佈（Starter/Pro/Business/Enterprise 佔比）
  - top_regions_chart: BarChart / required / Top 10 服務區域（匿名化為「區域 A / B / C」）
  - usage_heatmap: HeatMap / required / 租戶使用量分佈 × 時段
- **states**:
  - default: 顯示所有圖表
  - loading: 各圖表 Skeleton
  - empty: 新平台初期 < 3 租戶時顯示 "數據樣本不足，最少需 3 個租戶才顯示 KPI" （避免反匿名化）
  - export_csv_btn: Button Ghost / optional / "匯出 KPI 報表 (CSV)"
- **copy_constraints**: 圖表標題最多 20 字

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

#### A34 租戶設定
1. 進入頁面 → `v3_feature_gate` 檢查 `multi_tenant.v3_enabled` + `role === tenant_admin || super_admin`
2. 載入 `GET /api/v1/tenants/me` → 分發到各 Tab 的初始資料
3. 切換 Tab → URL query 更新 `?tab=brand` → 各 Tab 獨立 dirty state
4. 編輯任一欄位 → Tab 名稱旁出現 amber 圓點
5. 點擊儲存 →（若為 integrations/pricing/api-keys）彈出「當前密碼確認」Modal → 驗證 → `PUT /api/v1/tenants/me/{scope}` → 成功 Toast + 清除 dirty → 寫入 `audit-events`
6. 建立 API 金鑰 → Create Modal → 輸入名稱+scopes+當前密碼 → `POST /api/v1/tenants/me/api-keys` → Reveal Modal 強制顯示一次 → 勾選「已保存」才能關閉

#### A35 品牌客製化
1. 進入頁面 → 載入 `GET /api/v1/tenants/me/brand` → draft 狀態與 published 狀態共存（draft 只在本頁 preview，不影響正式環境）
2. 上傳 Logo → DropZone 接收檔案 → 前端壓縮（browser-image-compression）→ `POST /api/v1/tenants/me/brand/assets` (multipart) → 回傳 URL → 更新 draft + 預覽沙盒 refresh
3. 調整色票 → HSL 滑桿變動 → 500ms debounce → 更新 draft → `BrandPreviewSandbox` 透過 postMessage 注入新 CSS 變數
4. 編輯 LINE Flex JSON → 即時 JSON Schema 驗證 → 無誤則右側 MockPhone 更新渲染
5. 點擊「儲存所有變更」→ `PUT /api/v1/tenants/me/brand` → 成功後整站 `applyBrandConfig()` + Toast + `queryClient.invalidateQueries(['tenant', tenantId, 'brand'])`
6. 捨棄變更 → 重置 draft 至 last-published state

#### A36 超管平台
1. 進入頁面 → `v3_feature_gate` 要求 `role === 'super_admin'` → 載入 `GET /api/v1/super/tenants`
2. 搜尋/篩選 → query 更新 + debounce 300ms → 表格重新查詢
3. 點擊「切入檢視」→ `POST /api/v1/super/switch-context { tenant_id }` → 取回短期 token → `useTenantStore.reset() + queryClient.clear()` → `router.push('/admin/dashboard')` → 頁頂顯示 `tenant_safety_banner`
4. 點擊「新建租戶」→ Wizard 4 步驟 → Step 1 slug 即時唯一性驗證 → Step 4 輸入超管密碼 + 同意 TOS → `POST /api/v1/super/tenants` → 成功跳轉新租戶詳情
5. 打開租戶 Detail Drawer → 檢視訂閱/使用量/帳單 → 停用租戶需輸入 slug 驗證（防誤操作）
6. Cross-Tenant Dashboard → `GET /api/v1/super/analytics` → 載入匿名化 KPI → 圖表渲染

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | A34 水平 Tabs / A35 左右並排（60/40）/ A36 側欄+表格+Drawer | 完整體驗 |
| Tablet (768-1279px) | A34 Tabs 不變 / A35 上下堆疊（編輯器上 / 預覽下，各 50vh）/ A36 側欄收合為頂部下拉 | 預覽區 sticky `top-0` |
| Mobile (<768px) | A34 Tabs 橫向捲動 / A35 預覽區變為底部浮動按鈕 "預覽"（點開全屏 Modal）/ A36 表格轉卡片列表，Drawer 變為全屏 Modal | 色票編輯改為分頁 Step |

### 資料更新策略

- A34 各 Tab：`staleTime: 300_000`（5 分鐘），手動儲存後 invalidate
- A35 品牌預覽：draft 狀態僅 client-side，儲存後觸發整站 `applyBrandConfig()` 並廣播 `window.postMessage({ type: 'brand-updated' })`
- A36 租戶列表：`refetchInterval: 60_000`（60 秒自動更新使用量），其他欄位 `staleTime: 120_000`
- A36 Cross-Tenant KPI：`staleTime: 600_000`（10 分鐘，減少計算成本）
- A36 使用量趨勢圖：每次切換租戶重新載入，不共用快取
- **切換租戶時強制 `queryClient.clear()`**，避免跨租戶快取污染

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - **A34 租戶設定**:
    - GET `/api/v1/tenants/me` — 取得當前租戶完整設定
      - Response: `{ id, slug, display_name, brand_config, integrations, pricing_rules, service_areas, business_hours, plan, plan_expires_at, monthly_message_quota, monthly_message_used }`
    - PUT `/api/v1/tenants/me` — 更新基本資訊（僅 tenant_admin）
      - Body: `{ display_name?, service_areas?, business_hours? }`
    - PUT `/api/v1/tenants/me/integrations` — 更新整合設定
      - Body: `{ line?, payment?, email_smtp?, webhook? }`
      - Headers: `X-Current-Password` (sensitive operation)
    - PUT `/api/v1/tenants/me/pricing` — 更新定價策略
      - Body: `{ base_price_table, commission_rate, sla_thresholds, dual_sign_threshold }`
    - GET `/api/v1/tenants/me/api-keys` — 列出 API 金鑰（僅 prefix）
      - Response: `{ data: { id, name, prefix, scopes, created_at, last_used_at, status }[] }`
    - POST `/api/v1/tenants/me/api-keys` — 建立新 API 金鑰
      - Body: `{ name, scopes: string[], expires_in_days?: number }`
      - Headers: `X-Current-Password`
      - Response: `{ id, name, full_key: string /* 僅此次回傳 */, prefix, scopes }`
    - DELETE `/api/v1/tenants/me/api-keys/{id}` — 撤銷金鑰
      - Body: `{ reason: string }`
      - Headers: `X-Current-Password`
    - POST `/api/v1/tenants/me/integrations/line/test` — 測試 LINE 連線
  - **A35 品牌客製**:
    - GET `/api/v1/tenants/me/brand` — 取得品牌設定
      - Response: `{ logo_url, favicon_url, primary_color, secondary_color, accent_color, on_primary_color, agent_name, agent_persona, greeting_template, vocabulary: [], sensitive_words: [], line_flex_templates: { [type]: object } }`
    - PUT `/api/v1/tenants/me/brand` — 儲存品牌設定（整體 upsert）
      - Body: 同 GET response
    - POST `/api/v1/tenants/me/brand/assets` — 上傳 Logo/Favicon (multipart)
      - Body: `FormData { file, asset_type: "logo" | "favicon" }`
      - Response: `{ url, width, height, size_bytes }`
    - POST `/api/v1/tenants/me/brand/flex/validate` — 驗證 LINE Flex JSON
      - Body: `{ template_type, template: object }`
      - Response: `{ valid: boolean, errors?: { path, message }[] }`
  - **A36 超管平台**:
    - GET `/api/v1/super/tenants` — 租戶列表（需 `super_admin`）
      - Query: `search`, `plan`, `status`, `page`, `limit`, `sort_by`
      - Response: `{ data: Tenant[], total, summary: { total, active, suspended, trial } }`
    - GET `/api/v1/super/tenants/check-slug?slug=xxx` — slug 唯一性檢查
      - Response: `{ available: boolean }`
    - POST `/api/v1/super/tenants` — 建立新租戶（精靈提交）
      - Body: `{ basic_info, line_oa, plan, billing_cycle, trial, custom_quota? }`
      - Headers: `X-Current-Password`
    - GET `/api/v1/super/tenants/{tenant_id}` — 租戶詳情
    - GET `/api/v1/super/tenants/{tenant_id}/usage` — 使用量
      - Query: `period` (7d|30d|90d)
      - Response: `{ messages: TimeSeriesPoint[], technicians, storage_bytes, api_calls_today }`
    - GET `/api/v1/super/tenants/{tenant_id}/billing` — 帳單歷史
      - Response: `{ invoices: Invoice[], next_billing_date, mrr }`
    - PATCH `/api/v1/super/tenants/{tenant_id}` — 升降級、停用、啟用
      - Body: `{ plan?, status?, monthly_message_quota? }`
    - DELETE `/api/v1/super/tenants/{tenant_id}` — 永久刪除（僅無資料時）
      - Body: `{ slug_confirmation: string }` (三次輸入驗證)
      - Headers: `X-Current-Password`
    - POST `/api/v1/super/switch-context` — 超管切換租戶檢視
      - Body: `{ tenant_id: string }`
      - Response: `{ context_token: string, tenant: TenantConfig }`
    - GET `/api/v1/super/analytics` — 跨租戶匿名 KPI
      - Query: `period`
      - Response: `{ total_mrr, active_tenants, total_work_orders, avg_response_time_sec, total_messages, churn_rate, mrr_trend: [], plan_distribution: {}, top_regions: [], usage_heatmap: [][] }`
      - **樣本不足（< 3 租戶）時回 `{ error: "insufficient_samples" }`，前端顯示 empty state**
- **Zustand Stores**:
  - `useTenantStore`: `{ currentTenant, originalTenant, setCurrentTenant, reset }` — 持有當前檢視的租戶與本我租戶
  - `useMultiTenantSettingsStore`: 管理 A34 五個 Tab 的 dirty state
  - `useBrandDraftStore`: A35 的 draft 品牌設定（不送出前僅存 client）
  - `useSuperAdminStore`: A36 的租戶列表篩選、wizard 步驟狀態
- **TanStack Query Keys**（V3.0 強制租戶前綴）:
  - `['tenant', tenantId, 'settings']`
  - `['tenant', tenantId, 'brand']`
  - `['tenant', tenantId, 'api-keys']`
  - `['super', 'tenants', filters]`
  - `['super', 'tenant', targetTenantId, 'usage', period]`
  - `['super', 'analytics', period]`
- **error_cases**:
  - 網路錯誤：Toast "網路連線異常" + TanStack Query 自動重試
  - 權限不足（403）：未登入或非 `tenant_admin` / `super_admin` → redirect `/admin/dashboard` + Toast "無權限"
  - V3.0 未啟用（404 feature flag）：`notFound()` 回傳 404 頁
  - 密碼驗證失敗（401 on sensitive endpoint）：Modal 保留開啟 + 紅字 "密碼錯誤"
  - Slug 已被使用（409 on create_tenant）：Step 1 即時顯示 "此 slug 已被使用"
  - LINE 連線測試失敗：Toast 紅色 + 詳細錯誤（Channel ID/Secret 不符等）
  - API 金鑰名稱重複（409）：Modal 顯示 "相同名稱已存在"
  - Brand JSON Schema 錯誤（422）：CodeEditor 內紅底標紅 + 錯誤 Panel 列出 path/message
  - 租戶切換失敗（403）：Toast "無權切換至此租戶" + 保留原租戶
  - 租戶切換 tenant-id-mismatch（前端偵測）：強制登出 + Sentry 告警（對齊 `assertTenantMatch`）
  - 跨租戶 KPI 樣本不足：Empty State "數據樣本不足，最少需 3 個租戶"
  - 停用租戶時仍有進行中工單（409）：Toast "該租戶有 {n} 筆未結工單，無法停用" + 提供連結跳轉
  - 刪除租戶 slug 驗證失敗：Modal 紅字 "輸入不符"

---

## [EXCEPTION TO GLOBAL RULES]

- **V3.0 Feature Flag 強制守衛**：本頁面群所有路由在 Middleware 層額外檢查 `multi_tenant.v3_enabled`，失敗直接 404（不導向登入頁），違反 Global 的「未授權一律導向 `/login`」規則
- **強制租戶隔離前綴**：A34/A35/A36 所有 TanStack Query Key 必須以 `['tenant', tenantId, ...]` 或 `['super', ...]` 開頭，違反 Global 可省略 tenant 前綴的預設
- **切換租戶時強制 `queryClient.clear()`**：違反 Global 「盡量保留快取以加速」原則，此處為安全優先
- **API 金鑰建立後強制 Reveal Modal 單次顯示**：違反 Global 「敏感資訊一律 masked」，此處平台協定為「僅此次可見」
- **Danger Zone 三次 slug 確認**：刪除租戶需輸入 slug 三次，違反 Global 「二次確認足矣」，原因為此操作影響所有租戶使用者資料
- **A35 品牌預覽使用 iframe + postMessage 注入**：違反 Global 「單一 SPA context」，為隔離 draft 品牌與正式環境需要
- **A36 Cross-Tenant KPI 需 ≥ 3 租戶**：樣本不足時強制不顯示，違反 Global 「資料永遠要顯示」，防止反匿名化攻擊
- **V3.0 版本 Badge 與紫色超管標記**：顏色系統新增紫色（#8B5CF6 / purple-500）作為「超管專屬」語意色，不在 Global Design System 原始三色內（Primary Blue / Accent Amber / Secondary Slate）
- **超管切入他租戶時頁頂持久 banner + 琥珀條紋**：違反 Global 「不干擾主視覺」，此為安全操作提示

---

## [ACCEPTANCE CRITERIA]

### 共用（A34 / A35 / A36）
- [ ] 所有頁面進入前 Middleware 檢查 `multi_tenant.v3_enabled` feature flag
- [ ] A34/A35 要求 `tenant_admin` 或 `super_admin`、A36 僅限 `super_admin`
- [ ] 側邊欄入口對未授權角色自動隱藏（透過 `useHasPermission`）
- [ ] 所有 TanStack Query Key 含 tenant 前綴
- [ ] 所有敏感操作（integrations / pricing / api-keys / 停用 / 刪除）寫入 `audit-events`
- [ ] V3.0 Badge 在 AppBar 顯示
- [ ] RWD 三斷點佈局正確

### A34 租戶設定
- [ ] 5 個 Tab（brand / integrations / pricing / regions / api-keys）URL 同步
- [ ] 各 Tab 獨立 dirty state，未儲存變更在 Tab 名稱顯示 amber 圓點
- [ ] 敏感 Tab（integrations / pricing / api-keys）儲存需輸入當前密碼
- [ ] Integrations 的 secret 預設 masked，點眼睛 icon 需密碼驗證 + 5 秒後自動 re-mask
- [ ] API 金鑰建立成功後顯示 Reveal Modal，勾選「已保存」才能關閉
- [ ] API 金鑰列表僅顯示 prefix（`sk_live_xxxx...`）
- [ ] API 金鑰撤銷需當前密碼 + 撤銷原因（最少 10 字）
- [ ] LINE 連線測試功能正常
- [ ] 定價分潤率驗證 0-100%，雙簽門檻預設 NT$100,000

### A35 品牌客製化
- [ ] Logo 拖放上傳限制 2MB / PNG/JPG/SVG
- [ ] 前端圖片壓縮（browser-image-compression）成功
- [ ] 主色 + 文字色 WCAG AA 對比度檢查，未通過顯示 Warning
- [ ] HSL + Hex 色票選擇器雙模式可切換
- [ ] AI 人設最少 50 字、最多 2000 字，字數統計即時
- [ ] 術語詞彙表可新增/刪除列
- [ ] LINE Flex Message 4 種範本（work_order_confirm / dispatch_notify / completion_notify / scope_change_confirm）
- [ ] JSON Schema 即時驗證 + 錯誤高亮
- [ ] `BrandPreviewSandbox` 左右分屏：Admin Panel iframe + LINE MockPhone
- [ ] 預覽區 500ms debounce 後更新
- [ ] 儲存成功後整站 `applyBrandConfig()` + 廣播事件
- [ ] 捨棄變更可重置為 last-published
- [ ] Desktop 60/40 左右分屏、Tablet 上下堆疊、Mobile 預覽為全屏 Modal

### A36 超管平台
- [ ] 僅 `super_admin` 可見超管側欄（紫色標記）
- [ ] 租戶列表顯示 plan badge、使用量進度條（>90% 紅色脈動）、MRR、狀態
- [ ] 搜尋支援 display_name / slug / channel_id
- [ ] 新建租戶精靈 4 步驟，slug 即時唯一性驗證
- [ ] 精靈 Step 4 需輸入超管密碼 + 勾選 TOS
- [ ] `TenantSwitcher` 切換時呼叫 `/super/switch-context` → `queryClient.clear()` → reset Zustand → 重載
- [ ] 超管切入他租戶時頁頂顯示 `tenant_safety_banner` + 琥珀條紋
- [ ] 前端 `assertTenantMatch` 偵測 tenant_id 不符時強制登出 + Sentry 告警
- [ ] 租戶詳情 Drawer 顯示訂閱/使用量/帳單歷史
- [ ] 停用租戶需輸入 slug 驗證
- [ ] 永久刪除需超管密碼 + 輸入 slug 三次 + 租戶無資料
- [ ] 跨租戶 KPI 顯示匿名化數據 + disclaimer
- [ ] 樣本不足（< 3 租戶）時 Empty State，不顯示任何 KPI

### 安全與隔離（CRITICAL）
- [ ] 切換租戶時 `queryClient.clear()` + `useTenantStore.reset()` 必須執行，否則視為 P0 bug
- [ ] 所有 API 請求 `X-Tenant-ID` header 由 Middleware 注入
- [ ] 所有 API 回應 `assertTenantMatch` 驗證，不符觸發安全事件
- [ ] API 金鑰全文僅於建立時單次回傳，後端不留明文
- [ ] Channel Secret / Access Token 後端 AES-256 加密儲存
- [ ] 超管切入他租戶的 token 為短期（≤ 30 分鐘）且在 `audit-events` 留下紀錄

### 效能與規範
- [ ] A34 首次載入 < 2 秒
- [ ] A35 品牌預覽首次渲染 < 3 秒
- [ ] A36 租戶列表（100 筆以內）< 2 秒
- [ ] Cross-Tenant KPI 圖表載入 < 3 秒
- [ ] 符合 Design System 視覺規範（Primary #2563EB、Accent #F59E0B、Secondary #1E293B、BG #F8FAFC、Font Inter + Noto Sans TC）
- [ ] 超管紫色（#8B5CF6 / purple-500）僅用於超管專屬元件（Badge / 側欄 / TenantSwitcher），不滲入其他業務 UI
- [ ] V3.0 feature flag 關閉時，側邊欄入口完全消失，路由 404

---

## [T1.5 §6.26 補漏] A34 租戶設定 — 欄位/區域/Key 細節

**定價分頁具體欄位：**
- SLA 門檻：`response_sla_minutes` (15-120)、`arrival_sla_hours` (1-24)、`completion_sla_hours` (2-72)
- 雙簽金額門檻：`refund_dual_sign_threshold_twd`（預設 5,000）、`refund_triple_sign_threshold_twd`（預設 100,000）
- 退款率上限：`max_refund_rate_monthly_percent`（預設 5）超過告警 `operations_manager`
- 分潤率：`technician_commission_base_percent`（0-100）+ S 級加成 `level_s_bonus_percent`

**服務區域分頁（新 Tab）：**
- 區域選擇：行政區（縣市 / 鄉鎮市區）多選 + 地圖視覺化
- 服務時段：週七天 × 時段矩陣，支援跨日（22:00-02:00）
- 假日規則：國定假日 toggle（自動抓農曆春節、端午、中秋）+ 自訂休假日
- 離島 / 山區：獨立勾選欄 + 加成費率

**API 金鑰 Masked Prefix：**
- 格式：`sk_live_{first4}...{last4}`（例 `sk_live_abcd...9876`）
- 建立時彈窗顯示完整 Key 一次 + 複製按鈕 + 「我已保存，關閉後無法再顯示」確認 checkbox
- 管理介面：Masked prefix + 建立時間 + 最後使用 + 狀態（active / rotating / revoked）

---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
