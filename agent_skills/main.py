"""CLI 互動測試 — 不需要 LINE Bot 就能測試 agent。

用法：cd agent_v2 && python main.py
"""

import os
import asyncio

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from langchain_google_vertexai import ChatVertexAI
from agent import build_agent


async def main():
    project = os.getenv("VERTEX_PROJECT_ID", "")
    if not project:
        print("Please set VERTEX_PROJECT_ID env var")
        return

    model = ChatVertexAI(
        model_name="gemini-2.5-flash",
        project=project,
        location=os.getenv("VERTEX_LOCATION", "us-central1"),
        temperature=0.3,
    )

    agent = build_agent(model)
    thread_id = "cli-test"
    config = {"configurable": {"thread_id": thread_id}}

    print("=" * 50)
    print("🔒 智慧鎖 AI 客服 v2 (Skill-Based)")
    print("   輸入 'quit' 退出 | 輸入 'reset' 重置對話")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n👤 客戶: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再見！")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "reset":
            thread_id = f"cli-test-{id(object())}"
            config = {"configurable": {"thread_id": thread_id}}
            print("🔄 對話已重置")
            continue

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config,
        )

        # 取最後一則 AI 回覆
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                print(f"\n>> {_extract_text(msg.content)}")
                break


def _extract_text(content) -> str:
    """從 AI 回覆中提取純文字（Vertex AI 可能回傳 list[dict]）。"""
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
