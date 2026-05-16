"""PostgreSQL audit storage with structured event types.

Event types:
  - conversation:      AI agent chat messages (90-day retention)
  - tool_invocation:   Tool call + result summary (90-day retention)
  - safety_gate:       Safety layer gate decisions (1-year retention)
  - escalation:        Human handoff events (1-year retention)
  - dispatch_decision: Dispatch matching (2-year retention, V2.0)
  - financial_action:  Refunds/payments (7-year retention, V2.0)
  - admin_action:      Role/config changes (7-year retention, V2.0)
"""

import json
import os
import re
from datetime import datetime, timezone
from psycopg_pool import AsyncConnectionPool

# Pool 取代單一 conn — checkout 時自動驗證並回收壞掉的連線，避免 CloudSQL idle 斷線後整個模組失效。
_postgres_pool: AsyncConnectionPool | None = None
_postgres_uri_env: str = ""

# PII masking patterns
_PII_PATTERNS = [
    (re.compile(r'09\d{2}[\-\s]?\d{3}[\-\s]?\d{3}'), lambda m: m.group()[:4] + "-XXX-XXX"),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), lambda m: m.group()[0] + "***@" + m.group().split("@")[1]),
    (re.compile(r'[A-Z][12]\d{8}'), lambda m: m.group()[0] + "XXXXXXXXX"),
]


def _mask_pii(text: str) -> str:
    """Mask PII in text: phone → 09XX-XXX-XXX, email → a***@domain, ID → AXXXXXXXXX."""
    for pattern, replacer in _PII_PATTERNS:
        text = pattern.sub(replacer, text)
    return text


def get_pool() -> AsyncConnectionPool | None:
    """供 /health 等模組讀取 pool 健康狀態（不需要進行實際連線）。"""
    return _postgres_pool


class PostgresAuditStorage:

    # --- Legacy API (backward compatible) ---

    async def log_message(self, user_id: str, role: str, content: str):
        """Legacy: log a conversation message."""
        await self.log_event(
            event_type="conversation",
            actor_id=user_id,
            actor_role=role,
            action="conversation.message",
            payload={"content": content},
        )

    # --- Structured Event API ---

    async def log_event(
        self,
        event_type: str,
        actor_id: str,
        actor_role: str = "system",
        action: str = "",
        target_type: str = "",
        target_id: str = "",
        payload: dict | None = None,
    ):
        if _postgres_pool is None:
            return
        timestamp = datetime.now(timezone.utc).isoformat()

        # Mask PII in payload
        masked_payload = None
        if payload:
            masked_payload = _mask_pii(json.dumps(payload, ensure_ascii=False, default=str))

        # ADR-0030 / Phase C3-a：tenant_id 從 ContextVar 取，fail-safe 'default'。
        # Schema_cr0001 migration 已給 audit_log.tenant_id 加 NOT NULL DEFAULT
        # 'default'，未 ALTER 的舊環境靠 default 兜底，INSERT 不會失敗。
        try:
            from skills.tools import get_current_tenant
            tenant_id = get_current_tenant()
        except Exception:  # noqa: BLE001 — import 失敗（CLI 模式無 tools layer）
            tenant_id = "default"

        try:
            async with _postgres_pool.connection() as conn:
                await conn.execute(
                    """INSERT INTO audit_log
                       (user_id, role, content, timestamp, event_type, action, target_type, target_id, payload, tenant_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        actor_id,
                        actor_role,
                        payload.get("content", "") if payload else "",
                        timestamp,
                        event_type,
                        action,
                        target_type,
                        target_id,
                        masked_payload,
                        tenant_id,
                    ),
                )
        except Exception as e:
            print(f"[Audit DB] log_event 失敗: {e}")

    # --- Convenience methods for common events ---
    # ADR-0029: fail-soft 三件組 — audit method 禁留 pass no-op。
    # 之前這三個是 pass 導致 tool_invocation / safety_gate / escalation
    # 事件全部丟失（CR-0001 §1 黑洞點）；改成 log_event 對齊文件 §3-7。

    async def log_tool_invocation(
        self,
        user_id: str,
        actor: str,
        tool_name: str,
        *,
        risk_level: str = "read",
        args_summary: str = "",
    ):
        """Audit one agent tool call.

        ``actor`` is the agent identifier (e.g. ``smart_lock_agent``).
        ``risk_level`` ∈ {"read", "escalate"} per agent_audit.py:69 convention.
        ``args_summary`` truncated to 200 chars by caller (agent_audit.py:65).
        """
        await self.log_event(
            event_type="tool_invocation",
            actor_id=user_id,
            actor_role=actor,
            action=f"tool.{tool_name}",
            target_type="tool",
            target_id=tool_name,
            payload={"risk_level": risk_level, "args_summary": args_summary},
        )

    async def log_safety_gate(
        self,
        user_id: str,
        decision: str,
        details: list | None = None,
    ):
        """Audit one H6 safety-gate decision.

        ``decision`` ∈ {"blocked", "allowed"}; ``details`` is a list of
        per-rule hit records, e.g. ``[{"keyword_match": True, "rule": "..."}]``.
        """
        await self.log_event(
            event_type="safety_gate",
            actor_id=user_id,
            actor_role="system",
            action=f"safety_gate.{decision}",
            payload={"decision": decision, "details": details or []},
        )

    async def log_escalation(
        self,
        user_id: str,
        reason: str,
        *,
        contact: str | None = None,
        address: str | None = None,
        device_info: str | None = None,
        handoff_form_text: str | None = None,
    ):
        """Audit one transfer_to_human escalation.

        CR-0001 §8 Q1 decision (a)：handoff form 完整內容寫進 audit_log.payload，
        dashboard 從 ``WHERE event_type='escalation'`` 撈 handoff queue。
        所有 contact/address/device_info/handoff_form_text 為選填以保持
        backward compat (legacy 呼叫只帶 reason)。
        """
        payload: dict = {"reason": reason}
        if contact:
            payload["contact"] = contact
        if address:
            payload["address"] = address
        if device_info:
            payload["device_info"] = device_info
        if handoff_form_text:
            payload["handoff_form_text"] = handoff_form_text
        await self.log_event(
            event_type="escalation",
            actor_id=user_id,
            actor_role="user",
            action="escalation.transfer_to_human",
            payload=payload,
        )

    async def log_llm_interaction(self, user_id: str, model: str, call_site: str = "react_agent", latency_ms: float | int | None = None, **kwargs):
        """Backward-compatible wrapper — forwards to log_llm_call."""
        await self.log_llm_call(
            user_id=user_id,
            call_site=call_site,
            model=model,
            latency_ms=int(latency_ms) if latency_ms is not None else None,
            **kwargs,
        )

    async def log_llm_call(
        self,
        user_id: str,
        call_site: str,
        model: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
        success: bool = True,
        error_type: str | None = None,
        turn_id: str | None = None,
        user_question: str | None = None,
        ai_reply: str | None = None,
        metadata: dict | None = None,
    ):
        """記錄單次 LLM 呼叫的 token 使用量、延遲、與輸入/輸出原文（不阻塞回覆關鍵路徑）。

        - 寫入失敗只印 log，不 raise（呼叫端應已用 asyncio.create_task 火放即忘）
        - user_question / ai_reply 存原文不截斷、不遮罩（對齊 audit_log.content 規則）
        - metadata 僅存結構化欄位（step_index、tool_name、model_temperature 等），禁存訊息原文
        """
        if _postgres_pool is None:
            return
        try:
            async with _postgres_pool.connection() as conn:
                await conn.execute(
                    """INSERT INTO llm_usage_log
                       (user_id, turn_id, call_site, model, input_tokens, output_tokens,
                        total_tokens, latency_ms, success, error_type,
                        user_question, ai_reply, metadata)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        user_id,
                        turn_id,
                        call_site,
                        model,
                        input_tokens,
                        output_tokens,
                        total_tokens,
                        latency_ms,
                        success,
                        error_type,
                        user_question,
                        ai_reply,
                        json.dumps(metadata, ensure_ascii=False, default=str) if metadata else None,
                    ),
                )
        except Exception as e:
            print(f"[LLM Usage DB] log_llm_call 失敗: {e}")

