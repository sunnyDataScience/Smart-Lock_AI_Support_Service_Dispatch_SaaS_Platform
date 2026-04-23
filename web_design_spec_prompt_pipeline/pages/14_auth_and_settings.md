# Page-Level Prompt: 認證與系統設定（3 個頁面）

> 對應 `guides/vibe_coding_build_strategy.md` → Step 5。
> 本檔合併三個密切相關的頁面：管理員登入（A0）、技師登入（T0）、管理員系統設定（A16）。三者共享 Design System、驗證規則、安全策略（httpOnly Cookie、RBAC、稽核），但使用情境、裝置類型與操作深度差異顯著，採「共用 meta + 分頁覆蓋」撰寫。

---

## [PAGE META]

### 共用屬性（三頁一致）

- **design_system**: Primary `#2563EB`、Accent `#F59E0B`、Secondary `#1E293B`、BG `#F8FAFC`、Font `Inter + Noto Sans TC`
- **framework**: Next.js 14+ App Router + shadcn/ui + Tailwind CSS + React Hook Form + Zod
- **auth_storage**: JWT 存於 httpOnly Cookie（`access_token` + `refresh_token`），`Secure` + `SameSite=Strict`
- **tenant_header**: 所有登入後的 API 請求帶 `X-Tenant-ID`（由 Next.js Middleware 自 `tenant_id` Cookie 注入）

### A0 `/login` — 管理員登入頁

- **page_name**: 管理員登入 Admin Login
- **route_path**: `/login`
- **page_type**: auth（無側邊欄佈局）
- **primary_goal**: 管理員身分驗證，成功後導向 `/dashboard`
- **secondary_goal**: 多租戶情境下選擇/解析正確的租戶 context；MFA 通過後寫入稽核
- **target_users**:
  - 主要：平台管理員、租戶管理員、審核員、財務、調度員（桌面瀏覽器）
  - 次要：超級管理員（跨租戶切換於登入後執行）
- **entry_point**: 直接輸入網址 `/login` / 未登入者被 Middleware 重導 / 從 email 密碼重設連結返回
- **expected_time_on_page**: 15–45 秒（含 MFA 則 30–90 秒）

### T0 `/tech-login` — 技師登入頁

- **page_name**: 技師登入 Tech Login
- **route_path**: `/tech-login`
- **page_type**: auth（Mobile-First 全螢幕）
- **primary_goal**: 技師以手機號碼 + 密碼快速登入，成功後導向 `/pool`
- **secondary_goal**: V2.0 支援 SMS OTP 雙因素；觸控友善、單手操作
- **target_users**:
  - 主要：簽約外派技師（行動裝置為主，iOS/Android 瀏覽器）
  - 次要：無（不供管理員使用）
- **entry_point**: 技師掃 QR Code / 直接輸入網址 / 未登入者被 Middleware 重導
- **expected_time_on_page**: 10–30 秒

### A16 `/settings` — 管理員系統設定

- **page_name**: 系統設定 Admin Settings
- **route_path**: `/settings`
- **page_type**: tabbed_settings（左側 Tabs + 右側內容）
- **primary_goal**: 讓管理員維護個人帳號、帳戶安全、報價規則與加價規則
- **secondary_goal**: 敏感操作（變更密碼、修改規則）全部寫入稽核日誌；規則異動影響下一筆新工單報價
- **target_users**:
  - 主要：租戶管理員（擁有 `settings.write` 權限）
  - 次要：財務主管（僅能看報價/加價規則的讀取檢視）
- **entry_point**: 頂部導航右上角「頭像下拉 → 系統設定」/ 左側主導覽底部「設定」
- **expected_time_on_page**: 2–10 分鐘（視調整規則複雜度）

---

## [STRUCTURE: SECTIONS]

### A0 管理員登入頁

1. **auth_shell** — section_type: layout_shell — 全頁置中卡片 + 品牌背景
2. **brand_header** — section_type: hero — Logo + 平台名稱
3. **tenant_selector** — section_type: form_field — 多租戶環境下選擇租戶（條件渲染）
4. **login_form** — section_type: form — Email / Password / Remember Me / Submit
5. **auxiliary_links** — section_type: links — 忘記密碼 + 技師登入入口
6. **mfa_challenge** — section_type: form（條件顯示）— MFA OTP 驗證步驟
7. **footer_legal** — section_type: footer — 版權、隱私權、服務條款

### T0 技師登入頁

1. **mobile_auth_shell** — section_type: layout_shell — 全螢幕單欄、安全區域適配
2. **brand_header_mobile** — section_type: hero — Logo + 「技師工作台」標題
3. **tech_login_form** — section_type: form — 手機號 / 密碼 / 大按鈕
4. **otp_challenge** — section_type: form（條件顯示，V2.0）— SMS OTP 6 位數驗證
5. **mobile_footer** — section_type: footer — 忘記密碼 / 聯絡客服 / App 版本

### A16 系統設定（Tabs 多頁合一）

1. **page_shell** — section_type: layout_shell — 左側 Tab 垂直導覽 + 右側內容
2. **settings_nav** — section_type: sidebar_nav — 四分頁切換
3. **tab_profile** — section_type: form — 個人資料（頭像、姓名、email、手機）
4. **tab_security** — section_type: form — 密碼變更、MFA、Session 列表
5. **tab_pricing_rules** — section_type: rule_editor — 報價規則 V2.0
6. **tab_surcharge_rules** — section_type: rule_editor — 加價規則 V2.0

---

## [SECTION COMPONENT SPEC]

---

### 頁面 1: A0 `/login` 管理員登入

### Section: auth_shell

- **layout**: `min-h-screen flex items-center justify-center bg-gradient-to-br from-[#F8FAFC] via-white to-blue-50 px-4`；中央卡片 `w-full max-w-md bg-white rounded-2xl shadow-xl p-8`
- **elements**:
  - container: Main / required / `role="main"` / aria-labelledby 連結到 brand_header 標題
  - card: Card / required / `<form>` 包裝整張卡，Enter 鍵觸發提交
- **states**:
  - default: 淡入動畫 `animate-in fade-in slide-in-from-bottom-4 duration-300`
  - loading: 卡內 Skeleton（Logo + 2 field + button）
- **copy_constraints**: 卡片內無額外文案

### Section: brand_header

- **layout**: 垂直置中，`flex flex-col items-center gap-2 mb-8`
- **elements**:
  - logo_image: Image / required / 48×48px / `next/image`，`priority` 預載
  - product_name: H1 / required / 「Smart Lock 智慧派工平台」/ `text-2xl font-semibold text-[#1E293B]`
  - subtitle: Text / required / 「管理後台登入」/ `text-sm text-gray-500`
