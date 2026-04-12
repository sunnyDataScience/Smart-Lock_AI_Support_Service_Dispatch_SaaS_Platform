"""CLI 互動測試 — 不需要 LINE Bot 就能測試 agent。

用法：cd agent_skills && python main.py
所有設定從 config.toml 讀取。
"""

import os
import asyncio

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from core.config import load_config
from llms import get_llm
from memory import get_checkpointer, close_checkpointer
from agent import build_agent


async def main():
    cfg = load_config()

    # 建立 LLM（透過 registry）
    model = get_llm(cfg.llm)

    # 建立 checkpointer（透過 registry）
    checkpointer = await get_checkpointer(cfg.memory)

    agent = build_agent(model, cfg, checkpointer=checkpointer)
    thread_id = "cli-test"
    config = {"configurable": {"thread_id": thread_id}}

    print("=" * 50)
    print(f"  {cfg.system.get('agent_name', 'Smart Lock')} AI Agent (Skill-Based)")
    print("  'quit' to exit | 'reset' to clear history")
    print("=" * 50)

    try:
        while True:
            try:
                user_input = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break

            if not user_input:
                continue
            if user_input.lower() == "quit":
                break
            if user_input.lower() == "reset":
                thread_id = f"cli-test-{id(object())}"
                config = {"configurable": {"thread_id": thread_id}}
                print("[reset]")
                continue

            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config,
            )

            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                    print(f"\n{_extract_text(msg.content)}")
                    break
    finally:
        await close_checkpointer()


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts) if parts else str(content)
    return str(content)


if __name__ == "__main__":
    asyncio.run(main())