async def build_postgres_storage(config: dict) -> PostgresAuditStorage:
    global _postgres_pool, _postgres_uri_env
    _postgres_uri_env = config.get("postgres_uri_env", "POSTGRES_URI")
    uri = os.getenv(_postgres_uri_env)
    print(f"[*] 初始化審計日誌模組: 連線至 PostgreSQL（pool）")

    pool = AsyncConnectionPool(
        conninfo=uri,
        min_size=1,
        max_size=int(config.get("pool_max_size", 10)),
        max_idle=float(config.get("pool_max_idle_seconds", 240)),
        timeout=float(config.get("pool_checkout_timeout", 30)),
        kwargs={"autocommit": True},
        open=False,
        check=AsyncConnectionPool.check_connection,
    )
    await pool.open(wait=True)

    async with pool.connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL
            )
        """)
        for col_def in [
            "event_type VARCHAR(50) DEFAULT 'conversation'",
            "action VARCHAR(100) DEFAULT ''",
            "target_type VARCHAR(50) DEFAULT ''",
            "target_id VARCHAR(100) DEFAULT ''",
            "payload JSONB",
        ]:
            try:
                await conn.execute(f"ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS {col_def}")
            except Exception:
                pass

        # llm_usage_log: token 使用量 + 延遲度量 + 輸入/輸出原文（取代 Opik 角色）
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_usage_log (
                id BIGSERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                user_id TEXT NOT NULL,
                turn_id TEXT,
                call_site VARCHAR(50) NOT NULL,
                model VARCHAR(100) NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                latency_ms INTEGER,
                success BOOLEAN NOT NULL DEFAULT TRUE,
                error_type VARCHAR(50),
                user_question TEXT,
                ai_reply TEXT,
                metadata JSONB
            )
        """)
        # 既有資料表升級：補上 user_question / ai_reply 欄位
        for col_def in ["user_question TEXT", "ai_reply TEXT"]:
            try:
                await conn.execute(f"ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS {col_def}")
            except Exception as e:
                print(f"[Audit DB] llm_usage_log 升級欄位失敗（已忽略）: {e}")
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_llm_usage_timestamp ON llm_usage_log(timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_llm_usage_user_id ON llm_usage_log(user_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_llm_usage_call_site ON llm_usage_log(call_site, timestamp DESC)",
        ]:
            try:
                await conn.execute(idx_sql)
            except Exception as e:
                print(f"[Audit DB] 建立 llm_usage_log 索引失敗（已忽略）: {e}")

    _postgres_pool = pool
    return PostgresAuditStorage()


async def close_postgres_storage():
    global _postgres_pool
    if _postgres_pool is not None:
        await _postgres_pool.close()
        _postgres_pool = None