- **states**:
  - default: 靜態顯示
- **copy_constraints**: 平台名稱 ≤ 20 字，副標題 ≤ 10 字

### Section: tenant_selector

- **layout**: 條件渲染 — 僅在使用者 email 對應多個租戶、或超管登入時顯示；`mb-4`
- **elements**:
  - tenant_label: Label / required / 「選擇組織」/ `text-sm font-medium text-gray-700`
  - tenant_select: Select / required / shadcn/ui `<Select>` / placeholder: 「請選擇您要登入的組織」
    - 選項來源：使用者輸入 email 後 debounce 500ms 呼叫 `POST /api/v1/auth/resolve-tenant { email }`，回傳 `{ tenants: [{ id, name, logo_url }] }`
    - 若回傳單一租戶：自動選取並隱藏本 section（靜默 autopick）
    - 若回傳 0 個：顯示下方 error state「查無此 email 所屬組織」
    - 若回傳 >1 個：展開讓使用者選擇
  - tenant_helper_text: Text Caption / optional / 「同一 email 若屬多個組織，請先選擇要登入的組織」
- **states**:
  - default: 隱藏（單租戶）/ 顯示下拉（多租戶）
  - loading: 解析租戶中，Input 右側 Spinner 16×16px
  - error: 紅色訊息 `text-sm text-red-600 mt-1`
  - disabled: 表單提交中 disabled
- **copy_constraints**: Label 最多 6 字，helper 最多 30 字

### Section: login_form

- **layout**: 垂直表單 `flex flex-col gap-4`；每個 field 高 `h-11`，字級 `text-base`
- **elements**:
  - email_field: FormField / required /
    - Label「電子郵件」`text-sm font-medium text-gray-700`
    - Input `type="email"` / `autocomplete="username"` / placeholder 「your@company.com」
    - Zod 驗證：`z.string().email('請輸入有效的 Email 格式')`
    - 即時驗證 onBlur
    - 錯誤訊息以 `aria-describedby` 連結
  - password_field: FormField / required /
    - Label「密碼」
    - Input `type="password"` / `autocomplete="current-password"`
    - 右側 IconButton 眼睛 icon 切換明/暗文（Tab 可達）
    - Zod：`z.string().min(8, '密碼至少 8 碼')`
  - remember_me_checkbox: Checkbox / optional / Label「記住我（30 天）」
    - 勾選時 Cookie `max-age` 30 天，否則 session cookie（關閉瀏覽器失效）
    - 共用裝置警告 Tooltip：「請勿在公用電腦勾選」
  - submit_button: Button / required / Primary / full width / `h-11` / 文字「登入」
    - loading 時 Spinner + 「登入中…」+ disabled
    - 未通過驗證時 disabled（`form.formState.isValid === false`）
  - inline_error_banner: Alert / conditional /
    - 登入失敗顯示於表單頂部 `bg-red-50 border border-red-200 text-red-700 rounded-md p-3 mb-2`
    - 不同錯誤碼對應文案（見 error_cases）
- **states**:
  - default: 兩欄位空白，Submit disabled
  - valid: Submit 啟用
  - submitting: Submit Spinner + 「登入中…」+ 所有 field readonly
  - error_401: 顯示「電子郵件或密碼錯誤」+ 計數本次失敗次數（前端僅顯示提示，次數由後端回傳）
  - error_423_locked: 顯示「帳號已鎖定 15 分鐘（連續失敗 5 次）」+ 倒數計時器，Submit 永久 disabled 直到倒數結束
  - error_network: 顯示「網路連線異常，請重試」+ 重試按鈕
  - mfa_required: 整個 form disable，下方 mfa_challenge section 展開
- **copy_constraints**:
  - Label ≤ 6 字
  - placeholder ≤ 30 字
  - Button 文字 ≤ 4 字
  - 錯誤訊息 ≤ 40 字

### Section: auxiliary_links

- **layout**: 水平排列 `flex items-center justify-between mt-4 text-sm`
- **elements**:
  - forgot_password_link: Link / required / 「忘記密碼？」/ `text-[#2563EB] hover:underline` / 導向 `/forgot-password`
  - tech_login_link: Link / optional / 「我是技師」/ `text-gray-500 hover:text-[#2563EB]` / 導向 `/tech-login`
- **states**:
  - default: 正常連結
  - hover: 主色底線
  - focus: `ring-2 ring-[#2563EB]/40` 鍵盤可見焦點環
- **copy_constraints**: 每個連結文字 ≤ 8 字

### Section: mfa_challenge

- **layout**: 條件渲染 — 後端回傳 `{ mfa_required: true, mfa_token }` 時替換 login_form 內容；`flex flex-col gap-4`
- **elements**:
  - mfa_title: H3 / required / 「雙因素驗證」/ `text-lg font-semibold`
  - mfa_description: Text / required / 「請輸入您 Authenticator App 的 6 位數驗證碼」/ `text-sm text-gray-500`
  - otp_input: OTPInput / required / shadcn/ui `<InputOTP>` / 6 格 / 僅接受數字 / 自動聚焦下一格
  - otp_countdown: Text Caption / required / 「驗證碼有效時間：{mm:ss}」/ 倒數至 0 時 disable input 並顯示重送按鈕
  - resend_btn: Button Ghost / optional / 「重新傳送驗證碼」/ 冷卻 60 秒
  - verify_btn: Button Primary / required / 「驗證」/ 輸入滿 6 碼自動啟用
  - back_link: Link / optional / 「返回登入」/ 清空 OTP 並回到 login_form
- **states**:
  - default: OTP 空白，verify 按鈕 disabled
  - typing: 填入時即時隱藏下方 error
  - error_invalid_otp: 「驗證碼不正確，剩餘嘗試次數 {n}」
  - error_expired: 「驗證碼已過期，請重新傳送」
  - verifying: verify 按鈕 Spinner
- **copy_constraints**: 說明文字 ≤ 30 字，錯誤訊息 ≤ 30 字

### Section: footer_legal

- **layout**: `mt-8 text-center text-xs text-gray-400`
- **elements**:
  - copyright: Text / required / 「© 2026 Smart Lock. All rights reserved.」
  - privacy_link: Link / required / 「隱私權政策」
  - terms_link: Link / required / 「服務條款」
- **states**:
  - default: 靜態顯示
- **copy_constraints**: 連結文字 ≤ 8 字

---

### 頁面 2: T0 `/tech-login` 技師登入

