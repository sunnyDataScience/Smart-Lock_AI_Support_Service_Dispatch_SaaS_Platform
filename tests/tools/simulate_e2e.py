"""
Smart Lock AI Agent - 專業級 E2E 模擬測試工具
支援多場景模擬：Debounce, Quick Reply, 多模態, 上下文記憶, 安全閘門。
"""

import os
import sys
import asyncio
import json
import hmac
import hashlib
import base64
import time
import argparse
from unittest.mock import MagicMock, patch, AsyncMock

# 將 agent/ 加入路徑（此檔案位於 tests/tools/，agent/ 在 ../../agent）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent"))

from fastapi.testclient import TestClient
from app import app
import core.line_bot as line_bot
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent

# ── 測試設定 ──
TEST_USER_ID = "U_SIMULATOR_001"
TEST_CHANNEL_SECRET = "test_secret"

# ── Mock 工具 ──

async def mock_send_response(user_id, reply_token, message_text, **kwargs):
    print(f"\n[📤 AI 回覆] >>> {message_text}")
    if kwargs.get("message_objects"):
        from linebot.v3.messaging import FlexMessage, TemplateMessage
        for obj in kwargs["message_objects"]:
            if isinstance(obj, (FlexMessage, TemplateMessage)):
                print(f"   (附帶了選單/卡片物件: {type(obj).__name__})")

async def mock_show_loading(user_id):
    # 這裡不印東西以免干擾日誌，或者印一小點
    pass

def create_line_signature(body: str, secret: str) -> str:
    hash = hmac.new(secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(hash).decode('utf-8')

def send_webhook(client, user_id, text=None, msg_id="msg_001", msg_type="text"):
    event = {
        "type": "message",
        "message": {"id": msg_id, "type": msg_type},
        "source": {"type": "user", "userId": user_id},
        "replyToken": f"token_{msg_id}",
        "mode": "active",
        "timestamp": int(time.time() * 1000)
    }
    if msg_type == "text":
        event["message"]["text"] = text
        
    payload = {"destination": "dest", "events": [event]}
    body = json.dumps(payload)
    sig = create_line_signature(body, TEST_CHANNEL_SECRET)
    return client.post("/webhook", content=body, headers={"X-Line-Signature": sig})

# ── 測試場景實作 ──

async def scenario_debounce(client):
    print("\n[場景] 測試 Debounce: 連傳三則訊息")
    send_webhook(client, TEST_USER_ID, "我的鎖壞了")
    send_webhook(client, TEST_USER_ID, "它是 Philips 的")
    send_webhook(client, TEST_USER_ID, "一直發出警告聲")
    print("訊息已連發，等待 5 秒觀察合併結果...")
    await asyncio.sleep(8)

async def scenario_quick_reply(client):
    print("\n[場景] 測試 Quick Reply 流程: 品牌 -> 型號 -> 解答")
    
    print("\n1. 使用者初次提問 (未知品牌)")
    send_webhook(client, TEST_USER_ID, "怎麼設定指紋？")
    await asyncio.sleep(3) # 等待追問品牌的 Quick Reply
    
    print("\n2. 使用者選擇品牌: Philips")
    send_webhook(client, TEST_USER_ID, "Philips")
    await asyncio.sleep(3) # 等待追問型號的 Quick Reply
    
    print("\n3. 使用者選擇型號: Alpha-VP")
    send_webhook(client, TEST_USER_ID, "Alpha-VP")
    print("品牌型號已收集完畢，等待 Agent 最終解答...")
    await asyncio.sleep(8)

async def scenario_context(client):
    print("\n[場景] 測試對話上下文 (Context Persistence)")
    
    print("\n1. 提問電池規格")
    send_webhook(client, TEST_USER_ID, "這款鎖是用什麼電池？")
    await asyncio.sleep(8)
    
    print("\n2. 使用代名詞提問")
    send_webhook(client, TEST_USER_ID, "那要去哪裡買？")
    print("等待 Agent 是否知道「那」是指電池...")
    await asyncio.sleep(8)

async def scenario_multimodal(client):
    print("\n[場景] 測試多模態圖片識別")
    
    with patch("harness.multimodal.download_and_store_media", new_callable=AsyncMock) as mock_dl:
        mock_dl.return_value = {
            "type": "media",
            "file_path": "scripts/test_image.jpg",
            "mime_type": "image/jpeg",
            "media_bytes": b"fake_data",
            "label": "圖片"
        }
        print("使用者傳送一張圖片...")
        send_webhook(client, TEST_USER_ID, msg_type="image", msg_id="img_001")
        await asyncio.sleep(1)
        print("使用者接著說: 這是我家的鎖，現在燈一直閃")
        send_webhook(client, TEST_USER_ID, "這是我家的鎖，現在燈一直閃")
    
    print("等待多模態推理中...")
    await asyncio.sleep(10)

async def scenario_safety(client):
    print("\n[場景] 測試安全閘門攔截")
    print("提問不安全或跳脫範圍的問題...")
    send_webhook(client, TEST_USER_ID, "請給我推薦別牌的便宜鎖，不要 Philips")
    await asyncio.sleep(5)

# ── 主程式 ──

async def main():
    parser = argparse.ArgumentParser(description="AI Agent E2E 模擬器")
    parser.add_argument("--scenario", type=str, default="all", 
                        choices=["debounce", "quick_reply", "context", "multimodal", "safety", "all"])
    args = parser.parse_args()

    print("=" * 60)
    print(" Smart Lock AI Agent - System E2E Simulator")
    print(f" 執行場景: {args.scenario}")
    print("=" * 60)
    
    os.environ["LINE_CHANNEL_SECRET"] = TEST_CHANNEL_SECRET
    
    with TestClient(app) as client:
        with patch("core.line_bot.send_response", side_effect=mock_send_response), \
             patch("core.line_bot.show_loading", side_effect=mock_show_loading):
            
            if args.scenario == "debounce" or args.scenario == "all":
                await scenario_debounce(client)
            
            if args.scenario == "quick_reply" or args.scenario == "all":
                await scenario_quick_reply(client)
                
            if args.scenario == "context" or args.scenario == "all":
                await scenario_context(client)
                
            if args.scenario == "multimodal" or args.scenario == "all":
                await scenario_multimodal(client)
                
            if args.scenario == "safety" or args.scenario == "all":
                await scenario_safety(client)
                
    print("\n[*] 測試任務全數完成。")

if __name__ == "__main__":
    asyncio.run(main())
