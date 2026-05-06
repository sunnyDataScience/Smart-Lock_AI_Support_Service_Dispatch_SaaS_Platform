#!/usr/bin/env python3
"""CLI 工具：從 checkpointer 撈出完整 messages 上下文，輸出為 .md 檔。

用法：
    python tests/tools/view_context.py <thread_id>
"""

import asyncio
import os
import sys
from datetime import datetime

# 讓 import 能找到專案根目錄
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "agent"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))

TYPE_EMOJI = {
    "system": "🤖",
    "human": "🧑",
    "ai": "🧠",
    "tool": "🔧",
}

# 輸出到專案根目錄下的 tmp/（已在 .gitignore）
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tmp")
OUTPUT_PATH = os.path.join(TEMP_DIR, "messages_context.md")


def _format_content(content) -> str:
    """將 msg.content (str | list) 轉為純文字。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


async def main(thread_id: str):
    from core.config import load_config
    from llms import get_llm
    from memory import get_checkpointer, close_checkpointer
    from agent import build_agent, get_system_prompt

    cfg = load_config()
    model = get_llm(cfg.llm)
    checkpointer = await get_checkpointer(cfg.memory)
    app = build_agent(model, cfg, checkpointer=checkpointer)

    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = await app.aget_state(config)

    if not state_snapshot or not state_snapshot.values:
        print(f"找不到 thread_id={thread_id} 的狀態資料。")
        await close_checkpointer()
        return

    values = state_snapshot.values
    messages = values.get("messages", [])

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("# 📋 Messages 上下文記錄\n")
    lines.append(f"> 🧵 Thread: `{thread_id}`")
    lines.append(f"> 🕐 {timestamp}")
    lines.append(f"> 💬 共 {len(messages)} 則 messages\n")
    lines.append("---\n")

    # System Prompt
    lines.append("## 🎯 System Prompt\n")
    system_prompt = get_system_prompt()
    if system_prompt:
        lines.append(f"```\n{system_prompt}\n```\n")
    else:
        lines.append("> (尚未載入 system prompt)\n")
    lines.append("---\n")

    # Checkpoint Messages
    lines.append("## 💬 Checkpoint Messages\n")
    if not messages:
        lines.append("(無 messages)\n")
    for i, msg in enumerate(messages):
        msg_type = getattr(msg, "type", "unknown")
        emoji = TYPE_EMOJI.get(msg_type, "📨")
        content = _format_content(msg.content) if hasattr(msg, "content") else str(msg)

        # tool call 資訊
        tool_calls = getattr(msg, "tool_calls", None)
        tool_info = ""
        if tool_calls:
            calls = [f"`{tc.get('name', '?')}({tc.get('args', {})})`" for tc in tool_calls]
            tool_info = f"\n> Tool calls: {', '.join(calls)}"

        # tool message 的名稱
        tool_name = ""
        if msg_type == "tool":
            name = getattr(msg, "name", "")
            if name:
                tool_name = f" (`{name}`)"

        lines.append(f"### {emoji} [{i}] `{msg_type}`{tool_name}\n")
        if tool_info:
            lines.append(f"{tool_info}\n")
        lines.append(f"```\n{content}\n```\n")

    # 寫入檔案
    os.makedirs(TEMP_DIR, exist_ok=True)
    output = "\n".join(lines)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"已輸出至 {OUTPUT_PATH}（{len(messages)} 則 checkpoint messages）")

    await close_checkpointer()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tests/tools/view_context.py <thread_id>")
        sys.exit(1)

    thread_id = sys.argv[1]
    asyncio.run(main(thread_id))
