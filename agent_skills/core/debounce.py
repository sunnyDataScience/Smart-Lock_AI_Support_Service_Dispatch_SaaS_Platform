"""訊息防抖模組 — 合併使用者連續發送的多則訊息。

流程：
  1. add_message_to_buffer() 收到訊息 → 放入緩衝池 → 重設計時器
  2. buffer_wait 秒後觸發 process_and_reply()
  3. 合併所有緩衝訊息 → run_agent() → line_bot.send_response()

由 app.py startup 呼叫 init() 注入依賴。
"""

import time
import asyncio

import core.line_bot as line_bot
import core.memory_manager as memory_manager
from core.line_ui_factory import build_line_messages
from skills.tools import set_current_user_id
import core.profile_updater as profile_updater

# 模組層級狀態（由 init() 初始化）
_agent = None
_config: dict = {}
_templates: dict = {}
_profile_mgr = None
_audit_storage = None

# 訊息緩衝池：用來記錄每個使用者的狀態
user_buffers = {}


def init(agent, config: dict, templates: dict, profile_mgr=None, audit_storage=None):
    """注入依賴，由 app.py startup 呼叫。

    Args:
        agent: compiled LangGraph agent instance
        config: debounce + system config dict
        templates: 回覆模板 config dict
        profile_mgr: ProfileManager instance (optional)
        audit_storage: AuditStorage instance (optional)
    """
    global _agent, _config, _templates, _profile_mgr, _audit_storage
    _agent = agent
    _config = config
    _templates = templates
    _profile_mgr = profile_mgr
    _audit_storage = audit_storage


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


async def run_agent(user_id: str, user_text: str) -> str:
    """將使用者訊息送入 ReAct agent，回傳 AI 回覆文字。"""
    # 設定當前 user_id，讓 transfer_to_human 等工具可以查 DB
    set_current_user_id(user_id)

    request_timeout = _config.get("request_timeout", 60)

    try:
        thread_id = f"line_{user_id}"

        # 載入用戶畫像，注入訊息前綴
        message = user_text
        if _profile_mgr and _profile_mgr.enabled:
            profile_text = await _profile_mgr.load_full_profile(user_id)
            if profile_text:
                message = f"[用戶資料]\n{profile_text}\n\n[用戶訊息]\n{user_text}"

        config = {"configurable": {"thread_id": thread_id}}

        # 壓縮過長的對話歷史
        await memory_manager.maybe_compress(_agent, thread_id)

        # 注入摘要前綴
        summary = memory_manager.get_summary(thread_id)
        if summary:
            print(f"[Agent] 注入前情提要 ({len(summary)} 字)")
            message = memory_manager.build_summary_prefix(summary) + message

        print(f"[Agent] 開始思考 user_id: {user_id} 的問題...")
        print(f"[Agent] 送入內容:\n{'─' * 40}\n{message[:500]}{'...(截斷)' if len(message) > 500 else ''}\n{'─' * 40}")
        try:
            result = await asyncio.wait_for(
                _agent.ainvoke(
                    {"messages": [{"role": "user", "content": message}]},
                    config,
                ),
                timeout=request_timeout,
            )
        except asyncio.TimeoutError:
            print(f"[Agent 超時] {user_id} 的問題處理超過 {request_timeout} 秒")
            return _templates.get("error_timeout", "不好意思，系統處理時間過長，請稍後再試一次。")

        messages = result.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                return _extract_text(msg.content)

        return _templates.get("error_no_reply", "抱歉，系統沒有產生回覆。")

    except Exception as e:
        print(f"[Agent 執行錯誤] {e}")
        return _templates.get("error_system", "不好意思，系統大腦剛剛稍微當機了一下，請稍後再試一次！")


