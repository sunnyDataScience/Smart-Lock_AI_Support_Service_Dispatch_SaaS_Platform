"""極簡 LINE 客服機器人 — skill-based ReAct agent。

啟動：cd agent_skills && uvicorn app:app --reload --port 8000
所有設定從 config.toml 讀取。
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

from core.config import load_config
from agent import build_agent

app = FastAPI(title="Smart Lock AI Agent — Skill-Based")

# ── Global state ──
_agent = None
_cfg = None


def _get_env(env_name: str) -> str:
    """從 config 指定的 env var name 取值。"""
    return os.getenv(env_name, "")


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """驗證 LINE webhook 簽名。"""
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return hmac.compare_digest(base64.b64encode(mac.digest()).decode(), signature)


async def _reply_line(reply_token: str, text: str, token: str, max_len: int) -> None:
    """透過 LINE Messaging API 回覆訊息。"""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:max_len]}],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[LINE] reply failed: {resp.status_code} {resp.text}")


async def _push_line(user_id: str, text: str, token: str, max_len: int) -> None:
    """透過 LINE Messaging API 主動推送訊息。"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text[:max_len]}],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[LINE] push failed: {resp.status_code} {resp.text}")


async def _show_loading(user_id: str, token: str, seconds: int) -> None:
    """顯示 LINE loading 動畫。"""
    url = "https://api.line.me/v2/bot/chat/loading/start"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"chatId": user_id, "loadingSeconds": seconds}
    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json=payload, timeout=5)


# ── FastAPI lifecycle ──


@app.on_event("startup")
async def startup():
    global _agent, _cfg

    # 載入設定
    _cfg = load_config()
    print(f"[*] config loaded: domain={_cfg.system.get('domain', '')[:30]}...")

    # 建立 LLM（從 config）
    llm_cfg = _cfg.llm
    provider = llm_cfg.get("provider", "vertexai")

    if provider == "vertexai":
        from langchain_google_vertexai import ChatVertexAI
        model = ChatVertexAI(
            model_name=llm_cfg.get("model_name", "gemini-2.5-flash"),
            project=_get_env(llm_cfg.get("project_id_env", "VERTEX_PROJECT_ID")),
            location=_get_env(llm_cfg.get("location_env", "VERTEX_LOCATION")) or "us-central1",
            temperature=llm_cfg.get("temperature", 0.3),
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = ChatGoogleGenerativeAI(
            model=llm_cfg.get("model_name", "gemini-2.5-flash"),
            google_api_key=_get_env(llm_cfg.get("api_key_env", "GEMINI_API_KEY")),
            temperature=llm_cfg.get("temperature", 0.3),
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    # 建立 agent
    _agent = build_agent(model, _cfg)
    print("[*] Agent ready (skill-based)")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0-skills"}


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

    line_cfg = _cfg.line_bot
    secret = _get_env(line_cfg.get("channel_secret_env", "LINE_CHANNEL_SECRET"))
    token = _get_env(line_cfg.get("channel_access_token_env", "LINE_CHANNEL_ACCESS_TOKEN"))
    max_len = line_cfg.get("max_reply_length", 5000)
    loading_sec = line_cfg.get("loading_seconds", 20)

    # 簽名驗證
    if secret and not _verify_signature(body, signature, secret):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = json.loads(body)
    events = data.get("events", [])

    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            reply_token = event.get("replyToken", "")
            if reply_token:
                await _reply_line(reply_token, "目前僅支援文字訊息，請用文字描述您的問題", token, max_len)
            continue

        user_id = event.get("source", {}).get("userId", "unknown")
        reply_token = event.get("replyToken", "")
        text = message.get("text", "").strip()

        if not text:
            continue

        print(f"[LINE] user={user_id[:8]}... text={text[:50]}")

        asyncio.create_task(_show_loading(user_id, token, loading_sec))

        try:
            answer = await _invoke_agent(text, thread_id=f"line_{user_id}")
            try:
                await _reply_line(reply_token, answer, token, max_len)
            except Exception:
                await _push_line(user_id, answer, token, max_len)
        except Exception as e:
            print(f"[ERROR] agent invoke failed: {e}")
            fallback = "抱歉，系統暫時無法處理您的問題。請稍後再試，或透過 LINE 官方帳號聯繫真人客服。"
            try:
                await _reply_line(reply_token, fallback, token, max_len)
            except Exception:
                await _push_line(user_id, fallback, token, max_len)

    return {"status": "ok"}


# ── Agent invocation ──


async def _invoke_agent(text: str, thread_id: str) -> str:
    """呼叫 agent 並取得回覆文字。"""
    config = {"configurable": {"thread_id": thread_id}}
    result = await _agent.ainvoke(
        {"messages": [{"role": "user", "content": text}]},
        config,
    )

    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            return _extract_text(msg.content)

    return "抱歉，我暫時無法回覆。請透過 LINE 官方帳號聯繫真人客服。"


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
