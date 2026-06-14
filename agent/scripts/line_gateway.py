"""LINE 客服 gateway 啟動點 — 本機跑 webhook,用 ngrok 對外。

用法:
    cd lock-cs-agent
    .venv/bin/python scripts/line_gateway.py            # 預設 :8000
    PORT=9000 .venv/bin/python scripts/line_gateway.py

接 LINE:
    1) 另開終端:ngrok http 8000
    2) 把 ngrok 的 https URL + "/callback" 填到 LINE Developers > Messaging API > Webhook URL
    3) 開 "Use webhook";把官方帳號加好友後對它說話

機密讀 lock-cs-agent/.env(LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN);其餘設定讀 config.toml。
"""

import os
import sys
import tempfile
from pathlib import Path

from aiohttp import web

from lockcore.agent.loop import AgentLoop
from lockcore.app_config import (
    CS_TOOL_ALLOWLIST,
    build_escalation_store,
    build_memory_manager,
    build_provider,
    load_config,
)
from lockcore.bus.queue import MessageBus
from lockcore.channels.line_gateway import build_webapp, load_dotenv


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")

    secret = os.environ.get("LINE_CHANNEL_SECRET")
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not (secret and token):
        sys.exit("缺 LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN(放 lock-cs-agent/.env)")

    cfg = load_config()
    provider = build_provider(cfg)
    mgr = build_memory_manager(cfg, provider)
    esc = build_escalation_store(cfg)
    workspace = Path(tempfile.mkdtemp(prefix="lockcore-line-"))
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=workspace,
        model=cfg.model,
        memory_manager=mgr,
        memory_tenant=cfg.tenant,
        escalation_store=esc,
        tool_allowlist=CS_TOOL_ALLOWLIST,
    )

    app = build_webapp(loop, cfg.tenant, secret, token, escalation_store=esc)
    port = int(os.environ.get("PORT", "8000"))
    print(f"模型:{cfg.model}  租戶:{cfg.tenant}")
    print(f"LINE webhook 監聽 :{port}/callback")
    print(f"→ 另開終端跑:ngrok http {port},把 https URL + /callback 填進 LINE webhook 設定")
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