### Section: mobile_auth_shell

- **layout**: `min-h-[100dvh] flex flex-col bg-white px-6 py-8`；使用 `100dvh` 避免 iOS Safari 位址列造成的視窗跳動；`safe-area-inset-bottom` 適配 iPhone 底部 Home Indicator
- **elements**:
  - container: Main / required / full viewport
  - keyboard_spacer: Div / optional / `pb-[env(safe-area-inset-bottom)]` 讓 Submit 按鈕不被軟鍵盤遮擋
- **states**:
  - default: 白底全螢幕
- **copy_constraints**: 無

### Section: brand_header_mobile

- **layout**: `flex flex-col items-center gap-3 mt-12 mb-10`
- **elements**:
  - logo_image: Image / required / 64×64px / `priority`
  - product_title: H1 / required / 「Smart Lock 技師工作台」/ `text-xl font-semibold text-[#1E293B]` / 字級 ≥ 20px
  - subtitle: Text / optional / 「登入後即可接取工單」/ `text-sm text-gray-500`
- **states**:
  - default: 靜態
- **copy_constraints**: 標題 ≤ 15 字，副標 ≤ 15 字

### Section: tech_login_form

- **layout**: 垂直 `flex flex-col gap-5`；每個 input 高 `h-12`（48px）；字級 `text-lg`（18px）
- **elements**:
  - phone_field: FormField / required /
    - Label「手機號碼」`text-base font-medium`
    - Input `type="tel"` / `inputmode="numeric"` / `autocomplete="tel"` / `pattern="09[0-9]{8}"` / placeholder 「09xx-xxx-xxx」
    - 自動格式化：輸入 10 碼後以 `09xx-xxx-xxx` 顯示（值不含破折號）
    - Zod：`z.string().regex(/^09\d{8}$/, '請輸入有效的台灣手機號碼')`
  - password_field: FormField / required /
    - Label「密碼」
    - Input `type="password"` / `autocomplete="current-password"` / `h-12` / `text-lg`
    - 右側眼睛 icon 切換顯示/隱藏（按鈕尺寸 ≥ 44×44px）
  - submit_button: Button / required / Primary / full width / `h-12` / `text-lg font-semibold` / 「登入」
    - 高度 ≥ 48px（觸控友善超越 44px 標準）
    - loading Spinner + 「登入中…」
  - inline_error_banner: Alert / conditional / 同 A0，但字級 `text-base` 較大
  - otp_trigger_hint: Text Caption / conditional / V2.0 首次登入：「為保障您的帳號，下一步將傳送驗證碼到您的手機」
- **states**:
  - default: 兩欄位空白，Submit disabled
  - valid: Submit 啟用
  - submitting: Submit Spinner + disable 所有 field
  - error_401: 「手機號碼或密碼錯誤」
  - error_423_locked: 「帳號已鎖定 15 分鐘」+ 倒數計時
  - error_network: 「網路連線異常，請重試」+ 重試按鈕
  - keyboard_open: iOS/Android 軟鍵盤彈出時，brand_header 以 `hidden md:flex` 於小高度下收起（`@media (max-height: 600px)`）讓表單上移
- **copy_constraints**:
  - Label ≤ 6 字
  - placeholder ≤ 15 字
  - Button 文字 ≤ 4 字
  - 錯誤訊息 ≤ 20 字（行動裝置視覺空間有限）

### Section: otp_challenge

- **layout**: 條件渲染（V2.0）— 後端回 `{ mfa_required: true, channel: 'sms' }` 時全畫面替換 tech_login_form
- **elements**:
  - otp_title: H3 / required / 「輸入驗證碼」
  - otp_description: Text / required / 「驗證碼已傳送至 09xx-***-{末四碼}」
  - otp_input: OTPInput / required / 6 格大尺寸（每格 48×56px）/ 數字鍵盤 `inputmode="numeric"` / 貼上自動分配
  - countdown: Text / required / 「{mm:ss} 後可重新傳送」
  - resend_btn: Button Ghost Large / 「重新傳送」/ 60 秒冷卻 + disable
  - verify_btn: Button Primary Large / full width / `h-12` / 「驗證並登入」
  - change_number_link: Link / optional / 「變更手機號碼」/ 回到 tech_login_form
- **states**:
  - default / typing / verifying / error_invalid_otp / error_expired（同 A0 mfa_challenge）
  - sms_send_failed: 「簡訊發送失敗，請重試或聯絡客服」+ 重送按鈕
- **copy_constraints**: 說明文字 ≤ 25 字

### Section: mobile_footer

- **layout**: `mt-auto flex flex-col items-center gap-3 pb-6 text-sm text-gray-500`
- **elements**:
  - forgot_password_link: Link / required / 「忘記密碼？」/ `min-h-11` 觸控區域
  - contact_support_link: Link / required / 「聯絡客服」/ 點擊 `tel:` 或 LINE 官方帳號 deep link
  - app_version: Text Caption / required / 「v{APP_VERSION}」/ `text-xs text-gray-400`
- **states**:
  - default: 靜態
- **copy_constraints**: 連結文字 ≤ 6 字

---

### 頁面 3: A16 `/settings` 系統設定

### Section: page_shell

- **layout**: 繼承全站 Admin Shell（頂部導覽 + 左側主導覽）；內容區為 `flex gap-6 p-6 bg-[#F8FAFC]`，左側 Tab 垂直導覽 `w-60`，右側 `flex-1 max-w-3xl`
- **elements**:
  - page_title: H1 / required / 「系統設定」/ `text-2xl font-semibold mb-4`
  - settings_container: Div / required / 放置左導覽 + 內容
- **states**:
  - default / loading（標題 + Tab Skeleton）
- **copy_constraints**: 標題固定 4 字

### Section: settings_nav

- **layout**: 垂直 Tab List `flex flex-col gap-1 w-60 bg-white rounded-xl border border-gray-200 p-2 sticky top-20 self-start`
- **elements**:
  - tab_profile: NavItem / required / icon: User / 「個人資料」/ route `/settings?tab=profile`（預設）
  - tab_security: NavItem / required / icon: ShieldCheck / 「帳戶安全」/ route `?tab=security`
  - tab_pricing: NavItem / required / icon: Calculator / 「報價規則 V2.0」/ route `?tab=pricing`
  - tab_surcharge: NavItem / required / icon: TrendingUp / 「加價規則 V2.0」/ route `?tab=surcharge`
