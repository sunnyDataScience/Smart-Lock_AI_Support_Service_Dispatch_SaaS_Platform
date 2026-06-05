"""CR-0013 Stage 2 — LINE rich menu 部署腳本（HD-01=a）。

依 CR-0013 業主決議 HD-01=(a) 強制 rich menu + 專屬 postback handler。

本腳本：
  1. 用 LINE Messaging API `createRichMenu` 建立 rich menu 定義（2 按鈕區）：
     - 左半：「查進度」 postback data = 'g:p'
     - 右半：「綁定」postback data = 'b:s'
  2. 用 `setDefaultRichMenu` 設為所有用戶預設

執行：
  uv run python scripts/line/setup_rich_menu.py

需要 env:
  LINE_CHANNEL_ACCESS_TOKEN  (LINE Developer Console 取)

冪等：每次跑會先刪舊 default rich menu 再建新的（避免重複 createRichMenu）。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# rich menu 解析度固定 2500x843（LINE compact size 大版）
# 區域分割：左半 0..1250 / 右半 1250..2500
RICH_MENU_DEFINITION = {
    "size": {"width": 2500, "height": 843},
    "selected": True,
    "name": "consumer-default-v1",
    "chatBarText": "選單",
    "areas": [
        {
            "bounds": {"x": 0, "y": 0, "width": 1250, "height": 843},
            "action": {
                "type": "postback",
                "label": "查進度",
                "data": "g:p",
                "displayText": "查進度",
            },
        },
        {
            "bounds": {"x": 1250, "y": 0, "width": 1250, "height": 843},
            "action": {
                "type": "postback",
                "label": "綁定",
                "data": "b:s",
                "displayText": "綁定通知",
            },
        },
    ],
}

# 預設圖（純色占位）— ops 自行上傳真實設計圖時 setRichMenuImage
PLACEHOLDER_IMAGE_PATH = Path(__file__).parent / "rich_menu_placeholder.png"


def _api(token: str):
    import requests

    return requests.Session(), {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def list_existing(s, headers: dict) -> list[dict]:
    resp = s.get("https://api.line.me/v2/bot/richmenu/list", headers=headers)
    resp.raise_for_status()
    return resp.json().get("richmenus", [])


def delete(s, headers: dict, rm_id: str) -> None:
    resp = s.delete(
        f"https://api.line.me/v2/bot/richmenu/{rm_id}", headers=headers,
    )
    resp.raise_for_status()


def create(s, headers: dict) -> str:
    resp = s.post(
        "https://api.line.me/v2/bot/richmenu",
        headers=headers,
        data=json.dumps(RICH_MENU_DEFINITION),
    )
    resp.raise_for_status()
    return resp.json()["richMenuId"]


def upload_image(s, token: str, rm_id: str, path: Path) -> None:
    """上傳 rich menu 圖（content-type image/png 或 image/jpeg）。"""
    if not path.exists():
        print(f"[warn] image not found: {path} — 跳過 upload；rich menu 圖留空")
        return
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "image/png",
    }
    with open(path, "rb") as f:
        resp = s.post(
            f"https://api-data.line.me/v2/bot/richmenu/{rm_id}/content",
            headers=headers, data=f.read(),
        )
    resp.raise_for_status()


def set_default(s, headers: dict, rm_id: str) -> None:
    resp = s.post(
        f"https://api.line.me/v2/bot/user/all/richmenu/{rm_id}",
        headers=headers,
    )
    resp.raise_for_status()


def main() -> int:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        print("[error] LINE_CHANNEL_ACCESS_TOKEN env required", file=sys.stderr)
        return 1

    s, headers = _api(token)
    print("[step 1/4] list existing rich menus...")
    existing = list_existing(s, headers)
    for rm in existing:
        if rm.get("name", "").startswith("consumer-default-"):
            print(f"  → deleting old: {rm['richMenuId']} ({rm['name']})")
            delete(s, headers, rm["richMenuId"])

    print("[step 2/4] creating new rich menu...")
    new_id = create(s, headers)
    print(f"  → created: {new_id}")

    print("[step 3/4] uploading placeholder image (if exists)...")
    upload_image(s, token, new_id, PLACEHOLDER_IMAGE_PATH)

    print("[step 4/4] setting as default for all users...")
    set_default(s, headers, new_id)

    print("\n✅ rich menu deployed:", new_id)
    print("   postback data: 'g:p' (查進度) / 'b:s' (綁定)")
    print("   handled by: api/routers/line_webhook.py (CR-0013 Stage 2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
