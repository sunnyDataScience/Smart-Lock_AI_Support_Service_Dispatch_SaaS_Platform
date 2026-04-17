"""最小 LLM 測試 — 驗證 litellm + Vertex AI 連線是否正常。"""

import os
import asyncio

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from llms import get_llm
from core.config import load_config


async def main():
    cfg = load_config()
    model = get_llm(cfg.llm)

    print("送出測試訊息: 你好")
    result = await model.ainvoke("你好")
    print(f"回覆: {result.content}")
    print("OK")


if __name__ == "__main__":
    asyncio.run(main())