- **states**:
  - active: `bg-blue-50 text-[#2563EB] font-medium border-l-2 border-[#2563EB]`
  - inactive: `text-gray-600 hover:bg-gray-50`
  - dirty: 該 Tab 有未儲存變更時，文字右側顯示 amber 圓點 `w-2 h-2 rounded-full bg-[#F59E0B]`（切換離開時觸發未儲存確認 Dialog）
- **copy_constraints**: Tab 名稱 ≤ 8 字

### Section: tab_profile

- **layout**: 白底卡片 `bg-white rounded-xl border border-gray-200 p-6`；表單 `max-w-xl`
- **elements**:
  - section_title: H2 / required / 「個人資料」/ `text-xl font-semibold mb-1`
  - section_description: Text / required / 「您的個人檔案，部分欄位（如 Email）若要變更需經身分驗證」/ `text-sm text-gray-500 mb-6`
  - avatar_uploader: AvatarUploader / required /
    - 圓形 96×96px + 右下角相機 icon 按鈕（≥ 32×32px）
    - 點擊 → 檔案選擇 → 裁切 Modal（shadcn/ui `<Dialog>` + `react-easy-crop`）→ 上傳 `POST /api/v1/users/me/avatar`
    - 最大 2MB，僅接受 `image/jpeg`、`image/png`、`image/webp`
    - 上傳失敗 Toast「頭像上傳失敗，請重試」
  - name_field: FormField / required / 「姓名」/ Input / 最多 40 字 / Zod 非空
  - email_field: FormField / required /
    - 「電子郵件」/ Input `readonly` + 右側「變更」按鈕（需走重新驗證流程，開 `ChangeEmailDialog`）
    - 變更 email 需輸入當前密碼 + 新 email，後端寄驗證信，24 小時內完成
  - phone_field: FormField / optional / 「手機號碼」/ Input `type="tel"` / Zod `regex(/^09\d{8}$/).optional()`
  - timezone_select: Select / required / 「時區」/ 預設 `Asia/Taipei` / 選項含常見時區
  - language_select: Select / required / 「語系」/ `zh-TW`（預設）、`en-US`、`ja-JP`（V3.0）
  - save_btn: Button Primary / required / 「儲存變更」/ 無 dirty 時 disabled
  - cancel_btn: Button Ghost / optional / 「取消」/ 重設表單
- **states**:
  - default: 載入現有資料填入 field
  - loading: 整區 Skeleton（頭像圓 + 4 行 field）
  - dirty: 儲存按鈕啟用，離開頁面觸發 beforeunload 警告
  - saving: Spinner + 「儲存中…」
  - saved: Toast「個人資料已更新」+ dirty 清除
  - error: Toast「儲存失敗：{message}」
  - avatar_uploading: 頭像位置 Spinner 疊加半透明遮罩
- **copy_constraints**: 說明文字 ≤ 40 字，Label ≤ 6 字

### Section: tab_security

- **layout**: 白底卡片 `bg-white rounded-xl border border-gray-200 p-6 flex flex-col gap-8`
- **elements**:
  - section_title: H2 / required / 「帳戶安全」
  - **sub_block_password**（變更密碼）:
    - block_title: H3 / required / 「變更密碼」
    - current_password_field: Input `type="password"` / required / 「目前密碼」/ `autocomplete="current-password"`
    - new_password_field: Input `type="password"` / required / 「新密碼」/ `autocomplete="new-password"`
      - Zod：`z.string().min(12).regex(/[A-Z]/).regex(/[a-z]/).regex(/[0-9]/).regex(/[^A-Za-z0-9]/)` — 至少 12 碼 + 大小寫 + 數字 + 特殊符號
      - 即時強度指示器（weak/fair/strong/excellent，4 段彩條）
    - confirm_password_field: Input `type="password"` / required / 「確認新密碼」/ 與 new_password 比對
    - change_password_btn: Button Primary / required / 「變更密碼」
    - 成功後強制登出所有其他 session，Toast「密碼已更新，其他裝置已登出」
  - **sub_block_mfa**（雙因素驗證）:
    - block_title: H3 / required / 「雙因素驗證 (MFA)」
    - mfa_status_badge: StatusBadge / required / 「已啟用」`bg-green-100 text-green-700` / 「未啟用」`bg-gray-100 text-gray-600`
    - mfa_description: Text / required / 「啟用後，每次登入需額外輸入 Authenticator App 驗證碼」
    - setup_btn: Button Primary / conditional / 「設定 MFA」（未啟用時）
      - 點擊開啟 SetupMfaDialog：顯示 QR Code + 手動 Key，要求輸入 6 碼驗證碼確認
    - disable_btn: Button Destructive / conditional / 「停用 MFA」（已啟用時）
      - 點擊開啟確認 Dialog，需輸入當前密碼 + OTP 才能停用
    - backup_codes_btn: Button Secondary / conditional / 「查看備用驗證碼」/ 需輸入密碼後顯示 10 組一次性備用碼
  - **sub_block_sessions**（登入裝置）:
    - block_title: H3 / required / 「登入中的裝置」
    - session_list: List / required / 每列顯示：裝置 icon + OS/Browser + IP + 最後活動時間 + 地理位置（City, Country）
    - current_session_badge: Badge / required / 「本機」`bg-[#2563EB] text-white`
    - logout_session_btn: IconButton / required / `<LogOut>` / 登出單一 session（本機除外）
    - logout_all_btn: Button Destructive / required / 「登出所有其他裝置」
- **states**:
  - default: 載入 MFA 狀態 + 現有 session 列表
  - loading: 三個 sub_block 皆 Skeleton
  - password_saving / password_error_422 / password_error_401: 按鈕 Spinner / 錯誤顯示「目前密碼不正確」/ 「密碼不符規則」
  - mfa_setup_step1: Dialog 顯示 QR Code
  - mfa_setup_step2: Dialog 要求輸入 OTP 確認
  - mfa_setup_success: Toast「MFA 已啟用」
  - session_revoking: 該列 Spinner
- **copy_constraints**: sub_block 說明 ≤ 40 字

### Section: tab_pricing_rules

