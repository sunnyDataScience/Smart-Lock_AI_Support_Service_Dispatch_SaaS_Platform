---
title: "ADR-032: Skill 熱更新——品牌庫為 SSOT、image builtin 降級為離線保底、workspace overlay 物化"
version: 1.0
status: active
owner: 業主
last-updated: 2026-07-12
relates:
  - ./ADR-030_RAG定位_外接介面_Skill為知識主軸.md   # Skill 為知識主軸的定位不變
  - ./ADR-011_Agent整合風格三分類.md
---

# ADR-032: Skill 熱更新——品牌庫 SSOT + workspace overlay

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（業主裁決 2026-07-12，CR-0167 §8）|
| 層級 | 平台 |
| 關聯 ADR | 延續 [ADR-030](./ADR-030_RAG定位_外接介面_Skill為知識主軸.md)（Skill 為知識與推理主軸）；細化 CLAUDE.md Architecture Lock 條 2（skill 位置）|
| 觸發 | Skill 會持續迭代且必須是 agent 回答依據，但原架構 skill 隨 image 烤入——改一行知識就得重佈 agent（3-5 分、需工程師），品牌方無法自助維護 |

## Context（脈絡）

ADR-0107 起 agent 核心＝LockCore，知識與 SOP＝Agent Skills 標準 builtin skill
（`agent/lockcore/skills/`）。這些 skill 隨 `agent/Dockerfile` 的 `COPY agent/` 烤入映像，
載入路徑寫死 `lockcore/agent/skills.py:BUILTIN_SKILLS_DIR`。ADR-030 確立 Skill 為我方 agent
的知識與推理主軸（永久，非過渡）。但「skill 綁 image」與「skill 持續迭代且品牌自助維護」矛盾。

## Decision（裁決）

1. **Skill 的 SSOT 從 image 移到品牌庫 DB**：`saas.skill_revision`（版本快照 append-only）
   ＋`saas.skill_bundle`（發佈版本 stamp）。知識所有權歸品牌租戶（此 agent 是品牌開通
   LINE 客服才有的功能），品牌方有完整權限（HD-1=c），依品牌內部角色治理（編輯=OPS_ROLES、
   發佈=admin，HD-5）＋強制版控。

2. **image builtin skill 降級為「出廠範本 + 離線保底」**：`lockcore/skills/` 仍留原位
   （不違反 Architecture Lock 條 2），但定位改為出廠起點與 DB 全掛時的保底層。品牌首次
   編輯某 builtin skill，以其現行內容 seed 為 revision 1（`source=factory_seed`）作為 fork 起點。

3. **agent 端 workspace overlay 物化**（`SkillSync`，lockcore 核心零改動）：agent 以
   POSTGRES_URI 直讀品牌庫（HD-3=a），60s 輪詢 `published_stamp`，變了才把 published 版本
   物化到 `workspace/skills/`。SkillsLoader 既有 overlay 機制（workspace 優先於 builtin）
   即讓下一 turn 用到新知識——**發佈後 ≤60s 生效、不重佈**。原子換裝＝版本目錄＋symlink
   os.replace 重指。

4. **fail-soft**：DB/tenant 未配置或連線失敗 → 不動 overlay、不 crash，agent 續用上次
   物化版或 image builtin（對齊 ADR-010/030 的 `RAG_UNAVAILABLE` 哲學）。

5. **bronze-only 紅線範圍限縮**：僅約束「平台出廠內容與 knowledge-pipeline 自動汲取」
   （汲取一律進 draft 人工發佈，HD-2=a）；品牌方自行編輯的內容來源＝品牌方、責任歸品牌方，
   UI 以來源標示區隔（`brand_edit` / `pipeline_ingest` / `factory_seed`）。

## Consequences

- Skill 更新從「rebuild+push+deploy」變「品牌後台編輯→admin 發佈→≤60s 生效」；平台核心 SOP
  仍可留 image builtin 走 git 審計節奏（低頻改動才重佈）。
- 「image 即版本」的可回滾性由 DB `skill_revision` append-only ＋ 一鍵 rollback ＋ audit log
  ＋ agent turn 記 bundle stamp 取代（追溯「這個回答用哪版知識」）。
- 紅線不依賴 skill 內容：`reply_guard`（runtime 兜底）與工具白名單（`app_config.py:CS_TOOL_ALLOWLIST`）
  不受 skill 被改壞影響——品牌方有完整編輯權但繞不過安全閘。
- 發佈驗證閘（frontmatter 合規／SKILL.md ≤16KB／path traversal）在 publish 時強制。
- 〔實作＝CR-0167 S1（DB+API）/ S2（SkillSync+seed）/ S3（品牌後台 UI）/ S4（治理+pipeline ingest+重佈）〕

## 重評觸發

- 多品牌 skill 量體成長到單庫 jsonb 不敷（考慮拆 object storage + 指標表）。
- 需要「發佈前 golden QA smoke eval 過門檻」的自動品質閘（§5.6 後續強化）。
- 品牌自建 skill 與平台出廠內容的責任邊界產生法遵爭議時。