async def agent_and_reply(user_id: str, reply_token: str, text: str):
    """執行 agent 並回覆使用者。"""
    print(f"\n[開始處理] 準備將訊息送入 Agent...")

    if _audit_storage:
        try:
            await _audit_storage.log_message(user_id, "user", text)
        except Exception as e:
            print(f"[Audit] 記錄使用者訊息失敗: {e}")

    ai_response = await run_agent(user_id, text)
    print(f"[Agent] 思考完畢！準備回傳...")

    # 背景萃取用戶輪廓（不阻塞回覆）
    asyncio.create_task(profile_updater.extract_and_update(user_id, text, ai_response))

    if _audit_storage:
        try:
            await _audit_storage.log_message(user_id, "ai", ai_response)
        except Exception as e:
            print(f"[Audit] 記錄 AI 回覆失敗: {e}")

    # 偵測 URL 並轉換為 Flex Message 卡片
    max_len = _config.get("max_reply_length", 5000)
    message_objects = build_line_messages(ai_response[:max_len])
    await line_bot.send_response(user_id, reply_token, ai_response, max_len=max_len, message_objects=message_objects)


_MEDIA_PLACEHOLDER_PREFIX = "[使用者正在傳送"


async def process_and_reply(user_id: str, reply_token: str):
    """背景執行：等待緩衝 → 執行 agent → 回覆。"""
    try:
        await asyncio.sleep(_config.get("buffer_wait", 1.5))

        # 若有媒體佔位訊息，額外等待媒體處理完成
        media_wait = _config.get("media_extra_wait", 10)
        waited = 0.0
        while waited < media_wait:
            texts = user_buffers.get(user_id, {}).get("text", [])
            if not any(t.startswith(_MEDIA_PLACEHOLDER_PREFIX) for t in texts):
                break
            await asyncio.sleep(0.5)
            waited += 0.5

        # 合併文字，清除殘留的佔位訊息
        combined_text = "\n".join(
            t for t in user_buffers[user_id]["text"]
            if not t.startswith(_MEDIA_PLACEHOLDER_PREFIX)
        )
        if not combined_text.strip():
            combined_text = "[使用者傳送了媒體檔案，但系統處理超時，請盡量協助]"
        await agent_and_reply(user_id, reply_token, combined_text)

    except asyncio.CancelledError:
        print(f" ⏳ [任務取消] {user_id} 仍在輸入，更新計時器...")
        raise

    finally:
        if user_id in user_buffers and user_buffers[user_id].get("task") == asyncio.current_task():
            del user_buffers[user_id]


def add_message_to_buffer(
    user_id: str, reply_token: str | None, text: str,
    *, replace_media_placeholder: bool = False,
):
    """將訊息加入緩衝池，建立/重設防抖計時器。

    Args:
        reply_token: LINE reply token（None 表示不更新 token）。
        replace_media_placeholder: True 時，將 buffer 中的媒體佔位訊息替換為此 text。
    """
    if user_id in user_buffers:
        user_buffers[user_id]["task"].cancel()

        if replace_media_placeholder:
            user_buffers[user_id]["text"] = [
                t for t in user_buffers[user_id]["text"]
                if not t.startswith(_MEDIA_PLACEHOLDER_PREFIX)
            ]
        user_buffers[user_id]["text"].append(text)

        if reply_token is not None:
            user_buffers[user_id]["reply_token"] = reply_token
        user_buffers[user_id]["created_at"] = time.monotonic()
    else:
        user_buffers[user_id] = {
            "text": [text],
            "reply_token": reply_token or "",
            "created_at": time.monotonic(),
        }

    new_task = asyncio.create_task(
        process_and_reply(user_id, user_buffers[user_id]["reply_token"])
    )
    user_buffers[user_id]["task"] = new_task


async def cleanup_stale_buffers():
    """定期清理過期的使用者緩衝區。"""
    buffer_ttl = _config.get("buffer_ttl", 300)
    cleanup_interval = _config.get("cleanup_interval", 60)

    while True:
        await asyncio.sleep(cleanup_interval)
        now = time.monotonic()
        stale_users = [
            uid for uid, buf in user_buffers.items()
            if now - buf.get("created_at", 0) > buffer_ttl
        ]
        for uid in stale_users:
            buf = user_buffers.pop(uid, None)
            if buf:
                task = buf.get("task")
                if task and not task.done():
                    task.cancel()
                print(f"  [Buffer 清理] 移除 {uid} 的過期緩衝")
