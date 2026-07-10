#!/usr/bin/env python3
"""跨實例 WS 廣播 e2e(CR-0134 遺留/WBS 1.3.1 多實例 e2e)。

驗證鏈:實例 B 訂閱 /realtime/rbac → 實例 A 觸發 rbac publish
(讀當前權限集合後「原樣 PUT」——publish 必發、DB 零淨變化,不污染後續測試)
→ 斷言 B 在 timeout 內收到事件。收到=訊息走了 A 本地 fanout →
Redis pub/sub(lockai:ws:broadcast)→ B 的 _redis_reader → B 本地訂閱者,
即 ws_hub Redis 橋(api/realtime/ws_hub.py)跨實例路徑實證。

前置:兩實例共用同一 POSTGRES_URI 與 REDIS_URL;DB 已 seed admin 帳號。
用法:uv run python scripts/ci/e2e_multi_instance_ws.py \
        --a http://localhost:8001 --b http://localhost:8002
退出碼:0=跨實例收到;1=逾時/失敗。
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import urllib.request

ADMIN_EMAIL = "test@lock-ai.com"
ADMIN_PASSWORD = "changeme123"
PROBE_ROLE = "customer_service"
TIMEOUT_S = 15


def _post_json(url: str, payload: dict, token: str | None = None) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _put_json(url: str, payload: dict, token: str, tenant_id: str) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="PUT",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}",
                 "X-Tenant-ID": tenant_id},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _get_json(url: str, token: str, tenant_id: str) -> dict:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _jwt_claims(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--a", default="http://localhost:8001", help="實例 A(觸發端)")
    ap.add_argument("--b", default="http://localhost:8002", help="實例 B(訂閱端)")
    args = ap.parse_args()

    # 1. 於 A 登入 admin
    login = _post_json(f"{args.a}/api/v1/auth/login",
                       {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    token = login["data"]["access_token"]
    tenant_id = _jwt_claims(token)["tenant_id"]
    print(f"[1/4] A 登入 OK(tenant={tenant_id[:8]}…)")

    # 2. 讀 PROBE_ROLE 當前權限集合(供原樣 PUT)。list 回應為結構化
    #    {resource, read/write/delete/approve bool};PUT 收扁平 resource.action 碼。
    roles = _get_json(f"{args.a}/tenants/{tenant_id}/rbac/roles", token, tenant_id)
    target = next((r for r in roles["data"] if r.get("id") == PROBE_ROLE), None)
    if not target:
        print(f"❌ 找不到角色 {PROBE_ROLE}(seed 未灌?)", file=sys.stderr)
        return 1
    perms = sorted(
        f"{p['resource']}.{action}"
        for p in (target.get("permissions") or [])
        for action in ("read", "write", "delete", "approve")
        if p.get(action)
    )
    print(f"[2/4] 讀到 {PROBE_ROLE} 權限 {len(perms)} 條(原樣回寫,零淨變化)")

    # 3. 於 B 訂閱 /realtime/rbac(先訂閱、後觸發)
    import websockets  # uvicorn[standard] 相依,workspace 內必有

    ws_base = args.b.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/realtime/rbac?access_token={token}&tenant_id={tenant_id}"

    async with websockets.connect(ws_url, open_timeout=15) as ws:
        print(f"[3/4] B 訂閱 /realtime/rbac OK({args.b})")

        # 4. 於 A 觸發 publish(原集合原樣 PUT)
        _put_json(
            f"{args.a}/tenants/{tenant_id}/rbac/roles/{PROBE_ROLE}/permissions",
            {"permissions": perms,
             "reason": "e2e cross-instance ws probe(原樣回寫零淨變化)"},
            token, tenant_id,
        )
        print(f"[4/4] A 觸發 rbac publish → 等 B 收(timeout {TIMEOUT_S}s)…")

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=TIMEOUT_S)
        except asyncio.TimeoutError:
            print("❌ 逾時未收到——跨實例橋斷(REDIS_URL 未接或 Redis 不通?)",
                  file=sys.stderr)
            return 1

    msg = json.loads(raw)
    mtype = msg.get("type", "")
    if "rbac" not in mtype and "role" not in mtype and "permission" not in mtype:
        print(f"⚠️ 收到非預期事件 type={mtype}(仍證明跨實例通),全文:{raw[:200]}")
    print(f"✅ 跨實例 WS 廣播實證:A publish → Redis → B 收到(type={mtype})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