- **layout**: 白底卡片 `bg-white rounded-xl border border-gray-200 p-6`；上方規則列表 + 下方編輯表單
- **elements**:
  - section_title: H2 / required / 「報價規則 V2.0」
  - section_description: Text / required / 「設定不同服務類別的基礎報價；規則變更僅影響變更後建立的新工單」/ `text-sm text-gray-500 mb-4`
  - version_info_banner: AlertBanner / required / `bg-blue-50 border-blue-200 text-blue-700 rounded-lg p-3 mb-4`
    - 文案：「當前規則版本：v{version} / 最後更新：{updated_at} by {updated_by}」
  - rules_table: DataTable / required /
    - col_category: Text / required / 服務類別（如「鎖具更換」、「智能鎖安裝」、「緊急開鎖」）
    - col_base_price: Text Number / required / 基礎費用「NT$ {amount}」
    - col_min_price: Text Number / required / 最低收費
    - col_max_price: Text Number / required / 最高收費（可選，null 顯示「—」）
    - col_updated_at: Text / required / 最後更新時間
    - col_actions: ActionButtons / required /
      - 「編輯」Button Ghost Small / 開啟 RuleEditor Modal
      - 「停用」Toggle / 停用後該類別不可被新工單選用（但歷史工單不受影響）
  - add_rule_btn: Button Primary / required / icon: Plus / 「新增規則」
  - rule_editor_modal: Dialog / required /
    - title: 「新增 / 編輯報價規則」
    - category_input: Input / required / 「服務類別名稱」/ 最多 30 字 / 唯一性驗證
    - base_price_input: NumberInput / required / 「基礎費用」/ min 0 / 前綴 NT$
    - min_price_input: NumberInput / required / 「最低收費」/ min 0 / Zod 驗證 `min <= base`
    - max_price_input: NumberInput / optional / 「最高收費（選填）」/ 若填需 `>= base`
    - description_textarea: Textarea / optional / 「規則說明」/ 最多 200 字
    - effective_date_picker: DatePicker / optional / 「生效日期」/ 預設為「立即生效」
    - confirm_btn: Button Primary / 「儲存規則」
    - cancel_btn: Button Ghost / 「取消」
  - audit_link: Link / required / 「查看規則變更歷史」/ 右上角 / 導向 `/admin/audit-events?resource=pricing_rule`
- **states**:
  - default: 顯示現有規則列表
  - loading: 8 列 Skeleton rows
  - empty: 「尚無報價規則，請新增第一條」+ CTA
  - saving: Modal 確認按鈕 Spinner
  - validation_error: 行內紅字顯示「最低收費不可大於基礎費用」等
  - conflict_409: Toast「類別名稱已存在」
  - permission_denied: 整個 tab 唯讀 + Banner「您僅有檢視權限，需 `pricing.write` 權限才能修改」
- **copy_constraints**: 類別名稱 ≤ 30 字，說明 ≤ 200 字

### Section: tab_surcharge_rules

- **layout**: 白底卡片 `bg-white rounded-xl border border-gray-200 p-6`；上方條件規則列表 + 下方編輯 Modal
- **elements**:
  - section_title: H2 / required / 「加價規則 V2.0」
  - section_description: Text / required / 「依時段、距離、急件等條件自動加價；規則按優先順序套用」/ `text-sm text-gray-500 mb-4`
  - rule_priority_hint: AlertBanner / required / icon: Info / 「可拖曳列項調整優先順序；上方規則優先套用」
  - rules_table: DataTable / required / 支援 drag-and-drop 排序（dnd-kit）
    - col_drag_handle: DragHandle / required / `<GripVertical>` icon / 滑鼠/觸控可拖
    - col_priority: Text / required / 序號（隨拖曳即時更新）
    - col_rule_name: Text / required / 規則名稱（如「週末加價」、「夜間急件加價」）
    - col_condition: Badge[] / required / 條件摘要 Badge
      - 時段：「週六日」、「22:00-06:00」
      - 距離：「> 20km」
      - 急件：「SLA < 2h」
      - 天氣：V3.0「暴雨/颱風警報」
    - col_surcharge_type: Badge / required /
      - 固定金額：`bg-blue-100 text-blue-700` 「+NT$ {amount}」
      - 百分比：`bg-purple-100 text-purple-700` 「+{percent}%」
    - col_enabled: Switch / required / 啟用/停用
    - col_actions: ActionButtons / required / 「編輯」/ 「刪除」
  - add_surcharge_btn: Button Primary / required / icon: Plus / 「新增加價規則」
  - surcharge_editor_modal: Dialog / required /
    - title: 「新增 / 編輯加價規則」
    - rule_name_input: Input / required / 「規則名稱」/ 最多 30 字
    - condition_builder: ConditionBuilder / required /
      - 類型 Select：時段 / 距離 / 急件 / 服務類別 / 天氣 (V3)
      - 對應動態 UI：
        - 時段：DayPicker（週一～日 checkbox）+ TimeRange（start~end）
        - 距離：NumberInput（公里）+ 操作子 `>=` / `<=`
        - 急件：SLA 時數 NumberInput + `<=`
        - 服務類別：Multi-Select（串接 tab_pricing_rules 的類別）
      - 可 AND 多個條件（`條件全部滿足時觸發`）
    - surcharge_type_radio: RadioGroup / required / 「固定金額」/ 「百分比」
    - surcharge_amount_input: NumberInput / required / 依類型顯示 NT$ 或 %
    - max_surcharge_input: NumberInput / optional / 「加價上限（選填）」/ 百分比模式建議填
    - description_textarea: Textarea / optional / 「規則說明」
    - preview_card: PreviewCard / required / 即時預覽「範例：基礎 NT$2000 + 本規則 = NT${preview}」
    - confirm_btn: Button Primary / 「儲存規則」
    - cancel_btn: Button Ghost / 「取消」
  - test_calculator: TestCalculator / optional / 右上角 Popover / 輸入測試條件 → 顯示套用哪些規則 + 最終價格
- **states**:
  - default: 顯示規則列表
  - loading: Skeleton
  - empty: 「尚無加價規則」
  - reordering: 拖曳時列項半透明 `opacity-50`，放下後 Optimistic update + `PATCH /api/v1/surcharge-rules/reorder`
  - dirty_multiple: 多條規則調整後，頂部黏性 bar 顯示「有 {n} 項變更未儲存」+ 儲存/取消
  - saving / conflict_409 / permission_denied: 同 pricing_rules
- **copy_constraints**: 規則名稱 ≤ 30 字，說明 ≤ 200 字，條件 Badge 文字 ≤ 12 字

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

#### A0 管理員登入

