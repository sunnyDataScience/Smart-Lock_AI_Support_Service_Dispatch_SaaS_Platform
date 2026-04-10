"""JSON schemas for structured LLM output."""

# ── 分類 schema ──

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "skill_name": {
            "type": "string",
            "description": "分配到的技能名稱，或 UNCLASSIFIED",
        },
        "confidence": {
            "type": "number",
            "description": "分類確信度 0.0-1.0",
        },
        "reasoning": {
            "type": "string",
            "description": "分類理由（簡短）",
        },
    },
    "required": ["skill_name", "confidence", "reasoning"],
}

# ── 批次分類 schema ──

CLASSIFY_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "classifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_index": {
                        "type": "integer",
                        "description": "文件在批次中的索引（從 0 開始）",
                    },
                    "skill_name": {
                        "type": "string",
                        "description": "分配到的技能名稱，或 UNCLASSIFIED",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "分類確信度 0.0-1.0",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "分類理由（簡短）",
                    },
                },
                "required": ["chunk_index", "skill_name", "confidence", "reasoning"],
            },
        },
    },
    "required": ["classifications"],
}

# ── Skill 內容產出 schema ──

SKILL_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "skill_md": {
            "type": "string",
            "description": "完整的 SKILL.md 檔案內容（含 YAML frontmatter）",
        },
        "changes_summary": {
            "type": "string",
            "description": "變更摘要（新增了什麼內容）",
        },
        "has_changes": {
            "type": "boolean",
            "description": "是否有實質新增內容（false 表示全部重複）",
        },
    },
    "required": ["skill_md", "changes_summary", "has_changes"],
}
