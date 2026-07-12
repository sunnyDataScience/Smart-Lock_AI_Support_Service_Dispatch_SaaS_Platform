# CR-0168 — refinery 行為軌改走 LiveSkill DB 汲取（取代 git+重佈）

- **日期**：2026-07-13
- **狀態**：✅ §8 已裁決（業主選 a＋要求品質零影響），依 §9 實作完成
- **觸發面向**：External integration（refinery→api 新呼叫）＋ User/Business flow（skill 落地流程 git→DB）
- **關聯**：CR-0167 / ADR-032（LiveSkill）、ADR-030（Skill 為知識主軸、RAG＝外接 MCP）、CR-0140（refinery HITL）

---

## §1 一句話

knowledge-pipeline 淬鍊的產物就是 **skill**（非 RAG；RAG 是未來 MCP 外接介面，ADR-030）。
refinery 行為軌原本把核可話術寫進 `lockcore/skills/.../references/refined/` 走 **git commit + 重佈**；
改走 LiveSkill 的 `/internal/skills/ingest`（merge draft）→ 品牌後台人工發佈 → ≤60s 生效，**免重佈**。

## §2 動機

| 現狀（CR-0140） | 痛點 |
|---|---|
| `refinery/apply_behavior.py` 把核可 patch 寫檔到 repo，人 git commit | refinery 是服務容器（無 skills 檔案系統），git 落檔需 repo checkout；且 skill 更新要重佈 agent 才生效 |
| LiveSkill（CR-0167）已讓「品牌庫 draft→發佈→≤60s 生效不重佈」 | 但自動汲取的「生產端」未接——refinery 仍走舊 git 路徑 |

## §3 業主裁決（§8）

- **知識產線的產物＝skill，沒有用到 RAG；未來 RAG 走 MCP 外接**（釐清 ADR-030 定位；本 CR 不動 facts 軌/rag）。
- **合併語意選 (a)**：refinery 只送單一 refined reference，**後端讀現有基準併入**（ingest 加 merge 模式）。
- **硬性要求：改動後不得影響 agent 回答品質。**

## §4 設計

### 4.1 後端 ingest merge 模式（`skill_service.ingest_revision(merge=True)`）
- 讀基準 files：現有草稿優先（累積多次汲取）→ 發佈中版本 → 最新版本；皆無 → **404 SKILL_NOT_FOUND**
  （不憑空產不完整 skill）。
- `files = {**baseline, **new}`：**嚴格加性**——保留既有 SKILL.md 與所有 references，只新增/更新送來的檔。
- 存成 **draft**（`source=pipeline_ingest`），**絕不 publish**。

### 4.2 refinery 落地雙路徑（`apply_behavior.py` 依環境自動選）
- **A. LiveSkill DB 汲取（預設，服務容器）**：設 `LOCK_API_BASE_URL`+`INTERNAL_API_TOKEN` →
  POST `/internal/skills/ingest`（`merge=true`），`target_path` 解析出 skill_name/rel_path。標
  `provenance.published.channel='skill_ingest'`+draft_version（保留原 kind/content 溯源）。
- **B. git 落檔（fallback，repo checkout）**：無 API 環境 → 舊路徑（寫檔、人 git commit）。零破壞。

## §5 品質零影響論證（業主硬性要求）

| 保證 | 機制 |
|---|---|
| **汲取只進 draft、絕不 publish** | `ingest_revision`→`save_draft`（status='draft'）。agent 的 SkillSync 只物化 `status='published'`（`skill_sync.py:_fetch_published_skills`）→ **自動汲取無論如何都到不了 agent，直到人工在品牌後台按發佈**（HD-2）。 |
| **合併嚴格加性、SKILL.md 不動** | `{**baseline, **new}` 保留既有全部檔；行為軌只送 `references/refined/*.md`，從不覆寫 SKILL.md（進 prompt 的部分）→ 發佈後 skill 為既有內容超集，只多一條可 read_file 的參考，不刪不改。 |
| **references 不膨脹 prompt** | 只有 SKILL.md 進 system prompt；references 走 read_file 按需讀（與 git 路徑相同性質）。 |
| **人工審核把關** | 人在品牌後台看完整草稿 diff 才發佈；發佈閘（frontmatter/大小/path collision）仍強制。 |
| **汲取失敗不腐蝕** | refinery 捕捉 httpx 錯誤，draft 保持未 applied 待重試，不半套。 |
| **紅線不受影響** | reply_guard／工具白名單為 runtime 兜底，與 skill 內容無關。 |

結論：**此改動對 agent 回答品質的唯一可能路徑＝人工審核發佈後、新增一條參考**，屬人為可控的正向增益；
自動流程本身對 agent 零影響。

## §6 測試

- **api**（scratch 5490，14 綠）：merge 加性（基準全保留＋SKILL.md 不動＋只多新檔）、merge 無基準 404、
  merge=false 取代語意不變、只進 draft（發佈中版本仍為舊版）。
- **refinery**（scratch，7 綠）：`_parse_skill_target` 解析、ingest 路徑（merge=true＋token＋skill/rel 正確＋
  provenance channel/version＋冪等不重呼叫）、git fallback 路徑原測試不破。

## §7 進度

- ✅ 後端 ingest merge 模式＋端點 `merge` 參數。
- ✅ refinery `apply_behavior.py` 雙路徑（ingest 預設／git fallback）＋provenance 溯源保留修正。
- ✅ api 14＋refinery 7 測試綠。
- ⏳ 部署：refinery/agent 容器需帶 `LOCK_API_BASE_URL`+`INTERNAL_API_TOKEN`（compose/Cloud Run env）——與 agent 重佈同批（使用者執行）。

## §8 Human Decisions（已裁決）

| # | 問題 | 裁決 |
|---|---|---|
| HD-1 | 合併語意 | **(a) 後端讀基準併入**（refinery 送單檔） |
| HD-2 | facts 軌/rag 是否重新定位 | 本輪不動；維持 ADR-030（rag＝外接 MCP 參考實作） |
| HD-3 | 品質要求 | **零影響**——見 §5 論證（只進 draft、加性、人工發佈） |