1. 進入 `/login` → Next.js Middleware 檢查已有 `access_token` Cookie → 若有則 307 redirect 到 `/dashboard`
2. 使用者輸入 email → debounce 500ms → `POST /api/v1/auth/resolve-tenant { email }` → 若 >1 個租戶則顯示 tenant_selector
3. 填入 password + 選用「記住我」→ 點擊登入
4. `POST /api/v1/auth/login { email, password, tenant_id?, remember_me }` →
   - 成功 200：後端回 Set-Cookie `access_token`（httpOnly, Secure, SameSite=Strict, Max-Age=900s or 30d）+ `refresh_token` + 回傳 `{ user, permissions, brand_config }` → Zustand `useAuthStore.setUser()` + `applyBrandConfig()` → `router.push('/dashboard')`
   - 200 但 `mfa_required: true`：保留 `mfa_token`，展開 mfa_challenge，隱藏 login_form
   - 401：顯示「電子郵件或密碼錯誤」+ 前端不自行計數（以後端 `failed_attempts_remaining` 為準）
   - 423：顯示鎖定訊息 + 剩餘時間倒數
   - 429：顯示「請求過於頻繁，請 {retry_after} 秒後再試」
5. MFA：輸入 OTP → `POST /api/v1/auth/verify-mfa { mfa_token, otp }` → 同 4 成功流程
6. 點擊忘記密碼 → `router.push('/forgot-password')`

#### T0 技師登入

1. 進入 `/tech-login` → Middleware 檢查 `access_token` → 若存在且 role=technician 則 redirect 到 `/pool`
2. 輸入手機號（自動格式化）+ 密碼
3. 點擊登入 → `POST /api/v1/technicians/login { phone, password }` →
   - 成功 200：同 A0 寫 Cookie + Zustand → `router.push('/pool')`
   - 200 `mfa_required`（V2.0）：後端已寄 SMS OTP → 展開 otp_challenge
   - 401 / 423 / 429：同 A0
4. V2.0 OTP：`POST /api/v1/technicians/verify-otp { mfa_token, otp }` → 成功導向 `/pool`
5. 重送 OTP：`POST /api/v1/technicians/resend-otp { mfa_token }` → 60 秒冷卻

#### A16 系統設定

##### 共通
1. 進入 `/settings` → Middleware 驗證 session → `GET /api/v1/users/me` 載入當前使用者資料 → 預設顯示 `?tab=profile`
2. 切換 Tab：`router.push('/settings?tab=xxx', { scroll: false })`；若當前 Tab 有 dirty state → 顯示 ConfirmDialog「您有未儲存的變更，確定要離開？」

##### 個人資料 (tab_profile)
1. 載入 → 填入 field
2. 上傳頭像：檔案選擇 → 裁切 Modal → `POST /api/v1/users/me/avatar` (multipart) → 成功後更新頭像 URL + 全站 Zustand `useAuthStore.updateAvatar()`
3. 修改資料 → 點擊儲存 → `PATCH /api/v1/users/me { name, phone, timezone, language }` → 成功 Toast + dirty 清除
4. 變更 email：開 Dialog → 輸入當前密碼 + 新 email → `POST /api/v1/users/me/email-change-request` → 寄驗證信，新 email 點連結後才生效

##### 帳戶安全 (tab_security)
1. 變更密碼：三個欄位驗證 → `POST /api/v1/users/me/change-password { current_password, new_password }` →
   - 成功：強制登出所有其他 session（後端處理）+ Toast + 清空表單
   - 401：「目前密碼不正確」
   - 422：「新密碼不符規則：{details}」
2. 啟用 MFA：`POST /api/v1/users/me/mfa/setup` → 回傳 `{ secret, qr_code_data_url }` → Dialog 顯示 QR Code → 使用者用 Authenticator 掃碼 → 輸入 6 碼 → `POST /api/v1/users/me/mfa/confirm { otp }` → 成功回傳 10 組備用碼 → 提示下載/列印
3. 停用 MFA：Dialog 輸入密碼 + OTP → `DELETE /api/v1/users/me/mfa`
4. 登出單一 session：`DELETE /api/v1/users/me/sessions/{session_id}`
5. 登出所有其他：`DELETE /api/v1/users/me/sessions?exclude=current`

##### 報價規則 (tab_pricing_rules)
1. 載入 → `GET /api/v1/pricing-rules` → 顯示列表
2. 新增：Modal → 驗證 → `POST /api/v1/pricing-rules { category, base_price, min_price, max_price?, description?, effective_date? }` → 成功 refetch + Toast
3. 編輯：Modal 預填 → `PATCH /api/v1/pricing-rules/{id}` → refetch
4. 停用：`PATCH /api/v1/pricing-rules/{id} { enabled: false }` → Optimistic update
5. 每次 POST/PATCH/DELETE 後端自動寫稽核（`resource=pricing_rule, action=create/update/delete, actor=current_user`）

##### 加價規則 (tab_surcharge_rules)
1. 載入 → `GET /api/v1/surcharge-rules?sort=priority` → 顯示列表
2. 拖曳排序 → Optimistic update → `PATCH /api/v1/surcharge-rules/reorder { order: [id1, id2, ...] }`
3. 新增/編輯：ConditionBuilder + 預覽 → `POST/PATCH /api/v1/surcharge-rules`
4. 測試計算機：`POST /api/v1/surcharge-rules/test { base_price, conditions }` → 回傳套用的規則清單 + 最終價

### RWD 行為差異

| 斷點 | A0 `/login` | T0 `/tech-login` | A16 `/settings` |
|:-----|:------------|:------------------|:----------------|
| Desktop (≥1280px) | 卡片 max-w-md 置中，背景漸層填滿 | 不適用（行動優先，桌面上顯示置中 max-w-sm 以行動模擬） | 左側 Tab w-60 + 右側內容 max-w-3xl |
| Tablet (768–1279px) | 卡片 max-w-md 置中，padding 增加 | 全寬但 max-w-sm 置中，上下安全邊距 | Tab 收合為頂部水平 TabBar，內容全寬 max-w-3xl |
| Mobile (<768px) | 卡片 full width `mx-4`，字級維持但按鈕 h-11 | 原生 Mobile-First 全寬，`h-12` 按鈕，`text-lg` 字級，鍵盤彈出時隱藏 brand_header | Tab 改為頂部下拉選單（`<Select>`），內容單欄堆疊；敏感 Dialog 變為全螢幕 Sheet |

### 資料更新策略

- **A0 / T0**：登入頁無 polling；`resolve-tenant` 與 `login` 為單次 POST
- **A16 tab_profile / tab_security**：載入時一次 GET，手動操作觸發 mutation 後 invalidate 對應 query
- **A16 tab_pricing / tab_surcharge**：`staleTime: 60_000`；跨頁面返回自動背景 refetch；規則編輯後所有使用到規則的頁面（工單建立、報價計算）發 WebSocket 廣播 `/realtime/pricing-updated` 通知前端清除快取

### 鍵盤與輔助功能

