"""silver_to_skill pipeline — 將 silver 層文件轉換為 SKILL.md 技能文件。

三步驟流程：
1. classify_documents.py  — 將 silver docs 分類到對應的 skill
2. generate_drafts.py     — 產出 SKILL.md 草稿（更新既有 or 新增）
3. approve_drafts.py      — diff 審核 + 寫入到 agent/skills/data/
"""
