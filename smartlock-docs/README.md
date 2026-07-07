# Smart Lock 平台文件庫

> **版本:** 2.0 | **更新:** 2026-07-07
>
> 本文件庫的**正典開發文件集**為 [`enterprise/`](enterprise/)（平台級 27 份 SDLC 文件：策略 / 需求 / UX / UI / 架構 / 技術設計 / QA / 維運 / WBS）。
> 請由此進入 → **[`enterprise/README.md`](enterprise/README.md)**。

## 導覽

| 我想… | 去哪裡 |
| :--- | :--- |
| 看正典文件集（架構 / 需求 / 設計 / QA / 維運 / WBS） | [`enterprise/`](enterprise/) |
| 文件撰寫規範依據 | [`software_development_documentation_guide_zh_tw.docx`](software_development_documentation_guide_zh_tw.docx) |

## 關於 as-is 逐系統文件（已整併）

早期的逐系統 as-is baseline（`00_platform/`、`agent/`、`api/`、`web/`、`data-pipeline/`、`knowledge-refinery/`、`technician-platform/` 的 P1–P4）已於 **2026-07-07 整併進 `enterprise/` 並清理**：

- **決策 / 設計**（ADR、SAD、API 契約、Flow DSL、DB schema）已**完整吸收**進 enterprise 對應文件（30 份 ADR → [`enterprise/14_ADR/`](enterprise/14_ADR/)）。
- **code-grounded 稽核殘留**（file:line 技術債、安全發現、data-pipeline 產出鏈已斷之現況）已**內聯**至 [`enterprise/12_SAD.md` §12 附錄](enterprise/12_SAD.md)、[`enterprise/13_Security_Architecture.md` §8.6](enterprise/13_Security_Architecture.md)。
- **原文**封存於 git baseline commit `238f6fce`，可 `git show 238f6fce:smartlock-docs/<path>` 取回。
- enterprise 各文件 frontmatter 的 `upstream:` 為**歷史 git 參照**（指向已封存的 as-is 路徑）。