- 所有表單 `<Enter>` 提交、`<Esc>` 關閉 Modal
- Tab 順序：Logo → Tenant Select（若有）→ Email → Password → Remember → Submit → Forgot → Tech Login
- `aria-live="polite"` 區域用於登入錯誤訊息播報
- OTP Input 支援貼上整串 6 碼自動分配
- 螢幕閱讀器可朗讀密碼強度指示器

---

## [DATA & API]

- **uses_api**: true

- **endpoints**:

  ### 認證共用
  - `POST /api/v1/auth/resolve-tenant` — 依 email 解析所屬租戶
    - Body: `{ email: string }`
    - Response 200: `{ tenants: Array<{ id, name, logo_url }> }`
    - Rate limit: 10/min per IP
  - `POST /api/v1/auth/login` — 管理員登入
    - Body: `{ email, password, tenant_id?, remember_me }`
    - Response 200 (normal): `{ user, permissions, brand_config }` + Set-Cookie `access_token`, `refresh_token`, `tenant_id`
    - Response 200 (mfa): `{ mfa_required: true, mfa_token: string, channel: 'totp' }`
    - Errors: 401 / 423 / 429（見下方 error_cases）
  - `POST /api/v1/auth/verify-mfa` — MFA 驗證
    - Body: `{ mfa_token, otp }`
    - Response 200: 同 login 成功
    - Errors: 401（invalid otp）/ 410（expired）
  - `POST /api/v1/auth/logout` — 登出（清除 Cookie）
  - `POST /api/v1/auth/refresh` — Refresh token（由 Next.js Middleware 自動呼叫）

  ### 技師登入
  - `POST /api/v1/technicians/login` — 技師登入
    - Body: `{ phone, password }`
    - Response 200: 同管理員；V2.0 支援 `mfa_required` + `channel: 'sms'`
  - `POST /api/v1/technicians/verify-otp` — SMS OTP 驗證（V2.0）
    - Body: `{ mfa_token, otp }`
  - `POST /api/v1/technicians/resend-otp` — 重送 SMS OTP
    - Rate limit: 3/min per phone

  ### 使用者個人資料
  - `GET /api/v1/users/me` — 取得目前使用者完整資料
    - Response: `{ id, name, email, phone, avatar_url, timezone, language, role, permissions, mfa_enabled }`
  - `PATCH /api/v1/users/me` — 更新個人資料
    - Body: `{ name?, phone?, timezone?, language? }`
  - `POST /api/v1/users/me/avatar` — 上傳頭像（multipart/form-data）
    - 限制：2MB，image/jpeg|png|webp
  - `POST /api/v1/users/me/email-change-request` — 請求變更 email
    - Body: `{ current_password, new_email }` → 寄驗證信到新 email

  ### 安全
  - `POST /api/v1/users/me/change-password` — 變更密碼
    - Body: `{ current_password, new_password }`
    - 成功後後端撤銷所有其他 session
  - `POST /api/v1/users/me/mfa/setup` — 啟用 MFA 第一步
    - Response: `{ secret, qr_code_data_url, backup_codes_preview_count }`
  - `POST /api/v1/users/me/mfa/confirm` — 確認 MFA
    - Body: `{ otp }`
    - Response: `{ backup_codes: string[10] }`
  - `DELETE /api/v1/users/me/mfa` — 停用 MFA
    - Body: `{ current_password, otp }`
  - `GET /api/v1/users/me/sessions` — 登入中的 session 列表
  - `DELETE /api/v1/users/me/sessions/{session_id}` — 登出單一 session
  - `DELETE /api/v1/users/me/sessions?exclude=current` — 登出所有其他

  ### 報價規則
  - `GET /api/v1/pricing-rules` — 列出所有報價規則
  - `POST /api/v1/pricing-rules` — 新增規則（需 `pricing.write`）
  - `PATCH /api/v1/pricing-rules/{id}` — 更新規則
  - `DELETE /api/v1/pricing-rules/{id}` — 刪除規則（軟刪除）

  ### 加價規則
  - `GET /api/v1/surcharge-rules?sort=priority` — 列出加價規則
  - `POST /api/v1/surcharge-rules` — 新增
  - `PATCH /api/v1/surcharge-rules/{id}` — 更新
  - `PATCH /api/v1/surcharge-rules/reorder` — 重新排序
    - Body: `{ order: string[] }`（id 陣列）
  - `DELETE /api/v1/surcharge-rules/{id}` — 刪除
  - `POST /api/v1/surcharge-rules/test` — 測試計算
    - Body: `{ base_price, conditions: { time?, distance_km?, sla_hours?, category? } }`
    - Response: `{ applied_rules: Rule[], final_price }`

- **Zustand Stores**:
  - `useAuthStore`: `{ user, permissions, tenant, login(), logout(), updateProfile() }`
  - `useSettingsDirtyStore`: 追蹤各 Tab 的 dirty state（離開前警告）
  - `useBrandStore`: `brand_config`（登入成功時 applyBrandConfig）

- **error_cases**:
  - **401 Unauthorized**
    - A0：「電子郵件或密碼錯誤」+ 前端不計數（後端回 `failed_attempts_remaining`）
    - T0：「手機號碼或密碼錯誤」
    - A16 change-password：「目前密碼不正確」
  - **423 Locked** (連續 5 次失敗)
    - 顯示：「此帳號已鎖定，請於 {retry_after_seconds} 秒後再試（15 分鐘）」
    - Submit 按鈕永久 disabled 直到倒數結束；倒數結束自動重置表單
  - **410 Gone**（MFA token 過期）
    - 顯示：「驗證碼已過期，請重新登入」→ 2 秒後自動返回 login_form
  - **422 Unprocessable**（驗證失敗）
    - 密碼不符規則、email 格式錯誤等 → 行內欄位錯誤訊息
  - **429 Too Many Requests**
    - 顯示：「請求過於頻繁，請 {retry_after} 秒後再試」+ 整表單 disabled
  - **403 Forbidden**（權限不足）
    - A16 報價/加價規則：整個 tab 轉唯讀 + Banner「您僅有檢視權限」
  - **409 Conflict**（並發衝突）
    - 規則被其他管理員同時修改 → Toast「此規則已被其他使用者更新，請重新載入」+ 自動 refetch
  - **Network Error**
    - Toast「網路連線異常」+ Submit 啟用重試；TanStack Query 自動 retry 3 次
  - **Tenant Mismatch**（前端 guard 檢測到 tenant_id 不一致）
    - Sentry 記錄 `tenant-id-mismatch` → 強制登出 + 顯示「偵測到異常，請重新登入」

---

## [EXCEPTION TO GLOBAL RULES]

