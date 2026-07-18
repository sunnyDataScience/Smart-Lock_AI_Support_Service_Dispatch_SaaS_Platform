# CR-0171 — 知識庫 UI 階層式 + 型號知識新增精靈(#10 完結)

- **日期**:2026-07-18
- **狀態**:✅ §8 已裁決(業主 AskUserQuestion 拍板)並實作完成
- **觸發面向**:User flow(新增知識的表單式流程;顯示層 IA 重組)
- **關聯**:0715 會議 §3.5/決議 6(#10)、CR-0167/ADR-032(LiveSkill)、前輪口語化(commit 5209e98d,業主拍板顯示層方案)

---

## §1 一句話

會議 #10「頭語化階層式+一般 UI 讓客戶 CRUD 新增」的收尾:SkillEditor 左欄
references 從 45 檔平鋪改**品牌分組收合樹**;新增**型號知識精靈**——小編填表單
(品牌/型號/描述+三區塊),前端組標準 md 落 `references/{品牌}/{型號}.md`,
走既有 draft→admin 發佈。**零後端變更、可攜性零影響**。

## §2 查證要點(4 agent 並行 survey)

- 口語化已交付拍板;LiveSkill 編輯器(S3)已提供工程視角 CRUD——剩「階層式」+「非工程小編可新增」
- 「消費者」=品牌方小編(非終端住戶;CR-0167 HD-1 語境一致)
- 資料形狀:product-knowledge 45 檔 100% 有 frontmatter(brand/model/description)+穩定 H1;
  路徑慣例 `{Brand}/{Model}.md`+`_brand.md`+`_common/`;cs-sop 3 檔平鋪無 frontmatter
- API:saveDraft 收任意檔名整樹(新增/刪除/改名=整樹覆蓋語意),前端零 wrapper 缺口
- **查證途中抓到 P1**:`_REL_PATH_SEG_RE` ASCII 白名單擋掉 3 個出廠實檔(中文/括號/加號),
  seed 直 SQL 繞過入庫 → 品牌後台對產品知識庫存草稿/發佈全 422 → 已修
  (branch `fix/skill-relpath-unicode`,黑名單制+回歸測試 2,詳 CR-0167 進度)

## §8 業主裁決(2026-07-18,AskUserQuestion 帶 ASCII preview)

- **階層式=品牌分組收合樹**:依路徑第一段分組收合、`_brand.md`→「品牌通用」置頂、
  `_common`→「共用知識」置底、組內依顯示標題排序;無階層 skill 自動退平鋪
- **新增精靈=型號知識精靈**:表單(品牌下拉可新品牌/型號/一句話描述/設定步驟/常見
  問題/故障排除,內容至少一項)→組標準 md(frontmatter+H1+章節)→存為草稿

## §9 實作(branch `feat/kb-skill-hierarchy-wizard`)

- `SkillEditor.tsx`:`buildRefTree()`(純顯示層,路徑推導品牌樹)+收合狀態+選中自動
  展開;精靈按鈕(僅有品牌階層的 skill 顯示);**刪除改二段確認**(原 hover 一鍵即刪
  無確認,查證痛點);`handleSave(filesArg?)` 支援精靈落檔立即存
- `SkillModelWizard.tsx`(新):Radix Modal 表單;檔名 sanitize 與後端黑名單一致
  (中文/空格/連字號合法);重複路徑擋+inline 驗證
- 落盤仍標準 SKILL.md+references/(Architecture Lock 條 2 可攜性紅線不動)

### 驗證

- brand tsc 0;api+web 容器重建
- Playwright live:樹狀渲染(Dormakaba 17 展開/品牌通用置頂/共用知識置底)→精靈填表
  →**存草稿 v1 成功(整樹 PUT 含中文檔名=rel_path 修復同輪 live 實證)**→新檔自動
  選中+群組展開→二段刪除確認→還原存檔;cs-sop 平鋪 degrade+精靈按鈕隱藏
- 測試資料污染 0(DB 實查:draft 45 references、TEST 殘留 0)

### 進度

- ✅ 全部完成(merge 見 dev-ding;#10 至此完結)
