"""極簡 LINE 客服機器人 — skill-based ReAct agent。

啟動：cd agent_v2 && uvicorn app:app --reload --port 8000
"""

import os
import asyncio
import base64
import hashlib
import hmac
import json

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import httpx
from fastapi import FastAPI, Request, HTTPException
from langchain_google_vertexai import ChatVertexAI

from agent import build_agent

app = FastAPI(title="Smart Lock AI Agent v2 — Skill-Based")

# ── Global state ──
_agent = None

# ── LINE config ──
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")


def _verify_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE webhook 簽名。"""
    mac = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256
    )
    return hmac.compare_digest(base64.b64encode(mac.digest()).decode(), signature)


async def _reply_line(reply_token: str, text: str) -> None:
    """透過 LINE Messaging API 回覆訊息。"""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:5000]}],  # LINE 限制 5000 字
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[LINE] reply failed: {resp.status_code} {resp.text}")


async def _push_line(user_id: str, text: str) -> None:
    """透過 LINE Messaging API 主動推送訊息（reply_token 過期時使用）。"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text[:5000]}],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[LINE] push failed: {resp.status_code} {resp.text}")


async def _show_loading(user_id: str) -> None:
    """顯示 LINE loading 動畫。"""
    url = "https://api.line.me/v2/bot/chat/loading/start"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {"chatId": user_id, "loadingSeconds": 20}
    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json=payload, timeout=5)


# ── FastAPI lifecycle ──


@app.on_event("startup")
async def startup():
    global _agent

    # 建立 LLM (Vertex AI)
    model = ChatVertexAI(
        model_name="gemini-2.5-flash",
        project=os.getenv("VERTEX_PROJECT_ID", ""),
        location=os.getenv("VERTEX_LOCATION", "us-central1"),
        temperature=0.3,
    )

    # 建立 agent
    _agent = build_agent(model)
    print("[*] Agent v2 ready (skill-based)")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0-skills"}


# ── CLI 測試模式 ──


@app.get("/chat")
async def chat_test(q: str = "你好"):
    """GET /chat?q=門打不開 — 快速測試用。"""
    result = await _invoke_agent(q, thread_id="test-cli")
    return {"answer": result}


# ── LINE Webhook ──


@app.post("/webhook")
async def line_webhook(request: Request):
    """LINE Official Webhook Handler。"""
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    # 簽名驗證
    if LINE_CHANNEL_SECRET and not _verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = json.loads(body)
    events = data.get("events", [])

    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            # 非文字訊息先簡單回覆
            reply_token = event.get("replyToken", "")
            if reply_token:
                await _reply_line(reply_token, "目前僅支援文字訊息，請用文字描述您的問題 🙂")
            continue

        user_id = event.get("source", {}).get("userId", "unknown")
        reply_token = event.get("replyToken", "")
        text = message.get("text", "").strip()

        if not text:
            continue

        print(f"[LINE] user={user_id[:8]}... text={text[:50]}")

        # 顯示 loading 動畫
        asyncio.create_task(_show_loading(user_id))

        # 呼叫 agent
        try:
            answer = await _invoke_agent(text, thread_id=f"line_{user_id}")

            # 嘗試 reply，若失敗改用 push
            try:
                await _reply_line(reply_token, answer)
            except Exception:
                await _push_line(user_id, answer)

        except Exception as e:
            print(f"[ERROR] agent invoke failed: {e}")
            fallback = "抱歉，系統暫時無法處理您的問題。請稍後再試，或撥打 02-8601-9952 聯繫真人客服。"
            try:
                await _reply_line(reply_token, fallback)
            except Exception:
                await _push_line(user_id, fallback)

    return {"status": "ok"}


# ── Agent invocation ──


async def _invoke_agent(text: str, thread_id: str) -> str:
    """呼叫 agent 並取得回覆文字。"""
    config = {"configurable": {"thread_id": thread_id}}
    result = await _agent.ainvoke(
        {"messages": [{"role": "user", "content": text}]},
        config,
    )

    # 取最後一則 AI 訊息
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            return _extract_text(msg.content)

    return "抱歉，我暫時無法回覆。請撥打 02-8601-9952 聯繫真人客服。"


def _extract_text(content) -> str:
    """從 AI 回覆中提取純文字。

    Vertex AI 可能回傳 str 或 list[dict]（含 thought_signature 等欄位），
    這裡只取 type=text 的部分。
    """
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