- **A0 / T0 登入頁無全站 Shell**：不顯示頂部導覽列、側邊主導覽、Breadcrumb；為獨立全畫面（受 `app/(auth)/layout.tsx` 管轄），違反 Global「所有頁面帶導覽」規則
- **T0 使用 `100dvh`** 而非 Global 的 `100vh`，以處理 iOS Safari 動態位址列高度問題
- **A0 / T0 密碼欄位 `autocomplete="current-password"`、email 欄位 `autocomplete="username"`** — 符合瀏覽器密碼管理器整合最佳實踐，不視為全域樣式例外
- **A16 tab_security QR Code Dialog** 使用 `bg-white` 實心背景（非 Global `bg-[#F8FAFC]`），確保掃碼相機對比度
- **A16 tab_pricing / tab_surcharge 規則異動皆寫稽核**：比 Global「僅破壞性操作寫稽核」更嚴格
- **T0 支援 SMS OTP**（V2.0）：與 A0 的 TOTP（Authenticator）不同通道；後端負責通道選擇，前端依 `channel` 欄位切換 UI 文案（「Authenticator App 驗證碼」vs「簡訊驗證碼」）

---

## [ACCEPTANCE CRITERIA]

### A0 管理員登入

- [ ] 支援 email + password 登入，Zod schema 驗證 email 格式與密碼最小長度
- [ ] 多租戶情境下，輸入 email 後自動解析所屬租戶；單一租戶自動選取，多租戶顯示下拉
- [ ] 「記住我」勾選時 Cookie `Max-Age=30d`，否則 session cookie
- [ ] JWT 存於 httpOnly + Secure + SameSite=Strict Cookie，不在 localStorage
- [ ] 登入失敗顯示友善錯誤訊息，不洩露 email 是否存在（統一回「電子郵件或密碼錯誤」）
- [ ] 連續 5 次失敗（後端計數）回 423，前端顯示 15 分鐘倒數計時器
- [ ] MFA 必填情境：login 回 `mfa_required: true` 時展開 OTP 驗證，OTP 過期自動返回 login_form
- [ ] 登入成功導向 `/dashboard`，Zustand 寫入 user + permissions + brand_config
- [ ] 已登入者訪問 `/login` 自動 307 redirect 到 `/dashboard`
- [ ] 鍵盤操作：Tab 順序正確、Enter 提交、Esc 關閉 Dialog、焦點環清晰可見
- [ ] 密碼顯示切換按鈕 ≥ 44×44px，aria-label「顯示/隱藏密碼」

### T0 技師登入

- [ ] 支援手機號碼 + 密碼登入，Zod 驗證台灣手機號格式 `/^09\d{8}$/`
- [ ] 登入按鈕高度 ≥ 48px（超越 44px 標準）、字級 ≥ 18px
- [ ] Input 高度 ≥ 48px，字級 ≥ 16px（避免 iOS 自動放大）
- [ ] Mobile-First 佈局，375px 螢幕完整可用，支援 `100dvh` 動態視窗
- [ ] 軟鍵盤彈出時 Submit 按鈕不被遮擋（`safe-area-inset-bottom` + `@media max-height`）
- [ ] V2.0：首次登入自動觸發 SMS OTP，6 格大尺寸 OTP Input，`inputmode="numeric"` 喚起數字鍵盤
- [ ] OTP 重送冷卻 60 秒，Rate limit 3 次/分鐘
- [ ] 登入成功導向 `/pool`
- [ ] 聯絡客服連結使用 `tel:` 或 LINE deep link
- [ ] 無障礙：aria-live 錯誤播報，OTP 貼上自動分配，Switch/Button 可觸 ≥ 44×44px

### A16 系統設定 — 共通

- [ ] URL `?tab=` 同步當前分頁，重新整理回到相同 Tab
- [ ] 有 dirty state 時切換 Tab / 離開頁面觸發確認 Dialog
- [ ] 所有敏感操作（密碼、MFA、規則）寫入 `/api/v1/audit-events`
- [ ] 403 權限不足時整個 Tab 轉唯讀 + Banner 說明

### A16 個人資料

- [ ] 頭像上傳限制 2MB、image/jpeg|png|webp，支援裁切
- [ ] 姓名、手機、時區、語系可編輯並儲存
- [ ] Email 變更走獨立流程：輸入當前密碼 + 寄驗證信確認
- [ ] 儲存成功後 Zustand `useAuthStore` 同步更新

### A16 帳戶安全

- [ ] 新密碼規則：至少 12 碼 + 大小寫 + 數字 + 特殊符號，即時強度指示器
- [ ] 密碼變更成功後後端撤銷所有其他 session，前端 Toast 提示
- [ ] MFA 啟用三步驟：`setup` → 顯示 QR Code → `confirm` 回 10 組備用碼
- [ ] 停用 MFA 需同時驗證密碼 + OTP
- [ ] Session 列表顯示 OS/Browser/IP/地理位置/最後活動時間
- [ ] 本機 session 不可登出（需用「登出」按鈕）

### A16 報價規則 V2.0

- [ ] 列出所有服務類別基礎費用、最低/最高收費
- [ ] 新增/編輯：類別唯一性驗證、`min <= base <= max` 邏輯驗證
- [ ] 停用規則不影響歷史工單
- [ ] 顯示當前規則版本與最後更新者/時間
- [ ] 可跳轉至稽核日誌查看變更歷史

### A16 加價規則 V2.0

- [ ] 支援時段、距離、急件、服務類別四種條件（V3.0 加天氣）
- [ ] 條件可 AND 組合
- [ ] 支援固定金額 / 百分比兩種加價方式，百分比可設上限
- [ ] 拖曳排序（dnd-kit）+ Optimistic update
- [ ] 即時預覽卡片顯示套用後價格
- [ ] 測試計算機 Popover：輸入測試條件 → 顯示套用規則清單 + 最終價
- [ ] 儲存後透過 `/realtime/pricing-updated` 廣播通知其他前端清快取

### 效能與規範

- [ ] A0 / T0 首次載入 LCP < 1.5 秒（無需大量 JS）
- [ ] A16 首次載入 LCP < 2 秒
- [ ] 符合 Design System：Primary `#2563EB`、Accent `#F59E0B`、Secondary `#1E293B`、BG `#F8FAFC`、Font Inter + Noto Sans TC
- [ ] WCAG 2.1 AA：對比度 ≥ 4.5:1、鍵盤可達、焦點可見、ARIA 標籤完整
- [ ] 三斷點（Desktop / Tablet / Mobile）佈局皆通過驗收


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
