#!/bin/bash

# Architecture Lock Hook (PreToolUse: Write|Edit)
# 機械式強制 CLAUDE.md 🔒 Architecture Lock 第 1、2 條：
#   1. 不准在 agent/ 內 import skills
#   2. 不准重建 agent/skills/data/*/SKILL.md
# CLAUDE.md 規則順從率約 70%；真正的紅線靠 hook exit code 2 攔截，不是許願。
# exit 0 = 放行；exit 2 = 阻擋（stderr 訊息會回饋給 Claude）。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLAUDE_DIR="$PROJECT_ROOT/.claude"
mkdir -p "$CLAUDE_DIR/logs" 2>/dev/null

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [arch-lock] $1" >> "$CLAUDE_DIR/logs/hooks.log"
}

INPUT=$(cat)

# 無 jq 就放行（不阻斷正常工作），但記一筆
if ! command -v jq >/dev/null 2>&1; then
    log "jq 不存在，跳過 architecture-lock 檢查"
    exit 0
fi

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

# 只管 Write / Edit
case "$TOOL_NAME" in
    Write|Edit) ;;
    *) exit 0 ;;
esac

# 只管 agent/ 底下的檔案（絕對或相對路徑都比對）
case "$FILE_PATH" in
    *"/agent/"*|"agent/"*) ;;
    *) exit 0 ;;
esac

# 取得即將寫入的內容：Write 看 .content，Edit 看 .new_string
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // .tool_input.new_string // ""')

# ── 規則 2：重建 SKILL.md ──────────────────────────────
case "$FILE_PATH" in
    *"/agent/skills/data/"*"/SKILL.md"|"agent/skills/data/"*"/SKILL.md")
        log "BLOCK 規則2：嘗試重建 SKILL.md → $FILE_PATH"
        echo "🔒 Architecture Lock 違反（規則 2）：不准重建 agent/skills/data/*/SKILL.md。" >&2
        echo "新產品知識一律寫成 agent/product_info/{Brand}/{Model}.md mega-doc。詳見 ADR-0008 與 CLAUDE.md。" >&2
        exit 2
        ;;
esac

# ── 規則 1：在 agent/ 內 import skills ─────────────────
# 只檢查 .py。比對：from skills import / from skills. / import skills
case "$FILE_PATH" in
    *.py)
        if echo "$CONTENT" | grep -Eq '^[[:space:]]*(from[[:space:]]+skills(\.[A-Za-z0-9_]+)*[[:space:]]+import|import[[:space:]]+skills([[:space:]]|$|\.))'; then
            OFFENDING=$(echo "$CONTENT" | grep -En '^[[:space:]]*(from[[:space:]]+skills|import[[:space:]]+skills)' | head -3)
            log "BLOCK 規則1：agent/ 內 import skills → $FILE_PATH"
            echo "🔒 Architecture Lock 違反（規則 1）：不准在 agent/ 內 import skills。" >&2
            echo "偵測到：" >&2
            echo "$OFFENDING" >&2
            echo "skills/ 已於 A-3a/A-3b 退場。請改用 agent/agent_tools/tools.py 的 load_product_info。詳見 ADR-0008 與 CLAUDE.md。" >&2
            exit 2
        fi
        ;;
esac

exit 0
