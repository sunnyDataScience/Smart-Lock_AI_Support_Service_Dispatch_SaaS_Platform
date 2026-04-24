"""資料修正攔截模組 — 使用者輸入 #資料修正 時，記錄對話上下文至資料庫。

攔截後不進入 Agent，直接回覆確認訊息。
對話 checkpoint 不受影響，使用者可繼續正常對話。
"""

import os
import json

from psycopg import AsyncConnection


# ── Module-level state ──

_conn: AsyncConnection | None = None
_enabled: bool = False
_keyword: str = "#資料修正"
_reply: str = "已收到您的回報，我們會盡快處理，謝謝您！"


async def init_db(config: dict):
    """初始化資料修正模組 — 建立 DB 連線與 table。"""
    global _conn, _enabled, _keyword, _reply

    _enabled = config.get("enabled", False)
    if not _enabled:
        print("[Data Correction] 未啟用")
        return

    _keyword = config.get("keyword", "#資料修正")
    _reply = config.get("reply", _reply)

    uri_env = config.get("postgres_uri_env", "POSTGRES_URI")
    uri = os.getenv(uri_env)
    if not uri:
        print(f"[Data Correction] 警告：環境變數 {uri_env} 未設定，功能降級為停用")
        _enabled = False
        return

    try:
        _conn = await AsyncConnection.connect(uri)
        await _conn.execute("""
            CREATE TABLE IF NOT EXISTS data_corrections (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                note TEXT DEFAULT '',
                conversation_context TEXT NOT NULL,
                user_facts JSONB,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await _conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dc_user_id ON data_corrections (user_id)"
        )
        await _conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dc_status ON data_corrections (status)"
        )
        await _conn.commit()
        print(f"[Data Correction] 已啟用（關鍵字: {_keyword}）")
    except Exception as e:
        print(f"[Data Correction] DB 連線失敗，降級為停用: {e}")
        _enabled = False
        _conn = None


async def close_db():
    """關閉 DB 連線。"""
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def check_and_save(
    user_id: str,
    text: str,
    agent,
    profile_mgr,
) -> str | None:
    """檢查是否為資料修正指令，是則寫入 DB 並回傳回覆文字。

    Args:
        user_id: LINE 用戶 ID
        text: 使用者輸入文字
        agent: LangGraph agent（用於讀取 checkpoint 對話歷史）
        profile_mgr: ProfileManager（用於讀取 user_facts）

    Returns:
        回覆文字（已攔截）或 None（未攔截）
    """
    if not _enabled or not _conn:
        return None

    stripped = text.strip()
    if not stripped.startswith(_keyword):
        return None

    # 截取補充說明
    note = stripped[len(_keyword):].strip()

    print(f"[Data Correction] 攔截: user={user_id[:8]}... note={note[:50]}")

    # 擷取對話歷史
    conversation_context = await _extract_conversation(agent, user_id)

    # 擷取用戶資料
    facts = await _extract_facts(profile_mgr, user_id)

    # 寫入 DB
    try:
        await _conn.execute(
            "INSERT INTO data_corrections (user_id, note, conversation_context, user_facts) "
            "VALUES (%s, %s, %s, %s)",
            (user_id, note, conversation_context, json.dumps(facts, ensure_ascii=False)),
        )
        await _conn.commit()
        print(f"[Data Correction] 已寫入 DB (user={user_id[:8]}...)")
    except Exception as e:
        print(f"[Data Correction] DB 寫入失敗: {e}")

    return _reply


def _strip_prefix(content: str) -> str:
    """移除注入的 [可用技能] / [用戶資料] 前綴，只保留 [用戶訊息] 之後的實際內容。"""
    marker = "[用戶訊息]\n"
    idx = content.find(marker)
    if idx != -1:
        return content[idx + len(marker):]
    return content


async def _extract_conversation(agent, user_id: str) -> str:
    """從 checkpoint 擷取對話歷史，格式化為純文字。"""
    if not agent:
        return ""

    try:
        thread_id = f"line_{user_id}"
        config = {"configurable": {"thread_id": thread_id}}
        state = await agent.aget_state(config)

        if not state or not state.values:
            return ""

        messages = state.values.get("messages", [])
        lines = []
        for msg in messages:
            role = getattr(msg, "type", "")
            if role == "human":
                content = msg.content if isinstance(msg.content, str) else "[多模態]"
                lines.append(f"用戶: {_strip_prefix(content)}")
            elif role == "ai" and msg.content:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                lines.append(f"客服: {content}")
        return "\n".join(lines)

    except Exception as e:
        print(f"[Data Correction] 擷取對話歷史失敗: {e}")
        return ""


async def _extract_facts(profile_mgr, user_id: str) -> dict:
    """從 ProfileManager 擷取用戶資料。"""
    if not profile_mgr or not profile_mgr.facts_enabled:
        return {}

    try:
        _, facts = await profile_mgr.load_full_profile_with_facts(user_id)
        return facts
    except Exception as e:
        print(f"[Data Correction] 擷取用戶資料失敗: {e}")
        return {}
