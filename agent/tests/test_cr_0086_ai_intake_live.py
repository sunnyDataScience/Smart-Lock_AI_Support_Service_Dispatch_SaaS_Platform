"""CR-0086 / TI-M03-14（AI 段）+ TI-A05-01 live — AI 進線行為 E2E（需 Vertex 憑證）。

無 GOOGLE_APPLICATION_CREDENTIALS / credentials.json → 自動 skip（CI 無 LLM 不阻斷）。
有憑證時跑真 agent turn：驗詢價 → 轉真人且不報價、領域外 → 婉拒。
"""
from __future__ import annotations
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT))

_CREDS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or (
    str(AGENT_ROOT / "credentials.json") if (AGENT_ROOT / "credentials.json").exists() else None
)
_PRICE_RE = re.compile(r"(NT\$|＄|\$)\s*\d|[\d,]+\s*(元|塊|台幣|新台幣)")

pytestmark = pytest.mark.skipif(
    not _CREDS, reason="需 Vertex 憑證（GOOGLE_APPLICATION_CREDENTIALS / credentials.json）才跑 live AI E2E")


def _ensure_creds_env():
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ and _CREDS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _CREDS
    os.environ.setdefault("VERTEX_PROJECT_ID", "cedar-scope-489604-g3")
    os.environ.setdefault("VERTEX_LOCATION", "global")


async def _run_turn(question: str, user_id: str):
    """建 live AgentLoop 跑一輪，回 (reply, transferred)。"""
    from dataclasses import replace
    from lockcore.agent.loop import AgentLoop
    from lockcore.app_config import (
        CS_TOOL_ALLOWLIST, build_escalation_store, build_memory_manager,
        build_provider, load_config,
    )
    from lockcore.bus.events import InboundMessage
    from lockcore.bus.queue import MessageBus

    cfg = load_config(None)
    cfg = replace(cfg, db_path=str(Path(tempfile.mkdtemp(prefix="lockcore-e2e-")) / "m.db"))
    provider = build_provider(cfg)
    mgr = build_memory_manager(cfg, provider)
    esc = build_escalation_store(cfg)
    loop = AgentLoop(
        bus=MessageBus(), provider=provider, workspace=Path(tempfile.mkdtemp()),
        model=cfg.model, memory_manager=mgr, memory_tenant=cfg.tenant,
        escalation_store=esc, tool_allowlist=CS_TOOL_ALLOWLIST,
    )
    msg = InboundMessage(channel="cli", sender_id=user_id, chat_id=user_id, content=question)
    out = await loop._process_message(msg, session_key=f"{cfg.tenant}:{user_id}")
    reply = out if isinstance(out, str) else (getattr(out, "content", None) or str(out))
    transferred = bool(esc.list_for_user(cfg.tenant, user_id, limit=1))
    return reply, transferred


@pytest.mark.asyncio
async def test_ai_intake_pricing_escalates_no_quote():
    _ensure_creds_env()
    reply, transferred = await _run_turn("你們換一個電子鎖大概多少錢？", "e2e-price")
    assert transferred is True, "詢價應觸發 transfer_to_human"
    assert not _PRICE_RE.search(reply or ""), f"回覆不得含報價數字：{reply[:80]}"


@pytest.mark.asyncio
async def test_ai_intake_out_of_domain_declines():
    _ensure_creds_env()
    reply, transferred = await _run_turn("今天台北天氣如何？", "e2e-ood")
    # 領域外：不轉真人（婉拒收斂回服務範圍），且有回覆
    assert reply and len(reply) > 0
    assert transferred is False
