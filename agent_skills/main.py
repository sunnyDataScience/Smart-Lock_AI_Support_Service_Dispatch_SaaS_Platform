"""CLI 互動測試 — 不需要 LINE Bot 就能測試 agent。

用法：cd agent_skills && python main.py
所有設定從 config.toml 讀取。
"""

import os
import asyncio

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from core.config import load_config
from agent import build_agent


async def main():
    cfg = load_config()
    llm_cfg = cfg.llm
    provider = llm_cfg.get("provider", "vertexai")

    if provider == "vertexai":
        from langchain_google_vertexai import ChatVertexAI
        project = os.getenv(llm_cfg.get("project_id_env", "VERTEX_PROJECT_ID"), "")
        if not project:
            print(f"Please set {llm_cfg.get('project_id_env')} env var")
            return
        model = ChatVertexAI(
            model_name=llm_cfg.get("model_name", "gemini-2.5-flash"),
            project=project,
            location=os.getenv(llm_cfg.get("location_env", "VERTEX_LOCATION"), "") or "us-central1",
            temperature=llm_cfg.get("temperature", 0.3),
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv(llm_cfg.get("api_key_env", "GEMINI_API_KEY"), "")
        if not api_key:
            print(f"Please set {llm_cfg.get('api_key_env')} env var")
            return
        model = ChatGoogleGenerativeAI(
            model=llm_cfg.get("model_name", "gemini-2.5-flash"),
            google_api_key=api_key,
            temperature=llm_cfg.get("temperature", 0.3),
        )
    else:
        print(f"Unsupported LLM provider: {provider}")
        return

    agent = build_agent(model, cfg)
    thread_id = "cli-test"
    config = {"configurable": {"thread_id": thread_id}}

    print("=" * 50)
    print(f"  {cfg.system.get('agent_name', 'Smart Lock')} AI Agent (Skill-Based)")
    print("  'quit' to exit | 'reset' to clear history")
    print("=" * 50)

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
