# 師傅端「文件 vs 實作」盤點報告

- **日期**: 2026-07-06 21:45
- **任務**: 盤點各文件定義的師傅功能/畫面,交叉核對是否都有實作
- **範圍**: 設計 spec(T0-T11)/ UAT 素材(20260709)/ 業主資料(20260617/0628/0702)/ 治理文件(CR-0105~0117、phase1-backlog、completion-status)/ web/src/app 師傅端 16 頁
- **方法**: ultracode workflow 5 平行代理(4 文件讀取 + 1 實作稽核),577k tokens,主線交叉核對

## 結論

- **畫面覆蓋:設計 IA 定義的 12 頁(T0-T11)全部有對應實作**,另有 4 頁超出 IA(/home 決策屏、/tech-register KYC、/account/statements、/account/commission-statements)。16 頁中 15 頁主功能真接 API,唯一 partial 是 /account(收入卡「—」骨架 + 通知偏好/編輯個資 disabled 佔位;收入功能實際由 /home dashboard-summary 吸收)。
- **UAT 素材(7/9 Johnson UAT)宣稱的師傅端 15 項功能全部可對到真實作**;隱藏清單 8 項全在後台,師傅端零隱藏 — 素材宣稱成立。
- **功能細節層缺口**(文件明定、實作沒有):拒單 decline/出發 depart 端點、接單 SLA 逾時自動改派(410)、arrival 不轉 in_progress、技師取消 UI、KYC 文件上傳(S-upload)與審核頁 KYC 顯示(S7)、scope-change 佐證照片、BOM 用料/序號綁定、現場同意書、結案 PDF 三聯單、月結單下載、使用教學紀錄、客戶不在場流程、PWA SW 離線(~30%)、金流 0(Phase 2)。
- **spec 華麗版 vs 實作簡化版**(畫面在、互動降級):pool 無地圖/手勢滑動/離線佇列;T3 完工表單無零件動態列表/IndexedDB 草稿;T6 無零件主檔搜尋/庫存 ETA/部分完工決策;T7 無嚴重度預覽;T8 無三步 stepper/EXIF/SHA-256/Vision 比對;T9 無稽核元資料卡。
- **實作小刺**:/account/schedule closeToday 開關不回讀後端(重整歸零);door-check PhotoThumb 縮圖只渲染檔名;兩張對帳單頁用管理端 Sidebar 而非 TechShell(師傅端唯二 shell 不一致);commission-statements 角色定位是派工員卻掛 /account 下;tech-register/對帳單/功能測試區硬編繁中未走 i18n。
- **文件間漂移 3 處**:P1-05 LIFF 簽收(backlog 標待排 vs completion-status 記 0702 會議已裁關閉不做,未回寫);停權即失效(phase1 A2 ✅ vs 7/02 測試仍記 1hr token 缺口);CR-0117 frontmatter 仍 active 但進度全勾。另 CR-0103/0104 品牌端 UI 已被 CR-0114 收斂刪除但未標 superseded。
- **部署面**:多數「已完成」= 本機 docker 已部署;雲端部署 + migrations 086/088/089 是文件明說的系統性欠帳。

## 行動項目

- [ ] CR-0115 S-upload + S7(KYC 上傳與審核頁顯示)— 審核決策依據斷鏈,優先級最高
- [ ] 拒單/出發/SLA 逾時/取消 UI — contract 級,需 CIA + 業主排程
- [ ] P1-05 backlog 回寫「已裁關閉」;CR-0117 frontmatter 改 implemented;CR-0103/0104 標 superseded
- [ ] 對帳單兩頁換 TechShell(或確認 commission-statements 應搬離師傅端)
- [ ] closeToday 回讀後端狀態

## 影響評估

- **嚴重度**: MEDIUM(畫面全覆蓋;缺口集中在例外流程與帳務深水區,皆有文件記錄)
- **影響範圍**: 師傅端 16 頁、technician API、KYC 審核動線、月結帳務
